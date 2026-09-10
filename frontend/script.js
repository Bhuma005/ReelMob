const API_BASE = 'http://127.0.0.1:8000';

const ui = {
  inputSection: document.getElementById('input-section'),
  urlInput: document.getElementById('url-input'),
  fetchBtn: document.getElementById('fetch-btn'),
  loadingState: document.getElementById('loading-state'),
  errorPanel: document.getElementById('error-panel'),
  errorMsg: document.getElementById('error-message'),
  resultsContent: document.getElementById('results-content'),

  previewCard: document.getElementById('preview-card'),
  thumbnailImg: document.getElementById('thumbnail-img'),
  downloadBestBtn: document.getElementById('download-best-btn'),
  downloadThumbBtn: document.getElementById('download-thumb-btn'),

  captionCard: document.getElementById('caption-card'),
  captionText: document.getElementById('caption-text'),
  hashtagChips: document.getElementById('hashtag-chips'),
  copyCaptionBtn: document.getElementById('copy-caption-btn'),
  copyHashtagsBtn: document.getElementById('copy-hashtags-btn'),

  aiTagsHeader: document.getElementById('ai-tags-header'),
  aiTagsContainer: document.getElementById('ai-tags-container'),
  ytChips: document.getElementById('yt-chips'),
  igChips: document.getElementById('ig-chips'),
  copyAiBtn: document.getElementById('copy-ai-btn'),

  aiInsightBox: document.getElementById('ai-insight-box'),
  aiInsightText: document.getElementById('ai-insight-text'),

  // AI Generated Content card
  aiGenCard: document.getElementById('ai-gen-card'),
  aiViralTitle: document.getElementById('ai-viral-title'),
  aiOptDesc: document.getElementById('ai-opt-desc'),
  aiViralAnalysis: document.getElementById('ai-viral-analysis'),
  aiModelBadge: document.getElementById('ai-model-badge'),
  aiScheduleBadge: document.getElementById('ai-schedule-badge'),
  aiScheduleTime: document.getElementById('ai-schedule-time'),
  aiConfidenceNote: document.getElementById('ai-confidence-note'),

  formatsCard: document.getElementById('formats-card'),
  videoTitle: document.getElementById('video-title'),
  formatList: document.getElementById('format-list'),

  analyticsCard: document.getElementById('analytics-card'),
  engScore: document.getElementById('eng-score'),
  viralScore: document.getElementById('viral-score'),
  statCounts: document.getElementById('stat-counts'),

  automationCard: document.getElementById('automation-card'),
  automateBtn: document.getElementById('automate-btn'),
  autoLoader: document.getElementById('auto-loader'),
  autoResultBox: document.getElementById('automation-result-box'),
  autoTitle: document.getElementById('auto-title'),
  autoDesc: document.getElementById('auto-desc'),
  autoTime: document.getElementById('auto-time'),
  autoReason: document.getElementById('auto-reason'),

  ytAuthBanner: document.getElementById('yt-auth-banner'),
  ytAuthStatus: document.getElementById('yt-auth-status'),
  ytLoginBtn: document.getElementById('yt-login-btn'),
  opusClipToggle: document.getElementById('opus-clip-toggle'),

  resetBtn: document.getElementById('reset-btn'),
  toast: document.getElementById('toast'),
};

let currentUrl = '';
let bestFormatId = '';
let formatListItems = [];
let allHashtags = [];
let aiTagsList = [];
let currentMetadata = null;
let ollamaAnalysis = '';        // AI-generated description for YouTube upload
let ollamaScheduledTime = '';   // AI-recommended schedule time
let isYtAuthenticated = false;

// Check auth status on load
fetch(`${API_BASE}/auth/status`).then(r => r.json()).then(status => {
  if (status.is_authenticated) {
    isYtAuthenticated = true;
    ui.ytAuthStatus.textContent = status.channel_name || "Ready to Post";
    ui.ytAuthStatus.style.color = "#4CAF50";
    ui.ytLoginBtn.textContent = "Connected";
    ui.ytLoginBtn.disabled = true;
    ui.ytLoginBtn.style.background = "#333";
  }
}).catch(console.error);

ui.fetchBtn.addEventListener('click', handleFetch);
ui.urlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleFetch();
});

ui.resetBtn.addEventListener('click', () => {
  ui.urlInput.value = '';
  ui.urlInput.focus();
  ui.resultsContent.classList.add('hidden');
  ui.captionCard.classList.add('hidden');
  ui.previewCard.classList.add('hidden');
  ui.errorPanel.classList.add('hidden');
  ui.formatList.innerHTML = '';
  ui.hashtagChips.innerHTML = '';

  ui.aiTagsHeader.style.display = 'none';
  ui.aiTagsContainer.style.display = 'none';
  ui.ytChips.innerHTML = '';
  ui.igChips.innerHTML = '';

  ui.aiInsightBox.style.display = 'none';
  ui.aiInsightText.textContent = '';

  // Reset AI gen card
  ui.aiGenCard.classList.add('hidden');
  ui.aiViralTitle.textContent = '—';
  ui.aiOptDesc.textContent = '—';
  ui.aiViralAnalysis.textContent = '';

  ui.automationCard.classList.add('hidden');
  ui.autoResultBox.style.display = 'none';

  allHashtags = [];
  aiTagsList = [];
  currentMetadata = null;
  ollamaAnalysis = '';
});

ui.downloadBestBtn.addEventListener('click', () => {
  flashButton(ui.downloadBestBtn);
  downloadVideo(bestFormatId);
});

ui.downloadThumbBtn.addEventListener('click', () => {
  flashButton(ui.downloadThumbBtn);
  downloadThumbnail();
});

ui.copyCaptionBtn.addEventListener('click', () => {
  copyToClipboard(ui.captionText.textContent, ui.copyCaptionBtn);
});

ui.copyHashtagsBtn.addEventListener('click', () => {
  const text = allHashtags.map(t => (t.startsWith('#') ? t : '#' + t)).join(' ');
  copyToClipboard(text, ui.copyHashtagsBtn);
});

ui.copyAiBtn.addEventListener('click', () => {
  const text = aiTagsList.map(t => (t.startsWith('#') ? t : '#' + t)).join(' ');
  copyToClipboard(text, ui.copyAiBtn);
});

ui.ytLoginBtn.addEventListener('click', () => {
  if (isYtAuthenticated) {
    // Disconnect / Logout
    fetch(`${API_BASE}/auth/logout`).then(() => {
      isYtAuthenticated = false;
      ui.ytAuthStatus.textContent = 'Not connected';
      ui.ytAuthStatus.style.color = '';
      ui.ytLoginBtn.textContent = 'Connect';
      ui.ytLoginBtn.disabled = false;
      ui.ytLoginBtn.style.background = '#E0115F';
    });
    return;
  }

  ui.ytLoginBtn.textContent = 'Connecting...';
  ui.ytLoginBtn.disabled = true;

  fetch(`${API_BASE}/auth/login`).then(r => r.json()).then(res => {
    if (res.error) {
      showError('⚠️ ' + res.error);
      ui.ytLoginBtn.textContent = 'Connect';
      ui.ytLoginBtn.disabled = false;
    } else if (res.auth_url) {
      window.open(res.auth_url, '_blank');
      showToast('Login window opened — please grant access');
      // Poll every 3 seconds until authenticated
      const poll = setInterval(() => {
        fetch(`${API_BASE}/auth/status`).then(r => r.json()).then(s => {
          if (s.is_authenticated) {
            clearInterval(poll);
            isYtAuthenticated = true;
            ui.ytAuthStatus.textContent = '✅ ' + (s.channel_name || 'Connected');
            ui.ytAuthStatus.style.color = '#4CAF50';
            ui.ytLoginBtn.textContent = 'Disconnect';
            ui.ytLoginBtn.disabled = false;
            ui.ytLoginBtn.style.background = '#333';
            showToast('YouTube channel connected!');
          }
        });
      }, 3000);
    }
  }).catch(() => {
    showError('Failed to start login. Is the backend running?');
    ui.ytLoginBtn.textContent = 'Connect';
    ui.ytLoginBtn.disabled = false;
  });
});

ui.automateBtn.addEventListener('click', () => {
  if (!isYtAuthenticated) {
    showError("Please connect your YouTube channel first!");
    return;
  }
  flashButton(ui.automateBtn);
  triggerAutomation();
});

function flashButton(btn) {
  btn.classList.add('flash');
  setTimeout(() => btn.classList.remove('flash'), 300);
}

function showError(msg) {
  ui.errorMsg.textContent = msg;
  ui.errorPanel.classList.remove('hidden');
  ui.loadingState.classList.add('hidden');

  // re-trigger animation
  ui.errorPanel.style.animation = 'none';
  ui.errorPanel.offsetHeight; /* trigger reflow */
  ui.errorPanel.style.animation = null;
}

async function handleFetch() {
  const url = ui.urlInput.value.trim();
  if (!url) return;
  currentUrl = url;

  ui.errorPanel.classList.add('hidden');
  ui.resultsContent.classList.add('hidden');
  ui.captionCard.classList.add('hidden');
  ui.previewCard.classList.add('hidden');
  ui.loadingState.classList.remove('hidden');

  ui.fetchBtn.disabled = true;
  ui.urlInput.disabled = true;
  allHashtags = [];

  // Fire all three in parallel
  const pFormats = fetch(`${API_BASE}/formats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  }).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)));

  const pMetadata = fetch(`${API_BASE}/metadata`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  }).then(r => r.ok ? r.json() : {});

  const pComments = fetch(`${API_BASE}/metadata/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  }).then(r => r.ok ? r.json() : {});

  // Handle Metadata early rendering
  pMetadata.then(meta => {
    if (!meta) return;
    currentMetadata = meta;
    ui.videoTitle.textContent = meta.title ? meta.title.toUpperCase() : "VIDEO details";

    if (meta.description_clean || (meta.hashtags && meta.hashtags.length > 0)) {
      ui.captionText.textContent = meta.description_clean || '';
      ui.hashtagChips.innerHTML = '';
      if (meta.hashtags) {
        renderHashtags(meta.hashtags);
      }
      ui.captionCard.classList.remove('hidden');
    }

    if (meta.thumbnail_url) {
      ui.thumbnailImg.src = meta.thumbnail_url;
      ui.previewCard.classList.remove('hidden');
      ui.downloadThumbBtn.classList.remove('hidden');
    } else {
      ui.thumbnailImg.src = "";
      ui.downloadThumbBtn.classList.add('hidden');
    }

    if (meta.view_count || meta.like_count) {
      const likes = meta.like_count || 0;
      const comments = meta.comment_count || 0;
      const views = meta.view_count || (likes * 12); // Fallback: assume 8% engagement if views are hidden (Instagram)

      const formatNum = (num) => num > 1000000 ? (num / 1000000).toFixed(1) + 'M' : num > 1000 ? (num / 1000).toFixed(1) + 'K' : num;

      ui.statCounts.textContent = `${meta.view_count ? formatNum(views) : 'Hidden'} / ${formatNum(likes)}`;

      const engRate = ((likes + comments) / views) * 100;
      ui.engScore.textContent = engRate.toFixed(2) + '%';

      // Basic heuristic: >10% engagement is very high, 1M+ views pushes score up. Limit 0-100.
      let vScore = (engRate * 5) + Math.min((views / 100000), 50);
      vScore = Math.min(Math.max(vScore, 1), 100).toFixed(0);
      ui.viralScore.textContent = vScore + '/100';

      ui.analyticsCard.classList.remove('hidden');
    } else {
      // Even if view/like counts are hidden (Instagram), still show the analytics card
      ui.statCounts.textContent = 'Hidden / Hidden';
      ui.engScore.textContent = 'N/A';
      ui.viralScore.textContent = 'N/A';
      ui.analyticsCard.classList.remove('hidden');
    }

    if (meta.title || meta.description) {
      ui.automationCard.classList.remove('hidden');

      fetch(`${API_BASE}/metadata/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: meta.title, description: meta.description })
      })
        .then(r => r.ok ? r.json() : null)
        .then(analysis => {
          if (analysis) {
            const viralTitle = (analysis.viral_title || '').trim();
            const optDesc = (analysis.optimized_description || '').trim();
            const aiAnalysis = (analysis.analysis || '').trim();
            const schedTime = (analysis.scheduled_time || '').trim();
            const confNote = (analysis.confidence_notes || '').trim();

            if (viralTitle || optDesc) {
              ui.aiGenCard.classList.remove('hidden');
              ui.aiViralTitle.textContent = viralTitle || '—';
              ui.aiOptDesc.textContent = optDesc || '—';
              ui.aiViralAnalysis.textContent = aiAnalysis ? `💡 ${aiAnalysis}` : '';

              // Schedule time badge
              if (schedTime) {
                ollamaScheduledTime = schedTime;
                ui.aiScheduleTime.textContent = `Best time to post: ${schedTime}`;
                ui.aiScheduleBadge.style.display = 'inline-flex';
              }

              // Confidence / model notes
              if (confNote) {
                ui.aiConfidenceNote.textContent = confNote;
              }

              // Update model badge from confidence_notes (e.g. "Generated by qwen2.5:3b.")
              const modelMatch = confNote.match(/Generated by ([^\s.]+)/i);
              if (modelMatch) {
                ui.aiModelBadge.textContent = `⚡ ${modelMatch[1]}`;
              }
            }

            // Store for YouTube upload
            if (optDesc) ollamaAnalysis = optDesc;

            // Populate AI hashtag chips
            const allTags = [...(analysis.youtube || []), ...(analysis.instagram || [])];
            if (allTags.length > 0) {
              ui.aiTagsHeader.style.display = 'flex';
              ui.aiTagsContainer.style.display = 'flex';
              (analysis.youtube || []).forEach(tag => {
                aiTagsList.push(tag);
                const span = document.createElement('span');
                span.className = 'chip';
                span.textContent = tag;
                span.onclick = () => copyToClipboard(tag, span);
                ui.ytChips.appendChild(span);
              });
              (analysis.instagram || []).forEach(tag => {
                aiTagsList.push(tag);
                const span = document.createElement('span');
                span.className = 'chip';
                span.textContent = tag;
                span.onclick = () => copyToClipboard(tag, span);
                ui.igChips.appendChild(span);
              });
            }

            // Legacy insight box
            if (aiAnalysis) {
              ui.analyticsCard.classList.remove('hidden');
              ui.aiInsightBox.style.display = 'block';
              ui.aiInsightText.textContent = `"${aiAnalysis}"`;
            }
          }
        })
        .catch(e => console.error("Analyze error:", e));

    }
  }).catch(console.error);

  // Handle Comments early rendering
  pComments.then(comm => {
    if (comm && comm.available && comm.hashtags && comm.hashtags.length > 0) {
      renderHashtags(comm.hashtags);
    }
  }).catch(console.error);

  // Main Formats resolve
  try {
    const formats = await pFormats;
    ui.loadingState.classList.add('hidden');
    ui.resultsContent.classList.remove('hidden');

    renderFormats(formats);
  } catch (err) {
    showError(err.detail || 'Failed to fetch video formats');
  } finally {
    ui.fetchBtn.disabled = false;
    ui.urlInput.disabled = false;
    // ensure main content container is always shown if any child is
    if (!ui.previewCard.classList.contains('hidden') || !ui.captionCard.classList.contains('hidden')) {
      ui.resultsContent.classList.remove('hidden');
      if (ui.loadingState.classList.contains('hidden') === false && !ui.errorPanel.classList.contains('hidden')) {
        ui.formatsCard.classList.add('hidden'); // if formats failed but metadata succeeded
      }
    }
  }
}

function renderHashtags(tags) {
  tags.forEach(tag => {
    if (!allHashtags.includes(tag)) {
      allHashtags.push(tag);
      const span = document.createElement('span');
      span.className = 'chip';
      span.textContent = tag;
      span.onclick = () => copyToClipboard(tag, span);
      ui.hashtagChips.appendChild(span);
    }
  });
}

function renderFormats(formats) {
  ui.formatList.innerHTML = '';
  if (!formats || formats.length === 0) return;

  // Determine max file size for VU meter
  let maxSize = 0;
  formats.forEach(f => {
    if (f.filesize && f.filesize > maxSize) maxSize = f.filesize;
  });

  formats.forEach((f, idx) => {
    const isBest = idx === 0;
    if (isBest) bestFormatId = f.format_id;

    const sizeMb = f.filesize ? (f.filesize / 1024 / 1024).toFixed(1) + ' MB' : '??? MB';
    const vuWidth = f.filesize && maxSize > 0 ? Math.max((f.filesize / maxSize) * 100, 5) : 5;

    const row = document.createElement('div');
    row.className = 'channel-strip';
    row.innerHTML = `
            <div class="cs-left">
                <span class="cs-badge ${isBest ? 'best' : ''}">${isBest ? 'BEST' : f.ext.toUpperCase()}</span>
            </div>
            <div class="cs-middle">
                <span class="cs-resolution">${f.resolution}</span>
                <span class="cs-codec">Codec: ${f.format_note || f.ext}</span>
            </div>
            <div class="cs-right">
                <span class="cs-size">${sizeMb}</span>
                <div class="cs-vu-meter" style="width: ${vuWidth}%"></div>
            </div>
        `;

    // Animation stagger logic (cap at 6)
    const delay = Math.min(idx * 40, 6 * 40);
    row.style.animation = `strip-stagger 0.3s ease-out ${delay}ms both`;

    row.onclick = () => {
      flashButton(row);
      downloadVideo(f.format_id);
    };

    ui.formatList.appendChild(row);
  });
}

function downloadVideo(formatId) {
  fetch(`${API_BASE}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: currentUrl, format_id: formatId })
  })
    .then(r => {
      if (!r.ok) throw new Error("Download failed on server");
      handleFileDownload(r);
    })
    .catch(err => {
      showToast("Error starting download");
      console.error(err);
    });
}

function downloadThumbnail() {
  fetch(`${API_BASE}/download-thumbnail`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: currentUrl })
  })
    .then(r => {
      if (!r.ok) throw new Error("Thumbnail download failed");
      handleFileDownload(r);
    })
    .catch(err => {
      showToast("Error downloading thumbnail");
      console.error(err);
    });
}

function handleFileDownload(response) {
  const disposition = response.headers.get('content-disposition');
  let filename = 'download';
  if (disposition && disposition.indexOf('filename=') !== -1) {
    const matches = /filename="([^"]+)"/.exec(disposition);
    if (matches != null && matches[1]) filename = matches[1];
    else filename = disposition.split('filename=')[1];
  }

  response.blob().then(blob => {
    const a = document.createElement('a');
    const url = window.URL.createObjectURL(blob);
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  });
}

function copyToClipboard(text, el) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => showToast())
      .catch(err => fallbackCopyTextToClipboard(text));
  } else {
    fallbackCopyTextToClipboard(text);
  }
}

function fallbackCopyTextToClipboard(text) {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.position = "fixed";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  try {
    document.execCommand('copy');
    showToast();
  } catch (err) {
    console.error('Fallback: Oops, unable to copy', err);
  }
  document.body.removeChild(textArea);
}

let toastTimer;
function showToast(msg = "Copied") {
  clearTimeout(toastTimer);
  ui.toast.textContent = msg;
  ui.toast.classList.add('show');
  toastTimer = setTimeout(() => {
    ui.toast.classList.remove('show');
  }, 2000);
}

function triggerAutomation() {
  if (!currentMetadata) {
    showError("No metadata available to automate.");
    return;
  }

  ui.automateBtn.disabled = true;
  ui.autoLoader.classList.remove('hidden');
  ui.autoResultBox.style.display = 'none';

  // Set real-time progress indicator text
  const btnText = ui.automateBtn.querySelector('span');
  btnText.textContent = '⏱ Downloading & Syncing to Cloud...';

  const payload = {
    title: currentMetadata.title || 'Untitled',
    // Use Ollama AI-predicted description; fall back to original only if Ollama hasn't run yet
    description: ollamaAnalysis || currentMetadata.description || '',
    hashtags: allHashtags || [],
    thumbnail_url: currentMetadata.thumbnail_url || '',
    url: currentUrl,
    opus_mode: ui.opusClipToggle.checked
  };

  fetch(`${API_BASE}/automate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(r => r.ok ? r.json() : Promise.reject("Automation failed"))
    .then(data => {
      const details = data.automation_details;
      ui.autoTitle.textContent = details.title;
      ui.autoDesc.textContent = details.description;
      ui.autoTime.textContent = details.scheduled_time;
      ui.autoReason.textContent = details.reasoning;

      ui.autoResultBox.style.display = 'block';
      btnText.textContent = '✅ Scheduled Successfully';
      ui.automateBtn.style.background = '#4CAF50';
      showToast("Post scheduled securely!");
    })
    .catch(err => {
      console.error(err);
      showToast("Error starting automation pipeline");
      ui.automateBtn.disabled = false;
      btnText.textContent = '🚀 Automate & Post to YouTube';
    })
    .finally(() => {
      ui.autoLoader.classList.add('hidden');
    });
}

