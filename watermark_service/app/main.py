from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.database import init_db, get_db_context
from app.auth import verify_password, hash_password, create_access_token, get_current_user
from app.routes import auth, upload
import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(title="Video Watermark Service", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(upload.router)

templates = Jinja2Templates(directory="app/templates")

@app.get("/")
def root(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login")
def login_page(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(), password: str = Form()):
    email = username

    with get_db_context() as db:
        user = db.execute(
            "SELECT id, email, hashed_password FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if not user or not verify_password(password, user["hashed_password"]):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password"
        })

    token = create_access_token({"sub": str(user["id"])})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, path="/")
    return response

@app.get("/register")
def register_page(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, email: str = Form(), password: str = Form(), confirm_password: str = Form()):

    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match"
        })

    with get_db_context() as db:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "Email already registered"
            })

        hashed = hash_password(password)
        cursor = db.execute(
            "INSERT INTO users (email, hashed_password, created_at) VALUES (?, ?, ?)",
            (email, hashed, datetime.now(timezone.utc).isoformat())
        )
        db.commit()

    return RedirectResponse(url="/login", status_code=302)

@app.get("/dashboard")
def dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        from jose import jwt
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        return RedirectResponse(url="/login", status_code=302)

    with get_db_context() as db:
        user = db.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": dict(user)
    })

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@app.get("/download/{job_id}")
def download(job_id: int, request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        from jose import jwt
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        return RedirectResponse(url="/login", status_code=302)

    with get_db_context() as db:
        job = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id)
        ).fetchone()
        if not job or job["status"] != "completed":
            return RedirectResponse(url="/dashboard", status_code=302)

        output_path = config.PROCESSED_DIR / job["output_filename"]
        if not output_path.exists():
            return RedirectResponse(url="/dashboard", status_code=302)

        from pathlib import Path
        ext = Path(job["original_filename"]).suffix
        filename = job["original_filename"].replace(ext, f"_watermarked{ext}")

        from fastapi.responses import FileResponse
        return FileResponse(
            output_path,
            filename=filename,
            media_type="application/octet-stream"
        )
