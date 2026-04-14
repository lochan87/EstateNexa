from pathlib import Path

from fastapi import FastAPI
<<<<<<< Updated upstream
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from comparison_tool.api import router as comparison_router
from rag.api import router as rag_router
from routes import summarization

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="EstateNexa API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
=======
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from auth import router as auth_router
from investment.investment_routes import router as investment_router
from document_routes import router as document_router

app = FastAPI(title="EstateNexa API", version="1.0.0")

# CORS middleware
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
>>>>>>> Stashed changes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

<<<<<<< Updated upstream
app.include_router(auth_router)
app.include_router(rag_router)
app.include_router(comparison_router)
app.include_router(summarization.router)
=======
# Include routers
app.include_router(auth_router)
app.include_router(investment_router)
app.include_router(document_router)
>>>>>>> Stashed changes


@app.get("/")
def root():
    return {"message": "EstateNexa backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
