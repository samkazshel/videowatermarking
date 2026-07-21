import sqlite3
from datetime import datetime
from pathlib import Path
import contextlib
import config

def get_db():
    db = sqlite3.connect(config.DATABASE_URL)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    Path(config.DATABASE_URL).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                output_filename TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)

@contextlib.contextmanager
def get_db_context():
    db = get_db()
    try:
        yield db
    finally:
        db.close()
