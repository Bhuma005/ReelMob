import { fetchApi } from './client';

export const authApi = {
  getStatus: () => fetchApi('/auth/status'),
  getLoginUrl: () => fetchApi('/auth/login'),
  logout: () => fetchApi('/auth/logout'),
};
