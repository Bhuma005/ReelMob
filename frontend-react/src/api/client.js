export const API_BASE = ''; // Proxy handles the routing

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
    let errorMsg = 'An error occurred';
    try {
      const errData = await response.json();
      errorMsg = errData.detail || errData.error || errData.message || errorMsg;
    } catch {
      errorMsg = response.statusText;
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
