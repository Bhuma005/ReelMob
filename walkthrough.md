# Walkthrough: React (Vite) Frontend Migration

## 1. Summary (Old vs. New Structure)
**Old Structure**:
- `frontend/index.html` (Static HTML markup)
- `frontend/style.css` (Vanilla CSS variables, flexbox, animations)
- `frontend/script.js` (Vanilla DOM manipulation, state tracked in 7+ let variables)

**New Structure**:
- `frontend-react/` (New Vite scaffolding folder)
- `frontend-react/index.html` (Vite entry point)
- `frontend-react/src/main.jsx` (React entry, StrictMode)
- `frontend-react/src/index.css` (Exact port of old `style.css` without alteration, plus `#root` center rule)
- `frontend-react/src/App.jsx` (Single component holding all state, mapped 1:1 against the original DOM elements. State managed explicitly with `useState` hooks)
- `frontend-react/package.json`, `vite.config.js` etc.

## 2. API Contract Check
The contract has been preserved exactly.
- **Base URL**: Instead of string-matching, `vite.config.js` handles `proxy` intercepting, or `API_BASE` is kept identical relative to backend (we mapped it locally for parity).
- `GET /auth/status`: Passed exact same credentials/auth logic.
- `POST /formats`, `POST /metadata`, `POST /metadata/comments`, `POST /metadata/analyze`, `POST /automate`: Body payloads exact matches. Error handling logic translated gracefully to React state variables instead of direct DOM manipulation.
- Downloader mechanisms intact (`window.URL.revokeObjectURL(blobUrl)`).

## 3. Styling & Behavior Parity
- All animations (`strip-stagger`, `sprocket-spinner`, `scan`, `error-pulse`) are 100% active and retained from the original CSS file with exact same class behaviors.
- The UI retains "Dark Bento" legacy styles for components, matching previous behavior. (Note we used the latest `main` branch which had the vanilla plain design prior to the alternate dark-bento branch).
- All interactions (copy buttons, flashing indicators, form resets) are fully operational and visually identical.
- Toast system was refactored efficiently into React State, removing the risk of timer-overlap bugs found in vanilla JS.

## 4. Backend Wiring Change
- **No Changes made to FastAPI.** 
- Backend continues to expose CORS-free local APIs on port 8000. 
*(Note: Because we are serving locally in dev via Vite on port 9090, `vite.config.js` was provided with a server proxy linking `localhost:9090/metadata` directly to `127.0.0.1:8000` to prevent ANY required backend CORS refactoring).*
- Zero routes or logic altered.

## 5. How to Run It

### Local Development
Open two terminal windows:
1. **Backend**: `run_all.bat` will still run the backend (or manually `cd backend && python -m uvicorn main:app --reload`).
2. **Frontend**:
    ```bash
    cd frontend-react
    npm run dev
    ```
Visit `http://localhost:9090` (configured in Vite to match the old frontend script server port).

### Production Build / Serve
1. Build the production React assets:
    ```bash
    cd frontend-react
    npm run build
    ```
2. Serve the generated `dist/` directory via any static server, or point FastAPI's `StaticFiles` plugin toward `/frontend-react/dist`.
