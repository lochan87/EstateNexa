from pathlib import Path

from fastapi import FastAPI
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(rag_router)
app.include_router(comparison_router)
app.include_router(summarization.router)


@app.get("/")
def root():
    return {"message": "EstateNexa backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
