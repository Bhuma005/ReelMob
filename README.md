---
title: ReelsMob
emoji: 📱
colorFrom: red
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# ReelsMob — AI Video Analysis & YouTube Shorts Publisher

Automated Instagram Reels to YouTube Shorts studio powered by:
- **Google Gemini 3.6 Flash**: Deep video & scene understanding
- **Groq Cloud**: Sub-second viral metadata generation
- **FastAPI & React**: Ultra-fast dashboard

## Deploying to Hugging Face Spaces (100% Free, 24/7, No Credit Card)

1. Create a new Space on [Hugging Face](https://huggingface.co/new-space).
2. Space name: `reelsmob`.
3. License: `MIT`.
4. SDK: Choose **Docker** (Blank).
5. Clone the space or push this repository:
   ```bash
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/reelsmob
   git push space main
   ```
6. In **Settings** → **Variables and secrets**, add each required variable from `.env.example` as a Space **Repository secret** (or Environment variable):
   - `ENVIRONMENT`: `production`
   - `CORS_ORIGINS`: `https://YOUR_USERNAME-reelsmob.hf.space`
   - `PUBLIC_BASE_URL`: `https://YOUR_USERNAME-reelsmob.hf.space`
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY`: Your Supabase API key
   - `GROQ_API_KEY`: Your Groq Cloud API key
   - `GEMINI_API_KEY`: Your Google Gemini API key

> **Security Note**: Never commit or copy a `.env` file into the repository or container image. Secrets must always be injected at runtime via Hugging Face Space Secrets or container environment variables. `.dockerignore` prevents any local `.env` files from entering the Docker build context.

Your app will be live 24/7 with a permanent HTTPS link:
`https://YOUR_USERNAME-reelsmob.hf.space`
