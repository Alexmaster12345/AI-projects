/* VectorPass background service worker */
'use strict';

function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ baseUrl: 'http://127.0.0.1:8001', token: '' }, resolve);
  });
}

async function apiMatch(baseUrl, token, url) {
  const u = new URL('/api/ext/match', baseUrl);
  u.searchParams.set('url', url);
  const res = await fetch(u.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function apiAdd(baseUrl, token, payload) {
  const res = await fetch(new URL('/api/ext/add', baseUrl).toString(), {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    const { baseUrl, token } = await getSettings();

    if (!token) {
      sendResponse({ ok: false, error: 'No API token configured. Open VectorPass options.' });
      return;
    }

    if (msg.type === 'VP_MATCH') {
      try {
        const data = await apiMatch(baseUrl, token, msg.url);
        sendResponse({ match: data.match || null });
      } catch (e) {
        sendResponse({ match: null, error: e.message });
      }
    }

    if (msg.type === 'VP_SAVE') {
      try {
        const data = await apiAdd(baseUrl, token, msg.payload);
        sendResponse({ ok: true, id: data.id });
      } catch (e) {
        sendResponse({ ok: false, error: e.message });
      }
    }
  })();

  return true; // keep channel open for async response
});
