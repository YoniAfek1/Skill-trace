"""Pydantic request and response models for the API layer.

This module defines the data structures that describe the HTTP input and output
schemas used by the FastAPI endpoints, including team metadata, agent
descriptions, execution requests, and execution traces.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

print("[DEBUG] app.models: Module import start")


class Student(BaseModel):
    """Single student entry in the team information response."""

    name: str
    email: str


class TeamInfo(BaseModel):
    """Metadata about the team that implemented this project.

    Attributes:
        group_batch_order_number: Identifier for the cohort/batch and group.
        team_name: Human-readable team name.
        students: List of team members participating in the project.
    """

    group_batch_order_number: str
    team_name: str
    students: List[Student]


class AgentInfo(BaseModel):
    """Description of the multi-agent system and its prompt templates.

    Attributes:
        description: High-level description of what the system does.
        purpose: Business or pedagogical motivation for the system.
        prompt_template: Base template used to construct LLM prompts.
        prompt_examples: Example prompts and responses for documentation or UI.
    """

    description: str
    purpose: str
    prompt_template: Dict[str, str]
    prompt_examples: List[Dict[str, Any]]


class ExecuteRequest(BaseModel):
    """Payload sent to the `/api/execute` endpoint.

    Attributes:
        prompt: Full resume text, optionally containing a GitHub profile URL.
        job_role: The selected job role to evaluate the candidate against.
    """

    prompt: str = Field(
        ...,
        description="Resume text (may also contain GitHub URL)",
    )
    job_role: str = Field(
        default="AI Engineer",
        description="Job role to evaluate candidate against",
    )


class StepModel(BaseModel):
    """Single step in the agent execution trace.

    Attributes:
        module: Logical module or agent name (e.g., 'Screening Agent').
        prompt: Prompt or input passed into that step.
        response: Raw text output produced by that step.
    """

    module: str
    prompt: Dict[str, Any]
    response: Dict[str, Any]


class ExecuteResponse(BaseModel):
    """Standardized response envelope for `/api/execute`.

    Attributes:
        status: `"ok"` on success, or `"error"` if something failed.
        error: Optional error message when `status` is `"error"`.
        response: Final textual analysis or explanation returned to the client.
        steps: Ordered list of intermediate steps for UI inspection and debug.
    """

    status: str
    error: Optional[str]
    response: Optional[str]
    steps: List[StepModel]


print("[DEBUG] app.models: Module import end")
