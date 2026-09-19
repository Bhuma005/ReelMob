import { fetchApi } from './client';

export const authApi = {
  getStatus: (redirectUri) => fetchApi(`/auth/status${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ''}`),
  getLoginUrl: (redirectUri) => fetchApi(`/auth/login${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ''}`),
  logout: () => fetchApi('/auth/logout'),
};
