# ── STAGE 1: Build React Frontend ─────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend-react
COPY frontend-react/package*.json ./
RUN npm install
COPY frontend-react/ ./
RUN npm run build

# ── STAGE 2: Python Backend Runtime ──────────────────────────────────
FROM python:3.11-slim

# Install system dependencies (ffmpeg is essential for video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR $HOME/app

# Copy Python requirements & install
COPY --chown=user:user backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt && \
    pip install --no-cache-dir requests python-dotenv supabase google-api-python-client google-auth-oauthlib

# Copy built frontend from Stage 1
COPY --chown=user:user --from=frontend-builder /app/frontend-react/dist ./frontend-react/dist

# Copy backend and cloud source code
COPY --chown=user:user backend/ ./backend/
COPY --chown=user:user cloud/ ./cloud/

# Create downloads folder with write permissions
RUN mkdir -p downloads && chmod 777 downloads

# Expose standard Hugging Face Spaces port
EXPOSE 7860

# Launch FastAPI
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}
