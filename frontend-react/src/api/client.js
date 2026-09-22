export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchApi(endpoint, options = {}, retries = 1) {
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

  // Auto-retry transient 429 (Too Many Requests) once with backoff
  if (response.status === 429 && retries > 0) {
    await new Promise(r => setTimeout(r, 1800));
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
      errorMsg = response.statusText;
    }

    if (!errorMsg || !errorMsg.trim()) {
      if (response.status === 429) {
        errorMsg = 'Server is receiving too many requests (429). Please wait a few seconds and try again.';
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
    return await response.json();
  }
  return response;
}
