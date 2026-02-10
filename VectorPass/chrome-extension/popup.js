async function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ baseUrl: 'http://127.0.0.1:8001', token: '' }, resolve);
  });
}

function setStatus(text) {
  const el = document.getElementById('status');
  el.textContent = text;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

function guessAndFillCredentials(username, password) {
  const pwd = document.querySelector('input[type="password"]');

  const userCandidates = [
    'input[type="email"]',
    'input[name*="user" i]',
    'input[id*="user" i]',
    'input[name*="login" i]',
    'input[id*="login" i]',
    'input[name*="email" i]',
    'input[id*="email" i]',
    'input[type="text"]'
  ];

  let user = null;
  for (const sel of userCandidates) {
    const el = document.querySelector(sel);
    if (el && el !== pwd) { user = el; break; }
  }

  if (user) {
    user.focus();
    user.value = username;
    user.dispatchEvent(new Event('input', { bubbles: true }));
    user.dispatchEvent(new Event('change', { bubbles: true }));
  }

  if (pwd) {
    pwd.focus();
    pwd.value = password;
    pwd.dispatchEvent(new Event('input', { bubbles: true }));
    pwd.dispatchEvent(new Event('change', { bubbles: true }));
  }

  return { filledUsername: !!user, filledPassword: !!pwd };
}

async function fetchMatch(baseUrl, token, pageUrl) {
  const u = new URL('/api/ext/match', baseUrl);
  u.searchParams.set('url', pageUrl);

  const res = await fetch(u.toString(), {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${txt}`);
  }

  return await res.json();
}

async function run() {
  setStatus('Loading settings…');
  const { baseUrl, token } = await getSettings();

  if (!token) {
    setStatus('Missing API token. Open Options and paste your token.');
    return;
  }

  const tab = await getActiveTab();
  if (!tab || !tab.url) {
    setStatus('No active tab URL.');
    return;
  }

  setStatus('Searching vault…');
  const data = await fetchMatch(baseUrl, token, tab.url);
  if (!data || !data.match) {
    setStatus('No match found for this site.');
    return;
  }

  setStatus(`Filling: ${data.match.site_name}`);

  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: guessAndFillCredentials,
    args: [data.match.username, data.match.password]
  });

  setStatus('Done.');
}

document.getElementById('fillBtn').addEventListener('click', () => {
  run().catch((e) => setStatus(e.message || String(e)));
});

document.getElementById('openOptions').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});
