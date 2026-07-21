from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.models import UserCreate, UserResponse
from app.database import get_db_context
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
def register(data: UserCreate):
    with get_db_context() as db:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = hash_password(data.password)
        cursor = db.execute(
            "INSERT INTO users (email, hashed_password, created_at) VALUES (?, ?, ?)",
            (data.email, hashed, datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        return {"id": cursor.lastrowid, "email": data.email}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with get_db_context() as db:
        user = db.execute("SELECT id, email, hashed_password FROM users WHERE email = ?", (form_data.username,)).fetchone()
        if not user or not verify_password(form_data.password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token({"sub": user["id"]})
        return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(__import__("app.auth", fromlist=["get_current_user"]).get_current_user)):
    return current_user
