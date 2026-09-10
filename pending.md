# Pending Tasks & Roadmap

This document serves as the master tracking file for planned features, architecture updates, technical debt, and pending tasks for **ReelGrab**.

---

## 🗺️ Phase Roadmap

### Current Phase: Phase 3 — Intelligent Automation & Cloud Integration (In Progress / Stabilization)
- [x] Instagram Reel & YouTube video metadata extraction and high-speed downloading.
- [x] Multi-model local AI content generation via Ollama (Title, Description, Hashtags, Optimal Scheduling).
- [x] Cloud worker upload system (GitHub Actions + Supabase Database & Storage).
- [x] Automated 2-per-day posting slot enforcement and queueing logic.
- [x] Automated storage cleanup worker (daily retention policy).

### Phase 4: Platform Expansion & Advanced AI (Backlog)
- [ ] **Multi-Platform Support**: Extend automation worker pipeline to support TikTok and Facebook Reels.
- [ ] **AI Thumbnail Generation**: Automated clip thumbnail creation and custom canvas overlay rendering.
- [ ] **Batch URL Processing**: Enable multi-URL paste input queues in frontend UI for batch scheduling.
- [ ] **Advanced Video Analysis**: Add local vision AI integration to analyze video frames for visual context tag generation.

---

## 📋 Categorized Task Checklists

### 🎨 Frontend (`/frontend`)
- [ ] **Batch URL Input Queue**: Allow users to queue up multiple video links at once.
- [ ] **Upload Queue Progress Status**: Display live Supabase upload/scheduling status directly in the web UI.
- [x] **Error Toast Auto-Dismissal**: Add auto-close timers and dismiss buttons for error banners.
- [x] **Offline / Model Health Indicator**: Show Ollama connection status (Active Model / Down indicator) in top status bar.
- [x] **Accessibility (a11y) Polish**: Add explicit `aria-label` attributes to custom CRT toggle controls and action buttons.

### ⚙️ Backend (`/backend`)
- [x] **Asynchronous Download Pipelines**: Replace synchronous `yt-dlp` blocking calls with `asyncio` execution wrappers.
- [ ] **Local Model Fallback Dynamic Warmup**: Pre-warm smaller Ollama fallback models if primary model times out.
- [x] **Custom Rate Limiter Middleware**: Implement standard FastAPI middleware for rate-limiting rather than per-route dictionary lookup.
- [x] **Structured Log Rotator**: Implement Python standard `logging` with file rotation instead of plain `print()` calls.
- [x] **Sanitization Utilities**: Enhanced URL and user input string cleaning for file-system safety across platforms.

### ☁️ Infrastructure & Cloud (`/cloud` & `.github/workflows`)
- [x] **Supabase Table Indexes**: Add composite indexes on `scheduled_videos (upload_status, schedule_time)` for faster worker polling.
- [ ] **GitHub Action Alert Webhooks**: Integrate Discord/Slack webhooks when cloud upload workers encounter persistent OAuth errors.
- [ ] **Webhook Endpoint for Cloud Events**: Add real-time Supabase event trigger webhooks to report worker completion back to local service.
- [x] **Environment Secret Validator Script**: CLI utility to verify local `.env` and GitHub Secrets against required schemas before deployment.

### 📚 Documentation (`/`)
- [x] **API Reference Documentation**: OpenAPI / Swagger inline documentation expansion for all FastAPI routes.
- [ ] **Self-Hosting Guide**: Detailed deployment guide for setup on local home servers or headless Linux instances.
- [ ] **OAuth Setup Walkthrough**: Visual guide detailing Google Cloud OAuth Consent Screen configuration steps.

---

## 🛑 Blockers & Technical Debt

1. **Hardcoded API Key Fallbacks**:
   - `YOUTUBE_API_KEY` hardcoded string in `backend/main.py` presents security/quota technical debt. Should require environment configuration with graceful disabled states.
2. **Synchronous File Operations**:
   - `urllib.request.urlretrieve` and synchronous file I/O operations block FastAPI event loop workers during heavy loads.
3. **Storage Cleanup Dependency**:
   - Auto-deletion relies on external GitHub Actions cron timing (once daily). High influxes of videos can hit temporary Supabase storage caps before scheduled execution.
4. **Single-User OAuth Flow**:
   - Current YouTube OAuth storage in `youtube_auth.py` handles single-tenant refresh token persistence. Multi-user isolation requires database token encryption.
