/**
 * chunkReload.js
 * Utility to detect Vite stale chunk / dynamic import errors after deploys
 * and trigger an automatic, guarded one-time reload to fetch new bundles.
 */

export const CHUNK_RELOAD_STORAGE_KEY = 'reelsmob_chunk_reload_ts';
export const CHUNK_RELOAD_COOLDOWN_MS = 15000; // 15 seconds cooldown

/**
 * Checks if an error is a dynamic import or chunk loading failure caused by
 * newly-deployed assets replacing old hashed bundles.
 */
export function isStaleChunkError(error) {
  if (!error) return false;
  const message = (error.message || String(error) || '').toLowerCase();
  const name = (error.name || '').toLowerCase();

  return (
    name === 'chunkloaderror' ||
    message.includes('failed to fetch dynamically imported module') ||
    message.includes('importing a module script failed') ||
    message.includes('error loading dynamically imported module') ||
    message.includes('unable to preload css') ||
    message.includes('loading chunk') ||
    message.includes('loading css chunk') ||
    message.includes('dynamically imported') ||
    message.includes('vite:preloader')
  );
}

/**
 * Triggers a guarded one-time window.location.reload() if a stale chunk error is detected.
 * Returns true if an automatic reload was initiated, false if already attempted or not a chunk error.
 */
export function handleStaleChunkReload(error) {
  if (!isStaleChunkError(error)) return false;

  try {
    const lastReloadStr = sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY);
    const now = Date.now();

    if (lastReloadStr) {
      const lastReload = parseInt(lastReloadStr, 10);
      if (!isNaN(lastReload) && now - lastReload < CHUNK_RELOAD_COOLDOWN_MS) {
        console.warn('[StaleChunk] Already attempted automatic reload within cooldown. Showing error screen.');
        return false;
      }
    }

    console.info('[StaleChunk] Detected stale chunk error after deployment. Triggering one-time automatic reload...');
    sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(now));
    window.location.reload();
    return true;
  } catch (err) {
    console.error('[StaleChunk] Failed to access sessionStorage:', err);
    window.location.reload();
    return true;
  }
}

/**
 * Resets the reload attempt marker once the application has loaded and stabilized.
 */
export function clearStaleChunkReloadMarker() {
  try {
    sessionStorage.removeItem(CHUNK_RELOAD_STORAGE_KEY);
  } catch {
    // Ignore storage exceptions
  }
}
