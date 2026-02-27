'use strict';

function setStatus(text, cls) {
  const el = document.getElementById('status');
  el.textContent = text;
  el.className = 'status' + (cls ? ' ' + cls : '');
}

function load() {
  chrome.storage.sync.get({ baseUrl: 'http://192.168.50.225:8001', token: '' }, (items) => {
    document.getElementById('baseUrl').value = items.baseUrl;
    document.getElementById('token').value = items.token;
    setStatus(items.token ? 'Settings loaded.' : 'No token saved yet.');
  });
}

function save() {
  const baseUrl = document.getElementById('baseUrl').value.trim();
  const token   = document.getElementById('token').value.trim();
  if (!baseUrl) { setStatus('Enter the VectorPass server URL.', 'err'); return; }
  chrome.storage.sync.set({ baseUrl, token }, () => {
    setStatus('✓ Saved!', 'ok');
  });
}

async function testConnection() {
  const baseUrl = document.getElementById('baseUrl').value.trim();
  const token   = document.getElementById('token').value.trim();
  if (!baseUrl || !token) {
    setStatus('Enter URL and token first.', 'err');
    return;
  }
  setStatus('Testing…');
  try {
    const u = new URL('/api/ext/match', baseUrl);
    u.searchParams.set('url', 'https://test.example.com');
    const res = await fetch(u.toString(), {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 401) {
      setStatus('✗ Invalid token (401 Unauthorized).', 'err');
    } else if (res.status === 403) {
      setStatus('✗ Token lacks operator role (403 Forbidden).', 'err');
    } else if (res.ok) {
      setStatus('✓ Connection successful! Token is valid.', 'ok');
    } else {
      setStatus(`✗ Server returned ${res.status}.`, 'err');
    }
  } catch (e) {
    setStatus(`✗ Could not reach server: ${e.message}`, 'err');
  }
}

document.getElementById('save').addEventListener('click', save);
document.getElementById('testConn').addEventListener('click', testConnection);

load();
