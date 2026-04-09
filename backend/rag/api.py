from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from rag.models import PropertyRetrievalInput
from rag.retrieval import property_retrieval_tool

router = APIRouter(prefix="/rag", tags=["Property Retrieval"])


@router.post("/properties/search")
def search_properties(payload: PropertyRetrievalInput, current_user: dict = Depends(get_current_user)):
    token_role = (current_user.get("role") or "").lower()
    request_role = payload.user_role.lower()

    if token_role != request_role:
        raise HTTPException(status_code=403, detail="Role mismatch between token and request")

    results = property_retrieval_tool(
        query=payload.query,
        filters=payload.filters,
        user_role=request_role,
    )
    return {"count": len(results), "results": results}
