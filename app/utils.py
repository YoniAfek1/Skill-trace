"""Utility helpers for environment configuration and GitHub/LLM helpers.

This module centralizes shared constants and helper functions, including the
hard-coded job description, environment accessors for the LLM API key, and
helpers for extracting and querying GitHub resources.
"""

import os
import os
from dotenv import load_dotenv

load_dotenv()
import re
from typing import Optional
import requests

print("[DEBUG] app.utils: Module import start")


JOB_DESCRIPTION = """
Requirements:
* BSc or MSc in Computer Science, Electrical Engineering, or a related field
* 2+ years of experience in software engineering and applied AI (or equivalent)
* Strong proficiency in Python and modern AI frameworks
* Proven experience delivering production-grade AI systems
* Solid understanding of deep learning architectures (CNNs, transformers)
* Experience with system-level design, debugging, and performance optimization

Domain-Specific Experience (One or More):
1. LLM / Agentic Systems:
   * Experience working with Large Language Models (LLMs)
   * Building agentic workflows, reasoning systems, or AI-driven applications
   * Deploying and optimizing open-source LLMs for inference
2. Computer Vision:
   * Strong background in computer vision and deep learning
   * Hands-on experience with detection, segmentation, and tracking models
   * Experience with video pipelines and real-time or near-real-time systems
"""


def get_llm_api_key() -> str:
    """Return the API key used to authenticate with the LLM provider.

    The key is read from the `LLM_API_KEY` environment variable. An explicit
    error is raised if the variable is not set to avoid silent misconfiguration.

    Returns:
        The LLM API key as a string.

    Raises:
        ValueError: If `LLM_API_KEY` is not defined in the environment.
    """
    print("[DEBUG] get_llm_api_key: start")
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise ValueError("LLM_API_KEY not found in environment")
    print(f"[DEBUG] get_llm_api_key: end (using key length={len(key)})")
    return key


def extract_github_url(text: str) -> Optional[str]:
    """Extract a GitHub profile or repository URL from a free-text string.

    The function searches the text for patterns matching either a profile URL
    (e.g. ``https://github.com/username``) or a single-repository URL
    (e.g. ``https://github.com/username/repo``).

    Args:
        text: Arbitrary text, typically the full resume content.

    Returns:
        The first GitHub URL found, or ``None`` if no URL is detected.
    """
    print("[DEBUG] extract_github_url: start")
    # Matches https://github.com/Username or https://github.com/Username/Repo
    github_regex = r"(https?://github\.com/[a-zA-Z0-9\-_]+(?:/[a-zA-Z0-9\-_]+)?)"
    match = re.search(github_regex, text)
    url = match.group(1) if match else None
    print(f"[DEBUG] extract_github_url: end url={url}")
    return url


def fetch_user_public_repos(username: str) -> str:
    """Fetch a textual summary of a user's public repositories from GitHub.

    The function queries the GitHub REST API for the specified username and
    returns a human-readable summary of up to 10 most recently updated
    repositories (name, description, language, and star count).

    Args:
        username: GitHub username whose repositories should be listed.

    Returns:
        A multi-line string summarizing the available repositories or a short
        error message if the request fails.
    """
    print(f"[DEBUG] fetch_user_public_repos: fetching for {username}")
    api_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10"
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            return f"Error fetching repos: {resp.status_code}"

        repos = resp.json()
        if not repos:
            return "No public repositories found."

        summary = "Available Public Repositories:\n"
        for r in repos:
            summary += (
                f"- {r.get('name')}: {r.get('description', 'No desc')} "
                f"(Lang: {r.get('language')}, Stars: {r.get('stargazers_count')})\n"
            )
        return summary
    except Exception as e:
        return f"Error: {e}"


print("[DEBUG] app.utils: Module import end")

