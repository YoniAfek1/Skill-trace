"""Agent node implementations for the LangGraph workflow."""

from typing import Dict, Any, Optional, List
import requests
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.state import AgentState
from app.utils import (
    JOB_DESCRIPTION,
    extract_github_url,
    get_llm_api_key,
    fetch_user_public_repos,
)

print("[DEBUG] app.agents.nodes: Module import start")


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=get_llm_api_key(),
        base_url="https://api.llmod.ai/v1",
        model="RPRTHPB-gpt-5-mini",
        temperature=1,
    )


def _messages_to_trace(messages: List[Any]) -> List[Dict[str, str]]:
    """Serialize LangChain messages into role/content pairs for UI tracing."""
    serialized: List[Dict[str, str]] = []
    for msg in messages:
        serialized.append({
            "role": str(getattr(msg, "type", msg.__class__.__name__)),
            "content": str(getattr(msg, "content", "")),
        })
    return serialized


def _fetch_repo_context(url: str) -> str:
    print(f"[DEBUG] _fetch_repo_context: exploring {url}")
    parts = url.rstrip("/").split("/")
    if len(parts) < 4:
        return "Invalid URL"
    owner, repo = parts[-2], parts[-1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"

    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            return f"Error: Status {resp.status_code}"

        files_list = resp.json()
        structure_text = "Files:\n"

        readme_content = ""
        requirements_content = ""
        code_content = ""
        python_files_count = 0

        for file in files_list:
            name = file.get("name", "")
            download_url = file.get("download_url")
            structure_text += f"- {name}\n"

            if name.lower().startswith("readme") and download_url:
                try:
                    r = requests.get(download_url, timeout=5)
                    readme_content = f"\n[README summary]:\n{r.text[:10000]}\n"
                except:
                    pass

            elif name.lower() == "requirements.txt" and download_url:
                try:
                    r = requests.get(download_url, timeout=5)
                    requirements_content = f"\n[Libs]:\n{r.text[:3000]}\n"
                except:
                    pass

            elif name.endswith(".py") and download_url and python_files_count < 2:
                try:
                    r = requests.get(download_url, timeout=5)
                    code_content += f"\n[Code: {name}]:\n{r.text[:10000]}\n"
                    python_files_count += 1
                except:
                    pass

        return f"{structure_text}\n{requirements_content}\n{readme_content}\n{code_content}"

    except Exception as e:
        return f"Error fetching repo: {e}"


# --- NODES ---

def input_parser_node(state: AgentState) -> AgentState:
    print("[DEBUG] input_parser_node: start")
    text = state.get("resume_text", "")
    url = extract_github_url(text)
    state["github_url"] = url

    steps = state.get("steps", [])
    steps.append({
        "module": "Input Parser",
        "prompt": {
            "method": "deterministic_url_extraction",
            "llm_call": False
        },
        "response": {
            "github_url": url,
            "status": "found" if url else "not_found"
        }
    })
    state["steps"] = steps
    return state


def screening_agent_node(state: AgentState) -> AgentState:
    print("[DEBUG] screening_agent_node: start")
    llm = _build_llm()
    resume = state.get("resume_text", "")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a strict resume screener for a Data Science role.\n"
                   "Return ONLY valid JSON (no markdown, no extra text) with exactly these keys:\n"
                   "{{\n"
                   "  \"decision\": \"YES\" or \"NO\",\n"
                   "  \"feedback\": \"max 4 sentences\"\n"
                   "}}\n"
                   "Rules:\n"
                   "- Use only evidence from the provided resume.\n"
                   "- If you chose YES, specify in the feedback that further analysis is worth exploring.\n"
                   "- Choose NO only if the resume is clearly unrelated to the Job Description. If this is the case, specify in the feedback that further analysis of a GitHub repository is unnecessary.\n"
                   "- If evidence is partial/uncertain but directionally relevant, choose YES and mention uncertainty in feedback.\n"
                   "- Keep feedback concise, objective, and evidence-based."),
        ("user", "Job Description:\n{jd}\n\nResume:\n{resume}")
    ])

    formatted = prompt.format_messages(jd=JOB_DESCRIPTION, resume=resume)
    result = llm.invoke(formatted)

    try:
        clean = result.content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        decision = parsed.get("decision", "NO").upper()
        feedback = parsed.get("feedback", "No feedback.")
    except:
        decision = "YES"
        feedback = "Error parsing response."

    state["screening_decision"] = decision
    state["screening_feedback"] = feedback

    steps = state.get("steps", [])
    steps.append({
        "module": "Screening Agent",
        "prompt": {
            "messages": _messages_to_trace(formatted)
        },
        "response": {
            "raw": str(result.content),
            "parsed": {
                "decision": decision,
                "feedback": feedback
            }
        }
    })
    state["steps"] = steps

    return state


def git_planner_node(state: AgentState) -> AgentState:
    print("[DEBUG] git_planner_node: start")

    url = state.get("github_url", "")
    username = state.get("github_username")
    count = state.get("git_iteration_count", 0)

    # Module name changes based on iteration count
    module_name = f"Git Planner {count + 1}" if count > 0 else "Git Planner"

    if not username and url:
        parts = url.rstrip("/").split("/")
        username = parts[-1]
        state["github_username"] = username

    if not state.get("user_repos_metadata"):
        repos_summary = fetch_user_public_repos(username)
        state["user_repos_metadata"] = repos_summary

    repos_summary = state.get("user_repos_metadata")
    prev_analysis = state.get("technical_analysis", "None yet.")
    visited = state.get("visited_repos", [])
    visited_str = ", ".join(visited) if visited else "None"

    llm = _build_llm()

    # Prompt using Imperative Mood for instructions
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Tech Lead planning the next repository audit.\n"
                   "Goal: maximize signal about candidate fit to the Job Description, by creating a plan with direct instructions.\n"
                   "Select exactly ONE repo from 'All Repos' that is NOT in 'Already Visited Repos'.\n"
                   "Prefer repos with concrete ML/data-science implementation evidence (not only notebooks or vague descriptions).\n"
                   "Output the repo name and the plan (maximum 3 checks) in this plain-text format (no markdown):\n"
                   "REPO: <exact repo name from All Repos>\n"
                   "WHY: <one concise sentence tied to JD fit>\n"
                   "CHECK 1: <important thing to verify>\n"
                   "CHECK 2: <important thing to verify>\n"
                   "CHECK 3: <important thing to verify>\n"
                   "Checks should be practical and investigatory; they may be code-focused or design-focused and do not need exact file names."),
        ("user", "JD:\n{jd}\n\nAll Repos:\n{repos}\n\nAlready Visited Repos:\n{visited}\n\nPrev Analysis:\n{prev}")
    ])

    msg = prompt.format_messages(
        jd=JOB_DESCRIPTION,
        repos=repos_summary,
        visited=visited_str,
        prev=prev_analysis
    )
    res = llm.invoke(msg)

    state["git_plan"] = res.content

    steps = state.get("steps", [])
    steps.append({
        "module": module_name,
        "prompt": {
            "messages": _messages_to_trace(msg),
            "context": {
                "already_visited_repos": visited
            }
        },
        "response": {
            "raw": str(res.content)
        }
    })
    state["steps"] = steps

    return state


def git_executor_node(state: AgentState) -> AgentState:
    print("[DEBUG] git_executor_node: start")
    username = state.get("github_username")
    plan = state.get("git_plan")
    repo_list_str = state.get("user_repos_metadata")
    count = state.get("git_iteration_count", 0)

    # Module name changes based on iteration count
    module_name = f"Git Executor {count + 1}" if count > 0 else "Git Executor"

    llm = _build_llm()

    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", "Extract ONLY the repository name from the plan. Output just the name."),
        ("user", "Plan: {plan}\n\nRepos List: {repos}")
    ])
    extraction_messages = extraction_prompt.format_messages(plan=plan, repos=repo_list_str)
    extraction_result = llm.invoke(extraction_messages)
    target_repo_name = extraction_result.content.strip()

    steps = state.get("steps", [])
    steps.append({
        "module": f"{module_name} / Repo Selection",
        "prompt": {
            "messages": _messages_to_trace(extraction_messages)
        },
        "response": {
            "raw": str(extraction_result.content),
            "selected_repo": target_repo_name
        }
    })

    visited = state.get("visited_repos", [])
    if target_repo_name not in visited:
        visited.append(target_repo_name)
    state["visited_repos"] = visited

    full_repo_url = f"https://github.com/{username}/{target_repo_name}"
    repo_context = _fetch_repo_context(full_repo_url)

    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a senior code reviewer executing a planned repository audit.\n"
                   "Primary objective: follow the Planner Instructions and evaluate alignment with the Job Description (JD).\n"
                   "Use ONLY the provided Context and Instructions as evidence.\n"
                   "Do NOT invent files, functions, tests, frameworks, performance results, or behaviors.\n\n"
                   "Execution rules:\n"
                   "1) Execute/check each planner check in order.\n"
                   "2) For every finding, explicitly map it to one JD requirement, or say 'No clear JD mapping'.\n"
                   "3) If a planned check cannot be verified from context, mark it as insufficient evidence and explain briefly.\n"
                   "4) Prioritize concrete engineering signals: implementation depth, robustness, testing, architecture, and maintainability.\n\n"
                   "Output format (strict):\n"
                   "PLAN COVERAGE:\n"
                   "- CHECK 1: done|partial|not_found - <one short reason>\n"
                   "- CHECK 2: done|partial|not_found - <one short reason>\n"
                   "- CHECK 3: done|partial|not_found - <one short reason>\n\n"
                   "FINDINGS (exactly 3 bullets):\n"
                   "- Finding: <specific technical observation>\n"
                   "  Impact: <why this helps/harms role fit>\n\n"
                   "Keep output concise."),
        ("user", "JD:\n{jd}\n\nContext:\n{context}\n\nInstructions (Plan):\n{plan}")
    ])

    analysis_messages = analysis_prompt.format_messages(
        jd=JOB_DESCRIPTION,
        context=repo_context,
        plan=plan
    )
    analysis_res = llm.invoke(analysis_messages)

    current_analysis = state.get("technical_analysis", "")
    new_analysis = current_analysis + f"\n\n[Repo: {target_repo_name}]:\n{analysis_res.content}"
    state["technical_analysis"] = new_analysis

    steps.append({
        "module": module_name,
        "prompt": {
            "messages": _messages_to_trace(analysis_messages),
            "target_repo": target_repo_name
        },
        "response": {
            "raw": str(analysis_res.content)
        }
    })
    state["steps"] = steps

    return state


def git_replan_node(state: AgentState) -> AgentState:
    print("[DEBUG] git_replan_node: start")
    llm = _build_llm()
    findings = state.get("technical_analysis")
    count = state.get("git_iteration_count", 0)

    # Module name changes based on iteration count
    module_name = f"Git Replan {count + 1}" if count > 0 else "Git Replan"

    # --- Updated Logic ---

    # Case 1: Already looped once (count >= 1). Force stop.
    if count >= 1:
        decision = "FINISH"
        reasoning = "There is enough data to create a summary."

    # Case 2: First time (count == 0). Ask LLM but request leniency.
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a quality gate evaluator deciding whether to continue repository analysis.\n"
                       "Goal: decide if current evidence is sufficient for a reliable final score and recommendation.\n"
                       "Return ONLY valid JSON (no markdown):\n"
                       "{{\n"
                       "  \"decision\": \"FINISH\" or \"RETRY\",\n"
                       "  \"reasoning\": \"max 2 sentences\"\n"
                       "}}\n"
                       "Decision rules:\n"
                       "- Choose FINISH if findings already provide enough evidence for strengths, risks, and JD alignment.\n"
                       "- Choose RETRY only when there is a clear evidence gap that likely can be reduced by inspecting a different unvisited repo.\n"
                       "- Do NOT choose RETRY for minor uncertainty.\n"
                       "- Be conservative with retries: one additional repo should materially improve confidence.\n"
                       "Reasoning must reference evidence sufficiency, not preference."),
            ("user", "JD:\n{jd}\n\nCurrent Findings:\n{findings}")
        ])

        replan_messages = prompt.format_messages(jd=JOB_DESCRIPTION, findings=findings)
        result = llm.invoke(replan_messages)

        try:
            clean = result.content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean)
            decision = parsed.get("decision", "FINISH").upper()
            reasoning = parsed.get("reasoning", "Analysis complete.")
        except:
            decision = "FINISH"
            reasoning = "Error parsing decision, assuming finished."

    # Update counter for next time
    state["git_iteration_count"] = count + 1

    print(f"[DEBUG] Replan Decision: {decision}")
    state["replan_decision"] = decision

    steps = state.get("steps", [])
    if count >= 1:
        steps.append({
            "module": module_name,
            "prompt": {
                "rule": "Forced FINISH because git_iteration_count >= 1"
            },
            "response": {
                "decision": decision,
                "reasoning": reasoning
            }
        })
    else:
        steps.append({
            "module": module_name,
            "prompt": {
                "messages": _messages_to_trace(replan_messages)
            },
            "response": {
                "raw": str(result.content),
                "parsed": {
                    "decision": decision,
                    "reasoning": reasoning
                }
            }
        })
    state["steps"] = steps

    return state


def final_analysis_node(state: AgentState) -> AgentState:
    print("[DEBUG] final_analysis_node: start")

    decision = state.get("screening_decision", "NO")
    screen_feedback = state.get("screening_feedback", "")
    tech_analysis = state.get("technical_analysis", "")

    llm = _build_llm()

    if decision == "NO":
        system_prompt = (
            "You are a Technical Recruiter Assistant.\n"
            "Generate a structured hiring evaluation report for the hiring manager.\n"
            "This candidate does NOT meet the required threshold.\n"
            "Use ONLY the provided Screening Feedback and Technical Analysis.\n"
            "Do NOT invent skills or information.\n"
            "Be concise, objective, and HR-friendly.\n\n"

            "Return EXACTLY the following sections:\n\n"

            "Decision: REJECT\n\n"

            "Final Score: [Integer between 40 and 59]/100\n"
            "- Score must reflect insufficient technical depth or role mismatch.\n\n"

            "Candidate Summary:\n"
            "- Maximum 4 sentences.\n"
            "- Neutral and professional tone.\n\n"

            "Primary Gaps / Concerns:\n"
            "- Exactly 3 bullet points.\n"
            "- Focus on evidence-based gaps.\n\n"

            "Recommendation for HR:\n"
            "- Maximum 2 sentences.\n"
            "- Clear reasoning for rejection.\n"
        )

        user_content = (
            f"Screening Feedback:\n{screen_feedback}\n\n"
            f"Technical Analysis:\n{tech_analysis}"
        )

    else:
        system_prompt = (
            "You are a Technical Recruiter Assistant.\n"
            "Generate a structured hiring evaluation report for the hiring manager.\n"
            "Use ONLY the provided Screening Feedback and Technical Analysis.\n"
            "Do NOT invent skills or information.\n"
            "If evidence is insufficient, explicitly state 'Insufficient evidence'.\n"
            "Be concise, structured, and HR-friendly.\n\n"

            "Return EXACTLY the following sections:\n\n"

            "Decision: [CONSIDER / INTERVIEW / STRONG YES]\n\n"

            "Final Score: [Integer between 60 and 100]/100\n"
            "- Score must reflect technical depth, engineering quality, and fit.\n\n"

            "Candidate Summary:\n"
            "- Maximum 5 sentences.\n\n"

            "Verified Strengths:\n"
            "- Exactly 3 bullet points.\n\n"

            "Risks / Gaps:\n"
            "- Exactly 3 bullet points.\n\n"

            "Interview Focus Areas:\n"
            "- Exactly 3 bullet points.\n"
            "- Specific technical areas to validate.\n\n"

            "Recommendation for HR:\n"
            "- Maximum 2 sentences.\n"
        )

        user_content = (
            f"Screening Feedback:\n{screen_feedback}\n\n"
            f"Technical Analysis:\n{tech_analysis}"
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_content)
    ])

    final_messages = prompt.format_messages()
    res = llm.invoke(final_messages)
    final_text = res.content
    state["final_analysis"] = final_text

    steps = state.get("steps", [])
    steps.append({
        "module": "Final Analysis",
        "prompt": {
            "messages": _messages_to_trace(final_messages)
        },
        "response": {
            "raw": str(final_text)
        }
    })
    state["steps"] = steps

    return state


print("[DEBUG] app.agents.nodes: Module import end")
