/* ══════════════════════════════════════════════════════════
   file.js  —  Dashboard · Upload · List · Download · Share
   Task 2/6:  status=blocked  → red security toast
   Task 3:    status=restricted → red restricted toast
   Task 7:    100 MB client-side guard
   ══════════════════════════════════════════════════════════ */

/* ─── Toast System ──────────────────────────────────────── */

function toast(type, title, msg) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.innerHTML =
    '<span class="toast-icon">' + (icons[type] || 'ℹ️') + '</span>' +
    '<div class="toast-body">' +
      '<div class="toast-title">' + title + '</div>' +
      (msg ? '<div class="toast-msg">' + msg + '</div>' : '') +
    '</div>' +
    '<button class="toast-close" onclick="dismissToast(this.parentElement)">✕</button>' +
    '<div class="toast-progress"></div>';
  container.appendChild(el);
  setTimeout(function() { dismissToast(el); }, 5500);
}

function dismissToast(el) {
  if (!el || el._removing) return;
  el._removing = true;
  el.classList.add('removing');
  setTimeout(function() { el.remove(); }, 240);
}

/* ─── Inline Alert ───────────────────────────────────────── */

function showAlert(id, message, type) {
  type = type || 'error';
  const el = document.getElementById(id);
  if (!el) return;
  const icons = { error: '⛔', success: '✔', info: 'ℹ️' };
  el.className = 'alert alert-' + type + ' show';
  el.innerHTML = '<span>' + (icons[type] || '⛔') + '</span><span>' + message + '</span>';
  if (type === 'success') setTimeout(function() { hideAlert(id); }, 4000);
}

function hideAlert(id) {
  const el = document.getElementById(id);
  if (el) el.className = 'alert';
}

/* ─── Button Loading ─────────────────────────────────────── */

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  if (loading) {
    btn._orig = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span>&nbsp; Please wait…';
  } else if (btn._orig) {
    btn.innerHTML = btn._orig;
  }
}

/* ─── Formatters ─────────────────────────────────────────── */

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso + 'Z').toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function formatExpiry(iso) {
  if (!iso) return 'Never';
  const dt = new Date(iso + 'Z'), now = new Date();
  if (dt < now) return 'Expired';
  const diffMin = Math.round((dt - now) / 60000);
  if (diffMin < 60)   return diffMin + 'm left';
  if (diffMin < 1440) return Math.round(diffMin / 60) + 'h left';
  return Math.round(diffMin / 1440) + 'd left';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function fileTypeIcon(name) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const map = {
    pdf: '📄', jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', webp: '🖼️', svg: '🖼️',
    mp4: '🎬', mov: '🎬', avi: '🎬', mkv: '🎬',
    mp3: '🎵', wav: '🎵', flac: '🎵', ogg: '🎵',
    zip: '🗜️', rar: '🗜️', '7z': '🗜️', tar: '🗜️', gz: '🗜️',
    js: '📝', ts: '📝', py: '📝', html: '📝', css: '📝', json: '📝',
    doc: '📃', docx: '📃', xls: '📊', xlsx: '📊', ppt: '📑', pptx: '📑',
    txt: '📋', md: '📋', csv: '📊',
  };
  return map[ext] || '📁';
}

/* ─── Auth Guard ─────────────────────────────────────────── */

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    if (!res.ok) { window.location.href = '/'; return null; }
    const data = await res.json();
    const uname = data.username || 'User';
    const el = document.getElementById('topbar-username');
    if (el) el.textContent = uname;
    const avatarEl = document.getElementById('user-avatar-initials');
    if (avatarEl) avatarEl.textContent = uname.slice(0, 2).toUpperCase();
    return data;
  } catch (e) {
    window.location.href = '/';
    return null;
  }
}

/* ─── Logout ─────────────────────────────────────────────── */

async function logout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  window.location.href = '/';
}

/* ─── Drop Zone ──────────────────────────────────────────── */

function initDropZone() {
  const zone = document.getElementById('drop-zone');
  if (!zone) return;
  zone.addEventListener('dragover', function(e) {
    e.preventDefault(); zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', function() { zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', function(e) {
    e.preventDefault(); zone.classList.remove('drag-over');
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (!file) return;
    const inp = document.getElementById('file-input');
    const dt  = new DataTransfer();
    dt.items.add(file);
    inp.files = dt.files;
    onFileSelected(inp);
  });
}

function onFileSelected(input) {
  const label = document.getElementById('drop-filename');
  if (!label) return;
  if (input.files && input.files[0]) {
    label.textContent = '✔ ' + input.files[0].name;
    label.style.display = 'block';
  } else {
    label.style.display = 'none';
  }
}

/* ─── Upload (Tasks 2, 3, 6, 7) ─────────────────────────── */

async function uploadFile() {
  hideAlert('upload-alert');
  const fileInput    = document.getElementById('file-input');
  const expirySelect = document.getElementById('expiry-select');

  if (!fileInput.files.length) {
    toast('warning', 'No file selected', 'Please pick a file before uploading.'); return;
  }

  const file = fileInput.files[0];
  const blockedExt = ['exe', 'bat', 'sh', 'cmd', 'msi', 'vbs', 'ps1', 'scr', 'pif', 'com'];
  const ext = file.name.split('.').pop().toLowerCase();

  if (blockedExt.includes(ext)) {
    toast('error', 'File type blocked', '.' + ext + ' files are not allowed.'); return;
  }

  // Task 7: 100 MB client-side guard
  if (file.size > 100 * 1024 * 1024) {
    toast('error', 'File too large', 'Maximum file size is 100 MB.'); return;
  }

  const formData = new FormData();
  formData.append('file', file);
  if (expirySelect && expirySelect.value) formData.append('expiry_minutes', expirySelect.value);

  setLoading('btn-upload', true);
  try {
    const res  = await fetch('/api/files/upload', {
      method: 'POST', credentials: 'include', body: formData,
    });

    // Response may be non-JSON on server error, guard carefully
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }

    // ── Task 6: Malware blocked → red security toast (Task 2) ─────────────
    if (data.status === 'blocked') {
      // Scan failure case
      if (data.message === 'Security scan failed') {
        toast('error', 'Security Threat Detected', 'Upload blocked: security scan could not be completed');
        return;
      }
      // Actual malware detected
      const threatMsg = (data.threat_type && data.threat_type !== 'Malicious File')
        ? 'Upload blocked: ' + data.threat_type + ' detected'
        : 'Upload blocked due to suspicious file';
      toast('error', 'Security Threat Detected', threatMsg);
      // DO NOT reload page, DO NOT change UI layout
      return;
    }

    // ── Task 3: User restricted → red toast ───────────────────────────────
    if (data.status === 'restricted') {
      toast('error', 'Account Restricted',
        data.error || 'You are temporarily restricted due to suspicious activity.');
      return;
    }

    if (!res.ok) {
      toast('error', 'Upload failed', data.error || res.statusText);
      return;
    }

    toast('success', 'File uploaded!', file.name + ' encrypted and stored.');
    fileInput.value = '';
    if (expirySelect) expirySelect.value = '';
    const label = document.getElementById('drop-filename');
    if (label) label.style.display = 'none';
    await loadFiles();

  } catch (e) {
    toast('error', 'Network error', 'Could not reach the server.');
  } finally {
    setLoading('btn-upload', false);
  }
}

/* ─── Load Files ─────────────────────────────────────────── */

async function loadFiles() {
  const container = document.getElementById('file-list-container');
  container.innerHTML =
    '<div class="empty-state">' +
      '<div class="spinner spinner-lg" style="color:var(--indigo);"></div>' +
    '</div>';

  try {
    const res  = await fetch('/api/files/list', { credentials: 'include' });
    if (!res.ok) { window.location.href = '/'; return; }
    const data = await res.json();
    renderFileTable(data.files || []);
    updateStats(data.files || []);
  } catch (e) {
    container.innerHTML =
      '<div class="empty-state">' +
        '<div class="empty-icon-wrap">⚠️</div>' +
        '<div class="empty-title">Connection error</div>' +
        '<div class="empty-desc">Could not load files. Check that the server is running.</div>' +
      '</div>';
  }
}

/* ─── Stats ──────────────────────────────────────────────── */

function updateStats(files) {
  const total   = files.length;
  const storage = files.reduce(function(s, f) { return s + (f.size || 0); }, 0);
  const now     = new Date();
  const expiring = files.filter(function(f) {
    if (!f.expiry_time || f.expired) return false;
    const dt = new Date(f.expiry_time + 'Z');
    return dt > now && (dt - now) < 24 * 60 * 60 * 1000;
  }).length;

  setEl('stat-total',    total);
  setEl('stat-storage',  formatBytes(storage));
  setEl('stat-expiring', expiring);
  setEl('file-count-badge', total);

  const pct = Math.min((storage / (100 * 1024 * 1024)) * 100, 100);
  const bar = document.getElementById('storage-bar');
  if (bar) bar.style.width = pct.toFixed(1) + '%';
  setEl('storage-used-label', formatBytes(storage) + ' used');
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

/* ─── Render Table ───────────────────────────────────────── */

function renderFileTable(files) {
  const container = document.getElementById('file-list-container');

  if (!files.length) {
    container.innerHTML =
      '<div class="empty-state">' +
        '<div class="empty-icon-wrap">📂</div>' +
        '<div class="empty-title">No files yet</div>' +
        '<div class="empty-desc">Upload your first file above — it will be AES-encrypted automatically.</div>' +
      '</div>';
    return;
  }

  var rows = files.map(function(f) {
    var icon    = fileTypeIcon(f.name);
    var expired = f.expired;

    var expiryBadge = expired
      ? '<span class="badge badge-expired">⏱ Expired</span>'
      : f.expiry_time
        ? '<span class="badge badge-expiry">⏳ ' + formatExpiry(f.expiry_time) + '</span>'
        : '<span class="badge badge-active">∞ Never</span>';

    var dlBtn = expired
      ? '<button class="btn btn-ghost btn-sm" disabled>↓</button>'
      : '<button class="btn btn-ghost btn-sm" onclick="downloadFile(' + f.id + ')">↓ Download</button>';

    var shareBtn = expired
      ? ''
      : '<button class="btn btn-share btn-sm" onclick="openShareModal(' + f.id + ')">🔗 Share</button>';

    return '<tr>' +
      '<td>' +
        '<div class="td-name-wrap">' +
          '<div class="file-icon-wrap">' + icon + '</div>' +
          '<div class="file-label">' +
            '<span class="file-name-full" title="' + escapeHtml(f.name) + '">' + escapeHtml(f.name) + '</span>' +
          '</div>' +
        '</div>' +
      '</td>' +
      '<td class="td-meta">' + formatBytes(f.size) + '</td>' +
      '<td class="td-meta">' + formatDate(f.created_at) + '</td>' +
      '<td>' + expiryBadge + '</td>' +
      '<td class="td-actions">' +
        dlBtn + ' ' + shareBtn +
        '<button class="btn btn-danger btn-sm" onclick="deleteFile(' + f.id + ', \'' + escapeHtml(f.name) + '\')">🗑</button>' +
      '</td>' +
    '</tr>';
  }).join('');

  container.innerHTML =
    '<div class="file-table-wrap">' +
      '<table>' +
        '<thead><tr>' +
          '<th>File</th><th>Size</th><th>Uploaded</th><th>Expiry</th><th>Actions</th>' +
        '</tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table>' +
    '</div>';
}

/* ─── Download ───────────────────────────────────────────── */

async function downloadFile(fileId) {
  try {
    const res = await fetch('/api/files/download/' + fileId, { credentials: 'include' });
    if (!res.ok) {
      let data = {};
      try { data = await res.json(); } catch (e) {}
      toast('error', 'Download failed', data.error || res.statusText); return;
    }
    const blob        = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    var filename      = 'download';
    var match         = disposition.match(/filename[^;=\n]*=["']?([^"';\n]+)/i);
    if (match) filename = decodeURIComponent(match[1].replace(/['"]/g, ''));
    const url  = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.appendChild(link); link.click();
    link.remove(); URL.revokeObjectURL(url);
    toast('success', 'Download started', filename + ' decrypted successfully.');
  } catch (e) {
    toast('error', 'Download error', e.message);
  }
}

/* ─── Delete ─────────────────────────────────────────────── */

async function deleteFile(fileId, filename) {
  if (!confirm('Permanently delete "' + filename + '"?\n\nThis cannot be undone.')) return;
  try {
    const res  = await fetch('/api/files/delete/' + fileId, {
      method: 'DELETE', credentials: 'include',
    });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      toast('error', 'Delete failed', data.error || res.statusText);
    } else {
      toast('success', 'File deleted', filename + ' removed permanently.');
      await loadFiles();
    }
  } catch (e) {
    toast('error', 'Delete error', e.message);
  }
}

/* ─── Share Modal ────────────────────────────────────────── */

function openShareModal(fileId) {
  document.getElementById('share-file-id').value  = fileId;
  document.getElementById('share-password').value = '';
  document.getElementById('share-expiry').value   = '24';
  var box = document.getElementById('share-url-result');
  if (box) box.className = 'share-url-box';
  hideAlert('share-alert');
  document.getElementById('share-modal').classList.add('open');
  setTimeout(function() { document.getElementById('share-password').focus(); }, 80);
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('open');
}

document.getElementById('share-modal').addEventListener('click', function(e) {
  if (e.target === this) closeShareModal();
});

/* ─── Create Share ───────────────────────────────────────── */

async function createShare() {
  hideAlert('share-alert');
  const fileId      = parseInt(document.getElementById('share-file-id').value);
  const password    = document.getElementById('share-password').value;
  const expiryHours = parseInt(document.getElementById('share-expiry').value);

  if (!password) { showAlert('share-alert', 'A share password is required.'); return; }
  if (password.length < 4) { showAlert('share-alert', 'Password must be at least 4 characters.'); return; }

  setLoading('btn-create-share', true);
  try {
    const res  = await fetch('/api/share/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ file_id: fileId, password: password, expiry_hours: expiryHours }),
    });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      showAlert('share-alert', data.error || 'Failed to create share link.');
    } else {
      const fullUrl = window.location.origin + data.share_url;
      document.getElementById('share-url-text').textContent = fullUrl;
      document.getElementById('share-url-result').className = 'share-url-box show';
      showAlert('share-alert', 'Share link created!', 'success');
      toast('success', 'Share link ready!', 'Copy and send it to the recipient.');
    }
  } catch (e) {
    showAlert('share-alert', 'Network error. Could not reach server.');
  } finally {
    setLoading('btn-create-share', false);
  }
}

/* ─── Copy Share URL ─────────────────────────────────────── */

function copyShareUrl() {
  const url = document.getElementById('share-url-text').textContent;
  navigator.clipboard.writeText(url).then(function() {
    const btn  = document.querySelector('.copy-btn');
    const orig = btn.textContent;
    btn.textContent = '✔ Copied!';
    toast('success', 'Copied!', 'Share URL is in your clipboard.');
    setTimeout(function() { btn.textContent = orig; }, 2200);
  }).catch(function() { prompt('Copy this URL:', url); });
}

/* ─── Init ───────────────────────────────────────────────── */

(async function init() {
  const user = await checkAuth();
  if (!user) return;
  initDropZone();
  await loadFiles();
})();
