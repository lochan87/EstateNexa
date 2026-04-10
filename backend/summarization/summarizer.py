"""Groq-powered summary generation for role-based real estate insights."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    load_dotenv = None

try:
    from groq import Groq
except ImportError:  # pragma: no cover - optional dependency fallback
    Groq = None

if load_dotenv is not None:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(PROJECT_ROOT / ".env")

MODEL_CANDIDATES = [
    os.getenv("GROQ_MODEL", "").strip(),
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

_ROLE_INSTRUCTIONS = {
    "buyer": "Explain in simple terms, focus on practical takeaways and affordability.",
    "agent": "Provide detailed market and property insights useful for advising clients.",
    "admin": "Provide a full operational and strategic analysis with key risks and opportunities.",
}


def _fallback_summary(text: str) -> str:
    words = text.strip().split()
    if not words:
        return ""

    return " ".join(words[:180])


def _get_model_candidates() -> list[str]:
    # Preserve order while skipping empty/duplicate entries.
    unique_models = []
    for model in MODEL_CANDIDATES:
        if model and model not in unique_models:
            unique_models.append(model)

    return unique_models


def generate_summary(text: str, role: str, query: str = "") -> str:
    """Generate a role-specific summary using Groq LLaMA3.

    If query is provided, focus the summary on answering that query.
    Returns a fallback summary if the API call fails.
    """

    clean_text = (text or "").strip()
    if not clean_text:
        return ""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or Groq is None:
        return _fallback_summary(clean_text)

    role_key = (role or "").strip().lower()
    role_instruction = _ROLE_INSTRUCTIONS.get(
        role_key,
        "Provide a clear and balanced real estate summary.",
    )

    query_instruction = ""
    if query:
        query_instruction = f"\nUser query: {query}\nFocus the summary on answering this query with relevant details."

    prompt = (
        "You are a real estate expert. "
        f"Audience role: {role_key or 'general'}. "
        f"Instruction: {role_instruction} "
        "Write a concise summary in 150 to 200 words. "
        "Focus on accurate, actionable points and avoid unnecessary repetition."
        f"{query_instruction}\n\n"
        f"Source text:\n{clean_text}"
    )

    try:
        client = Groq(api_key=api_key)
        for model_name in _get_model_candidates():
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a precise real estate analyst."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )
                content = response.choices[0].message.content if response.choices else ""
                summary = (content or "").strip()
                if summary:
                    return summary
            except Exception:
                continue

        return _fallback_summary(clean_text)
    except Exception:
        return _fallback_summary(clean_text)
