import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { handleStaleChunkReload } from './utils/chunkReload'

// Auto-recover from stale chunks on deploy when Vite fires preloadError
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault();
  handleStaleChunkReload(event.payload || new Error('vite:preloadError'));
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Register PWA Service Worker
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.debug('ServiceWorker registration skipped:', err);
    });
  });
}
