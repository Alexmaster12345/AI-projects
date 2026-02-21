(() => {
  function $$(id) { return document.getElementById(id); }

  function fmtTs(ts) {
    const n = Number(ts);
    if (!Number.isFinite(n) || n <= 0) return '—';
    return new Date(n * 1000).toLocaleString();
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    if (r.status === 401) { location.href = '/login'; throw new Error('Not authenticated'); }
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(data && data.detail ? String(data.detail) : `HTTP ${r.status}`);
    return data;
  }

  let allLogs = [];

  function renderLogs(logs) {
    const tbody = $$('logsTbody');
    if (!tbody) return;

    let crit = 0, warn = 0, info = 0;
    for (const l of logs) {
      if (l.level === 'crit') crit++;
      else if (l.level === 'warn') warn++;
      else info++;
    }
    const sc = $$('sumCrit'); if (sc) sc.textContent = crit;
    const sw = $$('sumWarn'); if (sw) sw.textContent = warn;
    const si = $$('sumInfo'); if (si) si.textContent = info;
    const st = $$('sumTotal'); if (st) st.textContent = logs.length;

    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="logsEmpty muted">No log entries found.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    for (const l of logs) {
      const tr = document.createElement('tr');
      const lvl = (l.level || 'info').toLowerCase();
      if (lvl === 'crit') tr.className = 'row-crit';
      else if (lvl === 'warn') tr.className = 'row-warn';

      const tdTs  = document.createElement('td'); tdTs.className  = 'logTs';     tdTs.textContent  = fmtTs(l.ts);
      const tdLvl = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = `logLevel ${lvl}`;
        badge.textContent = lvl === 'crit' ? 'CRITICAL' : lvl.toUpperCase();
        tdLvl.appendChild(badge);
      const tdHost = document.createElement('td'); tdHost.className = 'logHost';   tdHost.textContent = l.hostname || '—';
      const tdIp   = document.createElement('td'); tdIp.className   = 'logIp';     tdIp.textContent   = l.ip || '—';
      const tdSrc  = document.createElement('td'); tdSrc.className  = 'logSource'; tdSrc.textContent  = l.source || '—';
      const tdMsg  = document.createElement('td'); tdMsg.className  = 'logMsg';    tdMsg.textContent  = l.message || '—';

      tr.append(tdTs, tdLvl, tdHost, tdIp, tdSrc, tdMsg);
      tbody.appendChild(tr);
    }
  }

  function applyFilters() {
    const level = ($$('logsLevelFilter') || {}).value || '';
    const host  = (($$('logsHostFilter') || {}).value || '').trim().toLowerCase();
    let filtered = allLogs;
    if (level) filtered = filtered.filter(l => l.level === level);
    if (host)  filtered = filtered.filter(l => (l.hostname || '').toLowerCase().includes(host));
    renderLogs(filtered);
  }

  async function loadLogs() {
    const connEl = $$('logsConn');
    if (connEl) connEl.textContent = 'loading…';
    try {
      const data = await fetchJson('/api/logs?limit=500');
      allLogs = data.logs || [];
      applyFilters();
      if (connEl) connEl.textContent = 'live';
      const errEl = $$('logsErr'); if (errEl) errEl.style.display = 'none';
    } catch(e) {
      if (connEl) connEl.textContent = 'error';
      const errEl = $$('logsErr');
      if (errEl) { errEl.textContent = e.message || 'Failed to load logs'; errEl.style.display = ''; }
    }
  }

  async function clearLogs() {
    if (!confirm('Clear all system logs? This cannot be undone.')) return;
    try {
      await fetch('/api/logs', { method: 'DELETE' });
      allLogs = [];
      renderLogs([]);
    } catch(e) {
      alert('Failed to clear logs: ' + e.message);
    }
  }

  function init() {
    const refreshBtn = $$('logsRefreshBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadLogs);

    const clearBtn = $$('logsClearBtn');
    if (clearBtn) clearBtn.addEventListener('click', clearLogs);

    const levelSel = $$('logsLevelFilter');
    if (levelSel) levelSel.addEventListener('change', applyFilters);

    const hostInp = $$('logsHostFilter');
    if (hostInp) hostInp.addEventListener('input', applyFilters);

    loadLogs();
    // Auto-refresh every 5s
    setInterval(loadLogs, 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
