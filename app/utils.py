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


JOB_DESCRIPTIONS = {
    "AI Engineer": """
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
""",
    
    "Data Analyst": """
Requirements:
* BSc in Industrial Engineering, Statistics, Economics, Mathematics, or related field
* 2-4 years of hands-on experience as a Data Analyst in a fast-paced environment
* Strong SQL skills - writing complex queries, optimizing performance
* Proficiency in Python (pandas, numpy) or R for data manipulation and analysis
* Experience with BI tools (Tableau, Looker, Power BI, or similar)
* Solid understanding of statistical methods and A/B testing
* Ability to communicate insights clearly to both technical and business stakeholders

Advantages:
* Military experience in intelligence/data units (8200, Mamram, or similar)
* Experience in B2B SaaS or fast-growing startups
* Knowledge of ETL processes and data pipelines
* Familiarity with cloud platforms (AWS, GCP, Azure)
* Experience building dashboards and self-service analytics solutions
* Background in product analytics or growth analytics
""",
    
    "Product Manager": """
Requirements:
* BSc in Computer Science, Engineering, or relevant field (or equivalent experience)
* 3-5 years of product management experience in tech companies
* Proven track record of launching successful products from 0 to 1
* Strong analytical skills - comfortable with data, metrics, and KPIs
* Experience working closely with engineering, design, and data teams
* Excellent communication skills in Hebrew and English
* Ability to define product vision, strategy, and roadmap
* Deep understanding of user needs and market dynamics

Advantages:
* Experience in B2B enterprise products or developer tools
* Background in technology (engineer-turned-PM)
* Military service in technological units (Talpiot, 8200, or similar)
* Experience with Agile/Scrum methodologies
* Track record in fast-paced startup environment (pre-seed to Series B)
* Strong stakeholder management skills across all levels
* Experience with product-led growth strategies
""",
    
    "Software Engineer": """
Requirements:
* BSc in Computer Science, Software Engineering, or equivalent practical experience
* 3+ years of hands-on software development experience
* Strong proficiency in at least one modern language (Python, Java, Go, TypeScript)
* Experience with cloud platforms and microservices architecture
* Solid understanding of data structures, algorithms, and design patterns
* Familiarity with CI/CD practices and modern development workflows
* Strong problem-solving skills and ability to work independently
* Experience with both backend and some frontend development

Advantages:
* Military service in elite technological units (8200, Mamram, C4I)
* Experience building and scaling distributed systems
* Contributions to open-source projects
* Startup experience or fast-paced development environments
* Knowledge of Kubernetes, Docker, and container orchestration
* Experience with modern frameworks (React, Node.js, FastAPI, Spring Boot)
* Understanding of security best practices and secure coding
* Experience mentoring junior developers
""",
    
    "Solutions Architect": """
Requirements:
* BSc/MSc in Computer Science, Engineering, or equivalent practical experience
* 5+ years of experience in software development, systems architecture, or technical consulting
* Deep understanding of cloud architectures (AWS, Azure, or GCP)
* Strong knowledge of distributed systems, microservices, and API design
* Experience designing enterprise-grade solutions for complex technical challenges
* Proven ability to communicate technical concepts to both technical and non-technical audiences
* Hands-on experience with infrastructure-as-code (Terraform, CloudFormation)
* Strong customer-facing skills and ability to lead technical discussions

Advantages:
* Military background in system architecture or technological leadership roles
* Experience with security architecture and compliance requirements
* Certifications (AWS Solutions Architect, Azure Architect, or similar)
* Track record working with Fortune 500 or large enterprises
* Experience in pre-sales or post-sales technical roles
* Knowledge of data architecture and big data technologies
* Background in DevOps, SRE, or platform engineering
* Experience with multi-cloud and hybrid cloud architectures
""",
    
    "Frontend Developer": """
Requirements:
* BSc in Computer Science, Software Engineering, or equivalent practical experience
* 2-4 years of hands-on frontend development experience
* Strong proficiency in modern JavaScript/TypeScript
* Expert-level knowledge of React or Vue.js (React strongly preferred)
* Solid understanding of HTML5, CSS3, and responsive design principles
* Experience with state management (Redux, Zustand, or similar)
* Familiarity with modern build tools (Vite, Webpack) and version control (Git)
* Strong eye for design and UX, ability to implement pixel-perfect interfaces

Advantages:
* Military service in technological units (8200, Mamram, C4I, or similar)
* Experience in fast-paced startup environment or product companies
* Knowledge of Next.js, server-side rendering, and modern React patterns
* Experience with design systems and component libraries (Tailwind, MUI, Ant Design)
* Understanding of web performance optimization and accessibility (a11y)
* Familiarity with backend technologies and RESTful/GraphQL APIs
* Experience with testing frameworks (Jest, Cypress, Playwright)
* Contributions to open-source projects or active GitHub profile
"""
}

# Keep backward compatibility with existing code
JOB_DESCRIPTION = JOB_DESCRIPTIONS["AI Engineer"]


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

