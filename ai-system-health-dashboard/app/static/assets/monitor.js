(function() {
  'use strict';
  
  console.log('[MONITOR] Script loaded');
  
  let ws = null;
  let canvases = {};
  let history = { time: [], cpu: [], ram: [], disk: [] };
  const MAX_HISTORY = 60;
  const LOG_KEY = 'ashd_system_logs_v1';
  const LOG_MAX = 60;

  function readSystemLogs() {
    try {
      const raw = localStorage.getItem(LOG_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  async function fetchHostsForButtons() {
    try {
      const resp = await fetch('/api/hosts', { credentials: 'same-origin' });
      if (!resp.ok) return [];
      const data = await resp.json();
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  async function fetchHostStatus(hostId) {
    try {
      const resp = await fetch(`/api/hosts/${encodeURIComponent(String(hostId))}/status`, { credentials: 'same-origin' });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) {
      return null;
    }
  }

  function renderHostButtons(hosts) {
    const wrap = document.getElementById('dashHostButtons');
    if (!wrap) return;

    const list = Array.isArray(hosts) ? hosts : [];
    wrap.innerHTML = '';
    if (!list.length) return;

    for (const h of list) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'hostBtn unknown';
      const name = (h && h.name) ? String(h.name) : 'host';
      const addr = (h && h.address) ? String(h.address) : '';
      btn.textContent = addr ? `${name} · ${addr}` : name;
      try {
        btn.dataset.hostId = String(h && h.id != null ? h.id : '');
      } catch (e) {
        // ignore
      }
      btn.addEventListener('click', () => {
        if (h && h.id != null) window.location.href = `/host/${h.id}`;
      });
      wrap.appendChild(btn);
    }
  }

  async function applyHostButtonStatuses(hosts) {
    const list = Array.isArray(hosts) ? hosts : [];
    const wrap = document.getElementById('dashHostButtons');
    if (!wrap || !list.length) return;

    const tasks = list
      .filter(h => h && h.id != null)
      .map(async (h) => {
        const res = await fetchHostStatus(h.id);
        const s = res && res.status ? String(res.status).toLowerCase() : 'unknown';
        const btn = wrap.querySelector(`button[data-host-id="${String(h.id)}"]`);
        if (!btn) return;
        btn.classList.remove('ok', 'crit', 'unknown');
        if (s === 'ok') btn.classList.add('ok');
        else if (s === 'crit') btn.classList.add('crit');
        else btn.classList.add('unknown');
      });

    await Promise.allSettled(tasks);
  }

  async function refreshHostButtons() {
    const hosts = await fetchHostsForButtons();
    renderHostButtons(hosts);
    await applyHostButtonStatuses(hosts);
  }

  function renderSystemLogs() {
    const linesEl = document.getElementById('logLines');
    const pillEl = document.getElementById('pill');
    if (!linesEl || !pillEl) return;

    const logs = readSystemLogs();
    if (!logs.length) {
      linesEl.textContent = '—';
      pillEl.textContent = '—';
      pillEl.className = 'pill';
      return;
    }

    const recent = logs.slice(-12);
    const text = recent
      .map(l => {
        const ts = l && l.ts ? new Date(l.ts * 1000).toLocaleTimeString() : '';
        const lvl = (l && l.level ? String(l.level).toUpperCase() : 'INFO');
        const msg = l && l.message ? String(l.message) : '';
        return `[${ts}] ${lvl}: ${msg}`;
      })
      .join('\n');
    linesEl.textContent = text;

    const sev = logs.reduce(
      (acc, l) => {
        const lvl = (l && l.level ? String(l.level).toLowerCase() : 'info');
        if (lvl === 'error') acc.error += 1;
        else if (lvl === 'warn' || lvl === 'warning') acc.warn += 1;
        else acc.info += 1;
        return acc;
      },
      { error: 0, warn: 0, info: 0 },
    );

    if (sev.error > 0) {
      pillEl.textContent = `${sev.error} error`;
      pillEl.className = 'pill crit';
    } else if (sev.warn > 0) {
      pillEl.textContent = `${sev.warn} warn`;
      pillEl.className = 'pill warn';
    } else {
      pillEl.textContent = 'ok';
      pillEl.className = 'pill ok';
    }
  }

  function formatBytes(b) {
    if (!b) return '—';
    const u = ['B', 'KB', 'MB', 'GB'];
    let n = b, i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return n.toFixed(1) + ' ' + u[i];
  }

  function drawSparkline(canvas, data, color) {
    if (!canvas) {
      console.warn('[MONITOR] Canvas is null in drawSparkline');
      return;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.warn('[MONITOR] Could not get 2D context');
      return;
    }
    
    const w = canvas.width;
    const h = canvas.height;
    
    // Clear with dark background
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(15, 25, 55, 0.8)';
    ctx.fillRect(0, 0, w, h);
    
    if (!data || data.length < 1) {
      // Draw empty state - just a centerline
      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();
      return;
    }
    
    // Calculate padding and scaling
    const p = 6; // padding
    const chartW = w - 2 * p;
    const chartH = h - 2 * p;
    const stepX = chartW / Math.max(data.length - 1, 1);
    
    // Draw filled area
    ctx.fillStyle = color.replace(')', ', 0.15)').replace('rgb', 'rgba');
    ctx.beginPath();
    ctx.moveTo(p, h - p);
    
    for (let i = 0; i < data.length; i++) {
      const x = p + i * stepX;
      const val = Math.max(0, Math.min(100, data[i]));
      const y = p + chartH - (val / 100) * chartH;
      if (i === 0) ctx.lineTo(x, y);
      else ctx.lineTo(x, y);
    }
    
    ctx.lineTo(p + (data.length - 1) * stepX, h - p);
    ctx.closePath();
    ctx.fill();
    
    // Draw line
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    
    for (let i = 0; i < data.length; i++) {
      const x = p + i * stepX;
      const val = Math.max(0, Math.min(100, data[i]));
      const y = p + chartH - (val / 100) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    
    ctx.stroke();
  }

  function updateCharts(c, r, d) {
    const t = new Date();
    const ts = String(t.getHours()).padStart(2, '0') + ':' + String(t.getMinutes()).padStart(2, '0') + ':' + String(t.getSeconds()).padStart(2, '0');
    
    history.time.push(ts);
    history.cpu.push(Math.min(c || 0, 100));
    history.ram.push(Math.min(r || 0, 100));
    history.disk.push(Math.min(d || 0, 100));

    if (history.time.length > MAX_HISTORY) {
      history.time.shift();
      history.cpu.shift();
      history.ram.shift();
      history.disk.shift();
    }

    // Draw using canvas API directly
    drawSparkline(canvases.cpu, history.cpu, '#ff6b6b');
    drawSparkline(canvases.ram, history.ram, '#4ecdc4');
    drawSparkline(canvases.disk, history.disk, '#ffd93d');
  }

  function updateMetrics(data) {
    if (!data || !data.sample) return;
    const s = data.sample, i = data.insights || {};
    
    if (s.cpu_percent != null) {
      const v = s.cpu_percent.toFixed(1) + '%';
      const e1 = document.getElementById('cpuLbl'), e2 = document.getElementById('cpuV');
      if (e1) e1.textContent = v;
      if (e2) e2.textContent = v;
    }
    
    if (s.mem_percent != null) {
      const e1 = document.getElementById('memLbl'), e2 = document.getElementById('ramV');
      if (e1) e1.textContent = formatBytes(s.mem_used_bytes) + ' / ' + formatBytes(s.mem_total_bytes);
      if (e2) e2.textContent = s.mem_percent.toFixed(1) + '%';
    }
    
    if (s.disk && s.disk[0]) {
      const d = s.disk[0];
      const e1 = document.getElementById('diskLbl'), e2 = document.getElementById('diskV');
      if (e1) e1.textContent = formatBytes(d.used_bytes) + ' / ' + formatBytes(d.total_bytes);
      if (e2) e2.textContent = d.percent.toFixed(1) + '%';
    }
    
    if (s.uptime_seconds != null) {
      const days = Math.floor(s.uptime_seconds / 86400), hrs = Math.floor((s.uptime_seconds % 86400) / 3600);
      const e = document.getElementById('uptimeV');
      if (e) e.textContent = (days > 0 ? days + 'd ' : '') + hrs + 'h';
    }
    
    if (s.hostname) {
      const e = document.getElementById('host');
      if (e) e.textContent = s.hostname;
    }
    
    const an = i.anomalies || [];
    const st = document.getElementById('diagStatus'), tx = document.getElementById('diagText');
    if (an.length > 0) {
      if (st) st.textContent = 'ALERT';
      if (tx) tx.textContent = an.map(a => a.message).join('; ');
    } else {
      if (st) st.textContent = 'STABLE';
      if (tx) tx.textContent = 'All systems operating normally';
    }
    
    updateCharts(s.cpu_percent, s.mem_percent, s.disk && s.disk[0] ? s.disk[0].percent : 0);
  }

  function connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = proto + '://' + location.host + '/ws/metrics';
    const conn = document.getElementById('conn');
    if (conn) conn.textContent = 'connecting…';
    
    ws = new WebSocket(url);
    ws.onopen = () => { if (conn) conn.textContent = 'connected'; };
    ws.onmessage = (e) => { try { updateMetrics(JSON.parse(e.data)); } catch (err) { console.error('Parse:', err); } };
    ws.onerror = () => { if (conn) conn.textContent = 'error'; };
    ws.onclose = () => { if (conn) conn.textContent = 'disconnected'; setTimeout(connectWebSocket, 3000); };
  }

  function updateClock() {
    const now = new Date();
    const e1 = document.getElementById('time'), e2 = document.getElementById('subtime'), e3 = document.getElementById('date');
    if (e1) e1.textContent = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
    if (e2) e2.textContent = String(now.getSeconds()).padStart(2, '0') + '.' + String(now.getMilliseconds()).padStart(3, '0');
    if (e3) e3.textContent = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  function setupSidebar() {
    const body = document.body;
    body.classList.add('sidebarAutoHide');
    const toggle = document.getElementById('sideToggle');
    if (toggle) {
      toggle.addEventListener('click', (e) => { e.preventDefault(); body.classList.toggle('sidebarOpen'); });
    }
    document.addEventListener('mousemove', (e) => {
      if (e.clientX < 50) body.classList.add('sidebarHover');
      else if (!body.classList.contains('sidebarOpen')) body.classList.remove('sidebarHover');
    });
  }

  function init() {
    console.log('[MONITOR] Initializing dashboard');
    setupSidebar();
    updateClock();
    setInterval(updateClock, 100);

    renderSystemLogs();
    setInterval(renderSystemLogs, 1500);
    window.addEventListener('storage', (e) => {
      if (e && e.key === LOG_KEY) renderSystemLogs();
    });

    refreshHostButtons();
    setInterval(refreshHostButtons, 6000);
    window.addEventListener('ashd:hosts-updated', () => {
      refreshHostButtons();
    });

    // Get canvas references
    canvases.cpu = document.getElementById('cpuSpark');
    canvases.ram = document.getElementById('memSpark');
    canvases.disk = document.getElementById('diskSpark');

    console.log('[MONITOR] Canvas elements:', {
      cpu: canvases.cpu ? 'found' : 'MISSING',
      ram: canvases.ram ? 'found' : 'MISSING',
      disk: canvases.disk ? 'found' : 'MISSING'
    });

    // Draw initial empty charts
    if (canvases.cpu) drawSparkline(canvases.cpu, [0], '#ff6b6b');
    if (canvases.ram) drawSparkline(canvases.ram, [0], '#4ecdc4');
    if (canvases.disk) drawSparkline(canvases.disk, [0], '#ffd93d');

    console.log('[MONITOR] Connecting WebSocket...');
    connectWebSocket();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
