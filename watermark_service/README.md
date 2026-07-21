# Video Watermark Service

A simple web service for adding email watermarks to videos.

## Setup

```bash
cd watermark_service
pip install -r requirements.txt
```

## Run

```bash
# Terminal 1: Start the API server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start the worker (processes videos)
python worker.py
```

## API Docs

Once running, visit http://localhost:8000/docs for interactive API documentation.

## Environment Variables

- `SECRET_KEY` - Secret key for JWT tokens (required for production)
