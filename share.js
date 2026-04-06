/* ══════════════════════════════════════════════════════════
   share.js  —  Shared File Download Page
   All existing API calls and element IDs preserved.
   UI enhancements: toasts, file type icon, expiry display.
   ══════════════════════════════════════════════════════════ */

/* ─── Toast System ──────────────────────────────────────── */

function toast(type, title, msg = '') {
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      ${msg ? `<div class="toast-msg">${msg}</div>` : ''}
    </div>
    <button class="toast-close" onclick="dismissToast(this.parentElement)">✕</button>
    <div class="toast-progress"></div>
  `;
  container.appendChild(el);
  setTimeout(() => dismissToast(el), 4200);
}

function dismissToast(el) {
  if (!el || el._removing) return;
  el._removing = true;
  el.classList.add('removing');
  setTimeout(() => el.remove(), 240);
}

/* ─── Alert Helper ───────────────────────────────────────── */

function showAlert(id, message, type = 'error') {
  const el = document.getElementById(id);
  if (!el) return;
  const icons = { error: '⛔', success: '✔', info: 'ℹ️' };
  el.className = `alert alert-${type} show`;
  el.innerHTML = `<span>${icons[type] || '⛔'}</span><span>${message}</span>`;
}

function hideAlert(id) {
  const el = document.getElementById(id);
  if (el) el.className = 'alert';
}

/* ─── Loading Button ─────────────────────────────────────── */

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  if (loading) {
    btn._orig = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span>&nbsp; Decrypting…';
  } else if (btn._orig) {
    btn.innerHTML = btn._orig;
  }
}

/* ─── Utilities ──────────────────────────────────────────── */

function formatBytes(bytes) {
  if (!bytes) return '—';
  const k = 1024, sizes = ['B','KB','MB','GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatExpiry(iso) {
  if (!iso) return 'Never';
  return new Date(iso + 'Z').toLocaleString(undefined, {
    month:'short', day:'numeric', year:'numeric',
    hour:'2-digit', minute:'2-digit',
  });
}

function fileTypeIcon(name) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const map = {
    pdf:'📄', jpg:'🖼️', jpeg:'🖼️', png:'🖼️', gif:'🖼️', webp:'🖼️', svg:'🖼️',
    mp4:'🎬', mov:'🎬', avi:'🎬', mkv:'🎬',
    mp3:'🎵', wav:'🎵', flac:'🎵',
    zip:'🗜️', rar:'🗜️', '7z':'🗜️',
    js:'📝', ts:'📝', py:'📝', html:'📝', css:'📝', json:'📝',
    doc:'📃', docx:'📃', xls:'📊', xlsx:'📊',
    txt:'📋', md:'📋', csv:'📊',
  };
  return map[ext] || '📁';
}

/* ─── Get Token ──────────────────────────────────────────── */

function getToken() {
  const parts = window.location.pathname.split('/');
  return parts[parts.length - 1] || null;
}

/* ─── Load Share Info ────────────────────────────────────── */

async function loadShareInfo() {
  const token = getToken();
  if (!token) { showError('Invalid share link — no token found.'); return; }

  try {
    const res  = await fetch(`/api/share/${token}`, { credentials:'include' });
    const data = await res.json();

    document.getElementById('state-loading').style.display = 'none';

    if (!res.ok) {
      showError(data.error || 'This share link is invalid or has expired.');
      return;
    }

    // Populate file info
    const filename = data.filename || 'Unknown file';
    document.getElementById('share-filename').textContent = filename;
    document.getElementById('share-filesize').textContent = formatBytes(data.size);

    // File type icon
    const iconEl = document.getElementById('share-file-type-icon');
    if (iconEl) iconEl.textContent = fileTypeIcon(filename);

    // Expiry
    const expiryEl = document.getElementById('share-expiry');
    if (expiryEl) expiryEl.textContent = 'Link expires ' + formatExpiry(data.expiry_time);

    document.getElementById('state-download').style.display = 'block';
    document.getElementById('share-pw-input').focus();

  } catch {
    document.getElementById('state-loading').style.display = 'none';
    showError('Network error. Could not verify the share link.');
  }
}

function showError(msg) {
  document.getElementById('error-message').textContent = msg;
  document.getElementById('state-error').style.display = 'block';
}

/* ─── Download Shared File ───────────────────────────────── */

async function downloadSharedFile() {
  hideAlert('share-dl-alert');
  const token    = getToken();
  const password = document.getElementById('share-pw-input').value;

  if (!password) {
    showAlert('share-dl-alert', 'Please enter the share password.'); return;
  }

  setLoading('btn-dl', true);
  try {
    const res = await fetch(`/api/share/${token}/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ password }),
    });

    if (!res.ok) {
      const data = await res.json();
      showAlert('share-dl-alert', data.error || 'Download failed.');
      toast('error', 'Access denied', data.error || 'Incorrect password or expired link.');
      setLoading('btn-dl', false);
      return;
    }

    const blob        = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    let filename = document.getElementById('share-filename').textContent || 'download';
    const match = disposition.match(/filename[^;=\n]*=["']?([^"';\n]+)/i);
    if (match) filename = decodeURIComponent(match[1].replace(/['"]/g,''));

    const url  = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.appendChild(link); link.click();
    link.remove(); URL.revokeObjectURL(url);

    toast('success', 'Download complete!', `${filename} decrypted and saved.`);
    showAlert('share-dl-alert', 'File decrypted and downloaded successfully!', 'success');

  } catch (err) {
    showAlert('share-dl-alert', 'Network error: ' + err.message);
    toast('error', 'Network error', err.message);
  } finally {
    setLoading('btn-dl', false);
  }
}

/* ─── Init ───────────────────────────────────────────────── */

loadShareInfo();
