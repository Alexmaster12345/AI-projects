(() => {
  function $$(id) { return document.getElementById(id); }
  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element: #${id}`);
    return el;
  }

  // ---- Helpers ----
  function fmtBytes(b) {
    b = Number(b) || 0;
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB';
    if (b >= 1048576)    return (b / 1048576).toFixed(1) + ' MB';
    if (b >= 1024)       return (b / 1024).toFixed(1) + ' KB';
    return b + ' B';
  }
  function fmtUptime(s) {
    s = Number(s) || 0;
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }
  function fmtTs(ts) {
    const n = Number(ts);
    if (!Number.isFinite(n) || n <= 0) return '—';
    return new Date(n * 1000).toLocaleString();
  }
  function statusClass(pct) {
    pct = Number(pct) || 0;
    if (pct >= 90) return 'crit';
    if (pct >= 70) return 'warn';
    return 'ok';
  }
  function sevClass(st) {
    const s = (st && st.status ? String(st.status) : 'unknown').toLowerCase();
    if (s === 'ok') return 'ok';
    if (s === 'crit') return 'crit';
    return 'unknown';
  }
  function fmtProto(st) {
    if (!st) return '—';
    const s = (st.status || 'unknown').toLowerCase();
    const lat = st.latency_ms != null ? `${Math.round(Number(st.latency_ms))} ms` : '';
    const msg = st.message ? String(st.message) : '';
    return [s.toUpperCase(), lat, msg].filter(Boolean).join(' · ');
  }

  // ---- Ring buffer (frontend rolling history, max 120 pts = 2 min at 1s) ----
  const MAX_PTS = 120;
  const ring = { labels:[], cpu:[], mem:[], disk:[], netSent:[], netRecv:[], rawSent:[], rawRecv:[], ts:[], gpus:{} };
  // ring.gpus[idx] = [] — one array per GPU index
  let gpuCount = 0;  // number of GPUs detected

  function ringPush(label, cpu, mem, disk, gpuList, rawSent, rawRecv, ts) {
    let sentRate = 0, recvRate = 0;
    const n = ring.ts.length;
    if (n > 0) {
      const dt = Math.max(ts - ring.ts[n - 1], 0.5);
      sentRate = Math.max(0, (rawSent - ring.rawSent[n - 1]) / dt);
      recvRate = Math.max(0, (rawRecv - ring.rawRecv[n - 1]) / dt);
    }
    ring.labels.push(label); ring.cpu.push(cpu); ring.mem.push(mem); ring.disk.push(disk);
    ring.netSent.push(sentRate); ring.netRecv.push(recvRate);
    ring.rawSent.push(rawSent);  ring.rawRecv.push(rawRecv); ring.ts.push(ts);
    // Per-GPU
    const gpus = Array.isArray(gpuList) ? gpuList : [];
    for (const g of gpus) {
      const idx = g.index != null ? g.index : 0;
      if (!ring.gpus[idx]) ring.gpus[idx] = [];
      ring.gpus[idx].push(Math.round(g.percent || 0));
      if (ring.gpus[idx].length > MAX_PTS) ring.gpus[idx].shift();
    }
    if (ring.labels.length > MAX_PTS) {
      ring.labels.shift(); ring.cpu.shift(); ring.mem.shift(); ring.disk.shift();
      ring.netSent.shift(); ring.netRecv.shift();
      ring.rawSent.shift(); ring.rawRecv.shift(); ring.ts.shift();
    }
  }

  function tsLabel(ts) {
    const d = new Date(ts * 1000);
    return d.getHours().toString().padStart(2,'0') + ':' +
           d.getMinutes().toString().padStart(2,'0') + ':' +
           d.getSeconds().toString().padStart(2,'0');
  }

  function seedRing(history) {
    for (const h of history)
      ringPush(tsLabel(h.ts), h.cpu||0, h.mem||0, h.disk||0,
               h.gpu||[], h.net_sent||0, h.net_recv||0, h.ts);
  }

  // ---- Chart factory ----
  function makeLineChart(canvasId, label, color) {
    const canvas = $$(canvasId);
    if (!canvas) return null;
    return new Chart(canvas, {
      type: 'line',
      data: { labels: [], datasets: [{ label, data: [],
        borderColor: color,
        backgroundColor: color.replace('rgb(','rgba(').replace(')',',0.13)'),
        fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        plugins: { legend: { display: false }, tooltip: { mode:'index', intersect:false } },
        scales: {
          x: { display: false },
          y: { min:0, max:100,
            ticks: { color:'rgba(255,255,255,0.3)', font:{size:10}, maxTicksLimit:4, callback: v => v+'%' },
            grid: { color:'rgba(255,255,255,0.05)' } }
        }
      }
    });
  }

  function makeNetChart(canvasId) {
    const canvas = $$(canvasId);
    if (!canvas) return null;
    return new Chart(canvas, {
      type: 'line',
      data: { labels: [], datasets: [
        { label:'Upload ↑',   data:[], borderColor:'rgb(99,179,237)',  backgroundColor:'rgba(99,179,237,0.1)',  fill:true, tension:0.3, borderWidth:1.5, pointRadius:0 },
        { label:'Download ↓', data:[], borderColor:'rgb(72,187,120)',  backgroundColor:'rgba(72,187,120,0.1)',  fill:true, tension:0.3, borderWidth:1.5, pointRadius:0 },
      ]},
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        plugins: {
          legend: { display:true, labels:{ color:'rgba(255,255,255,0.45)', font:{size:10}, boxWidth:10 } },
          tooltip: { mode:'index', intersect:false, callbacks:{ label: ctx => `${ctx.dataset.label}: ${fmtBytes(ctx.raw)}/s` } }
        },
        scales: {
          x: { display: false },
          y: { min:0,
            ticks: { color:'rgba(255,255,255,0.3)', font:{size:10}, maxTicksLimit:4, callback: v => fmtBytes(v)+'/s' },
            grid: { color:'rgba(255,255,255,0.05)' } }
        }
      }
    });
  }

  const GPU_COLORS = [
    'rgb(72,187,120)',  'rgb(246,173,85)',  'rgb(237,100,166)',
    'rgb(129,230,217)', 'rgb(252,211,77)',  'rgb(160,174,192)',
  ];

  let charts = {};
  // charts.gpus[idx] = Chart instance

  function initCharts() {
    charts.cpu  = makeLineChart('chartCpu',  'CPU %',  'rgb(99,179,237)');
    charts.mem  = makeLineChart('chartMem',  'RAM %',  'rgb(154,117,234)');
    charts.disk = makeLineChart('chartDisk', 'Disk %', 'rgb(246,173,85)');
    charts.net  = makeNetChart('chartNet');
    charts.gpus = {};
  }

  function ensureGpuChart(idx, name) {
    if (charts.gpus[idx]) return;
    const color = GPU_COLORS[idx % GPU_COLORS.length];
    const canvasId = `chartGpu${idx}`;
    // Create card in DOM if not present
    let card = document.getElementById(`chartGpuCard${idx}`);
    if (!card) {
      const grid = $$('hmChartsGrid');
      if (!grid) return;
      card = document.createElement('div');
      card.className = 'hmChartCard';
      card.id = `chartGpuCard${idx}`;
      const title = document.createElement('div');
      title.className = 'hmChartTitle';
      title.textContent = name ? `GPU ${idx}: ${name} %` : `GPU ${idx} Usage %`;
      const wrap = document.createElement('div');
      wrap.className = 'hmChartWrap';
      const canvas = document.createElement('canvas');
      canvas.id = canvasId;
      wrap.appendChild(canvas);
      card.appendChild(title);
      card.appendChild(wrap);
      grid.appendChild(card);
    }
    charts.gpus[idx] = makeLineChart(canvasId, `GPU ${idx} %`, color);
  }

  function redrawCharts() {
    const L = ring.labels;
    if (charts.cpu)  { charts.cpu.data.labels  = L; charts.cpu.data.datasets[0].data  = ring.cpu;  charts.cpu.update('none'); }
    if (charts.mem)  { charts.mem.data.labels  = L; charts.mem.data.datasets[0].data  = ring.mem;  charts.mem.update('none'); }
    if (charts.disk) { charts.disk.data.labels = L; charts.disk.data.datasets[0].data = ring.disk; charts.disk.update('none'); }
    if (charts.net)  { charts.net.data.labels  = L; charts.net.data.datasets[0].data  = ring.netSent; charts.net.data.datasets[1].data = ring.netRecv; charts.net.update('none'); }
    for (const [idx, ch] of Object.entries(charts.gpus)) {
      const data = ring.gpus[idx] || [];
      ch.data.labels = L.slice(-data.length);
      ch.data.datasets[0].data = data;
      ch.update('none');
    }
  }

  // ---- Tiles ----
  function setTile(id, val, cls) {
    const el = $$(id); if (!el) return;
    el.textContent = val;
    el.className = 'hmTileVal' + (cls ? ' ' + cls : '');
  }

  function ensureGpuTile(idx, name) {
    const tileId = `tGpu${idx}`;
    if ($$(tileId)) return;
    const tiles = $$('hmTiles');
    if (!tiles) return;
    const tile = document.createElement('div');
    tile.className = 'hmTile';
    tile.id = `tGpuTile${idx}`;
    const label = document.createElement('div');
    label.className = 'hmTileLabel';
    label.textContent = name ? `GPU ${idx}` : `GPU ${idx}`;
    if (name) label.title = name;
    const val = document.createElement('div');
    val.className = 'hmTileVal';
    val.id = tileId;
    val.textContent = '—';
    tile.appendChild(label);
    tile.appendChild(val);
    tiles.appendChild(tile);
    // Also add VRAM tile
    const vramTile = document.createElement('div');
    vramTile.className = 'hmTile';
    vramTile.id = `tVramTile${idx}`;
    const vramLabel = document.createElement('div');
    vramLabel.className = 'hmTileLabel';
    vramLabel.textContent = `VRAM ${idx}`;
    const vramVal = document.createElement('div');
    vramVal.className = 'hmTileVal';
    vramVal.id = `tVram${idx}`;
    vramVal.textContent = '—';
    vramTile.appendChild(vramLabel);
    vramTile.appendChild(vramVal);
    tiles.appendChild(vramTile);
    // Temp tile
    const tempTile = document.createElement('div');
    tempTile.className = 'hmTile';
    tempTile.id = `tTempTile${idx}`;
    const tempLabel = document.createElement('div');
    tempLabel.className = 'hmTileLabel';
    tempLabel.textContent = `GPU${idx} Temp`;
    const tempVal = document.createElement('div');
    tempVal.className = 'hmTileVal';
    tempVal.id = `tTemp${idx}`;
    tempVal.textContent = '—';
    tempTile.appendChild(tempLabel);
    tempTile.appendChild(tempVal);
    tiles.appendChild(tempTile);
  }

  function applyGpuTiles(gpuList) {
    if (!Array.isArray(gpuList) || !gpuList.length) return;
    for (const g of gpuList) {
      const idx = g.index != null ? g.index : 0;
      ensureGpuTile(idx, g.name || '');
      ensureGpuChart(idx, g.name || '');
      const pct = Math.round(g.percent || 0);
      setTile(`tGpu${idx}`, pct + '%', statusClass(pct));
      if (g.memory_used_mb != null && g.memory_total_mb != null) {
        setTile(`tVram${idx}`, `${Math.round(g.memory_used_mb)}/${Math.round(g.memory_total_mb)} MB`);
      }
      if (g.temperature != null) {
        const t = Math.round(g.temperature);
        setTile(`tTemp${idx}`, `${t}°C`, t >= 85 ? 'crit' : t >= 70 ? 'warn' : 'ok');
      }
    }
  }

  function applyTiles(latest, sentRate, recvRate) {
    const cpu  = latest.cpu    || {};
    const mem  = latest.memory || {};
    const disk = latest.disk   || {};
    const cpuPct  = Math.round(cpu.percent  || 0);
    const memPct  = Math.round(mem.percent  || 0);
    const diskPct = Math.round(disk.percent || 0);
    setTile('tCpu',     cpuPct  + '%', statusClass(cpuPct));
    setTile('tMem',     memPct  + '%', statusClass(memPct));
    setTile('tDisk',    diskPct + '%', statusClass(diskPct));
    setTile('tNetSent', fmtBytes(sentRate) + '/s');
    setTile('tNetRecv', fmtBytes(recvRate) + '/s');
    setTile('tUptime',  fmtUptime(latest.uptime || 0));
    setTile('tProcs',   String(latest.processes || 0));
    if (Array.isArray(latest.gpu) && latest.gpu.length) {
      applyGpuTiles(latest.gpu);
    }
  }

  // ---- Push one new sample into ring and refresh UI ----
  function pushLatestToRing(data) {
    const latest  = data.latest || {};
    const cpu     = latest.cpu    || {};
    const mem     = latest.memory || {};
    const disk    = latest.disk   || {};
    const gpuList = Array.isArray(latest.gpu) ? latest.gpu : [];
    const net     = latest.network || {};
    const rawSent = Number(net.bytes_sent || 0);
    const rawRecv = Number(net.bytes_recv || 0);
    const ts      = data.last_seen || (Date.now() / 1000);

    ringPush(tsLabel(ts),
      Math.round(cpu.percent  || 0),
      Math.round(mem.percent  || 0),
      Math.round(disk.percent || 0),
      gpuList,
      rawSent, rawRecv, ts);

    // Tiles: use last two ring entries for live net rate
    const n = ring.netSent.length;
    const sentRate = n > 0 ? ring.netSent[n-1] : 0;
    const recvRate = n > 0 ? ring.netRecv[n-1] : 0;
    applyTiles(latest, sentRate, recvRate);

    // Agent badge + last seen
    const badge = $$('hmAgentBadge');
    if (badge) {
      if (data.online) {
        badge.textContent = '● Agent Online';
        badge.style.color = '#4caf50';
        badge.style.background = 'rgba(76,175,80,0.12)';
        badge.style.borderColor = 'rgba(76,175,80,0.35)';
      } else {
        badge.textContent = '● Agent Offline';
        badge.style.color = '#9e9e9e';
        badge.style.background = 'rgba(158,158,158,0.10)';
        badge.style.borderColor = 'rgba(158,158,158,0.30)';
      }
    }
    const lsEl = $$('hLastSeen');
    if (lsEl && data.last_seen) lsEl.textContent = fmtTs(data.last_seen);

    redrawCharts();

    // Problem detection → blink + error panel
    const cpuPct  = Math.round(cpu.percent  || 0);
    const memPct  = Math.round(mem.percent  || 0);
    const diskPct = Math.round(disk.percent || 0);
    checkProblems(cpuPct, memPct, diskPct, !data.online, gpuList);

    // Show charts
    const noAgent = $$('hmNoAgent');   if (noAgent)    noAgent.style.display    = 'none';
    const cg      = $$('hmChartsGrid'); if (cg)         cg.style.display         = '';
    const tl      = $$('hmTiles');      if (tl)         tl.style.display         = '';
  }

  // ---- Problem detection & error panel ----
  let _lastReportedProblems = '';
  let _hostLogHostname = '';

  function checkProblems(cpuPct, memPct, diskPct, agentOffline, gpuList) {
    const problems = [];
    if (agentOffline)       problems.push({ level: 'crit', msg: 'Agent offline' });
    if (cpuPct  >= 90)      problems.push({ level: 'crit', msg: `CPU critical: ${cpuPct}%` });
    else if (cpuPct  >= 75) problems.push({ level: 'warn', msg: `CPU high: ${cpuPct}%` });
    if (memPct  >= 90)      problems.push({ level: 'crit', msg: `RAM critical: ${memPct}%` });
    else if (memPct  >= 80) problems.push({ level: 'warn', msg: `RAM high: ${memPct}%` });
    if (diskPct >= 95)      problems.push({ level: 'crit', msg: `Disk critical: ${diskPct}%` });
    else if (diskPct >= 85) problems.push({ level: 'warn', msg: `Disk high: ${diskPct}%` });
    if (Array.isArray(gpuList)) {
      for (const g of gpuList) {
        const idx = g.index != null ? g.index : 0;
        const gpuPct = Math.round(g.percent || 0);
        const temp   = g.temperature != null ? Math.round(g.temperature) : null;
        if (gpuPct >= 95)      problems.push({ level: 'crit', msg: `GPU ${idx} critical: ${gpuPct}%` });
        else if (gpuPct >= 85) problems.push({ level: 'warn', msg: `GPU ${idx} high: ${gpuPct}%` });
        if (temp != null) {
          if (temp >= 90)      problems.push({ level: 'crit', msg: `GPU ${idx} temp critical: ${temp}°C` });
          else if (temp >= 80) problems.push({ level: 'warn', msg: `GPU ${idx} temp high: ${temp}°C` });
        }
      }
    }

    const wrap = $$('hmWrap');
    const panel = $$('hmErrPanel');
    const list  = $$('hmErrList');

    if (!problems.length) {
      if (wrap)  wrap.classList.remove('hasProblem');
      if (panel) panel.style.display = 'none';
      _lastReportedProblems = '';
      return;
    }

    // Blink header
    if (wrap) wrap.classList.add('hasProblem');

    // Show panel
    if (panel) panel.style.display = '';
    const titleEl = $$('hmErrPanelTitle');
    if (titleEl) {
      const hasCrit = problems.some(p => p.level === 'crit');
      titleEl.textContent = hasCrit ? '⚠ Critical Problems Detected' : '⚠ Warnings Detected';
      titleEl.style.color = hasCrit ? '#f44336' : '#ff9800';
    }

    // Report to backend (deduplicated — only when problem set changes)
    const key = problems.map(p => p.msg).join('|');
    if (key !== _lastReportedProblems && _hostLogHostname) {
      _lastReportedProblems = key;
      const hasCrit = problems.some(p => p.level === 'crit');
      fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: hasCrit ? 'crit' : 'warn',
          source: 'host-monitor',
          hostname: _hostLogHostname,
          message: problems.map(p => p.msg).join('; '),
        })
      }).catch(() => null);
    }

    // Render inline problem rows
    if (list) {
      list.innerHTML = '';
      const now = Date.now() / 1000;
      for (const p of problems) {
        const row = document.createElement('div');
        row.className = 'hmErrRow';
        const ts  = document.createElement('span'); ts.className  = 'hmErrTs';    ts.textContent = fmtTs(now);
        const lvl = document.createElement('span'); lvl.className = `hmErrLevel ${p.level}`; lvl.textContent = p.level === 'crit' ? 'CRITICAL' : 'WARN';
        const msg = document.createElement('span'); msg.className = 'hmErrMsg';   msg.textContent = p.msg;
        row.append(ts, lvl, msg);
        list.appendChild(row);
      }
    }
  }

  // ---- Load per-host log history ----
  async function loadHostLogs(hostname) {
    if (!hostname) return;
    try {
      const data = await fetchJson(`/api/logs/host/${encodeURIComponent(hostname)}?limit=50`);
      const logs = data.logs || [];
      if (!logs.length) return;

      const panel = $$('hmErrPanel');
      const list  = $$('hmErrList');
      if (!panel || !list) return;

      panel.style.display = '';

      // Append history section
      const sep = document.createElement('div');
      sep.style.cssText = 'padding:6px 16px;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;opacity:0.35;border-top:1px solid rgba(255,255,255,0.06);margin-top:4px;';
      sep.textContent = 'Recent history';
      list.appendChild(sep);

      for (const l of logs) {
        const row = document.createElement('div');
        row.className = 'hmErrRow';
        const ts  = document.createElement('span'); ts.className  = 'hmErrTs';    ts.textContent = fmtTs(l.ts);
        const lvl = document.createElement('span'); lvl.className = `hmErrLevel ${l.level || 'info'}`; lvl.textContent = l.level === 'crit' ? 'CRITICAL' : (l.level || 'info').toUpperCase();
        const msg = document.createElement('span'); msg.className = 'hmErrMsg';   msg.textContent = l.message || '—';
        row.append(ts, lvl, msg);
        list.appendChild(row);
      }
    } catch(_) {}
  }

  // ---- Initial full load (seeds ring from backend history) ----
  function applyInitialData(data) {
    const latest = data.latest || {};
    const gpuList = Array.isArray(latest.gpu) ? latest.gpu : [];
    gpuCount = gpuList.length;
    // Create GPU tiles + charts for each GPU immediately
    for (const g of gpuList) {
      const idx = g.index != null ? g.index : 0;
      ensureGpuTile(idx, g.name || '');
      ensureGpuChart(idx, g.name || '');
    }
    // Hide the old static GPU tile/card (replaced by dynamic ones)
    const oldTile = $$('tGpuTile'); if (oldTile) oldTile.style.display = 'none';
    const oldCard = $$('chartGpuCard'); if (oldCard) oldCard.style.display = 'none';
    const osEl = $$('hOsType'); if (osEl && data.os_type) osEl.textContent = data.os_type;
    const setText = (id, v) => { const el = $$(id); if (el) el.textContent = v || '—'; };
    setText('hAgentId',  data.agent_id || (data.hostname ? `${data.hostname}-agent` : null));
    setText('hLastSeen', data.last_seen ? fmtTs(data.last_seen) : null);
    seedRing(data.history || []);
    redrawCharts();
    const noAgent = $$('hmNoAgent');   if (noAgent)    noAgent.style.display    = 'none';
    const cg      = $$('hmChartsGrid'); if (cg)         cg.style.display         = '';
    const tl      = $$('hmTiles');      if (tl)         tl.style.display         = '';
  }

  function showNoAgent() {
    const noAgent = $$('hmNoAgent');   if (noAgent)    noAgent.style.display    = '';
    const cg      = $$('hmChartsGrid'); if (cg)         cg.style.display         = 'none';
    const tl      = $$('hmTiles');      if (tl)         tl.style.display         = 'none';
    const badge = $$('hmAgentBadge');
    if (badge) {
      badge.textContent = '✕ No Agent';
      badge.style.color = '#f44336';
      badge.style.background = 'rgba(244,67,54,0.10)';
      badge.style.borderColor = 'rgba(244,67,54,0.30)';
    }
  }

  // ---- Protocol checks ----
  function applyChecks(checks) {
    const c = checks && typeof checks === 'object' ? checks : {};
    for (const [key, elId] of [['icmp','pIcmp'],['ssh','pSsh'],['snmp','pSnmp'],['ntp','pNtp'],['dns','pDns']]) {
      const el = $$(elId);
      if (!el) continue;
      const st = c[key] || null;
      el.className = 'hmProtoVal ' + sevClass(st);
      el.textContent = fmtProto(st);
      if (st && st.checked_ts) el.title = `Last check: ${fmtTs(st.checked_ts)}`;
    }
  }

  // ---- Reachability status ----
  function applyStatus(st) {
    const sev = st && st.status && st.status.toLowerCase() === 'ok' ? 'ok' : 'crit';
    const setText = (id, v) => { const el = $$(id); if (el) el.textContent = v || '—'; };
    setText('hStatus',  sev === 'ok' ? 'OK ✓' : 'ISSUE ✗');
    setText('hLatency', st && st.latency_ms != null ? `${Math.round(Number(st.latency_ms))} ms` : '—');
    setText('hChecked', st && st.checked_ts ? fmtTs(st.checked_ts) : '—');
    setText('hMsg',     st && st.message ? st.message : '—');
    const el = $$('hStatus');
    if (el) { el.className = 'v ' + sev; }
  }

  // ---- Sidebar search ----
  function setupSidebarSearch() {
    const search = $$('sideSearch');
    const nav = $$('sideNav');
    if (!search || !nav) return;
    search.addEventListener('input', () => {
      const q = (search.value || '').trim().toLowerCase();
      for (const it of nav.querySelectorAll('.sideItem')) {
        const label = (it.getAttribute('data-label') || it.textContent || '').toLowerCase();
        it.style.display = !q || label.includes(q) ? '' : 'none';
      }
      for (const g of nav.querySelectorAll('.sideGroup')) {
        const any = Array.from(g.querySelectorAll('.sideItem')).some(a => a.style.display !== 'none');
        g.style.display = any ? '' : 'none';
      }
    });
  }

  function getHostIdFromPath() {
    const parts = (location.pathname || '').split('/').filter(Boolean);
    const last = parts[parts.length - 1] || '';
    const n = Number(last);
    return Number.isFinite(n) ? String(Math.trunc(n)) : null;
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    if (r.status === 401) { location.href = '/login'; throw new Error('Not authenticated'); }
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(data && data.detail ? String(data.detail) : `HTTP ${r.status}`);
    return data;
  }

  let wsPingTimer = null;

  function connectWS(hostId) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/metrics`);
    if (wsPingTimer) { clearInterval(wsPingTimer); wsPingTimer = null; }

    ws.onopen = () => { const el = $$('hostConn'); if (el) el.textContent = 'live'; };
    ws.onclose = () => {
      const el = $$('hostConn'); if (el) el.textContent = 'reconnecting…';
      if (wsPingTimer) { clearInterval(wsPingTimer); wsPingTimer = null; }
      setTimeout(() => connectWS(hostId), 2000);
    };
    ws.onerror = () => { try { ws.close(); } catch(_) {} };
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'host_status') {
          const st = (msg.statuses || {})[String(hostId)] || (msg.statuses || {})[hostId] || null;
          if (st) applyStatus(st);
          const checks = (msg.checks || {})[String(hostId)] || (msg.checks || {})[hostId] || null;
          if (checks) applyChecks(checks);
        }
      } catch(_) {}
    };
    wsPingTimer = setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 4000);
  }

  async function loadAgentMetrics(hostId) {
    try {
      const data = await fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/agent-metrics`);
      if (data && data.found) {
        applyAgentMetrics(data);
      } else {
        showNoAgent();
      }
    } catch(_) {
      showNoAgent();
    }
  }

  async function init() {
    const connEl = $$('hostConn');
    if (connEl) connEl.textContent = 'loading…';
    setupSidebarSearch();

    try {
      const hostId = getHostIdFromPath();
      if (!hostId) throw new Error('Invalid host id in URL');

      initCharts();

      const [me, host] = await Promise.all([
        fetchJson('/api/me'),
        fetchJson(`/api/hosts/${encodeURIComponent(hostId)}`),
      ]);

      // Header
      const userEl = $$('hostUser'); if (userEl) userEl.textContent = me && me.username ? me.username : '—';
      const nameEl = $$('hName');   if (nameEl) nameEl.textContent = host.name || host.address || `host-${hostId}`;
      const addrEl = $$('hAddr');   if (addrEl) addrEl.textContent = host.address || '—';
      const typeEl = $$('hType');   if (typeEl) typeEl.textContent = host.type || '—';

      // Identity card
      const setText = (id, v) => { const el = $$(id); if (el) el.textContent = v || '—'; };
      setText('hNameKv',  host.name);
      setText('hAddrKv',  host.address);
      setText('hTypeKv',  host.type);
      setText('hTags',    Array.isArray(host.tags) && host.tags.length ? host.tags.join(', ') : '—');
      setText('hNotes',   host.notes);
      setText('hCreated', host.created_ts ? fmtTs(host.created_ts) : null);

      document.title = `System Trace · ${host.name || 'Host Monitor'}`;

      // Set hostname for log reporting
      _hostLogHostname = host.name || host.address || '';

      // Load status + checks + agent metrics in parallel
      const [statusRes, checksRes] = await Promise.all([
        fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/status`).catch(() => null),
        fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/checks`).catch(() => null),
      ]);
      if (statusRes && statusRes.status) applyStatus(statusRes.status);
      if (checksRes && checksRes.checks) applyChecks(checksRes.checks);

      // Initial full load (seeds ring from backend history)
      try {
        const agentData = await fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/agent-metrics`);
        if (agentData && agentData.found) {
          applyInitialData(agentData);
          // Use agent hostname if available (more accurate for log lookup)
          if (agentData.hostname) _hostLogHostname = agentData.hostname;
        } else {
          showNoAgent();
        }
      } catch(_) { showNoAgent(); }

      // Load per-host error history into the panel
      loadHostLogs(_hostLogHostname);

      connectWS(hostId);

      // Real-time: poll agent metrics every 1s (latest only), status/checks every 15s
      let rtActive = true;
      async function rtLoop() {
        if (!rtActive) return;
        try {
          const data = await fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/agent-metrics`);
          if (data && data.found) pushLatestToRing(data);
        } catch(_) {}
        if (rtActive) setTimeout(rtLoop, 1000);
      }
      rtLoop();
      setInterval(() => {
        fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/status`).then(r => { if (r && r.status) applyStatus(r.status); }).catch(() => null);
        fetchJson(`/api/hosts/${encodeURIComponent(hostId)}/checks`).then(r => { if (r && r.checks) applyChecks(r.checks); }).catch(() => null);
      }, 15_000);
      document.addEventListener('visibilitychange', () => { rtActive = !document.hidden; if (rtActive) rtLoop(); });

      if (connEl && connEl.textContent === 'loading…') connEl.textContent = 'ready';
      const errEl = $$('hostErr'); if (errEl) errEl.style.display = 'none';

    } catch(e) {
      if (connEl) connEl.textContent = 'error';
      const errEl = $$('hostErr');
      if (errEl) { errEl.textContent = e && e.message ? e.message : 'Failed to load host'; errEl.style.display = ''; }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
