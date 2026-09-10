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
6. In **Settings** → **Variables and secrets**, add:
   - `GEMINI_API_KEY`: Your Google AI Studio key
   - `GROQ_API_KEY`: Your Groq key
   - `SUPABASE_URL`: Your Supabase database URL
   - `SUPABASE_SERVICE_KEY`: Your Supabase service key

Your app will be live 24/7 with a permanent HTTPS link:
`https://YOUR_USERNAME-reelsmob.hf.space`
