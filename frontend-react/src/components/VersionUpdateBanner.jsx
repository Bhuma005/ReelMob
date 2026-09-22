import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw, X } from 'lucide-react';

// Build version injected at compile-time by Vite define
export const APP_CURRENT_VERSION = typeof __APP_BUILD_VERSION__ !== 'undefined' 
  ? __APP_BUILD_VERSION__ 
  : 'dev';

/**
 * Pure helper to determine whether fetched remote version indicates a newer build.
 */
export function isVersionOutdated(localVersion, remoteVersion) {
  if (!remoteVersion || !localVersion) return false;
  if (localVersion === 'dev' || remoteVersion === 'dev') return false;
  return String(remoteVersion).trim() !== String(localVersion).trim();
}

export function VersionUpdateBanner() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const checkVersion = async () => {
      try {
        const response = await fetch(`/version.json?t=${Date.now()}`, {
          cache: 'no-store',
          headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
          },
        });

        if (!response.ok) return;

        const data = await response.json();
        if (isMounted && data?.version && isVersionOutdated(APP_CURRENT_VERSION, data.version)) {
          console.info(`[VersionCheck] New build detected: ${data.version} (current: ${APP_CURRENT_VERSION})`);
          setUpdateAvailable(true);
        }
      } catch (err) {
        // Silent failure — network check should never break UX
        console.debug('[VersionCheck] Background version poll failed:', err);
      }
    };

    // 1. Initial check after app has stabilized (10s delay)
    const initialTimer = setTimeout(checkVersion, 10000);

    // 2. Periodic poll every 4 minutes
    const interval = setInterval(checkVersion, 4 * 60 * 1000);

    // 3. Proactive check when window regains visibility/focus after backgrounding
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkVersion();
      }
    };

    window.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', checkVersion);

    return () => {
      isMounted = false;
      clearTimeout(initialTimer);
      clearInterval(interval);
      window.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', checkVersion);
    };
  }, []);

  if (!updateAvailable || dismissed) return null;

  return (
    <div 
      role="alert"
      className="fixed bottom-4 right-4 z-50 max-w-sm w-full bg-surface border border-accent/40 rounded-xl p-3.5 shadow-2xl backdrop-blur-md animate-in slide-in-from-bottom-5 duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/20 flex items-center justify-center text-accent shrink-0 mt-0.5">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-xs font-bold text-text">New Version Available</h4>
          <p className="text-[11px] text-text-muted mt-0.5 leading-relaxed">
            A new update has been deployed. Refresh to load the latest features and fixes.
          </p>
          <div className="mt-2.5 flex items-center gap-2">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-accent text-accent-foreground text-xs font-semibold hover:bg-accent/90 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Refresh to update</span>
            </button>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="px-2 py-1 rounded-md text-xs text-text-muted hover:text-text hover:bg-surface-elevated transition-colors cursor-pointer"
            >
              Later
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="text-text-muted hover:text-text p-1 rounded-md hover:bg-surface-elevated transition-colors cursor-pointer"
          aria-label="Dismiss update alert"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
