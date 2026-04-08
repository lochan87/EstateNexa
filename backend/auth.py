import os
from datetime import datetime, timedelta
from typing import Literal, Optional

import psycopg2
from psycopg2 import OperationalError
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr


# Configure these through environment variables in production.
DB_HOST = os.getenv("DB_HOST", "172.25.81.34")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "estatenexa")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str



class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: Literal["buyer", "agent"] = "buyer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str


class LogoutResponse(BaseModel):
    message: str


def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    except OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Check DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD.",
        ) from exc


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate(email: str, password: str):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, email, password_hash, role
        FROM users
        WHERE email = %s
        """,
        (email,),
    )
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return None

    user_id, user_email, password_hash, role = row
    if not verify_password(password, password_hash):
        return None

    return {
        "id": user_id,
        "email": user_email,
        "role": role,
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Email is already registered")

    hashed_password = hash_password(payload.password)

    cur.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (%s, %s, %s, %s)
        RETURNING id, role
        """,
        (payload.name, payload.email, hashed_password, "buyer"),
    )

    user_id, role = cur.fetchone()
    conn.commit()

    cur.close()
    conn.close()

    access_token = create_access_token(subject=str(user_id), role=role)
    return TokenResponse(access_token=access_token, user_id=user_id, role=role)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if payload.role not in {"buyer", "agent"}:
        raise HTTPException(status_code=400, detail="Role must be buyer or agent")

    if user["role"] != payload.role:
        raise HTTPException(status_code=403, detail=f"This account is not registered as {payload.role}")

    access_token = create_access_token(subject=str(user["id"]), role=user["role"])
    return TokenResponse(access_token=access_token, user_id=user["id"], role=user["role"])


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user_id": user_id, "role": payload.get("role")}


@router.post("/logout", response_model=LogoutResponse)
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    current_user = get_current_user(credentials)
    return LogoutResponse(message=f"User {current_user['user_id']} successfully logged out")
