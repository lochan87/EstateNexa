"""API routes for document summarization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, get_db_connection
from summarization.summarization_tool import summarize_documents

router = APIRouter(prefix="/summarize", tags=["summarization"])


class SummarizationRequest(BaseModel):
    query: str
    session_id: int | None = None


@router.post("/")
def summarize(request: SummarizationRequest, current_user: dict = Depends(get_current_user)) -> dict[str, str | int]:
    role = str(current_user.get("role") or "buyer")
    query = (request.query or "").strip()
    user_id = int(current_user.get("user_id", 0))
    session_id = request.session_id
    
    summary = summarize_documents(role, query=query)
    
    if session_id is not None:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute(
                """
                INSERT INTO ai_responses (session_id, user_id, query, response, tool_used)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (session_id, user_id, query, summary, "summary"),
            )
            
            response_id, created_at = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            
            return {
                "user_id": str(user_id),
                "role": role,
                "query": query,
                "summary": summary,
                "response_id": response_id,
                "stored": "true",
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store response: {str(e)}",
            )
    
    return {
        "user_id": str(user_id),
        "role": role,
        "query": query,
        "summary": summary,
        "stored": "false",
    }
