(() => {
  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element: #${id}`);
    return el;
  }

  const els = {
    conn: $('hostConn'),
    user: $('hostUser'),
    err: $('hostErr'),

    name: $('hName'),
    addr: $('hAddr'),
    type: $('hType'),
    tags: $('hTags'),
    active: $('hActive'),
    created: $('hCreated'),
    notes: $('hNotes'),

    status: $('hStatus'),
    latency: $('hLatency'),
    checked: $('hChecked'),
    msg: $('hMsg'),

    pIcmp: document.getElementById('pIcmp'),
    pSsh: document.getElementById('pSsh'),
    pSnmp: document.getElementById('pSnmp'),
    pNtp: document.getElementById('pNtp'),
    pDns: document.getElementById('pDns'),

    sideNav: document.getElementById('sideNav'),
    sideSearch: document.getElementById('sideSearch'),
  };

  function setErr(msg) {
    if (!msg) {
      els.err.style.display = 'none';
      els.err.textContent = '';
      return;
    }
    els.err.style.display = '';
    els.err.textContent = String(msg);
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    if (r.status === 401) {
      try {
        location.href = '/login';
      } catch (_) {
        // ignore
      }
      throw new Error('Not authenticated');
    }
    let data = null;
    try {
      data = await r.json();
    } catch (_) {
      data = null;
    }
    if (!r.ok) {
      const msg = data && data.detail ? String(data.detail) : `HTTP ${r.status}`;
      const err = new Error(msg);
      err.status = r.status;
      throw err;
    }
    return data;
  }

  function setText(el, txt) {
    el.textContent = txt == null || txt === '' ? '—' : String(txt);
  }

  function fmtTs(ts) {
    const n = Number(ts);
    if (!Number.isFinite(n) || n <= 0) return '—';
    try {
      return new Date(n * 1000).toLocaleString();
    } catch (_) {
      return String(n);
    }
  }

  function normalizeSev(st) {
    const s = (st && st.status ? String(st.status) : 'unknown').toLowerCase();
    return s === 'ok' ? 'ok' : 'crit';
  }

  function sevClass(st) {
    const s = (st && st.status ? String(st.status) : 'unknown').toLowerCase();
    if (s === 'ok') return 'ok';
    if (s === 'crit') return 'crit';
    return 'unknown';
  }

  function fmtProto(st) {
    if (!st) return '—';
    const s = (st.status ? String(st.status) : 'unknown').toLowerCase();
    const msg = st.message ? String(st.message) : '';
    const lat = st.latency_ms != null && Number.isFinite(Number(st.latency_ms)) ? `${Math.round(Number(st.latency_ms))} ms` : '';
    const parts = [];
    parts.push(s.toUpperCase());
    if (lat) parts.push(lat);
    if (msg) parts.push(msg);
    return parts.join(' · ');
  }

  function applyInlineProtoStyle(el, cls) {
    // Hard fallback colors so status remains readable even if CSS variables
    // or additional styles fail to load.
    if (!el) return;
    try {
      if (cls === 'ok') el.style.color = '#55ffa6';
      else if (cls === 'crit') el.style.color = '#ff4d6d';
      else el.style.color = 'rgba(233, 249, 255, 0.62)';
    } catch (_) {
      // ignore
    }
  }

  function applyChecks(checks) {
    const c = checks && typeof checks === 'object' ? checks : {};

    const map = [
      ['icmp', els.pIcmp],
      ['ssh', els.pSsh],
      ['snmp', els.pSnmp],
      ['ntp', els.pNtp],
      ['dns', els.pDns],
    ];

    for (const [key, el] of map) {
      if (!el) continue;
      const st = c[key] || null;
      el.classList.remove('ok', 'crit', 'unknown');
      const cls = sevClass(st);
      el.classList.add(cls);
      applyInlineProtoStyle(el, cls);
      el.textContent = fmtProto(st);
      try {
        el.title = (st && st.checked_ts != null) ? `Last check: ${fmtTs(st.checked_ts)}` : '';
      } catch (_) {
        // ignore
      }
    }
  }

  function setupSidebarSearch() {
    if (!els.sideSearch || !els.sideNav) return;
    els.sideSearch.addEventListener('input', () => {
      const q = (els.sideSearch.value || '').trim().toLowerCase();
      const items = els.sideNav.querySelectorAll('.sideItem');
      for (const it of items) {
        const label = (it.getAttribute('data-label') || it.textContent || '').toLowerCase();
        it.style.display = !q || label.includes(q) ? '' : 'none';
      }
      const groups = els.sideNav.querySelectorAll('.sideGroup');
      for (const g of groups) {
        const anyVisible = Array.from(g.querySelectorAll('.sideItem')).some((a) => a.style.display !== 'none');
        g.style.display = anyVisible ? '' : 'none';
      }
    });
  }

  function getHostIdFromPath() {
    // /host/{id}
    const parts = (location.pathname || '').split('/').filter(Boolean);
    const last = parts[parts.length - 1] || '';
    const n = Number(last);
    return Number.isFinite(n) ? String(Math.trunc(n)) : null;
  }

  async function loadHost(hostId) {
    const h = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}`);
    if (!h) throw new Error(`Host not found: ${hostId}`);

    setText(els.name, h.name);
    setText(els.addr, h.address);
    setText(els.type, h.type || '—');
    setText(els.active, String(!!h.is_active));
    setText(els.created, h.created_ts != null ? fmtTs(h.created_ts) : '—');

    const tags = Array.isArray(h.tags) ? h.tags : [];
    setText(els.tags, tags.length ? tags.join(', ') : '—');
    setText(els.notes, h.notes || '—');

    try {
      document.title = `System Trace · ${h.name || 'Host'}`;
    } catch (_) {
      // ignore
    }

    return h;
  }

  function applyStatus(st) {
    const sev = normalizeSev(st);
    els.status.classList.remove('ok', 'crit');
    els.status.classList.add(sev);

    // Color adjacent fields consistently with reachability.
    for (const el of [els.latency, els.checked, els.msg]) {
      if (!el) continue;
      el.classList.remove('ok', 'crit', 'unknown');
      el.classList.add(sev);
    }

    setText(els.status, sev === 'ok' ? 'OK' : 'ISSUE');
    setText(els.latency, st && st.latency_ms != null ? `${Math.round(Number(st.latency_ms))} ms` : '—');
    setText(els.checked, st && st.checked_ts != null ? fmtTs(st.checked_ts) : '—');
    setText(els.msg, st && st.message ? st.message : '—');
  }

  async function loadStatusOnce(hostId) {
    const r = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}/status`);
    applyStatus(r && r.status ? r.status : null);
  }

  async function loadChecksOnce(hostId) {
    const r = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}/checks`);
    applyChecks(r && r.checks ? r.checks : {});
  }

  let wsPingTimer = null;

  function connectWS(hostId) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/metrics`);

    if (wsPingTimer) {
      clearInterval(wsPingTimer);
      wsPingTimer = null;
    }

    ws.onopen = () => {
      els.conn.textContent = 'live';
    };

    ws.onclose = () => {
      els.conn.textContent = 'disconnected';
      if (wsPingTimer) {
        clearInterval(wsPingTimer);
        wsPingTimer = null;
      }
      // fallback: retry
      setTimeout(() => connectWS(hostId), 1500);
    };

    ws.onerror = () => {
      try {
        ws.close();
      } catch (_) {
        // ignore
      }
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'host_status') {
          const statuses = (msg && msg.statuses && typeof msg.statuses === 'object') ? msg.statuses : {};
          const st = statuses[String(hostId)] || statuses[hostId] || null;
          applyStatus(st);

          const checksAll = (msg && msg.checks && typeof msg.checks === 'object') ? msg.checks : null;
          if (checksAll) {
            const checks = checksAll[String(hostId)] || checksAll[hostId] || null;
            if (checks) applyChecks(checks);
          }
        }
      } catch (_) {
        // ignore
      }
    };

    // keepalive
    wsPingTimer = setInterval(() => {
      if (ws && ws.readyState === 1) ws.send('ping');
    }, 4000);
  }

  async function init() {
    els.conn.textContent = 'loading…';
    setupSidebarSearch();

    try {
      const hostId = getHostIdFromPath();
      if (!hostId) throw new Error('Invalid host id in URL');

      const [me] = await Promise.all([fetchJson('/api/me')]);
      setText(els.user, me && me.username ? me.username : '—');

      await loadHost(hostId);
      await loadStatusOnce(hostId);
      await loadChecksOnce(hostId);
      connectWS(hostId);

      // Poll as a fallback so checks remain live even if WS is blocked.
      setInterval(() => {
        loadStatusOnce(hostId).catch(() => null);
        loadChecksOnce(hostId).catch(() => null);
      }, 15_000);

      // If WS connects, it will flip to 'live'. Until then, show 'ready'.
      if (els.conn.textContent === 'loading…') els.conn.textContent = 'ready';
      setErr('');
    } catch (e) {
      els.conn.textContent = 'error';
      setErr(e && e.message ? e.message : 'Failed to load host');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
