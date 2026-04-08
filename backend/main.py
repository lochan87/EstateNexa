from fastapi import FastAPI

from auth import router as auth_router

app = FastAPI(title="EstateNexa API", version="1.0.0")

app.include_router(auth_router)


@app.get("/")
def root():
    return {"message": "EstateNexa backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
