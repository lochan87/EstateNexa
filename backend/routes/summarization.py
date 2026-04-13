"""API routes for document summarization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, get_db_connection
from summarization.summarization_tool import summarize_documents

router = APIRouter(prefix="/summarize", tags=["summarization"])


class SummarizationRequest(BaseModel):
    query: str


@router.post("/")
def summarize(request: SummarizationRequest, current_user: dict = Depends(get_current_user)) -> dict[str, str | int]:
    role = str(current_user.get("role") or "buyer")
    query = (request.query or "").strip()
    user_id = int(current_user.get("user_id", 0))
    
    summary = summarize_documents(role, query=query)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id
            FROM chat_sessions
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        latest_row = cur.fetchone()
        latest_session_id = int(latest_row[0]) if latest_row else 0
        next_session_index = latest_session_id + 1

        cur.execute(
            """
            INSERT INTO chat_sessions (user_id, session_title)
            VALUES (%s, %s)
            RETURNING id
            """,
            (user_id, f"Session {next_session_index}"),
        )
        created_session_row = cur.fetchone()
        if not created_session_row:
            cur.close()
            conn.close()
            raise HTTPException(status_code=500, detail="Failed to create chat session")
        session_id = int(created_session_row[0])

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
            "session_id": session_id,
            "query": query,
            "summary": summary,
            "response_id": response_id,
            "stored": "true",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store response: {str(e)}",
        )
