import { API_BASE, fetchApi } from './client';

export const dashboardApi = {
  exportAnalytics: async (format = 'csv', days = 30) => {
    const res = await fetch(`${API_BASE}/api/dashboard/analytics/export?format=${format}&days=${days}`);
    if (!res.ok) throw new Error(`Analytics export failed: ${res.statusText}`);
    return res;
  },
  getStats: () => fetchApi('/api/dashboard/stats'),
  getVideos: (params = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.limit) query.append('limit', params.limit);
    if (params.status && params.status !== 'all') query.append('status', params.status);
    if (params.search) query.append('search', params.search);
    const qs = query.toString();
    return fetchApi(`/api/dashboard/videos${qs ? `?${qs}` : ''}`);
  },
  getLogs: () => fetchApi('/api/dashboard/logs'),
  getRecommendation: () => fetchApi('/api/scheduling/recommendation'),
  deleteVideo: (id) => fetchApi(`/api/dashboard/videos/${id}`, { method: 'DELETE' }),
  convertVideo: (id, ratio) => fetchApi(`/api/dashboard/videos/${id}/convert`, {
    method: 'POST',
    body: JSON.stringify({ ratio })
  }),
  publishVideo: (id) => fetchApi(`/api/dashboard/videos/${id}/publish`, { method: 'POST' }),
  getTrends: (days = 30) => fetchApi(`/api/dashboard/analytics/trends?days=${days}`),
  updateVideoTags: (id, tags) => fetchApi(`/api/dashboard/videos/${id}/tags`, {
    method: 'PATCH',
    body: JSON.stringify({ tags })
  }),
  getTagAnalytics: (days = 30) => fetchApi(`/api/dashboard/analytics/tags?days=${days}`),
  searchVideos: (q) => fetchApi(`/api/dashboard/search?q=${encodeURIComponent(q)}`),
};
