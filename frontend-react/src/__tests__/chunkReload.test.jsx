import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { 
  isStaleChunkError, 
  handleStaleChunkReload, 
  clearStaleChunkReloadMarker,
  CHUNK_RELOAD_STORAGE_KEY,
  CHUNK_RELOAD_COOLDOWN_MS
} from '../utils/chunkReload';
import { isVersionOutdated } from '../components/VersionUpdateBanner';
import { ErrorBoundary } from '../components/ErrorBoundary';

describe('Stale Chunk Recovery Utilities', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  describe('isStaleChunkError', () => {
    it('identifies Vite dynamic import fetch failure', () => {
      const err = new TypeError('Failed to fetch dynamically imported module: http://localhost:9090/assets/DashboardPage-xyz.js');
      expect(isStaleChunkError(err)).toBe(true);
    });

    it('identifies Safari module script failure', () => {
      const err = new TypeError('Importing a module script failed.');
      expect(isStaleChunkError(err)).toBe(true);
    });

    it('identifies Firefox dynamic module error', () => {
      const err = new Error('error loading dynamically imported module');
      expect(isStaleChunkError(err)).toBe(true);
    });

    it('identifies Vite CSS preload failure', () => {
      const err = new Error('Unable to preload CSS: /assets/index-123.css');
      expect(isStaleChunkError(err)).toBe(true);
    });

    it('identifies standard ChunkLoadError', () => {
      const err = new Error('Loading chunk 456 failed');
      err.name = 'ChunkLoadError';
      expect(isStaleChunkError(err)).toBe(true);
    });

    it('ignores regular application runtime errors', () => {
      expect(isStaleChunkError(new Error('Cannot read properties of null (reading "map")'))).toBe(false);
      expect(isStaleChunkError(new Error('Network request failed: 500 Internal Server Error'))).toBe(false);
      expect(isStaleChunkError(null)).toBe(false);
    });
  });

  describe('handleStaleChunkReload and Infinite Loop Guard', () => {
    it('triggers window.location.reload on first occurrence and sets session marker', () => {
      const reloadMock = vi.fn();
      Object.defineProperty(window, 'location', {
        value: { reload: reloadMock },
        writable: true,
      });

      const err = new Error('Failed to fetch dynamically imported module');
      const result = handleStaleChunkReload(err);

      expect(result).toBe(true);
      expect(reloadMock).toHaveBeenCalledTimes(1);
      expect(sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY)).toBeTruthy();
    });

    it('blocks subsequent reload within cooldown window to prevent infinite reload loop', () => {
      const reloadMock = vi.fn();
      Object.defineProperty(window, 'location', {
        value: { reload: reloadMock },
        writable: true,
      });

      // Simulate a reload that occurred 2 seconds ago
      sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(Date.now() - 2000));

      const err = new Error('Failed to fetch dynamically imported module');
      const result = handleStaleChunkReload(err);

      expect(result).toBe(false);
      expect(reloadMock).not.toHaveBeenCalled();
    });

    it('permits reload again once cooldown period expires', () => {
      const reloadMock = vi.fn();
      Object.defineProperty(window, 'location', {
        value: { reload: reloadMock },
        writable: true,
      });

      // Simulate a reload that occurred beyond the cooldown window
      sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(Date.now() - (CHUNK_RELOAD_COOLDOWN_MS + 5000)));

      const err = new Error('Failed to fetch dynamically imported module');
      const result = handleStaleChunkReload(err);

      expect(result).toBe(true);
      expect(reloadMock).toHaveBeenCalledTimes(1);
    });

    it('clears storage marker when clearStaleChunkReloadMarker is called', () => {
      sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, '123456789');
      clearStaleChunkReloadMarker();
      expect(sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY)).toBeNull();
    });
  });

  describe('Version Mismatch Detection', () => {
    it('correctly compares local vs remote versions', () => {
      expect(isVersionOutdated('100', '100')).toBe(false);
      expect(isVersionOutdated('100', '200')).toBe(true);
      expect(isVersionOutdated('dev', '200')).toBe(false);
      expect(isVersionOutdated('100', 'dev')).toBe(false);
      expect(isVersionOutdated(null, '200')).toBe(false);
      expect(isVersionOutdated('100', null)).toBe(false);
    });
  });

  describe('ErrorBoundary Component with Stale Chunk Handling', () => {
    it('renders user-friendly recovery UI if reload was already attempted', () => {
      // Simulate reload already tried
      sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(Date.now() - 1000));

      const ThrowingComponent = () => {
        throw new Error('Failed to fetch dynamically imported module');
      };

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      expect(screen.getByText('New Version Available')).toBeDefined();
      expect(screen.getByText(/Your browser had an older cached session/i)).toBeDefined();
      expect(screen.getByRole('button', { name: /Reload Latest Version/i })).toBeDefined();
    });

    it('manual reload button clears session marker and reloads page', () => {
      sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(Date.now() - 1000));
      const reloadMock = vi.fn();
      Object.defineProperty(window, 'location', {
        value: { reload: reloadMock },
        writable: true,
      });

      const ThrowingComponent = () => {
        throw new Error('Failed to fetch dynamically imported module');
      };

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      const reloadBtn = screen.getByRole('button', { name: /Reload Latest Version/i });
      fireEvent.click(reloadBtn);

      expect(sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY)).toBeNull();
      expect(reloadMock).toHaveBeenCalledTimes(1);
    });
  });
});
