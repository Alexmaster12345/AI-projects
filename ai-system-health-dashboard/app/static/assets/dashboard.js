/* Dashboard behavior extracted from index.html and enhanced:
   - URL prefs (theme/layout/density/wallboard)
   - Canvas resize handling for crisp sparklines on any resolution/DPI
   - WebSocket reconnect without accumulating timers
*/

(() => {
  const MAX = 72;
  const series = { cpu: [], mem: [], disk: [], gpuHealth: [] };
  const logs = [];

  function applyPrefs() {
    const q = new URLSearchParams(location.search);

    const theme = (q.get('theme') || 'midnight').toLowerCase();
    const density = (q.get('density') || 'cozy').toLowerCase();
    const layout = (q.get('layout') || 'split').toLowerCase();
    const wallboard = q.get('wallboard') === '1' || q.get('wallboard') === 'true';

    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.density = density;
    document.documentElement.dataset.layout = layout;
    if (wallboard) document.body.classList.add('wallboard');
  }

  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element: #${id}`);
    return el;
  }

  const els = {
    date: $('date'),
    time: $('time'),
    subtime: $('subtime'),
    host: $('host'),
    conn: $('conn'),

    cpuLbl: $('cpuLbl'),
    memLbl: $('memLbl'),
    diskLbl: $('diskLbl'),
    gpuHealthLbl: $('gpuHealthLbl'),

    diagStatus: $('diagStatus'),
    diagText: $('diagText'),
    diagRec: $('diagRec'),
    pill: $('pill'),
    logLines: $('logLines'),
    actionBtn: $('actionBtn'),
    dangerBtn: $('dangerBtn'),

    cpuV: $('cpuV'),
    ramV: $('ramV'),
    diskV: $('diskV'),
    netV: $('netV'),
    uptimeV: $('uptimeV'),
    gpuV: $('gpuV'),

    ntpV: $('ntpV'),
    icmpV: $('icmpV'),
    snmpV: $('snmpV'),
    netflowV: $('netflowV'),

    cmd: $('cmd'),

    cpuSpark: $('cpuSpark'),
    memSpark: $('memSpark'),
    diskSpark: $('diskSpark'),
    gpuHealthSpark: $('gpuHealthSpark'),

    // Hosts view
    hostsView: $('hostsView'),
    hostsErr: $('hostsErr'),
    hostsForm: $('hostsForm'),
    hostName: $('hostName'),
    hostAddress: $('hostAddress'),
    hostType: $('hostType'),
    hostTags: $('hostTags'),
    hostNotes: $('hostNotes'),
    hostsAddBtn: $('hostsAddBtn'),
    hostsEmpty: $('hostsEmpty'),
    hostsTbody: $('hostsTbody'),

    // Maps view
    mapsView: $('mapsView'),
    mapsErr: $('mapsErr'),
    mapStage: $('mapStage'),
    mapSvg: $('mapSvg'),
    mapEditBtn: $('mapEditBtn'),
    mapSeverity: $('mapSeverity'),
    mapHint: $('mapHint'),
    mapMenu: $('mapMenu'),
    mapMenuGoHosts: $('mapMenuGoHosts'),
    mapMenuCopyAddr: $('mapMenuCopyAddr'),
  };

  function setView(view) {
    document.body.dataset.view = view || 'dashboard';

    // Update sidebar current item.
    try {
      const sideNav = document.getElementById('sideNav');
      if (sideNav) {
        const items = sideNav.querySelectorAll('a.sideItem[data-action]');
        for (const it of items) {
          const a = it.getAttribute('data-action') || '';
          if (a === 'dashboard' && (view === 'dashboard' || !view)) it.setAttribute('aria-current', 'page');
          else if (a === 'hosts' && view === 'hosts') it.setAttribute('aria-current', 'page');
          else if (a === 'maps' && view === 'maps') it.setAttribute('aria-current', 'page');
          else it.removeAttribute('aria-current');
        }
      }
    } catch (_) {
      // ignore
    }
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    if (r.status === 401) {
      // Not authenticated; bounce to login.
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

  function setHostsError(msg) {
    if (!msg) {
      els.hostsErr.style.display = 'none';
      els.hostsErr.textContent = '';
      return;
    }
    els.hostsErr.style.display = '';
    els.hostsErr.textContent = String(msg);
  }

  function renderHosts(hosts) {
    const list = Array.isArray(hosts) ? hosts : [];
    els.hostsTbody.innerHTML = '';

    if (!list.length) {
      els.hostsEmpty.style.display = '';
      return;
    }
    els.hostsEmpty.style.display = 'none';

    for (const h of list) {
      const tr = document.createElement('tr');

      const name = (h && h.name) || '—';
      const address = (h && h.address) || '—';
      const type = (h && h.type) || '—';
      const notes = (h && h.notes) || '';
      const tags = Array.isArray(h && h.tags) ? h.tags : [];

      const tdName = document.createElement('td');
      tdName.textContent = name;

      const tdAddr = document.createElement('td');
      tdAddr.textContent = address;

      const tdType = document.createElement('td');
      tdType.textContent = type;

      const tdTags = document.createElement('td');
      if (tags.length) {
        for (const t of tags) {
          const span = document.createElement('span');
          span.className = 'hostsTag';
          span.textContent = String(t);
          tdTags.appendChild(span);
        }
      } else {
        tdTags.textContent = '—';
      }

      const tdNotes = document.createElement('td');
      tdNotes.textContent = notes || '—';

      const tdAct = document.createElement('td');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'hostsBtnSmall danger';
      btn.textContent = 'Delete';
      btn.addEventListener('click', async () => {
        setHostsError('');
        const id = h && h.id;
        if (id == null) return;
        try {
          await fetchJson(`/api/admin/hosts/${encodeURIComponent(String(id))}`, { method: 'DELETE' });
          await refreshHosts();
        } catch (e) {
          setHostsError(e && e.message ? e.message : 'Delete failed');
        }
      });
      tdAct.appendChild(btn);

      tr.appendChild(tdName);
      tr.appendChild(tdAddr);
      tr.appendChild(tdType);
      tr.appendChild(tdTags);
      tr.appendChild(tdNotes);
      tr.appendChild(tdAct);
      els.hostsTbody.appendChild(tr);
    }
  }

  async function refreshHosts() {
    try {
      const hosts = await fetchJson('/api/hosts');
      renderHosts(hosts);
    } catch (e) {
      renderHosts([]);
      setHostsError(e && e.message ? e.message : 'Failed to load hosts');
    }
  }

  // --- Maps (SVG) ---
  let mapEdit = false;
  let mapFocusedId = null;
  let mapMenuHost = null;
  let mapPositions = null;

  function setMapsError(msg) {
    if (!msg) {
      els.mapsErr.style.display = 'none';
      els.mapsErr.textContent = '';
      return;
    }
    els.mapsErr.style.display = '';
    els.mapsErr.textContent = String(msg);
  }

  function loadMapPositions() {
    if (mapPositions) return mapPositions;
    try {
      const raw = localStorage.getItem('ashd_map_positions');
      const parsed = raw ? JSON.parse(raw) : {};
      mapPositions = parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_) {
      mapPositions = {};
    }
    return mapPositions;
  }

  function saveMapPositions() {
    try {
      localStorage.setItem('ashd_map_positions', JSON.stringify(mapPositions || {}));
    } catch (_) {
      // ignore
    }
  }

  function hostStatus(host) {
    // Until real per-host checks exist, treat active hosts as OK.
    // Allow user to force critical via tag/type for demo parity.
    const tags = Array.isArray(host && host.tags) ? host.tags.map((t) => String(t).toLowerCase()) : [];
    const t = String((host && host.type) || '').toLowerCase();
    if (tags.includes('disabled') || tags.includes('crit') || t.includes('disabled') || t.includes('crit')) return 'crit';
    if (host && host.is_active === false) return 'crit';
    return 'ok';
  }

  function clearSvg(svg) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
  }

  function svgEl(name, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', name);
    if (attrs) {
      for (const k of Object.keys(attrs)) {
        el.setAttribute(k, String(attrs[k]));
      }
    }
    return el;
  }

  function getSvgPointFromEvent(svg, evt) {
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function hideMapMenu() {
    els.mapMenu.style.display = 'none';
    mapMenuHost = null;
  }

  async function renderMap() {
    setMapsError('');
    hideMapMenu();

    let hosts = [];
    try {
      hosts = await fetchJson('/api/hosts');
    } catch (e) {
      setMapsError(e && e.message ? e.message : 'Failed to load hosts');
      hosts = [];
    }

    const svg = els.mapSvg;
    clearSvg(svg);

    // Background grid (subtle)
    const bg = svgEl('g');
    for (let x = 0; x <= 1000; x += 100) {
      bg.appendChild(svgEl('line', { x1: x, y1: 0, x2: x, y2: 640, stroke: 'rgba(255,255,255,0.04)', 'stroke-width': 1 }));
    }
    for (let y = 0; y <= 640; y += 80) {
      bg.appendChild(svgEl('line', { x1: 0, y1: y, x2: 1000, y2: y, stroke: 'rgba(255,255,255,0.04)', 'stroke-width': 1 }));
    }
    svg.appendChild(bg);

    const center = { x: 500, y: 260 };
    const positions = loadMapPositions();

    // Compute node positions.
    const nodes = [];
    nodes.push({
      kind: 'server',
      id: 'server',
      name: 'ASHD server',
      address: '127.0.0.1',
      status: 'unknown',
      x: center.x,
      y: center.y,
    });

    const ringR = 240;
    const count = Array.isArray(hosts) ? hosts.length : 0;
    for (let i = 0; i < count; i++) {
      const h = hosts[i];
      const hid = h && h.id != null ? String(h.id) : `idx_${i}`;
      const saved = positions && positions[hid];

      let x = center.x + ringR * Math.cos((i / Math.max(1, count)) * Math.PI * 2);
      let y = center.y + (ringR * 0.72) * Math.sin((i / Math.max(1, count)) * Math.PI * 2);
      if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
        x = clamp(saved.x * 1000, 60, 940);
        y = clamp(saved.y * 640, 60, 580);
      }

      nodes.push({
        kind: 'host',
        id: hid,
        rawId: h && h.id,
        name: (h && h.name) || `host-${hid}`,
        address: (h && h.address) || '—',
        type: (h && h.type) || '',
        tags: Array.isArray(h && h.tags) ? h.tags : [],
        notes: (h && h.notes) || '',
        status: hostStatus(h),
        x,
        y,
      });
    }

    // Links
    const linksG = svgEl('g');
    svg.appendChild(linksG);
    for (const n of nodes) {
      if (n.kind !== 'host') continue;
      const line = svgEl('line', { x1: center.x, y1: center.y, x2: n.x, y2: n.y, class: 'mapLink' });
      if (mapFocusedId && n.id !== mapFocusedId) {
        line.setAttribute('stroke', 'rgba(255,255,255,0.10)');
      }
      linksG.appendChild(line);
    }

    // Nodes
    const nodesG = svgEl('g');
    svg.appendChild(nodesG);

    function addNode(n) {
      const g = svgEl('g', { class: `mapNode ${n.status || 'unknown'}` });
      g.dataset.id = String(n.id);
      g.dataset.kind = String(n.kind);
      g.setAttribute('transform', `translate(${n.x},${n.y})`);

      const r = n.kind === 'server' ? 70 : 56;
      g.appendChild(svgEl('circle', { cx: 0, cy: 0, r }));

      // Title
      const t1 = svgEl('text', { x: 0, y: -6, 'text-anchor': 'middle' });
      t1.textContent = String(n.name).slice(0, 22);
      g.appendChild(t1);

      // Subtitle
      const t2 = svgEl('text', { x: 0, y: 14, 'text-anchor': 'middle', class: 'sub' });
      t2.textContent = n.kind === 'server' ? String(n.address) : String(n.address).slice(0, 26);
      g.appendChild(t2);

      // Badge / status
      const badge = svgEl('text', { x: 0, y: 34, 'text-anchor': 'middle', class: 'badge' });
      badge.textContent = (n.status || 'unknown').toUpperCase();
      g.appendChild(badge);

      const title = svgEl('title');
      title.textContent = `${n.name}\n${n.address}`;
      g.appendChild(title);

      // Interaction
      g.addEventListener('click', () => {
        if (n.kind === 'host') {
          mapFocusedId = n.id;
          renderMap();
        }
      });

      g.addEventListener('contextmenu', (evt) => {
        evt.preventDefault();
        if (n.kind !== 'host') return;
        mapMenuHost = n;
        const rect = els.mapStage.getBoundingClientRect();
        const x = clamp(evt.clientX - rect.left, 6, rect.width - 6);
        const y = clamp(evt.clientY - rect.top, 6, rect.height - 6);
        els.mapMenu.style.left = `${x}px`;
        els.mapMenu.style.top = `${y}px`;
        els.mapMenu.style.display = '';
      });

      // Drag in edit mode
      if (n.kind === 'host') {
        let dragging = false;
        let pointerId = null;

        function onDown(evt) {
          if (!mapEdit) return;
          dragging = true;
          pointerId = evt.pointerId;
          try {
            g.setPointerCapture(pointerId);
          } catch (_) {
            // ignore
          }
        }

        function onMove(evt) {
          if (!dragging || !mapEdit) return;
          const p = getSvgPointFromEvent(svg, evt);
          n.x = clamp(p.x, 60, 940);
          n.y = clamp(p.y, 60, 580);
          g.setAttribute('transform', `translate(${n.x},${n.y})`);
          // Update link in place by re-rendering links only is more complex; simplest: re-render whole map on drop.
        }

        async function onUp() {
          if (!dragging) return;
          dragging = false;
          pointerId = null;
          // Persist normalized position
          const pos = loadMapPositions();
          pos[String(n.id)] = { x: n.x / 1000, y: n.y / 640 };
          mapPositions = pos;
          saveMapPositions();
          await renderMap();
        }

        g.addEventListener('pointerdown', onDown);
        g.addEventListener('pointermove', onMove);
        g.addEventListener('pointerup', onUp);
        g.addEventListener('pointercancel', onUp);
      }

      nodesG.appendChild(g);
    }

    for (const n of nodes) {
      // If a node is focused, de-emphasize others by forcing unknown styling? Keep simple.
      if (mapFocusedId && n.kind === 'host' && n.id !== mapFocusedId) {
        // no-op; links already dimmed
      }
      addNode(n);
    }

    // Empty state hint
    if (!count) {
      const g = svgEl('g');
      const t = svgEl('text', { x: 500, y: 520, 'text-anchor': 'middle', fill: 'rgba(233,249,255,0.72)', 'font-size': 14 });
      t.textContent = 'No hosts yet. Add hosts first, then come back to Maps.';
      g.appendChild(t);
      svg.appendChild(g);
    }
  }

  function setupMaps() {
    // Close menu on any click outside
    document.addEventListener('click', (e) => {
      const t = e.target;
      if (els.mapMenu.style.display === 'none') return;
      if (t && (els.mapMenu.contains(t) || (els.mapStage && els.mapStage.contains(t) && t.closest && t.closest('#mapMenu')))) return;
      hideMapMenu();
    });

    els.mapStage.addEventListener('contextmenu', (e) => {
      // Right-click on empty stage closes menu
      const tgt = e.target;
      if (!tgt || !(tgt.closest && tgt.closest('.mapNode'))) {
        hideMapMenu();
      }
    });

    els.mapEditBtn.addEventListener('click', async () => {
      mapEdit = !mapEdit;
      els.mapEditBtn.textContent = mapEdit ? 'Editing…' : 'Edit map';
      await renderMap();
    });

    els.mapMenuGoHosts.addEventListener('click', () => {
      hideMapMenu();
      try {
        location.hash = 'hosts';
      } catch (_) {
        // ignore
      }
      routeFromHash();
    });

    els.mapMenuCopyAddr.addEventListener('click', async () => {
      const addr = mapMenuHost && mapMenuHost.address ? String(mapMenuHost.address) : '';
      hideMapMenu();
      if (!addr) return;
      try {
        await navigator.clipboard.writeText(addr);
      } catch (_) {
        // ignore
      }
    });

    els.mapSeverity.addEventListener('change', () => {
      // placeholder for future severity filtering
      renderMap();
    });
  }

  function parseTags(s) {
    // Tags are currently a dropdown (single-select). Keep this helper flexible
    // in case we switch back to comma-separated input later.
    const v = String(s || '').trim();
    if (!v) return [];
    if (!v.includes(',')) return [v];

    const raw = v
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean);
    const seen = new Set();
    const out = [];
    for (const t of raw) {
      const k = t.toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(t);
    }
    return out;
  }

  function setupHosts() {
    if (!els.hostsForm) return;
    els.hostsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      setHostsError('');

      const payload = {
        name: String(els.hostName.value || '').trim(),
        address: String(els.hostAddress.value || '').trim(),
        type: String(els.hostType.value || '').trim() || null,
        tags: parseTags(els.hostTags.value),
        notes: String(els.hostNotes.value || '').trim() || null,
      };
      if (!payload.name || !payload.address) {
        setHostsError('Name and Address are required.');
        return;
      }

      try {
        els.hostsAddBtn.disabled = true;
        await fetchJson('/api/admin/hosts', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(payload),
        });

        els.hostName.value = '';
        els.hostAddress.value = '';
        els.hostType.value = '';
        try {
          els.hostTags.value = '';
        } catch (_) {
          // ignore
        }
        els.hostNotes.value = '';

        await refreshHosts();
      } catch (e2) {
        setHostsError(e2 && e2.message ? e2.message : 'Add host failed');
      } finally {
        els.hostsAddBtn.disabled = false;
      }
    });
  }

  function routeFromHash() {
    const h = (location.hash || '').toLowerCase();
    if (h === '#hosts') {
      setView('hosts');
      refreshHosts();
      return;
    }
    if (h === '#maps') {
      setView('maps');
      renderMap();
      return;
    }
    setView('dashboard');
  }

  // --- Sidebar UX (Zabbix-style menu) ---
  function setupSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sideToggle = document.getElementById('sideToggle');
    const sideSearch = document.getElementById('sideSearch');
    const sideNav = document.getElementById('sideNav');

    if (!sidebar) return;

    const supportsHover =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(hover:hover) and (pointer:fine)').matches;
    const isDesktop =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(min-width: 981px)').matches;

    // Auto-hide sidebar on desktop: collapse to a thin left edge when mouse isn't near.
    // (Mobile uses the drawer toggle instead.)
    if (supportsHover && isDesktop) {
      document.body.classList.add('sidebarAutoHide');
    }

    // Collapse mode removed: ensure any previously saved preference can't
    // leave the UI stuck in a collapsed state with no control to expand.
    document.body.classList.remove('sidebarCollapsed');
    try {
      localStorage.removeItem('ashd_sidebar_collapsed');
    } catch (_) {
      // ignore
    }

    function setOpen(open) {
      document.body.classList.toggle('sidebarOpen', !!open);
    }

    function setHoverOpen(open) {
      // Never fight the mobile drawer.
      if (document.body.classList.contains('sidebarOpen')) return;
      document.body.classList.toggle('sidebarHover', !!open);
    }

    if (sideToggle) {
      sideToggle.addEventListener('click', () => {
        setOpen(!document.body.classList.contains('sidebarOpen'));
      });
    }

    // Clicking outside closes the drawer on mobile.
    document.addEventListener('click', (e) => {
      if (!document.body.classList.contains('sidebarOpen')) return;
      // clicks inside sidebar or on toggle shouldn't close
      const t = e.target;
      if (t && (sidebar.contains(t) || (sideToggle && sideToggle.contains(t)))) return;
      setOpen(false);
    });

    // ESC closes drawer
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') setOpen(false);
    });

    // Desktop hover edge behavior
    if (document.body.classList.contains('sidebarAutoHide')) {
      const EDGE_PX = 26;
      const CLOSE_PAD_PX = 48;

      let closeTimer = null;

      function openNow() {
        if (closeTimer) {
          clearTimeout(closeTimer);
          closeTimer = null;
        }
        setHoverOpen(true);
      }

      function closeSoon() {
        if (closeTimer) return;
        closeTimer = setTimeout(() => {
          closeTimer = null;
          setHoverOpen(false);
        }, 240);
      }

      function handleMove(e) {
        if (!e) return;
        const x = e.clientX;

        // Use geometry rather than event target, because when the sidebar is
        // transformed off-screen some browsers report unexpected targets.
        let rectRight = EDGE_PX;
        try {
          const r = sidebar.getBoundingClientRect();
          rectRight = typeof r.right === 'number' ? r.right : EDGE_PX;
        } catch (_) {
          rectRight = EDGE_PX;
        }

        // Hysteresis: open a little earlier than we close.
        const openZone = Math.max(EDGE_PX, rectRight + 6);
        const closeZone = rectRight + CLOSE_PAD_PX;
        const isOpen = document.body.classList.contains('sidebarHover');

        if (!isOpen) {
          if (x <= openZone) openNow();
          else closeSoon();
          return;
        }

        // When already open: keep it open while the cursor is within (or near)
        // the sidebar's visible width.
        if (x <= closeZone) openNow();
        else closeSoon();
      }

      document.addEventListener('mousemove', handleMove, { passive: true });
      sidebar.addEventListener('mouseenter', () => openNow());
      sidebar.addEventListener('mouseleave', (e) => {
        try {
          const x = e && typeof e.clientX === 'number' ? e.clientX : EDGE_PX + 1;
          if (x > EDGE_PX) closeSoon();
        } catch (_) {
          closeSoon();
        }
      });
    }

    // Search filter
    if (sideSearch && sideNav) {
      sideSearch.addEventListener('input', () => {
        const q = (sideSearch.value || '').trim().toLowerCase();
        const items = sideNav.querySelectorAll('.sideItem');
        for (const it of items) {
          const label = (it.getAttribute('data-label') || it.textContent || '').toLowerCase();
          it.style.display = !q || label.includes(q) ? '' : 'none';
        }
        // Hide group titles if none of their items match
        const groups = sideNav.querySelectorAll('.sideGroup');
        for (const g of groups) {
          const anyVisible = Array.from(g.querySelectorAll('.sideItem')).some((a) => a.style.display !== 'none');
          g.style.display = anyVisible ? '' : 'none';
        }
      });
    }

    // Placeholder actions (until multi-page features exist)
    if (sideNav) {
      sideNav.addEventListener('click', (e) => {
        const a = e.target && e.target.closest ? e.target.closest('a.sideItem') : null;
        if (!a) return;
        const action = a.getAttribute('data-action') || '';
        if (!action) return;

        // Dashboard is current page; allow no-op.
        if (action === 'dashboard') {
          e.preventDefault();
          setOpen(false);
          try {
            location.hash = '';
          } catch (_) {
            // ignore
          }
          routeFromHash();
          return;
        }

        if (action === 'hosts') {
          e.preventDefault();
          setOpen(false);
          try {
            location.hash = 'hosts';
          } catch (_) {
            // ignore
          }
          routeFromHash();
          return;
        }

        if (action === 'maps') {
          e.preventDefault();
          setOpen(false);
          try {
            location.hash = 'maps';
          } catch (_) {
            // ignore
          }
          routeFromHash();
          return;
        }

        // Block navigation for sections not implemented.
        e.preventDefault();
        setOpen(false);
        try {
          const label = a.getAttribute('data-label') || action;
          logs.push(`${new Date().toTimeString().slice(0, 8)} INFO: ${label} is not implemented yet`);
          if (logs.length > 14) logs.shift();
          els.logLines.textContent = logs.join('\n');
        } catch (_) {
          // ignore
        }
      });
    }
  }

  function fmtPct(v) {
    return v == null ? '—' : (Math.round(v * 10) / 10).toFixed(1) + '%';
  }

  function fmtLoad(v) {
    return v == null ? '—' : (Math.round(v * 100) / 100).toFixed(2);
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

  function primaryDisk(disks) {
    if (!disks || disks.length === 0) return null;
    const root = disks.find((d) => d.mount === '/');
    if (root) return root;
    return disks.reduce((a, b) => (b.percent > a.percent ? b : a), disks[0]);
  }

  function push(arr, v) {
    arr.push(v);
    if (arr.length > MAX) arr.shift();
  }

  function cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function setConn(state) {
    els.conn.textContent = state;
  }

  // --- Canvas sizing (crisp on any resolution/DPI) ---
  const sparkCanvases = [els.cpuSpark, els.memSpark, els.diskSpark, els.gpuHealthSpark];

  function resizeCanvasToDisplaySize(canvas) {
    const rect = canvas.getBoundingClientRect();
    const cssW = Math.max(1, Math.round(rect.width));
    const cssH = Math.max(1, Math.round(rect.height));
    const dpr = Math.max(1, Math.round((window.devicePixelRatio || 1) * 100) / 100);

    const newW = Math.max(1, Math.round(cssW * dpr));
    const newH = Math.max(1, Math.round(cssH * dpr));

    if (canvas.width !== newW || canvas.height !== newH) {
      canvas.width = newW;
      canvas.height = newH;
      const ctx = canvas.getContext('2d');
      if (ctx) ctx.setTransform(1, 0, 0, 1, 0, 0);
      return true;
    }
    return false;
  }

  function drawSpark(canvas, values, color) {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // background glow
    ctx.fillStyle = 'rgba(0,0,0,0.12)';
    ctx.fillRect(0, 0, w, h);

    if (!values || values.length < 2) return;
    const min = 0;
    const max = 100;

    // grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      const y = (h * i) / 4;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    ctx.beginPath();
    for (let i = 0; i < values.length; i++) {
      const x = (w * i) / (values.length - 1);
      const v = values[i];
      const y = h - ((v - min) / (max - min)) * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // endpoint dot (keep fully visible)
    const lx = w - 1;
    const lv = values[values.length - 1];
    const ly = h - ((lv - min) / (max - min)) * h;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(lx, ly, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  function redrawSparks(lastSample) {
    if (!lastSample) return;

    const pd = primaryDisk(lastSample.disk);
    const gh = gpuHealthFromSample(lastSample);

    // Ensure backing stores match display sizes before drawing.
    for (const c of sparkCanvases) resizeCanvasToDisplaySize(c);

    drawSpark(els.cpuSpark, series.cpu, cssVar('--cpu', '#6ee7ff'));
    drawSpark(els.memSpark, series.mem, cssVar('--mem', '#55ffa6'));
    drawSpark(els.diskSpark, series.disk, cssVar('--disk', '#ffd166'));
    drawSpark(els.gpuHealthSpark, series.gpuHealth, gpuHealthColor(gh));
  }

  function setupSparkResizeObserver(getLastSample) {
    if (typeof ResizeObserver === 'undefined') {
      // Fallback: resize on window events.
      window.addEventListener('resize', () => {
        for (const c of sparkCanvases) resizeCanvasToDisplaySize(c);
        redrawSparks(getLastSample());
      });
      return;
    }

    const ro = new ResizeObserver(() => {
      let changed = false;
      for (const c of sparkCanvases) changed = resizeCanvasToDisplaySize(c) || changed;
      if (changed) redrawSparks(getLastSample());
    });

    // Observe the canvas itself (size follows its container).
    for (const c of sparkCanvases) ro.observe(c);
  }

  // --- Diagnostic + vitals ---

  function setDiag(insights, sample) {
    const anoms = insights && insights.anomalies ? insights.anomalies : [];
    const worst = anoms.reduce(
      (acc, a) => {
        const rank = a.severity === 'crit' ? 3 : a.severity === 'warn' ? 2 : 1;
        return rank > acc.rank ? { rank, sev: a.severity, a } : acc;
      },
      { rank: 0, sev: '', a: null },
    );

    let status = 'STABLE';
    let statusColor = 'var(--ok)';
    let pillCls = 'pill ok';
    if (worst.rank === 3) {
      status = 'CRITICAL';
      statusColor = 'var(--crit)';
      pillCls = 'pill crit';
    } else if (worst.rank === 2) {
      status = 'WARNING';
      statusColor = 'var(--warn)';
      pillCls = 'pill warn';
    }

    els.diagStatus.textContent = status;
    els.diagStatus.style.color = statusColor;
    els.pill.className = pillCls;
    els.pill.textContent = status;

    if (!sample) {
      els.diagText.textContent = 'Collecting baseline…';
      els.diagRec.textContent = 'RECOMMENDATION: —';
      els.dangerBtn.style.display = 'none';
      return;
    }

    const pd = primaryDisk(sample.disk);
    const suspects = [];
    if (sample.top_processes && sample.top_processes.length > 0) {
      const p = sample.top_processes[0];
      if (p && p.name) suspects.push(String(p.name));
    }

    const temp = sample.cpu_temp_c != null ? `${Math.round(sample.cpu_temp_c)}°C` : null;
    const cpuLine = `CPU ${fmtPct(sample.cpu_percent)}${temp ? ' · ' + temp : ''}`;
    const memLine = `RAM ${fmtPct(sample.mem_percent)} · ${fmtBytes(sample.mem_available_bytes)} free`;
    const diskLine = pd ? `DISK ${fmtPct(pd.percent)} used · ${fmtBytes(pd.free_bytes)} free` : 'DISK —';

    if (worst.a) {
      els.diagText.textContent = `${worst.a.message}. ${cpuLine}. ${memLine}. ${diskLine}.`;
      els.diagRec.textContent = suspects.length
        ? `RECOMMENDATION: investigate ${suspects[0]}; reduce load and re-check.`
        : 'RECOMMENDATION: reduce load and re-check.';
      els.dangerBtn.style.display = worst.rank >= 2 ? 'inline-flex' : 'none';
      els.dangerBtn.textContent = suspects.length ? `TAKE ACTION: ${suspects[0].toUpperCase()}` : 'TAKE ACTION';
    } else {
      els.diagText.textContent = `${insights && insights.summary ? insights.summary : 'All vitals within expected ranges.'} ${cpuLine}. ${memLine}. ${diskLine}.`;
      els.diagRec.textContent = 'RECOMMENDATION: No immediate action required.';
      els.dangerBtn.style.display = 'none';
    }

    // Add log lines
    const now = new Date(sample.ts * 1000);
    const stamp = now.toTimeString().slice(0, 8);
    const lines = [];
    if (worst.a) lines.push(`${stamp} ALERT: ${worst.a.message}`);
    if (temp && Number(temp.replace('°C', '')) >= 80) lines.push(`${stamp} WARN: CPU temperature elevated (${temp})`);
    if (sample.disk_health === 'crit') lines.push(`${stamp} CRIT: Disk usage critical`);
    if (sample.disk_health === 'warn') lines.push(`${stamp} WARN: Disk usage high`);
    if (sample.gpu_health === 'crit') lines.push(`${stamp} CRIT: GPU health critical`);
    if (sample.gpu_health === 'warn') lines.push(`${stamp} WARN: GPU health degraded`);

    for (const ln of lines) {
      logs.push(ln);
      if (logs.length > 14) logs.shift();
    }
    els.logLines.textContent = logs.length ? logs.join('\n') : `${stamp} INFO: system stable`;
  }

  function gpuHealthFromSample(sample) {
    if (!sample) return 'unknown';
    if (sample.gpu_health) return sample.gpu_health;
    if (!sample.gpu || sample.gpu.length === 0) return 'unknown';

    let worst = 'ok';
    const rank = (s) => (s === 'crit' ? 3 : s === 'warn' ? 2 : s === 'ok' ? 1 : 0);

    for (const g of sample.gpu) {
      let st = 'ok';
      if (g && g.temp_c != null) {
        const t = Number(g.temp_c);
        if (t >= 90) st = 'crit';
        else if (t >= 83) st = 'warn';
      }
      if (g && g.mem_used_mb != null && g.mem_total_mb) {
        const pct = (Number(g.mem_used_mb) / Number(g.mem_total_mb)) * 100;
        if (pct >= 99) st = 'crit';
        else if (pct >= 95 && st !== 'crit') st = 'warn';
      }
      if (g && g.util_percent != null && st === 'ok') {
        const u = Number(g.util_percent);
        if (u >= 99) st = 'warn';
      }
      if (rank(st) > rank(worst)) worst = st;
    }

    return worst;
  }

  function gpuHealthScore(status) {
    if (status === 'crit') return 100;
    if (status === 'warn') return 65;
    if (status === 'ok') return 20;
    return 0;
  }

  function gpuHealthColor(status) {
    if (status === 'crit') return 'var(--crit)';
    if (status === 'warn') return 'var(--warn)';
    if (status === 'ok') return 'var(--ok)';
    return cssVar('--gpu', '#a78bfa');
  }

  function proto(sample, name) {
    if (!sample || !sample.protocols) return null;
    return sample.protocols[name] || null;
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

  function setVitals(sample, netRate) {
    if (!sample) return;
    const temp = sample.cpu_temp_c != null ? `${Math.round(sample.cpu_temp_c)}°C` : '—';
    const freq = sample.cpu_freq_mhz != null ? `${Math.round(sample.cpu_freq_mhz)}MHz` : '—';
    const pd = primaryDisk(sample.disk);

    els.cpuV.textContent = `${temp} / ${fmtPct(sample.cpu_percent)} / ${fmtLoad(sample.load1)} / ${freq}`;
    els.ramV.textContent = `${fmtPct(sample.mem_percent)} used / ${fmtBytes(sample.mem_available_bytes)} free`;
    els.diskV.textContent = pd ? `${fmtPct(pd.percent)} used / ${fmtBytes(pd.free_bytes)} free` : '—';
    els.netV.textContent = netRate ? `TX ${fmtMbps(netRate.tx)} / RX ${fmtMbps(netRate.rx)}` : '—';
    els.uptimeV.textContent = fmtUptime(sample.uptime_seconds);

    setProto(els.ntpV, proto(sample, 'ntp'));
    setProto(els.icmpV, proto(sample, 'icmp'));
    setProto(els.snmpV, proto(sample, 'snmp'));
    setProto(els.netflowV, proto(sample, 'netflow'));

    if (sample.gpu && sample.gpu.length > 0) {
      const g = sample.gpu[0];
      const gtemp = g.temp_c != null ? `${Math.round(g.temp_c)}°C` : '—';
      const util = g.util_percent != null ? `${Math.round(g.util_percent)}%` : '—';
      els.gpuV.textContent = `${gtemp} / ${util}`;
    } else {
      els.gpuV.textContent = '—';
    }
  }

  function setLeft(sample) {
    if (!sample) return;
    els.cpuLbl.textContent = fmtPct(sample.cpu_percent);
    els.memLbl.textContent = fmtPct(sample.mem_percent);

    const pd = primaryDisk(sample.disk);
    els.diskLbl.textContent = pd ? fmtPct(pd.percent) : '—';

    const gh = gpuHealthFromSample(sample);
    els.gpuHealthLbl.textContent = (gh || 'unknown').toUpperCase();

    push(series.cpu, sample.cpu_percent);
    push(series.mem, sample.mem_percent);
    push(series.disk, pd ? pd.percent : 0);
    push(series.gpuHealth, gpuHealthScore(gh));

    // canvas drawing happens in redrawSparks() to ensure correct backing store
  }

  function updateClock() {
    const now = new Date();
    const dateStr = now.toLocaleDateString(undefined, {
      weekday: 'long',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

    els.date.textContent = dateStr;
    els.time.textContent = now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    els.subtime.textContent = now.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  // Demo command bar
  function setupDemoActions() {
    els.cmd.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const v = els.cmd.value.trim();
      if (!v) return;
      logs.push(`${new Date().toTimeString().slice(0, 8)} CMD: ${v}`);
      if (logs.length > 14) logs.shift();
      els.logLines.textContent = logs.join('\n');
      els.cmd.value = '';
    });

    els.actionBtn.addEventListener('click', () => {
      logs.push(`${new Date().toTimeString().slice(0, 8)} INFO: acknowledged`);
      if (logs.length > 14) logs.shift();
      els.logLines.textContent = logs.join('\n');
    });

    els.dangerBtn.addEventListener('click', () => {
      logs.push(`${new Date().toTimeString().slice(0, 8)} ACTION: queued (demo)`);
      if (logs.length > 14) logs.shift();
      els.logLines.textContent = logs.join('\n');
    });
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

  let lastSample = null;
  let lastInsights = null;

  function render(sample, insights) {
    if (sample && sample.hostname) els.host.textContent = sample.hostname;
    const nr = netRate(sample);

    lastSample = sample;
    lastInsights = insights;

    setLeft(sample);
    redrawSparks(sample);
    setVitals(sample, nr);
    setDiag(insights, sample);
  }

  // --- Data transport: WS then poll fallback ---
  let polling = false;
  async function pollFallback() {
    if (polling) return;
    polling = true;
    setConn('polling');

    while (polling) {
      try {
        const [latest, insights] = await Promise.all([
          fetch('/api/metrics/latest').then((r) => r.json()),
          fetch('/api/insights').then((r) => r.json()),
        ]);
        if (latest && latest.ts) render(latest, insights);
      } catch (_) {
        // ignore
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
      // If we were polling previously, stop.
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

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'snapshot' || msg.type === 'sample') {
          render(msg.sample, msg.insights);
        }
      } catch (_) {
        // ignore
      }
    };

    wsPingTimer = setInterval(() => {
      if (ws && ws.readyState === 1) ws.send('ping');
    }, 4000);

    // If WS can't open quickly (common when unauthenticated), fallback to polling.
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

  function init() {
    applyPrefs();
    setupSidebar();
    setupHosts();
    setupMaps();
    window.addEventListener('hashchange', routeFromHash);
    routeFromHash();
    updateClock();
    setInterval(updateClock, 500);
    setupDemoActions();

    // Ensure initial canvas sizes are correct.
    for (const c of sparkCanvases) resizeCanvasToDisplaySize(c);
    setupSparkResizeObserver(() => lastSample);

    connectWS();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
