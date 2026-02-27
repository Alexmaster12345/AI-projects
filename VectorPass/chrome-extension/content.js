/* VectorPass content script — detects login form submissions and offers to save */
'use strict';

(function () {
  if (window.__vpInjected) return;
  window.__vpInjected = true;

  // ── Helpers ────────────────────────────────────────────────────────────────

  function findPasswordField() {
    return document.querySelector('input[type="password"]:not([autocomplete*="new"])');
  }

  function findUsernameField(pwdField) {
    const selectors = [
      'input[type="email"]',
      'input[autocomplete="username"]',
      'input[autocomplete="email"]',
      'input[name*="user" i]',
      'input[id*="user" i]',
      'input[name*="email" i]',
      'input[id*="email" i]',
      'input[name*="login" i]',
      'input[id*="login" i]',
      'input[type="text"]'
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el !== pwdField && el.value) return el;
    }
    return null;
  }

  // ── Save prompt banner ─────────────────────────────────────────────────────

  function showSaveBanner(username, password, pageUrl, siteName) {
    // Don't show twice
    if (document.getElementById('vp-save-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'vp-save-banner';
    banner.style.cssText = [
      'position:fixed', 'top:12px', 'right:12px', 'z-index:2147483647',
      'background:#1e1e2e', 'color:#cdd6f4', 'border-radius:12px',
      'box-shadow:0 4px 24px rgba(0,0,0,.45)', 'padding:14px 16px',
      'font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif',
      'font-size:14px', 'min-width:300px', 'max-width:360px',
      'border:1px solid #313244'
    ].join(';');

    banner.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
        <span style="font-size:22px">🔐</span>
        <div>
          <div style="font-weight:700;font-size:15px">Save to VectorPass?</div>
          <div style="font-size:12px;color:#a6adc8;margin-top:2px">${escHtml(siteName)}</div>
        </div>
        <button id="vp-dismiss" style="margin-left:auto;background:none;border:none;color:#a6adc8;font-size:20px;cursor:pointer;line-height:1" title="Dismiss">×</button>
      </div>
      <div style="font-size:12px;color:#a6adc8;margin-bottom:10px">
        Username: <strong style="color:#cdd6f4">${escHtml(username)}</strong>
      </div>
      <div style="display:flex;gap:8px">
        <button id="vp-save-yes" style="flex:1;background:#1e66f5;color:#fff;border:none;border-radius:8px;padding:8px;cursor:pointer;font-weight:600">Save</button>
        <button id="vp-save-no" style="flex:1;background:#313244;color:#cdd6f4;border:none;border-radius:8px;padding:8px;cursor:pointer">Not now</button>
      </div>
      <div id="vp-banner-status" style="font-size:12px;color:#a6adc8;margin-top:8px;display:none"></div>
    `;

    document.body.appendChild(banner);

    document.getElementById('vp-dismiss').onclick = () => banner.remove();
    document.getElementById('vp-save-no').onclick = () => banner.remove();
    document.getElementById('vp-save-yes').onclick = async () => {
      const statusEl = document.getElementById('vp-banner-status');
      statusEl.style.display = 'block';
      statusEl.textContent = 'Saving…';
      try {
        const resp = await chrome.runtime.sendMessage({
          type: 'VP_SAVE',
          payload: { site_name: siteName, url: pageUrl, login_username: username, password }
        });
        if (resp && resp.ok) {
          statusEl.style.color = '#a6e3a1';
          statusEl.textContent = '✓ Saved to vault!';
          setTimeout(() => banner.remove(), 1800);
        } else {
          statusEl.style.color = '#f38ba8';
          statusEl.textContent = resp?.error || 'Failed to save.';
        }
      } catch (e) {
        statusEl.style.color = '#f38ba8';
        statusEl.textContent = e.message || 'Extension error.';
      }
    };

    // Auto-dismiss after 20s
    setTimeout(() => { if (banner.parentNode) banner.remove(); }, 20000);
  }

  function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ── Autofill prompt banner ─────────────────────────────────────────────────

  function showFillBanner(match) {
    if (document.getElementById('vp-fill-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'vp-fill-banner';
    banner.style.cssText = [
      'position:fixed', 'top:12px', 'right:12px', 'z-index:2147483647',
      'background:#1e1e2e', 'color:#cdd6f4', 'border-radius:12px',
      'box-shadow:0 4px 24px rgba(0,0,0,.45)', 'padding:14px 16px',
      'font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif',
      'font-size:14px', 'min-width:300px', 'max-width:360px',
      'border:1px solid #313244'
    ].join(';');

    banner.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
        <span style="font-size:22px">🔐</span>
        <div>
          <div style="font-weight:700;font-size:15px">VectorPass</div>
          <div style="font-size:12px;color:#a6adc8;margin-top:2px">Saved login found</div>
        </div>
        <button id="vp-fill-dismiss" style="margin-left:auto;background:none;border:none;color:#a6adc8;font-size:20px;cursor:pointer;line-height:1" title="Dismiss">×</button>
      </div>
      <div style="font-size:12px;color:#a6adc8;margin-bottom:10px">
        <strong style="color:#cdd6f4">${escHtml(match.site_name)}</strong><br>
        ${escHtml(match.username)}
      </div>
      <div style="display:flex;gap:8px">
        <button id="vp-fill-yes" style="flex:1;background:#1e66f5;color:#fff;border:none;border-radius:8px;padding:8px;cursor:pointer;font-weight:600">Fill login</button>
        <button id="vp-fill-no" style="flex:1;background:#313244;color:#cdd6f4;border:none;border-radius:8px;padding:8px;cursor:pointer">Not now</button>
      </div>
    `;

    document.body.appendChild(banner);

    document.getElementById('vp-fill-dismiss').onclick = () => banner.remove();
    document.getElementById('vp-fill-no').onclick = () => banner.remove();
    document.getElementById('vp-fill-yes').onclick = () => {
      fillForm(match.username, match.password);
      banner.remove();
    };

    setTimeout(() => { if (banner.parentNode) banner.remove(); }, 15000);
  }

  // ── Form fill ──────────────────────────────────────────────────────────────

  function fillForm(username, password) {
    const pwdField = findPasswordField();
    const userField = findUsernameField(pwdField);

    if (userField) {
      userField.focus();
      userField.value = username;
      userField.dispatchEvent(new Event('input', { bubbles: true }));
      userField.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if (pwdField) {
      pwdField.focus();
      pwdField.value = password;
      pwdField.dispatchEvent(new Event('input', { bubbles: true }));
      pwdField.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  // ── Form submission intercept ──────────────────────────────────────────────

  function watchForms() {
    document.querySelectorAll('form').forEach(attachForm);

    // Watch for dynamically added forms
    const observer = new MutationObserver(() => {
      document.querySelectorAll('form:not([data-vp])').forEach(attachForm);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function attachForm(form) {
    if (form.dataset.vp) return;
    form.dataset.vp = '1';
    form.addEventListener('submit', onFormSubmit, true);
  }

  function onFormSubmit(e) {
    const form = e.currentTarget;
    const pwdField = form.querySelector('input[type="password"]');
    if (!pwdField || !pwdField.value) return;

    const userField = findUsernameField(pwdField) || form.querySelector('input[type="text"], input[type="email"]');
    const username = userField ? userField.value.trim() : '';
    const password = pwdField.value;

    if (!username && !password) return;

    const pageUrl = window.location.href;
    const siteName = document.title || new URL(pageUrl).hostname;

    // Delay to let page navigate first, then prompt
    setTimeout(() => {
      showSaveBanner(username, password, pageUrl, siteName);
    }, 800);
  }

  // ── Auto-fill on page load if login form present ───────────────────────────

  async function checkAutoFill() {
    const pwdField = findPasswordField();
    if (!pwdField) return; // not a login page

    const pageUrl = window.location.href;
    try {
      const resp = await chrome.runtime.sendMessage({ type: 'VP_MATCH', url: pageUrl });
      if (resp && resp.match) {
        showFillBanner(resp.match);
      }
    } catch (_) {
      // Extension not configured — silent fail
    }
  }

  // ── Boot ───────────────────────────────────────────────────────────────────

  watchForms();

  // Small delay to let SPA frameworks render forms
  setTimeout(checkAutoFill, 800);

  // Listen for manual fill trigger from popup
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === 'VP_FILL') {
      fillForm(msg.username, msg.password);
      sendResponse({ ok: true });
    }
  });
})();
