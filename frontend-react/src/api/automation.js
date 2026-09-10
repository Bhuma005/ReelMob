import { fetchApi } from './client';

export const automationApi = {
  triggerAutomation: (payload) => fetchApi('/automate', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
};
