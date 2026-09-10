import { fetchApi } from './client';

export const dashboardApi = {
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
};
