"""FastAPI application entrypoint and HTTP API definitions.

This module wires together the LangGraph workflow with HTTP endpoints consumed
by the front-end UI and any external clients. It also exposes static assets for
the single-page interface.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Any, Dict
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

print("[DEBUG] app.main: Module import start")

app = FastAPI(title="Multi-Agent Data Science Resume Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


graph_app = build_graph()



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
        team_name="יוני שני ובר",
        students=students_list
    )
    print("[DEBUG] get_team_info: end")
    return info


@app.get("/api/agent_info", response_model=AgentInfo)
def get_agent_info() -> AgentInfo:
    """Describe the multi-agent system and its prompting strategy.

    Returns:
        An `AgentInfo` model containing description, purpose, and prompt
        examples that can be surfaced in the UI.
    """
    print("[DEBUG] get_agent_info: start")
    
    info = AgentInfo(
        description="A multi-agent system that evaluates Data Science candidates by analyzing their Resume text and performing a deep-dive technical audit of their GitHub repositories.",
        
        purpose="To automate the screening process for Data Scientist roles, specifically verifying technical claims made in resumes against actual code quality and project relevance found in public repositories.",
        
        prompt_template={
            "template": "Here is the candidate's resume text: {resume_text}. The text includes a link to their GitHub profile: {github_url}"
        },
        
        prompt_examples=[
            {
                "prompt": """Education
B.Sc, Data Science and Engineering
Technion - Israel Institute of Technology, 2021 - 2025
GPA - 90.
Achieved Dean's List honors four times.
Relevant Courses: Probability (100), Statistics (91), Data Structures and Algorithms (86), Deep Learning (91).

Technion Data Science and Engineering graduate with 2 years of software development experience. Skilled in Python, PyTorch, and Deep Learning methods.

Surgical Computer Vision Project: Surgical tool pose-estimation system that generates synthetic labeled data. GitHub Link.
RAG Project: An LLM-based assistant using RAG and vector search. GitHub Link.
Time Series Project: Forecasting electricity consumption with ARIMA, Prophet, and XGBoost. GitHub Link.

https://github.com/YoniAfek1""",

                "full_response": """**Final Score:** 86

                **Candidate Profile:** A junior ML/CV engineer with ~2 years of professional engineering experience, solid Python/PyTorch skills, and hands‑on projects spanning computer vision (pose/YOLO pipelines) and LLM work. Their repositories show practical end‑to‑end thinking (synthetic data → finetune → pseudo‑label) and familiarity with common tooling, but some implementations are incomplete and need hardening.

                **Strengths & Gaps:** Strength — pragmatic ML pipeline design and domain adaptation intuition: sensible 3‑phase approach, runtime heuristics (frame skipping, confidence/min‑detections filtering), and awareness of efficiency/noise tradeoffs. Gaps — engineering robustness and polish: incomplete/fragile code (cut‑off functions, hardcoded absolute paths), missing tensor→numpy conversions and normalization for outputs, brittle assumptions about model result shapes, limited CLI/config, resource handling and defensive checks; would benefit from stronger I/O handling, testing, and production hardened utilities.""",
                
                "steps": [
                    "Input Parser: Found: https://github.com/YoniAfek1",
                    
                    "Screening Agent: Decision: YES , Feedback: Relevant ML/CV and LLM projects, Python/PyTorch skills, 2 years engineering experience.",
                    
                    "Git Planner: Check repo surgical_tool_pose_detection for surgical tool detection, pose estimation, and real-time computer-vision pipelines.",
                    
                    """Git Executor: 
                    - Good direction and sensible heuristics: the repo implements a sensible 3‑phase approach (synthetic data → finetune YOLO‑pose → pseudo‑label real video), and domain_adaptation.py already includes useful runtime heuristics (frame_skip to reduce computation and a confidence / min‑detections filter) which shows practical thinking about noisy unlabeled video and efficiency.

                    - domain_adaptation.py is incomplete and fragile — the function is cut off mid‑write and the file hardcodes many absolute paths. Current checks also assume a lot about ultralytics' result shapes (e.g., results[0].boxes / keypoints APIs) and there is no conversion/normalization shown before writing pseudo labels (so produced labels may not match YOLO keypoint format). Fixes: complete the I/O (write image and properly formatted .txt), use argparse/config for paths, add defensive checks and explicit .cpu().numpy() conversions, and ensure keypoints are converted to the expected (normalized) coordinate format when saving.

                    - predict.py is close to usable but has small robustness issues and is incomplete at the end: convert tensors to numpy before drawing (e.g., .cpu().numpy()), clamp/check shapes for multi‑instance outputs, persist the annotated image (cv2.imwrite) and free/close resources. Also consider exposing model/device/conf thresholds via CLI and returning non‑zero exit codes on failures rather than bare asserts for better UX.""",
                    
                    """Final Analysis: **Final Score:** 86 **Candidate Profile:** A junior ML/CV engineer with ~2 years of professional engineering experience. 
                    **Strengths:** Pragmatic ML pipeline design and domain adaptation intuition. 
                    **Gaps:** Engineering robustness and polish: incomplete/fragile code, missing tensor→numpy conversions, brittle assumptions.""",
                ]
            }
        ]
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
async def execute(request: ExecuteRequest):
    """
    Run the multi-agent workflow based on the provided resume text/URL.
    """
    # 1. יצירת ה-State ההתחלתי
    initial_state: AgentState = {
        "resume_text": request.prompt,
        "steps": [],
        "git_iteration_count": 0,
        "visited_repos": []
    }

    # 2. הרצת הגרף
    try:
        final_state = app_graph.invoke(initial_state)
    except Exception as e:
        return ExecuteResponse(
            status="error",
            error=str(e),
            response="Internal Server Error during execution.",
            steps=[]
        )

    # 3. שליפת התשובה הסופית בצורה בטוחה
    # התיקון: מוודאים שאנחנו לוקחים את 'final_analysis'. אם זה ריק, מחזירים הודעת שגיאה.
    final_text = final_state.get("final_analysis")
    
    if not final_text:
        # במקרה נדיר שהסוכן האחרון נכשל ולא ייצר טקסט
        final_text = "Analysis completed, but no final text was generated."

    return ExecuteResponse(
        status="success",
        response=final_text,  # זה השדה הקריטי שה-JS מחפש!
        steps=final_state.get("steps", [])
    )
    
@app.get("/")
def index() -> FileResponse:
    """Serve the main HTML file for the front-end UI."""
    return FileResponse(os.path.join("static", "index.html"), media_type="text/html")


print("[DEBUG] app.main: Module import end")