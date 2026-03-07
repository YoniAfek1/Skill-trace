"""FastAPI application entrypoint and HTTP API definitions.

This module wires together the LangGraph workflow with HTTP endpoints consumed
by the front-end UI and any external clients. It also exposes static assets for
the single-page interface.
"""
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Any, Dict, List
import os

from app.models import (
    ExecuteRequest,
    ExecuteResponse,
    StepModel,
    TeamInfo,
    Student,
    AgentInfo,
)
from app.state import AgentState
from app.agents.graph import build_graph
from app.utils import JOB_DESCRIPTIONS
from app.agent_info_examples import AGENT_INFO_PROMPT_EXAMPLES

print("[DEBUG] app.main: Module import start")

app = FastAPI(title="Multi-Agent Technical Resume Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

graph_app = build_graph()


def _normalize_role_name(value: str) -> str:
    """Return canonical role name if value matches available roles (case-insensitive)."""
    candidate = (value or "").strip()
    candidate = re.sub(r"[.!?,;:\s]+$", "", candidate)
    if not candidate:
        return ""
    lowered = candidate.lower()
    for role in JOB_DESCRIPTIONS.keys():
        if role.lower() == lowered:
            return role
    return ""


def _resolve_job_role_and_prompt(prompt: str) -> tuple[str, str]:
    """Resolve JD from prompt and strip all inline Job Role lines."""
    role = "AI Engineer"
    cleaned_lines: List[str] = []
    removed_any = False

    for line in prompt.splitlines():
        stripped = line.strip()
        match = re.match(r"^job\s*role\s*:\s*(.+)$", stripped, flags=re.IGNORECASE)
        if match:
            removed_any = True
            parsed_role = _normalize_role_name(match.group(1))
            if parsed_role == "":
                continue
            if role == "AI Engineer":
                role = parsed_role
            continue
        cleaned_lines.append(line)

    cleaned_prompt = "\n".join(cleaned_lines).strip()
    if removed_any:
        return role, cleaned_prompt
    return role, prompt


def _normalize_steps(raw_steps: List[Dict[str, Any]]) -> List[StepModel]:
    normalized_steps: List[StepModel] = []
    for raw_step in raw_steps:
        module_name = str(raw_step.get("module", "Unknown Module"))
        prompt_payload = raw_step.get("prompt", {})
        response_payload = raw_step.get("response", {})

        if not isinstance(prompt_payload, dict):
            prompt_payload = {"value": str(prompt_payload)}
        if not isinstance(response_payload, dict):
            response_payload = {"value": str(response_payload)}

        normalized_steps.append(
            StepModel(
                module=module_name,
                prompt=prompt_payload,
                response=response_payload,
            )
        )
    return normalized_steps


@app.get("/api/team_info", response_model=TeamInfo)
def get_team_info() -> TeamInfo:
    """Return metadata about the student team that built this project.

    Returns:
        A `TeamInfo` model with batch identifier, team name, and students.
    """
    print("[DEBUG] get_team_info: start")

    students_list = [
        Student(name="Bar Muller", email="bar.muller@campus.technion.ac.il"),
        Student(name="Shani Angel", email="shani.angel@campus.technion.ac.il"),
        Student(name="Jonathan Haber-Afek", email="jonathanh@campus.technion.ac.il")
    ]

    info = TeamInfo(
        group_batch_order_number="batch3_order3",
        team_name="Yoni, Shani, and Bar",
        students=students_list
    )
    print("[DEBUG] get_team_info: end")
    return info


@app.get("/api/job_roles")
def get_job_roles() -> Dict[str, Any]:
    """Return available job roles for candidate evaluation.

    Returns:
        A dictionary with job role names as keys.
    """
    print("[DEBUG] get_job_roles: start")
    roles = list(JOB_DESCRIPTIONS.keys())
    print(f"[DEBUG] get_job_roles: returning {len(roles)} roles")
    return {"roles": roles}


@app.get("/api/agent_info", response_model=AgentInfo)
def get_agent_info() -> AgentInfo:
    """Describe the multi-agent system and its prompting strategy.

    Returns:
        An `AgentInfo` model containing description, purpose, and prompt
        examples that can be surfaced in the UI.
    """
    print("[DEBUG] get_agent_info: start")

    info = AgentInfo(
        description=(
            "A multi-agent resume analyzer that screens candidate relevance to a selected job role, "
            "extracts GitHub links from the resume text, audits repositories, and returns a final hiring "
            "summary with a verdict."
        ),
        purpose=(
            "Provide transparent technical screening by combining resume evidence with repository-level code signals, "
            "in the intent to help bridge the gap between keywords and competency, in an Recruiter friendly tone."
        ),
        prompt_template={
            "template":
                "Input modes:\n"
                "- API (/api/execute): send JSON where prompt is a single string; represent line breaks with \\n.\n"
                "- UI: paste the resume normally with regular line breaks (no escaping needed).\n\n"
                "Required first line of the prompt in API mode:\n"
                "Job Role: [Insert one of /api/job_roles]\n\n"
                "[Paste the full candidate resume text, including GitHub URL]\n\n"
        },
        prompt_examples=AGENT_INFO_PROMPT_EXAMPLES,
    )
    print("[DEBUG] get_agent_info: end")
    return info


@app.get("/api/model_architecture")
def get_model_architecture() -> FileResponse:
    """Serve the static PNG that documents the model architecture.

    Returns:
        A `FileResponse` for `static/architecture.png`, or a 404 if missing.
    """
    print("[DEBUG] get_model_architecture: start")
    file_path = os.path.join("static", "architecture.png")
    if not os.path.exists(file_path):
        # Fallback behaviour if the architecture diagram is missing.
        print("[DEBUG] get_model_architecture: file not found")
        raise HTTPException(status_code=404, detail="architecture.png not found")

    print("[DEBUG] get_model_architecture: end")
    return FileResponse(file_path, media_type="image/png")


# --- Endpoint D: Execute (Main) ---
@app.post("/api/execute", response_model=ExecuteResponse)
def execute(request: ExecuteRequest) -> ExecuteResponse:
    """Run the multi-agent workflow and return final response with full trace."""
    resolved_role, cleaned_prompt = _resolve_job_role_and_prompt(request.prompt)
    initial_state: AgentState = {
        "resume_text": cleaned_prompt,
        "job_role": resolved_role,
        "steps": [],
        "git_iteration_count": 0,
        "visited_repos": [],
    }

    try:
        final_state = graph_app.invoke(initial_state)

        raw_steps: List[Dict[str, Any]] = final_state.get("steps", []) or []
        normalized_steps = _normalize_steps(raw_steps)

        final_text = str(final_state.get("final_analysis", "")).strip()
        if not final_text:
            final_text = "Analysis completed, but no final text was generated."

        return ExecuteResponse(
            status="ok",
            error=None,
            response=final_text,
            steps=normalized_steps,
        )
    except Exception as exc:
        return ExecuteResponse(
            status="error",
            error=f"Execution failed: {str(exc)}",
            response=None,
            steps=[],
        )


@app.post("/api/execute/stream")
def execute_stream(request: ExecuteRequest) -> StreamingResponse:
    """Run the workflow and stream step trace events in real time (solely for UX/UI purposes, this has the exact same
    functionality as api/execute."""

    def event_generator():
        resolved_role, cleaned_prompt = _resolve_job_role_and_prompt(request.prompt)
        initial_state: AgentState = {
            "resume_text": cleaned_prompt,
            "job_role": resolved_role,
            "steps": [],
            "git_iteration_count": 0,
            "visited_repos": [],
        }

        emitted_steps_count = 0
        final_text = ""

        try:
            for event in graph_app.stream(initial_state):
                for _, state_update in event.items():
                    if "steps" in state_update and state_update["steps"]:
                        all_steps = state_update["steps"]
                        new_steps = all_steps[emitted_steps_count:]
                        normalized_new = _normalize_steps(new_steps)
                        for step in normalized_new:
                            yield f"data: {json.dumps({'type': 'step', 'step': step.model_dump()})}\n\n"
                        emitted_steps_count = len(all_steps)

                    if "final_analysis" in state_update:
                        raw = state_update["final_analysis"]
                        final_text = str(raw).strip() if raw else ""

            if not final_text:
                final_text = "Analysis completed, but no final text was generated."

            yield f"data: {json.dumps({'type': 'done', 'response': final_text})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/")
def index() -> FileResponse:
    """Serve the main HTML file for the front-end UI."""
    return FileResponse(os.path.join("static", "index.html"), media_type="text/html")


print("[DEBUG] app.main: Module import end.")