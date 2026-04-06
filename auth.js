/* ══════════════════════════════════════════════════════════
   auth.js  —  Login · Register · OTP
   Task 4:  OTP delivered via email (server-side).
   Task 5:  Single clean OTP input — no grid.
   Task 11: Red toast on account locked response.
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

/* ─── Tab Switching ─────────────────────────────────────── */

function showTab(tab) {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs[0].classList.toggle('active', tab === 'login');
  tabs[1].classList.toggle('active', tab === 'register');
  document.getElementById('panel-login').classList.toggle('active', tab === 'login');
  document.getElementById('panel-register').classList.toggle('active', tab === 'register');
  hideAlert('login-alert');
  hideAlert('register-alert');
}

/* ─── Register ──────────────────────────────────────────── */

async function register() {
  hideAlert('register-alert');
  const username = document.getElementById('reg-username').value.trim();
  const email    = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;

  if (!username || !email || !password) {
    showAlert('register-alert', 'All fields are required.'); return;
  }
  if (!email.includes('@')) {
    showAlert('register-alert', 'Please enter a valid email address.'); return;
  }

  setLoading('btn-register', true);
  try {
    const res  = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAlert('register-alert', data.error || 'Registration failed.');
    } else {
      toast('success', 'Account created!', 'You can now sign in.');
      ['reg-username', 'reg-email', 'reg-password'].forEach(function(id) {
        document.getElementById(id).value = '';
      });
      setTimeout(function() { showTab('login'); }, 900);
    }
  } catch (e) {
    showAlert('register-alert', 'Network error. Is the server running?');
  } finally {
    setLoading('btn-register', false);
  }
}

/* ─── Login ─────────────────────────────────────────────── */

async function login() {
  hideAlert('login-alert');
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  if (!username || !password) {
    showAlert('login-alert', 'Username and password are required.'); return;
  }

  setLoading('btn-login', true);
  try {
    const res  = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();

    // ── Task 11: Account locked — red toast ───────────────────────────────
    if (res.status === 429 || data.status === 'locked') {
      const retryMsg = data.retry_in_minutes
        ? 'Try again in ' + data.retry_in_minutes + ' minute(s).'
        : 'Too many incorrect password attempts. Try again later.';
      toast('error', 'Account Locked', retryMsg);
      showAlert('login-alert', retryMsg);
      return;
    }

    if (!res.ok) {
      showAlert('login-alert', data.error || 'Login failed.');
      return;
    }

    if (data.otp_required) {
      document.getElementById('step-credentials').style.display = 'none';
      document.getElementById('step-otp').style.display = 'block';
      const otpField = document.getElementById('otp-code');
      if (otpField) { otpField.value = ''; otpField.focus(); }
      toast('info', 'OTP sent', 'Check your email for the verification code.');
    }
  } catch (e) {
    showAlert('login-alert', 'Network error. Is the server running?');
  } finally {
    setLoading('btn-login', false);
  }
}

/* ─── OTP Verify ─────────────────────────────────────────── */

async function verifyOTP() {
  hideAlert('otp-alert');
  const otp = document.getElementById('otp-code').value.trim();

  if (!otp || otp.length < 6) {
    showAlert('otp-alert', 'Please enter the full 6-digit code.'); return;
  }

  setLoading('btn-otp', true);
  try {
    const res  = await fetch('/api/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ otp }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAlert('otp-alert', data.error || 'OTP verification failed.');
    } else {
      toast('success', 'Verified!', 'Redirecting to your vault…');
      setTimeout(function() { window.location.href = '/dashboard'; }, 700);
    }
  } catch (e) {
    showAlert('otp-alert', 'Network error. Is the server running?');
  } finally {
    setLoading('btn-otp', false);
  }
}

/* ─── Cancel OTP ─────────────────────────────────────────── */

function cancelOTP() {
  document.getElementById('step-otp').style.display = 'none';
  document.getElementById('step-credentials').style.display = 'block';
  hideAlert('otp-alert');
}

/* ─── Enter key ──────────────────────────────────────────── */

document.addEventListener('keydown', function(e) {
  if (e.key !== 'Enter') return;
  const otpStep = document.getElementById('step-otp');
  if (otpStep && otpStep.style.display !== 'none') {
    verifyOTP(); return;
  }
  if (document.getElementById('panel-login').classList.contains('active')) {
    login();
  } else {
    register();
  }
});

/* ─── Redirect if already logged in ─────────────────────── */

(async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    if (res.ok) window.location.href = '/dashboard';
  } catch (e) { /* not logged in */ }
})();
