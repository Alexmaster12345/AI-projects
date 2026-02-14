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
    pSyslog: document.getElementById('pSyslog'),
    pNetflow: document.getElementById('pNetflow'),

    // Agent metric values in chart titles
    cpuValue: document.getElementById('cpuValue'),
    memValue: document.getElementById('memValue'),
    diskValue: document.getElementById('diskValue'),
    loadValue: document.getElementById('loadValue'),
    netSentValue: document.getElementById('netSentValue'),
    netRecvValue: document.getElementById('netRecvValue'),

    // Charts
    cpuChart: document.getElementById('cpuChart'),
    memChart: document.getElementById('memChart'),
    diskChart: document.getElementById('diskChart'),
    loadChart: document.getElementById('loadChart'),
    netSentChart: document.getElementById('netSentChart'),
    netRecvChart: document.getElementById('netRecvChart'),

    problemsSection: document.getElementById('problemsSection'),
    problemsList: document.getElementById('problemsList'),

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
      ['syslog', els.pSyslog],
      ['netflow', els.pNetflow],
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

      // Log problems for critical services
      if (currentHost && st && st.status === 'crit' && st.message) {
        addHostProblem(currentHost.id, 'warning', `${key.toUpperCase()} check failed: ${st.message}`);
      }
    }
  }

  function setupSidebarSearch() {
    if (!els.sideSearch) return;
    els.sideSearch.addEventListener('input', (e) => {
      const q = (e.target.value || '').trim().toLowerCase();
      const items = els.sideNav?.querySelectorAll('.sideItem') || [];
      items.forEach(item => {
        const label = item.getAttribute('data-label') || '';
        if (label.toLowerCase().includes(q)) {
          item.style.display = '';
        } else {
          item.style.display = 'none';
        }
      });
    });

    // Problems button toggle
    const problemsBtn = els.sideNav?.querySelector('.sideProblems');
    if (problemsBtn) {
      problemsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (els.problemsSection) {
          const isVisible = els.problemsSection.style.display !== 'none';
          els.problemsSection.style.display = isVisible ? 'none' : '';
          problemsBtn.classList.toggle('active', !isVisible);
        }
      });
    }
  }

  function getHostIdFromPath() {
    // /host/{id}
    const parts = (location.pathname || '').split('/').filter(Boolean);
    const last = parts[parts.length - 1] || '';
    const n = Number(last);
    return Number.isFinite(n) ? String(Math.trunc(n)) : null;
  }

  let currentHost = null;

  async function loadHost(hostId) {
    const h = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}`);
    if (!h) throw new Error(`Host not found: ${hostId}`);

    currentHost = h; // Store for WebSocket filtering

    setText(els.name, h.name);
    setText(els.addr, h.address);
    setText(els.type, h.type || '—');
    setText(els.active, String(!!h.is_active));
    setText(els.created, h.created_ts != null ? fmtTs(h.created_ts) : '—');

    const tags = Array.isArray(h.tags) ? h.tags : [];
    setText(els.tags, tags.length ? tags.join(', ') : '—');
    setText(els.notes, h.notes || '—');

    try {
      document.title = `ASHD · ${h.name || 'Host'}`;
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

  async function loadStatus(hostId) {
    const r = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}/status`);
    applyStatus(r ? r : null);
  }

  function applyStatus(st) {
    if (!st) {
      setText(els.status, 'ISSUE');
      setText(els.latency, '—');
      setText(els.checked, '—');
      setText(els.msg, '—');
      els.status.classList.remove('ok', 'crit');
      els.status.classList.add('crit');
      return;
    }

    const s = (st.status ? String(st.status).toLowerCase() : 'unknown');
    const isOk = s === 'ok';
    els.status.classList.remove('ok', 'crit');
    els.status.classList.add(isOk ? 'ok' : 'crit');
    setText(els.status, isOk ? 'OK' : 'ISSUE');
    setText(els.latency, st.latency_ms != null ? `${Math.round(Number(st.latency_ms))} ms` : '—');
    setText(els.checked, st.checked_ts != null ? fmtTs(st.checked_ts) : '—');
    setText(els.msg, st.message ? st.message : '—');

    // Log problems
    if (currentHost) {
      if (!isOk && st.message) {
        addHostProblem(currentHost.id, 'error', `Host unreachable: ${st.message}`);
      }
    }
  }

  async function loadChecksOnce(hostId) {
    const r = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}/checks`);
    applyChecks(r || {});
  }

  async function loadAgentMetrics(hostId) {
    try {
      const r = await fetchJson(`/api/hosts/${encodeURIComponent(String(hostId))}/metrics`);
      if (!r || r.status === 'no_data') {
        // Clear chart title values
        setText(els.cpuValue, '—');
        setText(els.memValue, '—');
        setText(els.diskValue, '—');
        setText(els.loadValue, '—');
        setText(els.netSentValue, '—');
        setText(els.netRecvValue, '—');
        return;
      }

      // Update chart title values
      setText(els.cpuValue, r.cpu_percent != null ? `${Number(r.cpu_percent).toFixed(1)}%` : '—');
      setText(els.memValue, r.mem_percent != null ? `${Number(r.mem_percent).toFixed(1)}%` : '—');
      setText(els.diskValue, r.disk_percent != null ? `${Number(r.disk_percent).toFixed(1)}%` : '—');
      setText(els.loadValue, r.load1 != null ? Number(r.load1).toFixed(2) : '—');

      // Update charts
      if (r.cpu_percent != null) cpuChart.add(Number(r.cpu_percent));
      if (r.mem_percent != null) memChart.add(Number(r.mem_percent));
      if (r.disk_percent != null) diskChart.add(Number(r.disk_percent));
      if (r.load1 != null) loadChart.add(Number(r.load1));

      // Compute network rates (bytes per second)
      const ts = r.received_ts || r.timestamp || Date.now() / 1000;
      if (lastNetTs != null && r.net_bytes_sent != null && r.net_bytes_recv != null) {
        const dt = ts - lastNetTs;
        if (dt > 0) {
          const sentRate = (r.net_bytes_sent - lastNetSent) / dt;
          const recvRate = (r.net_bytes_recv - lastNetRecv) / dt;
          netSentChart.add(sentRate);
          netRecvChart.add(recvRate);
          // Update chart title values with rates
          setText(els.netSentValue, fmtBytes(sentRate) + '/s');
          setText(els.netRecvValue, fmtBytes(recvRate) + '/s');
        }
      } else {
        setText(els.netSentValue, '—');
        setText(els.netRecvValue, '—');
      }
      lastNetTs = ts;
      lastNetSent = r.net_bytes_sent;
      lastNetRecv = r.net_bytes_recv;
    } catch (e) {
      // ignore
    }
  }

  function fmtDuration(sec) {
    const days = Math.floor(sec / 86400);
    const hrs = Math.floor((sec % 86400) / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    if (days > 0) return `${days}d ${hrs}h ${mins}m`;
    if (hrs > 0) return `${hrs}h ${mins}m`;
    return `${mins}m`;
  }

  function fmtBytes(b) {
    if (!b || b === 0) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let n = Number(b), i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
  }

  // Problems history management
  function getHostProblems(hostId) {
    const key = `ashd_problems_${hostId}`;
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function addHostProblem(hostId, severity, message) {
    const problems = getHostProblems(hostId);
    const problem = {
      ts: Date.now() / 1000,
      severity, // 'error' or 'warning'
      message,
    };
    problems.unshift(problem);
    // Keep only last 100 problems
    if (problems.length > 100) problems.splice(100);
    const key = `ashd_problems_${hostId}`;
    try {
      localStorage.setItem(key, JSON.stringify(problems));
    } catch (_) {
      // ignore quota errors
    }
    renderProblems(problems);
  }

  function renderProblems(problems) {
    if (!els.problemsList) return;
    if (problems.length === 0) {
      els.problemsList.innerHTML = '<div class="muted">No problems recorded.</div>';
      return;
    }
    els.problemsList.innerHTML = problems.map(p => `
      <div class="problemItem ${p.severity}">
        <div class="problemTime">${fmtTs(p.ts)}</div>
        <div class="problemText">${escapeHtml(p.message)}</div>
      </div>
    `).join('');
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Simple time-series chart
  class MiniChart {
    constructor(canvas, maxPoints = 30) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.maxPoints = maxPoints;
      this.data = [];
      this.resize();
    }

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      this.canvas.width = rect.width * window.devicePixelRatio;
      this.canvas.height = rect.height * window.devicePixelRatio;
      this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }

    add(value) {
      this.data.push(value);
      if (this.data.length > this.maxPoints) this.data.shift();
      this.draw();
    }

    draw() {
      const ctx = this.ctx;
      const w = this.canvas.width / window.devicePixelRatio;
      const h = this.canvas.height / window.devicePixelRatio;
      ctx.clearRect(0, 0, w, h);

      if (this.data.length < 2) return;

      const step = w / (this.maxPoints - 1);
      const max = Math.max(...this.data, 1);
      const min = 0;

      // Grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = (h / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Line
      ctx.strokeStyle = '#55ffa6';
      ctx.lineWidth = 2;
      ctx.beginPath();
      this.data.forEach((v, i) => {
        const x = i * step;
        const y = h - ((v - min) / (max - min)) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Fill
      ctx.fillStyle = 'rgba(85, 255, 166, 0.1)';
      ctx.beginPath();
      ctx.moveTo(0, h);
      this.data.forEach((v, i) => {
        const x = i * step;
        const y = h - ((v - min) / (max - min)) * h;
        ctx.lineTo(x, y);
      });
      ctx.lineTo((this.data.length - 1) * step, h);
      ctx.closePath();
      ctx.fill();
    }
  }

  const cpuChart = new MiniChart(els.cpuChart);
  const memChart = new MiniChart(els.memChart);
  const diskChart = new MiniChart(els.diskChart);
  const loadChart = new MiniChart(els.loadChart);
  const netSentChart = new MiniChart(els.netSentChart);
  const netRecvChart = new MiniChart(els.netRecvChart);

  // Track previous network values to compute rates
  let lastNetTs = null;
  let lastNetSent = null;
  let lastNetRecv = null;

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
        } else if (msg.type === 'agent_report' && currentHost) {
          // Real-time agent report
          const report = msg.report;
          if (!report) return;

          // Check if this report is for the current host (by name or address)
          const hostname = msg.hostname || '';
          if (hostname !== currentHost.name && hostname !== currentHost.address) {
            // Try fuzzy matching (space vs dash)
            const norm = (s) => s.replace(' ', '-').replace('-', ' ').toLowerCase();
            if (norm(hostname) !== norm(currentHost.name)) return;
          }

          // Update chart title values
          setText(els.cpuValue, report.cpu_percent != null ? `${Number(report.cpu_percent).toFixed(1)}%` : '—');
          setText(els.memValue, report.mem_percent != null ? `${Number(report.mem_percent).toFixed(1)}%` : '—');
          setText(els.diskValue, report.disk_percent != null ? `${Number(report.disk_percent).toFixed(1)}%` : '—');
          setText(els.loadValue, report.load1 != null ? Number(report.load1).toFixed(2) : '—');

          // Update charts
          if (report.cpu_percent != null) cpuChart.add(Number(report.cpu_percent));
          if (report.mem_percent != null) memChart.add(Number(report.mem_percent));
          if (report.disk_percent != null) diskChart.add(Number(report.disk_percent));
          if (report.load1 != null) loadChart.add(Number(report.load1));

          // Compute network rates (bytes per second)
          const ts = report.received_ts || report.timestamp || Date.now() / 1000;
          if (lastNetTs != null && report.net_bytes_sent != null && report.net_bytes_recv != null) {
            const dt = ts - lastNetTs;
            if (dt > 0) {
              const sentRate = (report.net_bytes_sent - lastNetSent) / dt;
              const recvRate = (report.net_bytes_recv - lastNetRecv) / dt;
              netSentChart.add(sentRate);
              netRecvChart.add(recvRate);
              // Update chart title values with rates
              setText(els.netSentValue, fmtBytes(sentRate) + '/s');
              setText(els.netRecvValue, fmtBytes(recvRate) + '/s');
            }
          }
          lastNetTs = ts;
          lastNetSent = report.net_bytes_sent;
          lastNetRecv = report.net_bytes_recv;
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

      try {
        await loadHost(hostId);
        await loadStatus(hostId);
        await loadChecksOnce(hostId);
        await loadAgentMetrics(hostId);

        // Load and render existing problems
        const problems = getHostProblems(hostId);
        renderProblems(problems);
      } catch (e) {
        setErr(e.message);
      }
      connectWS(hostId);

      // Poll as a fallback so checks remain live even if WS is blocked.
      setInterval(() => {
        loadStatus(hostId).catch(() => null);
        loadChecksOnce(hostId).catch(() => null);
        loadAgentMetrics(hostId).catch(() => null);
      }, 5_000);

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
