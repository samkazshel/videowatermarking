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
async def create_jobs(
    email: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    current_user: dict = Depends(get_current_user)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    job_ids = []
    errors = []

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in config.ALLOWED_EXTENSIONS:
            errors.append(f"{file.filename}: unsupported file type")
            continue

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
        upload_ok = True
        try:
            with open(upload_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    file_size += len(chunk)
                    if file_size > config.MAX_FILE_SIZE:
                        os.remove(upload_path)
                        errors.append(f"{file.filename}: file too large")
                        upload_ok = False
                        break
                    f.write(chunk)
        except Exception as e:
            errors.append(f"{file.filename}: {str(e)}")
            upload_ok = False
        if upload_ok:
            job_ids.append({"job_id": job_id, "filename": original_filename})

    return {"jobs": job_ids, "errors": errors if errors else None}

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
            filename=job["output_filename"],
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

@router.delete("/jobs")
def delete_all_jobs(current_user: dict = Depends(get_current_user)):
    with get_db_context() as db:
        jobs = db.execute(
            "SELECT * FROM jobs WHERE user_id = ?",
            (current_user["id"],)
        ).fetchall()

        for job in jobs:
            if job["output_filename"]:
                output_path = config.PROCESSED_DIR / job["output_filename"]
                if output_path.exists():
                    output_path.unlink()

        db.execute("DELETE FROM jobs WHERE user_id = ?", (current_user["id"],))
        db.commit()
        return {"message": "All jobs deleted"}
