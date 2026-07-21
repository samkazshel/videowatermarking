import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import config
from app.database import get_db_context

# Add parent to path so we can import the original script
SCRIPT_DIR = Path(__file__).parent.parent.parent
EMAIL_WATERMARK = SCRIPT_DIR.parent / "email_watermark.py"

def process_job(job_id: int):
    with get_db_context() as db:
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            return
        if job["status"] != "pending":
            return

        db.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
        db.commit()

    actual_input = None
    for ext in config.ALLOWED_EXTENSIONS:
        candidate = config.UPLOAD_DIR / f"{job['id']}{ext}"
        if candidate.exists():
            actual_input = candidate
            break

    if not actual_input:
        mark_failed(job_id, "Input file not found")
        return

    output_filename = f"{job['id']}_watermarked{actual_input.suffix}"
    output_path = config.PROCESSED_DIR / output_filename
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable, str(EMAIL_WATERMARK),
                str(actual_input),
                job["email"],
                "-o", str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=config.FFMPEG_TIMEOUT
        )

        if result.returncode == 0 and output_path.exists():
            with get_db_context() as db:
                db.execute(
                    "UPDATE jobs SET status = 'completed', output_filename = ?, completed_at = ? WHERE id = ?",
                    (output_filename, datetime.now(timezone.utc).isoformat(), job_id)
                )
                db.commit()
        else:
            mark_failed(job_id, result.stderr[-1000:] if result.stderr else "Unknown error")

    except subprocess.TimeoutExpired:
        mark_failed(job_id, "Processing timed out")
    except Exception as e:
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
