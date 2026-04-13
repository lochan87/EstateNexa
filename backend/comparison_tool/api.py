from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from .comparison_service import ComparisonService
    from .config import get_settings
    from .vector_store import collection_document_count
except ImportError:
    from comparison_service import ComparisonService
    from config import get_settings
    from vector_store import collection_document_count


router = APIRouter(prefix="/comparison", tags=["Comparison Tool"])


class ComparisonRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Comparison query such as comparing multiple Bangalore locations.")
    user_role: str = Field(..., description="One of buyer, agent, or admin.")
    user_agent_id: Optional[str] = Field(
        default=None,
        description="Required when user_role is agent so only that agent's properties are visible.",
    )


@router.post("/compare")
def compare_properties(payload: ComparisonRequest):
    try:
        service = ComparisonService()
        result = service.compare(
            query=payload.query,
            user_role=payload.user_role,
            user_agent_id=payload.user_agent_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Comparison tool failed ({type(exc).__name__}): {exc}",
        ) from exc


@router.post("/ingest")
def ingest_comparison_documents():
    try:
        service = ComparisonService()
        result = service.ensure_ingested()
        return {
            "message": "Ingestion completed" if result else "Collection already contains documents",
            "details": result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc


@router.get("/health")
def comparison_health():
    settings = get_settings()
    return {
        "groq_api_key_configured": bool(settings.groq_api_key),
        "property_pdf_exists": settings.property_pdf_path.exists(),
        "property_pdf_path": str(settings.property_pdf_path),
        "location_pdf_exists": settings.location_pdf_path.exists(),
        "location_pdf_path": str(settings.location_pdf_path),
        "collection_document_count": collection_document_count(),
    }
