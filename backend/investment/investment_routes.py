"""
Investment Recommendation API Routes
Full context synthesis with best_area identification and per-area properties
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
import json
import os
import re
from typing import Optional, Dict, Any, List

from auth import decode_token
from database import get_db
from models import User, InvestmentAnalysis, Property
from .investment_recommendation_tool import investment_tool
from document_loader import DocumentLoader
from rbac_utils import RBACEnforcer

router = APIRouter(prefix="/investment", tags=["Investment Recommendations"])
security = HTTPBearer()
INVESTMENT_DOCS_PATH = Path(__file__).resolve().parent / "documents"
document_loader = DocumentLoader(documents_path=str(INVESTMENT_DOCS_PATH))


def _safe_float(value: any) -> float:
    """Safely convert value to float."""  
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r'[-+]?\d*\.?\d+', value)
        if match:
            return float(match.group())
    return 0.0


class InvestmentQueryRequest(BaseModel):
    query: str


class BestArea(BaseModel):
    location: str
    score: float
    roi: float
    rental_yield: float
    risk_level: str
    property_count: int
    reasoning: str


class InvestmentRecommendationResponse(BaseModel):
    query: str
    best_area: BestArea
    synthesized_analysis: str
    properties_by_area: Dict[str, List[Dict[str, Any]]]
    matched_insights_count: int
    analysis_timestamp: str


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": int(user_id), "role": payload.get("role")}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/analyze", response_model=InvestmentRecommendationResponse)
def analyze_investment_opportunity(
    request: InvestmentQueryRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze with full PDF context -> natural ROI-focused response + best area + properties.
    """
    try:
        print(f"🔍 Analyzing: {request.query} (User: {current_user['role']})")
        
        # Load documents
        insights_chunks = document_loader.load_and_chunk_document("Investment_Insights.pdf")
        property_chunks = document_loader.load_and_chunk_document("Property_Listings.pdf")
        
        if not insights_chunks or not property_chunks:
            raise HTTPException(status_code=404, detail="Required documents missing")
        
        insights_text = "\n".join([c.page_content for c in insights_chunks])
        property_text = "\n".join([c.page_content for c in property_chunks])
        
        # Analyze w/ new logic
        analysis = investment_tool.analyze_opportunity(
            user_query=request.query,
            investment_insights_text=insights_text,
            property_listings_text=property_text,
            user_role=current_user["role"],
        )
        
        print(f"✅ Best area: {analysis['best_area']['location']} | Insights: {analysis['matched_insights_count']}")
        
        # Store enhanced analysis
        best = analysis['best_area']
        db_analysis = InvestmentAnalysis(
            user_id=current_user["user_id"],
            investment_location=best['location'],
            profit_potential=_safe_float(best['roi']),
            risk_level=best['risk_level'],
            roi_percentage=_safe_float(best['roi']),
            rental_yield_percentage=_safe_float(best['rental_yield']),
            analysis_details=json.dumps({
                "query": request.query,
                "best_area": best['location'],
                "synthesized_analysis": analysis['synthesized_analysis'][:500],
                "insights_count": analysis['matched_insights_count'],
                "properties_by_area": {k: len(v) for k, v in analysis['properties_by_area'].items()}
            })
        )
        db.add(db_analysis)
        db.commit()
        
        # Return full new response
        return InvestmentRecommendationResponse(
            query=analysis["query"],
            best_area=BestArea(**analysis["best_area"]),
            synthesized_analysis=analysis["synthesized_analysis"],
            properties_by_area=analysis["properties_by_area"],
            matched_insights_count=analysis["matched_insights_count"],
            analysis_timestamp=analysis["analysis_timestamp"],
        )
    
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/history")
def get_investment_history(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    analyses = db.query(InvestmentAnalysis).filter(InvestmentAnalysis.user_id == current_user["user_id"]).order_by(InvestmentAnalysis.analysis_timestamp.desc()).all()
    return {
        "total_analyses": len(analyses),
        "analyses": [
            {
                "location": a.investment_location,
                "roi_percentage": float(a.roi_percentage),
                "risk_level": a.risk_level,
                "timestamp": a.analysis_timestamp.isoformat(),
            } for a in analyses
        ]
    }


@router.get("/documents/available")
def get_available_documents(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    accessible_docs = RBACEnforcer.get_accessible_documents(current_user["role"], db)
    docs_path = os.path.join(os.path.dirname(__file__), "..", "Documents")
    available_docs = []
    for doc in accessible_docs:
        file_path = os.path.join(docs_path, os.path.basename(doc.file_path))
        if os.path.exists(file_path):
            available_docs.append({
                "id": doc.id,
                "name": doc.title,
                "file_name": os.path.basename(doc.file_path),
                "type": doc.doc_type,
                "access_role": doc.access_role,
            })
    return {
        "user_role": current_user["role"],
        "available_documents": available_docs,
    }


@router.get("/properties/accessible", response_model=dict)
def get_accessible_properties(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    properties = RBACEnforcer.get_accessible_properties(current_user["user_id"], current_user["role"], db)
    serialized_props = [RBACEnforcer.serialize_property(p, current_user["role"]) for p in properties]
    return {
        "user_role": current_user["role"],
        "accessible_properties": serialized_props,
        "total_count": len(serialized_props),
    }


@router.get("/properties/{property_id}", response_model=dict)
def get_property_details(property_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    property_obj = RBACEnforcer.enforce_property_access(current_user["user_id"], current_user["role"], property_id, db)
    property_data = RBACEnforcer.serialize_property(property_obj, current_user["role"])
    property_data["accessed_by_role"] = current_user["role"]
    return property_data
