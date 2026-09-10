import { API_BASE } from './client';

export const videosApi = {
  downloadVideo: async (url, format_id) => {
    const res = await fetch(`${API_BASE}/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, format_id })
    });
    if (!res.ok) throw new Error("Download failed");
    return res;
  },
  downloadThumbnail: async (url) => {
    const res = await fetch(`${API_BASE}/download-thumbnail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!res.ok) throw new Error("Thumbnail download failed");
    return res;
  },
  // Handles the actual browser download action
  handleFileDownload: (response) => {
    const disposition = response.headers.get('content-disposition');
    let filename = 'download';
    if (disposition && disposition.indexOf('filename=') !== -1) {
      const matches = /filename="([^"]+)"/.exec(disposition);
      if (matches != null && matches[1]) filename = matches[1];
      else filename = disposition.split('filename=')[1];
    }
    response.blob().then(blob => {
      const a = document.createElement('a');
      const blobUrl = window.URL.createObjectURL(blob);
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      a.remove();
    });
  }
};
