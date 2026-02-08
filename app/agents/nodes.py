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
                    readme_content = f"\n[README summary]:\n{r.text[:1500]}\n"
                except: pass

            elif name.lower() == "requirements.txt" and download_url:
                try:
                    r = requests.get(download_url, timeout=5)
                    requirements_content = f"\n[Libs]:\n{r.text[:800]}\n"
                except: pass

            elif name.endswith(".py") and download_url and python_files_count < 2:
                try:
                    r = requests.get(download_url, timeout=5)
                    code_content += f"\n[Code: {name}]:\n{r.text[:1500]}\n"
                    python_files_count += 1
                except: pass

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
        "prompt": "Extracting URL...",
        "response": f"Found: {url}" if url else "No URL found"
    })
    state["steps"] = steps
    return state


def screening_agent_node(state: AgentState) -> AgentState:
    print("[DEBUG] screening_agent_node: start")
    llm = _build_llm()
    resume = state.get("resume_text", "")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Technical Recruiter Assistant. Output ONLY JSON with keys: 'decision' (YES/NO) and 'feedback' (Max 6 sentences). Reject ('NO') only if completely irrelevant."),
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
        "prompt": "Screening for relevance...",
        "response": f"Decision: {decision}\nFeedback: {feedback}"
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
        ("system", "You are a Tech Lead instructing a Code Reviewer.\n"
                   "Select the ONE best repo to analyze next (ignore 'Already Visited').\n"
                   "Write your plan as DIRECT INSTRUCTIONS to the Executor (e.g., 'Go to repo X, check file Y, and look for Z').\n"
                   "Output ONLY the instructional plan (MAX 4 sentences)."),
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
    steps.append({"module": module_name, "prompt": f"Planning (Ignoring: {visited_str})...", "response": res.content})
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
    target_repo_name = llm.invoke(extraction_prompt.format_messages(plan=plan, repos=repo_list_str)).content.strip()
    
    visited = state.get("visited_repos", [])
    if target_repo_name not in visited:
        visited.append(target_repo_name)
    state["visited_repos"] = visited

    full_repo_url = f"https://github.com/{username}/{target_repo_name}"
    repo_context = _fetch_repo_context(full_repo_url)
    
    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Code Reviewer executing instructions.\n"
                   "Output MAX 3 BULLET POINTS of technical findings based on the plan."),
        ("user", "JD:\n{jd}\n\nContext:\n{context}\n\nInstructions (Plan):\n{plan}")
    ])
    
    analysis_res = llm.invoke(analysis_prompt.format_messages(
        jd=JOB_DESCRIPTION, 
        context=repo_context, 
        plan=plan
    ))
    
    current_analysis = state.get("technical_analysis", "")
    new_analysis = current_analysis + f"\n\n[Repo: {target_repo_name}]:\n{analysis_res.content}"
    state["technical_analysis"] = new_analysis
    
    steps = state.get("steps", [])
    steps.append({"module": module_name, "prompt": f"Executing: {target_repo_name}...", "response": analysis_res.content})
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
        reasoning = "Maximum iterations (2) reached. Proceeding to final analysis to save resources."
        
    # Case 2: First time (count == 0). Ask LLM but request leniency.
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Evaluator. Do we have enough info to grade the candidate (60-100)?\n"
                       "BE LENIENT: If the current findings are decent, choose 'FINISH'.\n"
                       "Only choose 'RETRY' if the candidate looks bad but might have a better repo we missed.\n"
                       "Output JSON with:\n"
                       "- 'decision': 'FINISH' or 'RETRY'\n"
                       "- 'reasoning': Short explanation (MAX 2 sentences)."),
            ("user", "JD:\n{jd}\n\nCurrent Findings:\n{findings}")
        ])
        
        result = llm.invoke(prompt.format_messages(jd=JOB_DESCRIPTION, findings=findings))
        
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
    steps.append({
        "module": module_name, 
        "prompt": "Evaluating sufficiency...", 
        "response": f"Decision: {decision}\nReasoning: {reasoning}"
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
        system_prompt = "You are a Hiring Manager. Write a polite, short rejection (MAX 30 WORDS)."
        user_content = f"Feedback: {screen_feedback}"
    else:
        system_prompt = (
            "You are a Hiring Manager. Output 3 sections:\n"
            "**Final Score:** [60-100]\n"
            "**Candidate Profile:** [Summary]\n"
            "**Strengths & Gaps:** [Details]"
        )
        user_content = f"Screening Feedback: {screen_feedback}\n\nTechnical Analysis:\n{tech_analysis}"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_content)
    ])
    
    res = llm.invoke(prompt.format_messages())
    final_text = res.content
    state["final_analysis"] = final_text
    
    steps = state.get("steps", [])
    steps.append({
        "module": "Final Analysis",
        "prompt": "Generating Final Report...",
        "response": final_text
    })
    state["steps"] = steps
    
    return state

print("[DEBUG] app.agents.nodes: Module import end")