export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchApi(endpoint, options = {}, retries = 2) {
  const url = `${API_BASE}${endpoint}`;
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
  } catch (netErr) {
    if (retries > 0) {
      await new Promise(r => setTimeout(r, 1200));
      return fetchApi(endpoint, options, retries - 1);
    }
    throw netErr;
  }

  // Auto-retry transient server errors (429 rate limit or 502/504 bad gateway) with backoff
  if ((response.status === 429 || response.status === 502 || response.status === 504) && retries > 0) {
    let delay = 1500;
    if (response.status === 429) {
      const retryAfterHeader = response.headers.get('retry-after');
      const retryAfterSec = parseInt(retryAfterHeader, 10);
      if (!isNaN(retryAfterSec) && retryAfterSec > 0) {
        // Wait retry-after seconds + 250ms buffer, capped at 8s for user interactivity
        delay = Math.min(retryAfterSec * 1000 + 250, 8000);
      } else {
        // Progressive backoff: retries=2 -> 1500ms; retries=1 -> 3000ms
        delay = retries === 2 ? 1500 : 3000;
      }
      console.warn(`[API] 429 received for ${endpoint}. Retrying in ${delay}ms (${retries} attempts left)...`);
    } else {
      delay = 2500;
    }
    await new Promise(r => setTimeout(r, delay));
    return fetchApi(endpoint, options, retries - 1);
  }

  if (!response.ok) {
    let errorMsg = '';
    try {
      const errData = await response.json();
      const extracted = errData.detail || errData.error || errData.message;
      if (typeof extracted === 'string' && extracted.trim()) {
        errorMsg = extracted;
      } else if (Array.isArray(extracted) && extracted.length > 0) {
        errorMsg = extracted.map(e => e.msg || JSON.stringify(e)).join(', ');
      } else if (typeof extracted === 'object' && extracted !== null) {
        errorMsg = extracted.message || JSON.stringify(extracted);
      }
    } catch {
      // Body is not JSON (e.g. HTML from Cloudflare, reverse proxy, or empty)
      errorMsg = response.statusText;
    }

    if (!errorMsg || !errorMsg.trim()) {
      if (response.status === 429) {
        errorMsg = 'Server is currently busy processing requests (429). Please wait a moment and try again.';
      } else if (response.status === 502 || response.status === 504) {
        errorMsg = `Server is temporarily unavailable (${response.status}). Please try again in a few moments.`;
      } else {
        errorMsg = response.statusText || `Server returned error (${response.status})`;
      }
    }
    throw new Error(errorMsg);
  }

  // Not all endpoints return JSON (e.g. downloads)
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    const data = await response.json();
    if (data && typeof data === 'object' && data.status === 'error') {
      throw new Error(data.message || 'Operation failed');
    }
    return data;
  }
  return response;
}
