# Docker Deployment

## Quick Start

1. Generate a secure secret key:
   ```bash
   openssl rand -hex 32
   ```

2. Create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and add your SECRET_KEY
   ```

3. Build and run:
   ```bash
   docker-compose up -d
   ```

4. Visit `http://your-server:8000`

## Manual Deployment (without Docker)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install bcrypt==4.2.0 email-validator==2.2.0
   ```

2. Set environment variable:
   ```bash
   export SECRET_KEY="your-secure-random-key"
   ```

3. Run the service:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. Run the worker (in a separate terminal):
   ```bash
   python worker.py
   ```

## HTTPS Setup (Production)

For production, use nginx as a reverse proxy with Let's Encrypt:

1. nginx config (`/etc/nginx/sites-available/watermark`):
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. Enable SSL with Let's Encrypt:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

## File Cleanup

To automatically delete old processed files, add a cron job:
 ```bash
   # Delete processed files older than 7 days
   0 */6 * * * find /path/to/processed -mtime +7 -delete
   ```
