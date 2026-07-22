import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import config
from app.database import get_db_context

EMAIL_WATERMARK = Path(__file__).parent / "email_watermark.py"

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def process_job(job_id: int):
    with get_db_context() as db:
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            log(f"Job {job_id}: not found")
            return
        if job["status"] != "pending":
            log(f"Job {job_id}: status is {job['status']}, skipping")
            return

        log(f"Job {job_id}: processing '{job['original_filename']}'")
        db.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
        db.commit()

    actual_input = None
    for ext in config.ALLOWED_EXTENSIONS:
        candidate = config.UPLOAD_DIR / f"{job['id']}{ext}"
        if candidate.exists():
            actual_input = candidate
            break

    if not actual_input:
        log(f"Job {job_id}: input file not found")
        mark_failed(job_id, "Input file not found")
        return

    log(f"Job {job_id}: input={actual_input.name}, email={job['email']}")

    output_filename = f"{job['id']}_watermarked{actual_input.suffix}"
    output_path = config.PROCESSED_DIR / output_filename
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        log(f"Job {job_id}: starting ffmpeg...")
        result = subprocess.run(
            [
                sys.executable, str(EMAIL_WATERMARK),
                str(actual_input),
                job["email"],
                "-o", str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=config.FFMPEG_TIMEOUT,
            cwd=str(EMAIL_WATERMARK.parent)
        )

        if result.returncode == 0 and output_path.exists():
            log(f"Job {job_id}: completed successfully")
            with get_db_context() as db:
                db.execute(
                    "UPDATE jobs SET status = 'completed', output_filename = ?, completed_at = ? WHERE id = ?",
                    (output_filename, datetime.now(timezone.utc).isoformat(), job_id)
                )
                db.commit()
        else:
            error = result.stderr[-1000:] if result.stderr else "Unknown error"
            log(f"Job {job_id}: failed - {error[:100]}")
            mark_failed(job_id, error)

    except subprocess.TimeoutExpired:
        log(f"Job {job_id}: timed out after {config.FFMPEG_TIMEOUT}s")
        mark_failed(job_id, "Processing timed out")
    except Exception as e:
        log(f"Job {job_id}: error - {e}")
        mark_failed(job_id, str(e))
    finally:
        if actual_input.exists():
            os.remove(actual_input)

def mark_failed(job_id: int, error: str):
    with get_db_context() as db:
        db.execute(
            "UPDATE jobs SET status = 'failed', error_message = ? WHERE id = ?",
            (error, job_id)
        )
        db.commit()

async def worker_loop():
    log("Worker started, waiting for jobs...")
    while True:
        with get_db_context() as db:
            pending = db.execute(
                "SELECT id FROM jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1"
            ).fetchone()

        if pending:
            process_job(pending["id"])
        else:
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(worker_loop())
