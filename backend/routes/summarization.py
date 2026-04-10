"""API routes for document summarization."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
from summarization.summarization_tool import summarize_documents

router = APIRouter(prefix="/summarize", tags=["summarization"])


class SummarizationRequest(BaseModel):
    query: str


@router.post("/")
def summarize(request: SummarizationRequest, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    role = str(current_user.get("role") or "buyer")
    query = (request.query or "").strip()
    summary = summarize_documents(role, query=query)
    return {
        "user_id": str(current_user.get("user_id", "")),
        "role": role,
        "query": query,
        "summary": summary,
    }
