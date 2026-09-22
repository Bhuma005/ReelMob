export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

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
      errorMsg = response.statusText || `Server returned error (${response.status})`;
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
