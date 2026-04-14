"""
Document Access Routes with RBAC
Routes for retrieving documents based on user role access control
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from auth import decode_token
from database import get_db
from models import Document, User

router = APIRouter(prefix="/documents", tags=["Documents"])
security = HTTPBearer()


class DocumentResponse(BaseModel):
    """Response model for documents"""
    id: int
    title: str
    doc_type: str
    access_role: str
    created_at: str
    uploaded_by: str
    
    class Config:
        from_attributes = True


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current user from JWT token"""
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": int(user_id), "role": payload.get("role")}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def can_access_document(user_role: str, doc_access_role: str) -> bool:
    """
    Check if user can access document based on role hierarchy
    
    Rules:
    - admin → can access all documents (access_role = admin/agent/buyer)
    - agent → can access agent + buyer documents (access_role = agent/buyer)
    - buyer → can access only buyer documents (access_role = buyer)
    """
    access_matrix = {
        "admin": {"admin", "agent", "buyer"},      # Admin sees all
        "agent": {"agent", "buyer"},                # Agent sees agent + buyer docs
        "buyer": {"buyer"},                         # Buyer sees only buyer docs
    }
    
    accessible_roles = access_matrix.get(user_role, set())
    return doc_access_role in accessible_roles


@router.get("/list", response_model=List[DocumentResponse])
def list_documents(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all documents accessible to the current user based on their role
    
    Args:
        current_user: Authenticated user info (user_id, role)
        db: Database session
    
    Returns:
        List of documents the user can access
    """
    user_role = current_user["role"]
    user_id = current_user["user_id"]
    
    # Get all documents from database
    all_documents = db.query(Document).all()
    
    # Filter documents based on user role
    accessible_documents = []
    for doc in all_documents:
        if can_access_document(user_role, doc.access_role):
            uploaded_by_user = db.query(User).filter(User.id == doc.uploaded_by).first()
            uploaded_by_name = uploaded_by_user.name if uploaded_by_user else "Unknown"
            
            accessible_documents.append(DocumentResponse(
                id=doc.id,
                title=doc.title,
                doc_type=doc.doc_type,
                access_role=doc.access_role,
                created_at=doc.created_at.isoformat(),
                uploaded_by=uploaded_by_name,
            ))
    
    return accessible_documents


@router.get("/check/{doc_id}")
def check_document_access(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check if current user can access a specific document
    
    Args:
        doc_id: Document ID to check
        current_user: Authenticated user info
        db: Database session
    
    Returns:
        Access check result with details
    """
    user_role = current_user["role"]
    
    document = db.query(Document).filter(Document.id == doc_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    can_access = can_access_document(user_role, document.access_role)
    
    return {
        "document_id": doc_id,
        "document_title": document.title,
        "document_access_role": document.access_role,
        "user_role": user_role,
        "can_access": can_access,
        "reason": (
            f"✅ {user_role.upper()} can access '{document.access_role}' documents"
            if can_access
            else f"❌ {user_role.upper()} cannot access '{document.access_role}' documents (only {', '.join(can_access.__doc__ or '')})"
        )
    }


@router.get("/{doc_id}/details", response_model=DocumentResponse)
def get_document_details(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific document (only if user has access)
    
    Args:
        doc_id: Document ID
        current_user: Authenticated user info
        db: Database session
    
    Returns:
        Document details if accessible
    """
    user_role = current_user["role"]
    
    document = db.query(Document).filter(Document.id == doc_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if user has access
    if not can_access_document(user_role, document.access_role):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. This is a '{document.access_role}' document and you are a '{user_role}'"
        )
    
    uploaded_by_user = db.query(User).filter(User.id == document.uploaded_by).first()
    uploaded_by_name = uploaded_by_user.name if uploaded_by_user else "Unknown"
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        doc_type=document.doc_type,
        access_role=document.access_role,
        created_at=document.created_at.isoformat(),
        uploaded_by=uploaded_by_name,
    )
