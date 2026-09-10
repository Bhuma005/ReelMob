import { fetchApi } from './client';

export const metadataApi = {
  getFormats: (url) => fetchApi('/formats', {
    method: 'POST',
    body: JSON.stringify({ url })
  }),
  getMetadata: (url) => fetchApi('/metadata', {
    method: 'POST',
    body: JSON.stringify({ url })
  }),
  getComments: (url) => fetchApi('/metadata/comments', {
    method: 'POST',
    body: JSON.stringify({ url })
  }),
  analyze: (title, description, url) => fetchApi('/metadata/analyze', {
    method: 'POST',
    body: JSON.stringify({ title, description, url })
  }),
  getAnalysisStatus: (jobId) => fetchApi(`/api/analyze/status/${jobId}`),
  cancelAnalysis: (jobId) => fetchApi(`/api/analyze/cancel/${jobId}`, {
    method: 'POST'
  }),
};
