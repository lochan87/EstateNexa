from fastapi import APIRouter
from market_analysis.analysis import generate_market_analysis

router = APIRouter()

@router.post("/market-analysis")
def market_analysis(query: dict):
    result = generate_market_analysis(query["query"])
    return {"response": result}