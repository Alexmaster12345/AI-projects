(() => {
  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element: #${id}`);
    return el;
  }

  const els = {
    conn: $('ovConn'),
    user: $('ovUser'),
    err: $('ovErr'),

    hostname: $('ovHostname'),
    uptime: $('ovUptime'),
    cpu: $('ovCpu'),
    mem: $('ovMem'),
    disk: $('ovDisk'),
    net: $('ovNet'),
    gpu: $('ovGpu'),
    lastUpdate: $('ovLastUpdate'),

    ntp: $('ovNtp'),
    icmp: $('ovIcmp'),
    snmp: $('ovSnmp'),
    netflow: $('ovNetflow'),

    summary: $('ovSummary'),
    anoms: $('ovAnoms'),

    hostCount: $('ovHostCount'),

    dbCard: $('ovDbCard'),
    dbStatus: $('ovDbStatus'),
    dbJson: $('ovDbJson'),

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

  function setConn(txt) {
    els.conn.textContent = String(txt || '—');
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

  function fmtPct(v) {
    return v == null ? '—' : (Math.round(v * 10) / 10).toFixed(1) + '%';
  }

  function fmtBytes(b) {
    if (b == null) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    let n = Number(b);
    let i = 0;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    const d = i <= 1 ? 0 : 1;
    return `${n.toFixed(d)} ${units[i]}`;
  }

  function fmtMbps(bytesPerSec) {
    if (bytesPerSec == null) return '—';
    const mbps = (bytesPerSec * 8) / 1_000_000;
    return `${mbps.toFixed(1)} Mb/s`;
  }

  function fmtUptime(sec) {
    if (sec == null) return '—';
    sec = Math.max(0, Math.floor(sec));
    const d = Math.floor(sec / 86400);
    sec -= d * 86400;
    const h = Math.floor(sec / 3600);
    sec -= h * 3600;
    const m = Math.floor(sec / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  function fmtLocalTs(tsSec) {
    if (!tsSec) return '—';
    const d = new Date(Number(tsSec) * 1000);
    return d.toLocaleString();
  }

  function primaryDisk(disks) {
    if (!disks || disks.length === 0) return null;
    const root = disks.find((d) => d.mount === '/');
    if (root) return root;
    return disks.reduce((a, b) => (b.percent > a.percent ? b : a), disks[0]);
  }

  function setText(el, txt) {
    if (!el) return;
    el.textContent = txt == null ? '—' : String(txt);
  }

  function setProto(el, p) {
    const st = ((p && p.status) || 'unknown').toLowerCase();
    el.classList.remove('ok', 'warn', 'crit', 'unknown');
    el.classList.add(st);

    let txt = st.toUpperCase();
    if (p && p.latency_ms != null) txt += ` ${Math.round(Number(p.latency_ms))}ms`;
    if (p && p.message) txt += ` · ${String(p.message)}`;
    el.textContent = txt;
  }

  function proto(sample, name) {
    if (!sample || !sample.protocols) return null;
    return sample.protocols[name] || null;
  }

  let lastNet = null;
  let lastNetTs = null;
  function netRate(sample) {
    if (!sample || !sample.net) return null;
    if (lastNet == null) {
      lastNet = sample.net;
      lastNetTs = sample.ts;
      return null;
    }
    const dt = Math.max(0.2, sample.ts - lastNetTs);
    const tx = (sample.net.bytes_sent - lastNet.bytes_sent) / dt;
    const rx = (sample.net.bytes_recv - lastNet.bytes_recv) / dt;
    lastNet = sample.net;
    lastNetTs = sample.ts;
    return { tx: Math.max(0, tx), rx: Math.max(0, rx) };
  }

  let currentUser = null;
  let lastSample = null;
  let lastInsights = null;
  let lastInvFetchMs = 0;
  let lastDbFetchMs = 0;

  function render(sample, insights) {
    lastSample = sample;
    lastInsights = insights;

    const nr = netRate(sample);

    setText(els.hostname, sample && sample.hostname ? sample.hostname : '—');
    setText(els.uptime, sample ? fmtUptime(sample.uptime_seconds) : '—');
    setText(els.cpu, sample ? fmtPct(sample.cpu_percent) : '—');
    setText(els.mem, sample ? fmtPct(sample.mem_percent) : '—');

    const pd = sample ? primaryDisk(sample.disk) : null;
    setText(els.disk, pd ? `${fmtPct(pd.percent)} used / ${fmtBytes(pd.free_bytes)} free` : '—');

    if (nr) setText(els.net, `TX ${fmtMbps(nr.tx)} / RX ${fmtMbps(nr.rx)}`);
    else setText(els.net, '—');

    if (sample && sample.gpu && sample.gpu.length > 0) {
      const g = sample.gpu[0];
      const gtemp = g && g.temp_c != null ? `${Math.round(g.temp_c)}°C` : '—';
      const util = g && g.util_percent != null ? `${Math.round(g.util_percent)}%` : '—';
      setText(els.gpu, `${gtemp} / ${util}`);
    } else {
      setText(els.gpu, '—');
    }

    setText(els.lastUpdate, sample && sample.ts ? fmtLocalTs(sample.ts) : '—');

    setProto(els.ntp, proto(sample, 'ntp'));
    setProto(els.icmp, proto(sample, 'icmp'));
    setProto(els.snmp, proto(sample, 'snmp'));
    setProto(els.netflow, proto(sample, 'netflow'));

    setText(els.summary, insights && insights.summary ? insights.summary : '—');
    try {
      const list = insights && Array.isArray(insights.anomalies) ? insights.anomalies : [];
      const total = list.length;
      const warn = list.filter((a) => a && a.severity === 'warn').length;
      const crit = list.filter((a) => a && a.severity === 'crit').length;
      setText(els.anoms, total ? `total ${total} (warn ${warn}, crit ${crit})` : 'none');
    } catch (_) {
      setText(els.anoms, '—');
    }
  }

  async function refreshInventoryAndDb() {
    const now = Date.now();

    if (els.hostCount && now - lastInvFetchMs > 5000) {
      lastInvFetchMs = now;
      try {
        const hosts = await fetchJson('/api/hosts');
        setText(els.hostCount, Array.isArray(hosts) ? hosts.length : '—');
      } catch (_) {
        setText(els.hostCount, '—');
      }
    }

    const isAdmin = currentUser && String(currentUser.role || '').toLowerCase() === 'admin';
    if (els.dbCard) els.dbCard.style.display = isAdmin ? '' : 'none';

    if (isAdmin && now - lastDbFetchMs > 10000) {
      lastDbFetchMs = now;
      try {
        const stats = await fetchJson('/api/admin/db');
        setText(
          els.dbStatus,
          `rows: ${stats && stats.rows != null ? stats.rows : '—'} · size: ${fmtBytes(stats && stats.file_bytes)} · retention: ${stats && stats.retention_seconds != null ? stats.retention_seconds + 's' : '—'}`,
        );
        if (els.dbJson) els.dbJson.textContent = JSON.stringify(stats, null, 2);
      } catch (e) {
        setText(els.dbStatus, e && e.message ? e.message : 'Failed to load DB stats');
      }
    }
  }

  async function loadMe() {
    try {
      currentUser = await fetchJson('/api/me');
      const usernameEl = document.getElementById('ovUsername');
if (usernameEl) {
  setText(usernameEl, currentUser && currentUser.username ? currentUser.username : '—');
} else {
  setText(els.user, currentUser && currentUser.username ? currentUser.username : '—');
}
    } catch (_) {
      currentUser = null;
      setText(els.user, '—');
    }
  }

  // Transport: WS with fallback polling
  let polling = false;
  async function pollFallback() {
    if (polling) return;
    polling = true;
    setConn('polling');

    while (polling) {
      try {
        const [latest, insights] = await Promise.all([fetchJson('/api/metrics/latest'), fetchJson('/api/insights')]);
        if (latest && latest.ts) render(latest, insights);
        await refreshInventoryAndDb();
        setErr('');
      } catch (e) {
        // Keep polling; show last error briefly.
        setErr(e && e.message ? e.message : 'Failed to refresh');
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  let ws = null;
  let wsPingTimer = null;
  let wsFallbackTimer = null;

  function clearWsTimers() {
    if (wsPingTimer) {
      clearInterval(wsPingTimer);
      wsPingTimer = null;
    }
    if (wsFallbackTimer) {
      clearTimeout(wsFallbackTimer);
      wsFallbackTimer = null;
    }
  }

  function connectWS() {
    clearWsTimers();

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws/metrics`);
    setConn('connecting…');

    ws.onopen = () => {
      setConn('live');
      polling = false;
    };

    ws.onclose = () => {
      setConn('disconnected');
      clearWsTimers();
      setTimeout(connectWS, 1500);
    };

    ws.onerror = () => {
      try {
        ws.close();
      } catch (_) {
        // ignore
      }
    };

    ws.onmessage = async (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'snapshot' || msg.type === 'sample') {
          if (msg.sample && msg.sample.ts) render(msg.sample, msg.insights);
          await refreshInventoryAndDb();
          setErr('');
        }
      } catch (_) {
        // ignore
      }
    };

    wsPingTimer = setInterval(() => {
      if (ws && ws.readyState === 1) ws.send('ping');
    }, 4000);

    wsFallbackTimer = setTimeout(() => {
      if (!ws || ws.readyState !== 1) {
        try {
          ws && ws.close();
        } catch (_) {
          // ignore
        }
        pollFallback();
      }
    }, 3000);
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

  async function init() {
    setupSidebarSearch();
    await loadMe();

    // Initial snapshot (helps even before WS opens)
    try {
      const [latest, insights] = await Promise.all([fetchJson('/api/metrics/latest'), fetchJson('/api/insights')]);
      if (latest && latest.ts) render(latest, insights);
      await refreshInventoryAndDb();
    } catch (_) {
      // ignore
    }

    connectWS();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
