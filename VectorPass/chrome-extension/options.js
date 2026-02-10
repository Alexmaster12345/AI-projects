function setStatus(text) {
  document.getElementById('status').textContent = text;
}

async function load() {
  chrome.storage.sync.get({ baseUrl: 'http://127.0.0.1:8001', token: '' }, (items) => {
    document.getElementById('baseUrl').value = items.baseUrl;
    document.getElementById('token').value = items.token;
    setStatus('Loaded.');
  });
}

async function save() {
  const baseUrl = document.getElementById('baseUrl').value.trim();
  const token = document.getElementById('token').value.trim();
  chrome.storage.sync.set({ baseUrl, token }, () => {
    setStatus('Saved.');
  });
}

document.getElementById('save').addEventListener('click', () => {
  save().catch((e) => setStatus(e.message || String(e)));
});

load().catch((e) => setStatus(e.message || String(e)));
