# ReelMob Production Deployment Guide

This guide details the prerequisites, environment configuration, database migration sequence, and health verification steps for deploying ReelMob to production environments (such as Render, Hugging Face Spaces, or Docker / Kubernetes).

---

## 1. Environment Variables Checklist

Ensure the following environment variables are securely configured in your deployment platform:

### Core Application & Server
| Variable | Required | Description | Example |
|---|---|---|---|
| `PORT` | Yes | Port for the FastAPI server | `7860` or `8000` |
| `ENVIRONMENT` | Yes | Runtime environment | `production` |
| `PUBLIC_BASE_URL` | Yes | Canonical public URL of your service | `https://reelmob.onrender.com` |
| `ALLOWED_HOSTS` | Optional | Comma-separated list of allowed hostnames | `reelmob.onrender.com,api.reelmob.app` |

### Supabase Cloud Database & Storage
| Variable | Required | Description | Example |
|---|---|---|---|
| `SUPABASE_URL` | Yes | Supabase Project REST URL | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | High-privilege service role key (>= 32 chars) | `eyJhbGciOi...` |
| `SUPABASE_KEY` | Optional | Alias for service role key | `eyJhbGciOi...` |

### Cloud AI Optimization Providers
| Variable | Required | Description | Example |
|---|---|---|---|
| `GROQ_API_KEY` | Recommended | Groq API Key for viral metadata synthesis | `gsk_...` |
| `GEMINI_API_KEY` | Recommended | Google Gemini API Key for multimodal video vision | `AIzaSy...` |

### Google / YouTube OAuth
| Variable | Required | Description | Example |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | Yes | OAuth 2.0 Web Client ID | `<id>.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Yes | OAuth 2.0 Client Secret | `GOCSPX-...` |
| `GOOGLE_REDIRECT_URI` | Yes | Authorized Redirect URI | `https://reelmob.onrender.com/auth/callback` |
| `ALLOWED_OAUTH_REDIRECT_URIS` | Optional | Custom authorized redirect URIs | `https://reelmob.app/auth/callback` |

---

## 2. Supabase Migrations Execution Order

Run the following SQL migrations in order within the Supabase SQL Editor:

1. `cloud/001_initial_schema.sql` — Base tables (`video_library`, `scheduled_videos`, `video_activity_log`).
2. `cloud/002_fix_rls.sql` — Row Level Security policies.
3. `cloud/003_storage_bucket.sql` — `reelgrab-videos` bucket and access policies.
4. `cloud/004_production_audit.sql` — Performance indexes for library and queue.
5. `cloud/005_video_edit_metadata.sql` — Aspect ratio and trim editing fields.
6. `cloud/006_video_tags.sql` — Categorization and tag benchmark arrays.
7. `cloud/007_youtube_oauth_tokens.sql` — Persistent OAuth credentials storage.
8. `cloud/008_production_hardening.sql` — Durable `jobs` table, atomic claim columns (`claimed_at`, `lease_expires_at`, `worker_id`), and state machine constraints.

---

## 3. Production Health Check & Verification

After deployment, verify the platform using these health endpoints:

### Liveness & Dependency Probe
```bash
curl -f https://<your-domain>/health
```
Expected output:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "dependencies": {
    "supabase": "connected",
    "ffmpeg": "available",
    "cloud_ai": "configured"
  }
}
```

### Dashboard Statistics
```bash
curl -f https://<your-domain>/api/dashboard/stats
```

### YouTube OAuth Status
```bash
curl -f https://<your-domain>/api/auth/youtube/status
```

---

## 4. Cloud Automation Workflows (GitHub Actions)

Configure the following secrets in GitHub Repository Settings (`Settings -> Secrets and variables -> Actions`):
- `SUPABASE_URL`
- `SUPABASE_KEY` (service role key)
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`

Workflows run automatically:
- **Scheduled Publishing**: Every 15 minutes (`.github/workflows/upload-scheduled.yml`) via `cloud/workflow_upload.py`.
- **Storage Soft-Cleanup**: Daily (`.github/workflows/cleanup-storage.yml`) via `cloud/workflow_cleanup.py`.
- **Headless Video Analysis**: Triggered via repository dispatch when offloaded.
