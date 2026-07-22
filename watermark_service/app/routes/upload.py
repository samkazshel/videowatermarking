import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.auth import get_current_user
from app.database import get_db_context
import config

router = APIRouter(prefix="/api", tags=["upload"])

@router.post("/jobs")
async def create_job(
    email: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    current_user: dict = Depends(get_current_user)
):
    ext = Path(file.filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {ext}")

    file_size = 0
    original_filename = file.filename
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with get_db_context() as db:
        cursor = db.execute(
            "INSERT INTO jobs (user_id, original_filename, email, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (current_user["id"], original_filename, email, "pending", datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        job_id = cursor.lastrowid

    upload_path = config.UPLOAD_DIR / f"{job_id}{ext}"
    with open(upload_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > config.MAX_FILE_SIZE:
                os.remove(upload_path)
                raise HTTPException(status_code=413, detail="File too large")
            f.write(chunk)

    return {"job_id": job_id, "filename": original_filename}

@router.get("/jobs")
def list_jobs(current_user: dict = Depends(get_current_user)):
    with get_db_context() as db:
        jobs = db.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC",
            (current_user["id"],)
        ).fetchall()
        return [dict(j) for j in jobs]

@router.get("/jobs/{job_id}")
def get_job(job_id: int, current_user: dict = Depends(get_current_user)):
    with get_db_context() as db:
        job = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, current_user["id"])
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(job)

@router.get("/jobs/{job_id}/download")
def download_file(job_id: int, current_user: dict = Depends(get_current_user)):
    with get_db_context() as db:
        job = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, current_user["id"])
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not ready")

        output_path = config.PROCESSED_DIR / job["output_filename"]
        if not output_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            output_path,
            filename=job["original_filename"].replace(ext := Path(job["original_filename"]).suffix, f"_watermarked{ext}"),
            media_type="application/octet-stream"
        )

@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, current_user: dict = Depends(get_current_user)):
    with get_db_context() as db:
        job = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, current_user["id"])
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job["output_filename"]:
            output_path = config.PROCESSED_DIR / job["output_filename"]
            if output_path.exists():
                output_path.unlink()

        db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        db.commit()
        return {"message": "Job deleted"}
