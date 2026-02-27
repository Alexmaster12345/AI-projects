'use strict';

// ── Helpers ──────────────────────────────────────────────────────────────────

function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ baseUrl: 'http://127.0.0.1:8001', token: '' }, resolve);
  });
}

function getActiveTab() {
  return chrome.tabs.query({ active: true, currentWindow: true }).then(t => t[0]);
}

function setStatus(text, cls) {
  const el = document.getElementById('status');
  el.textContent = text;
  el.className = 'status' + (cls ? ' ' + cls : '');
}

// ── Boot ─────────────────────────────────────────────────────────────────────

(async () => {
  const { baseUrl, token } = await getSettings();
  const tab = await getActiveTab();

  // Show current host in footer
  if (tab && tab.url) {
    try {
      const host = new URL(tab.url).hostname;
      document.getElementById('currentHost').textContent = host;
      document.getElementById('saveUrl').value = tab.url;
      document.getElementById('saveSite').value = host.replace(/^www\./, '');
    } catch (_) {}
  }

  // Open vault link
  document.getElementById('openVault').addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: baseUrl + '/vault' });
  });

  // Options button
  document.getElementById('openOptions').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });

  // Toggle manual save form
  document.getElementById('toggleSave').addEventListener('click', () => {
    const form = document.getElementById('saveForm');
    const visible = form.style.display !== 'none' && form.style.display !== '';
    form.style.display = visible ? 'none' : 'block';
    document.getElementById('toggleSave').textContent = visible
      ? '＋ Save credentials manually'
      : '▲ Hide save form';
  });

  // Save button
  document.getElementById('saveBtn').addEventListener('click', async () => {
    const site_name = document.getElementById('saveSite').value.trim();
    const url       = document.getElementById('saveUrl').value.trim();
    const username  = document.getElementById('saveUser').value.trim();
    const password  = document.getElementById('savePwd').value;

    if (!site_name || !url || !username) {
      setStatus('Fill in site, URL and username.', 'err');
      return;
    }
    if (!token) {
      setStatus('No API token — open Options.', 'err');
      return;
    }

    setStatus('Saving…');
    try {
      const resp = await chrome.runtime.sendMessage({
        type: 'VP_SAVE',
        payload: { site_name, url, login_username: username, password, notes: '', tags: [] }
      });
      if (resp && resp.ok) {
        setStatus('✓ Saved!', 'ok');
        document.getElementById('saveForm').style.display = 'none';
        document.getElementById('toggleSave').textContent = '＋ Save credentials manually';
      } else {
        setStatus(resp?.error || 'Save failed.', 'err');
      }
    } catch (e) {
      setStatus(e.message || 'Error', 'err');
    }
  });

  // Fill button (shown only when match found)
  const fillBtn = document.getElementById('fillBtn');
  fillBtn._match = null;
  fillBtn.addEventListener('click', async () => {
    const match = fillBtn._match;
    if (!match || !tab) return;
    try {
      await chrome.tabs.sendMessage(tab.id, {
        type: 'VP_FILL',
        username: match.username,
        password: match.password
      });
      setStatus('✓ Filled!', 'ok');
      setTimeout(() => window.close(), 900);
    } catch (e) {
      // Content script not ready — fall back to scripting API
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (u, p) => {
          function fill(sel, val) {
            const el = document.querySelector(sel);
            if (!el) return;
            el.focus();
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
          }
          const pwd = document.querySelector('input[type="password"]');
          const userSels = ['input[type="email"]','input[autocomplete="username"]',
            'input[name*="user" i]','input[id*="user" i]',
            'input[name*="email" i]','input[type="text"]'];
          for (const s of userSels) {
            const el = document.querySelector(s);
            if (el && el !== pwd && !el.value) { fill(s, u); break; }
          }
          if (pwd) fill('input[type="password"]', p);
        },
        args: [match.username, match.password]
      });
      setStatus('✓ Filled!', 'ok');
      setTimeout(() => window.close(), 900);
    }
  });

  // Auto-lookup match for current page
  if (!token) {
    setStatus('Set API token in Options to use VectorPass.', 'err');
    return;
  }

  if (!tab || !tab.url) {
    setStatus('No active tab.');
    return;
  }

  setStatus('Searching vault…');
  try {
    const resp = await chrome.runtime.sendMessage({ type: 'VP_MATCH', url: tab.url });

    if (resp && resp.match) {
      const m = resp.match;
      setStatus('Login found for this site.', 'ok');
      document.getElementById('matchCard').style.display = 'block';
      document.getElementById('matchSite').textContent = m.site_name;
      document.getElementById('matchUser').textContent = m.username;
      fillBtn._match = m;
      fillBtn.style.display = 'block';

      // Pre-fill save form with found username
      document.getElementById('saveUser').value = m.username;
    } else {
      setStatus('No saved login for this site.');
    }
  } catch (e) {
    setStatus('Could not reach VectorPass — check Options.', 'err');
  }
})();
