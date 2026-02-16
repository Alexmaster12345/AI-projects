(() => {
  'use strict';

  // === Utility functions ===
  function $(id) {
    return document.getElementById(id);
  }

  // === Racks (localStorage) ===
  function getRacks() {
    try {
      const raw = localStorage.getItem('ashd_racks');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function setRacks(racks) {
    try {
      localStorage.setItem('ashd_racks', JSON.stringify(Array.isArray(racks) ? racks : []));
    } catch (e) {
      // ignore
    }
  }

  function _mkShelves(n) {
    const out = [];
    const count = Math.max(1, Number(n || 12));
    for (let i = 1; i <= count; i++) {
      out.push({ pos: i, label: '' });
    }
    return out;
  }

  function renderRacks() {
    if (!rackList) return;
    const racks = getRacks();
    rackList.innerHTML = '';

    if (!racks.length) {
      if (rackEmpty) rackEmpty.style.display = 'block';
      selectedRackId = null;
      renderShelves();
      return;
    }

    if (rackEmpty) rackEmpty.style.display = 'none';

    if (selectedRackId == null || !racks.some(r => String(r?.id) === String(selectedRackId))) {
      selectedRackId = racks[0].id;
    }

    for (const r of racks) {
      const row = document.createElement('div');
      row.className = 'rackItem' + (String(r?.id) === String(selectedRackId) ? ' isActive' : '');

      const meta = document.createElement('div');
      meta.className = 'rackMeta';
      const t = document.createElement('div');
      t.className = 'rackName';
      t.textContent = String(r?.name ?? '—');
      const sub = document.createElement('div');
      sub.className = 'rackSub muted';
      const loc = String(r?.location ?? '').trim();
      const shelfCount = Array.isArray(r?.shelves) ? r.shelves.length : 0;
      sub.textContent = `${loc ? loc + ' · ' : ''}${shelfCount} shelves`;
      meta.appendChild(t);
      meta.appendChild(sub);
      meta.style.cursor = 'pointer';
      meta.onclick = () => {
        selectedRackId = r.id;
        renderRacks();
      };

      const actions = document.createElement('div');
      const del = document.createElement('button');
      del.className = 'hostsBtnSmall';
      del.textContent = 'Delete';
      del.style.padding = '4px 8px';
      del.style.fontSize = '11px';
      del.onclick = () => {
        const cur = getRacks();
        const next = cur.filter(x => String(x?.id) !== String(r?.id));
        setRacks(next);
        if (String(selectedRackId) === String(r?.id)) selectedRackId = null;
        renderRacks();
      };
      actions.appendChild(del);

      row.appendChild(meta);
      row.appendChild(actions);
      rackList.appendChild(row);
    }

    renderShelves();
  }

  function renderShelves() {
    if (!shelvesWrap) return;
    const racks = getRacks();
    const rack = racks.find(r => String(r?.id) === String(selectedRackId));

    shelvesWrap.innerHTML = '';
    if (!rack) {
      if (rackEditorTitle) rackEditorTitle.textContent = 'Shelves';
      if (shelvesHint) shelvesHint.style.display = 'block';
      if (rackViz) rackViz.innerHTML = '';
      if (rackPreview) rackPreview.innerHTML = '';
      if (rackPreviewTitle) rackPreviewTitle.textContent = 'Rack preview';
      return;
    }

    if (shelvesHint) shelvesHint.style.display = 'none';
    if (rackEditorTitle) rackEditorTitle.textContent = `Shelves · ${String(rack.name ?? '')}`;

    const shelves = Array.isArray(rack.shelves) ? rack.shelves : [];
    for (const sh of shelves) {
      const row = document.createElement('div');
      row.className = 'shelfRow';

      const idx = document.createElement('div');
      idx.className = 'shelfIdx';
      idx.textContent = String(sh?.pos ?? '—');

      const input = document.createElement('input');
      input.className = 'shelfInput';
      input.setAttribute('data-pos', String(sh?.pos ?? ''));
      input.placeholder = 'Shelf label / contents…';
      input.value = String(sh?.label ?? '');
      input.oninput = () => {
        const cur = getRacks();
        const r = cur.find(x => String(x?.id) === String(selectedRackId));
        if (!r || !Array.isArray(r.shelves)) return;
        const target = r.shelves.find(x => Number(x?.pos) === Number(sh?.pos));
        if (!target) return;
        target.label = String(input.value ?? '');
        setRacks(cur);
        renderRackViz();
      };

      row.appendChild(idx);
      row.appendChild(input);
      shelvesWrap.appendChild(row);
    }

    renderRackViz();
    renderRackPreview();
  }

  function renderRackViz() {
    if (!rackViz) return;
    const racks = getRacks();
    const rack = racks.find(r => String(r?.id) === String(selectedRackId));
    rackViz.innerHTML = '';
    if (!rack) return;

    const wrap = document.createElement('div');
    wrap.className = 'rackVizInner';

    const shelves = Array.isArray(rack.shelves) ? rack.shelves : [];
    const sorted = [...shelves].sort((a, b) => Number(b?.pos || 0) - Number(a?.pos || 0));
    for (const sh of sorted) {
      const slot = document.createElement('div');
      slot.className = 'rackSlot' + (Number(selectedShelfPos) === Number(sh?.pos) ? ' isSelected' : '');

      const idx = document.createElement('div');
      idx.className = 'rackSlotIdx';
      idx.textContent = String(sh?.pos ?? '—');

      const label = document.createElement('div');
      label.className = 'rackSlotLabel';
      const txt = String(sh?.label ?? '').trim();
      const primary = document.createElement('div');
      primary.className = 'rackSlotLabelPrimary';
      primary.textContent = txt ? txt : 'Empty';
      const secondary = document.createElement('div');
      secondary.className = 'rackSlotLabelSecondary muted';
      secondary.textContent = `Shelf ${String(sh?.pos ?? '—')}`;
      label.appendChild(primary);
      label.appendChild(secondary);

      const leds = document.createElement('div');
      leds.className = 'rackSlotLeds';

      slot.appendChild(idx);
      slot.appendChild(label);
      slot.appendChild(leds);

      slot.onclick = () => {
        selectedShelfPos = Number(sh?.pos);
        const input = document.querySelector(`.shelfInput[data-pos="${String(sh?.pos)}"]`);
        if (input && typeof input.focus === 'function') {
          input.focus();
          if (typeof input.scrollIntoView === 'function') {
            input.scrollIntoView({ block: 'center' });
          }
        }
        renderRackViz();
      };

      wrap.appendChild(slot);
    }

    const addSlot = document.createElement('div');
    addSlot.className = 'rackSlot isAdd';
    const addIdx = document.createElement('div');
    addIdx.className = 'rackSlotIdx';
    addIdx.textContent = '+';
    const addLbl = document.createElement('div');
    addLbl.className = 'rackSlotLabel';
    addLbl.textContent = 'Add shelf';
    const addLeds = document.createElement('div');
    addLeds.className = 'rackSlotLeds';
    addLeds.style.opacity = '0.25';
    addSlot.appendChild(addIdx);
    addSlot.appendChild(addLbl);
    addSlot.appendChild(addLeds);
    addSlot.onclick = () => {
      addShelf();
      const cur = getRacks();
      const r = cur.find(x => String(x?.id) === String(selectedRackId));
      const last = r && Array.isArray(r.shelves) && r.shelves.length ? r.shelves[r.shelves.length - 1] : null;
      selectedShelfPos = last ? Number(last.pos) : null;
      renderShelves();
    };
    wrap.appendChild(addSlot);

    rackViz.appendChild(wrap);
  }

  function renderRackPreview() {
    if (!rackPreview) return;
    const racks = getRacks();
    const rack = racks.find(r => String(r?.id) === String(selectedRackId));
    rackPreview.innerHTML = '';
    if (!rack) return;

    const nm = String(rack?.name ?? '').trim();
    const loc = String(rack?.location ?? '').trim();
    if (rackPreviewTitle) {
      rackPreviewTitle.textContent = `Rack preview${nm ? ' · ' + nm : ''}${loc ? ' · ' + loc : ''}`;
    }

    const wrap = document.createElement('div');
    wrap.className = 'rackVizInner';

    const shelves = Array.isArray(rack.shelves) ? rack.shelves : [];
    const sorted = [...shelves].sort((a, b) => Number(b?.pos || 0) - Number(a?.pos || 0));
    for (const sh of sorted) {
      const slot = document.createElement('div');
      slot.className = 'rackSlot';

      const idx = document.createElement('div');
      idx.className = 'rackSlotIdx';
      idx.textContent = String(sh?.pos ?? '—');

      const label = document.createElement('div');
      label.className = 'rackSlotLabel';
      const txt = String(sh?.label ?? '').trim();
      const primary = document.createElement('div');
      primary.className = 'rackSlotLabelPrimary';
      primary.textContent = txt ? txt : 'Empty';
      const secondary = document.createElement('div');
      secondary.className = 'rackSlotLabelSecondary muted';
      secondary.textContent = `Shelf ${String(sh?.pos ?? '—')}`;
      label.appendChild(primary);
      label.appendChild(secondary);

      const leds = document.createElement('div');
      leds.className = 'rackSlotLeds';

      slot.appendChild(idx);
      slot.appendChild(label);
      slot.appendChild(leds);

      wrap.appendChild(slot);
    }

    rackPreview.appendChild(wrap);
  }

  function addRack(e) {
    if (e) e.preventDefault();
    if (!rackName) return;
    const name = String(rackName.value ?? '').trim();
    if (!name) {
      showError(rackErr, 'Rack name is required');
      return;
    }
    const nShelves = rackShelves && String(rackShelves.value ?? '').trim() !== '' ? Number(rackShelves.value) : 12;
    const rack = {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      name,
      location: rackLocation ? String(rackLocation.value ?? '').trim() : '',
      shelves: _mkShelves(nShelves),
      created_ts: Date.now(),
    };
    const cur = getRacks();
    setRacks([rack, ...cur]);
    selectedRackId = rack.id;
    selectedShelfPos = null;
    if (rackForm) rackForm.reset();
    showError(rackErr, '');
    renderRacks();
    renderRackPreview();
  }

  function addShelf() {
    const cur = getRacks();
    const r = cur.find(x => String(x?.id) === String(selectedRackId));
    if (!r) return;
    if (!Array.isArray(r.shelves)) r.shelves = [];
    const nextPos = r.shelves.length ? Math.max(...r.shelves.map(x => Number(x?.pos || 0))) + 1 : 1;
    r.shelves.push({ pos: nextPos, label: '' });
    setRacks(cur);
    selectedShelfPos = nextPos;
    renderShelves();
    renderRacks();
    renderRackPreview();
  }

  function removeShelf() {
    const cur = getRacks();
    const r = cur.find(x => String(x?.id) === String(selectedRackId));
    if (!r || !Array.isArray(r.shelves) || r.shelves.length <= 1) return;
    r.shelves.pop();
    setRacks(cur);
    selectedShelfPos = null;
    renderShelves();
    renderRacks();
    renderRackPreview();
  }

  function setText(el, text) {
    if (el) el.textContent = String(text ?? '');
  }

  function pushSystemLog(level, message) {
    try {
      const key = 'ashd_system_logs_v1';
      const raw = localStorage.getItem(key);
      const cur = raw ? JSON.parse(raw) : [];
      const logs = Array.isArray(cur) ? cur : [];
      logs.push({ ts: Date.now() / 1000, level: String(level || 'info'), message: String(message || '') });
      const trimmed = logs.slice(-60);
      localStorage.setItem(key, JSON.stringify(trimmed));
    } catch (e) {
      // ignore
    }
  }

  async function fetchJson(url, opts = {}) {
    try {
      const finalOpts = {
        credentials: 'same-origin',
        ...opts,
      };
      const resp = await fetch(url, finalOpts);
      if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${err}`);
      }
      return await resp.json();
    } catch (e) {
      throw e;
    }
  }

  // === Elements ===
  const hostsView = $('hostsView');
  const inventoryView = $('inventoryView');
  const racksView = $('racksView');
  const mapsView = $('mapsView');
  const hostsForm = $('hostsForm');
  const hostsErr = $('hostsErr');
  const mapsErr = $('mapsErr');
  const hostsTable = $('hostsTable');
  const hostsTbody = $('hostsTbody');
  const hostsEmpty = $('hostsEmpty');
  const mapSvg = $('mapSvg');
  const mapLayoutSel = $('mapLayout');
  const mapAutoDiscoverBtn = $('mapAutoDiscover');

  const invForm = $('invForm');
  const invErr = $('invErr');
  const invName = $('invName');
  const invCategory = $('invCategory');
  const invLocation = $('invLocation');
  const invQty = $('invQty');
  const invNotes = $('invNotes');
  const invRefreshBtn = $('invRefreshBtn');
  const invSearch = $('invSearch');
  const invTable = $('invTable');
  const invTbody = $('invTbody');
  const invEmpty = $('invEmpty');
  const invCount = $('invCount');
  const invLastRefresh = $('invLastRefresh');

  const rackForm = $('rackForm');
  const rackErr = $('rackErr');
  const rackName = $('rackName');
  const rackLocation = $('rackLocation');
  const rackShelves = $('rackShelves');
  const rackRefreshBtn = $('rackRefreshBtn');
  const rackList = $('rackList');
  const rackEmpty = $('rackEmpty');
  const rackEditorTitle = $('rackEditorTitle');
  const rackViz = $('rackViz');
  const rackPreview = $('rackPreview');
  const rackPreviewTitle = $('rackPreviewTitle');
  const shelvesWrap = $('shelvesWrap');
  const shelvesHint = $('shelvesHint');
  const shelfAddBtn = $('shelfAddBtn');
  const shelfRemoveBtn = $('shelfRemoveBtn');

  // === Hosts Management ===
  let hostsData = [];
  let editingHostId = null;
  let mapSelectedHostId = null;
  let selectedRackId = null;
  let selectedShelfPos = null;

  // === Inventory (localStorage) ===
  function getInventoryItems() {
    try {
      const raw = localStorage.getItem('ashd_inventory_items');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function setInventoryItems(items) {
    try {
      localStorage.setItem('ashd_inventory_items', JSON.stringify(Array.isArray(items) ? items : []));
    } catch (e) {
      // ignore
    }
  }

  function formatLocalTs(ts) {
    try {
      const d = new Date(ts);
      return d.toLocaleString();
    } catch (e) {
      return '—';
    }
  }

  function renderInventory() {
    if (!invTbody) return;
    const q = (invSearch && invSearch.value ? String(invSearch.value) : '').trim().toLowerCase();
    const all = getInventoryItems();
    const items = q
      ? all.filter(it => {
          const n = String(it?.name ?? '').toLowerCase();
          const c = String(it?.category ?? '').toLowerCase();
          const l = String(it?.location ?? '').toLowerCase();
          return n.includes(q) || c.includes(q) || l.includes(q);
        })
      : all;

    invTbody.innerHTML = '';
    if (invCount) invCount.textContent = String(all.length);
    if (invLastRefresh) invLastRefresh.textContent = formatLocalTs(Date.now());

    if (!items.length) {
      if (invEmpty) invEmpty.style.display = 'block';
      if (invTable) invTable.style.display = 'none';
      return;
    }

    if (invEmpty) invEmpty.style.display = 'none';
    if (invTable) invTable.style.display = 'table';

    for (const it of items) {
      const tr = document.createElement('tr');

      const tdName = document.createElement('td');
      tdName.textContent = String(it?.name ?? '—');
      tr.appendChild(tdName);

      const tdCat = document.createElement('td');
      tdCat.textContent = String(it?.category ?? '—');
      tr.appendChild(tdCat);

      const tdLoc = document.createElement('td');
      tdLoc.textContent = String(it?.location ?? '—');
      tr.appendChild(tdLoc);

      const tdQty = document.createElement('td');
      tdQty.textContent = String((it?.qty ?? '') === '' ? '—' : it.qty);
      tr.appendChild(tdQty);

      const tdNotes = document.createElement('td');
      tdNotes.textContent = String(it?.notes ?? '—');
      tdNotes.className = 'muted';
      tdNotes.style.fontSize = '11px';
      tr.appendChild(tdNotes);

      const tdActions = document.createElement('td');
      const delBtn = document.createElement('button');
      delBtn.textContent = 'Delete';
      delBtn.className = 'hostsBtnSmall';
      delBtn.style.padding = '4px 8px';
      delBtn.style.fontSize = '11px';
      delBtn.onclick = () => {
        const cur = getInventoryItems();
        const next = cur.filter(x => String(x?.id ?? '') !== String(it?.id ?? ''));
        setInventoryItems(next);
        renderInventory();
      };
      tdActions.appendChild(delBtn);
      tr.appendChild(tdActions);

      invTbody.appendChild(tr);
    }
  }

  function addInventoryItem(e) {
    if (e) e.preventDefault();
    if (!invName) return;
    const name = String(invName.value ?? '').trim();
    if (!name) {
      showError(invErr, 'Name is required');
      return;
    }

    const item = {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      name,
      category: invCategory ? String(invCategory.value ?? '').trim() : '',
      location: invLocation ? String(invLocation.value ?? '').trim() : '',
      qty: invQty && String(invQty.value ?? '').trim() !== '' ? Number(invQty.value) : '',
      notes: invNotes ? String(invNotes.value ?? '').trim() : '',
      created_ts: Date.now(),
    };

    const cur = getInventoryItems();
    setInventoryItems([item, ...cur]);
    if (invForm) invForm.reset();
    showError(invErr, '');
    renderInventory();
  }

  function getMapLinks() {
    try {
      const raw = localStorage.getItem('ashd_map_links');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function setMapLinks(links) {
    try {
      localStorage.setItem('ashd_map_links', JSON.stringify(Array.isArray(links) ? links : []));
    } catch (e) {
      // ignore
    }
  }

  function isManualMapLayout() {
    return !!(mapLayoutSel && mapLayoutSel.value === 'manual');
  }

  function isLinkingEnabled() {
    return true;
  }

  function _linkKey(a, b) {
    const sa = String(a);
    const sb = String(b);
    return sa < sb ? `${sa}|${sb}` : `${sb}|${sa}`;
  }

  async function loadHosts() {
    try {
      hostsData = await fetchJson('/api/hosts');
      renderHostsTable();
      renderMapView();
    } catch (e) {
      showError(hostsErr, `Failed to load hosts: ${e.message}`);
    }
  }

  function renderHostsTable() {
    if (!hostsTbody) return;
    
    hostsTbody.innerHTML = '';
    
    if (hostsData.length === 0) {
      if (hostsEmpty) hostsEmpty.style.display = 'block';
      if (hostsTable) hostsTable.style.display = 'none';
      return;
    }
    
    if (hostsEmpty) hostsEmpty.style.display = 'none';
    if (hostsTable) hostsTable.style.display = 'table';
    
    for (const host of hostsData) {
      const tr = document.createElement('tr');

      const isEditing = String(editingHostId) === String(host.id);
      
      // Hostname
      const tdName = document.createElement('td');
      if (isEditing) {
        const input = document.createElement('input');
        input.value = host.name || '';
        input.style.width = '100%';
        input.className = 'shelfInput';
        input.id = `edit_name_${host.id}`;
        tdName.appendChild(input);
      } else {
        const nameLink = document.createElement('a');
        nameLink.href = `/host/${host.id}`;
        nameLink.textContent = host.name || '—';
        nameLink.style.color = '#78e6ff';
        nameLink.style.textDecoration = 'none';
        tdName.appendChild(nameLink);
      }
      tr.appendChild(tdName);
      
      // Address
      const tdAddr = document.createElement('td');
      if (isEditing) {
        const input = document.createElement('input');
        input.value = host.address || '';
        input.style.width = '100%';
        input.className = 'shelfInput';
        input.id = `edit_addr_${host.id}`;
        tdAddr.appendChild(input);
      } else {
        tdAddr.textContent = host.address || '—';
      }
      tr.appendChild(tdAddr);
      
      // Type
      const tdType = document.createElement('td');
      if (isEditing) {
        const input = document.createElement('input');
        input.value = host.type || '';
        input.style.width = '100%';
        input.className = 'shelfInput';
        input.id = `edit_type_${host.id}`;
        tdType.appendChild(input);
      } else {
        tdType.textContent = host.type || '—';
      }
      tr.appendChild(tdType);
      
      // Tags
      const tdTags = document.createElement('td');
      const tags = Array.isArray(host.tags) ? host.tags : [];
      if (isEditing) {
        const input = document.createElement('input');
        input.value = tags.join(', ');
        input.style.width = '100%';
        input.className = 'shelfInput';
        input.id = `edit_tags_${host.id}`;
        tdTags.appendChild(input);
      } else {
        if (tags.length) {
          const tagsContainer = document.createElement('div');
          tagsContainer.style.display = 'flex';
          tagsContainer.style.flexWrap = 'wrap';
          tagsContainer.style.gap = '6px';
          for (const tag of tags) {
            const tagEl = document.createElement('span');
            tagEl.className = 'hostsTag';
            tagEl.textContent = tag;
            tagsContainer.appendChild(tagEl);
          }
          tdTags.appendChild(tagsContainer);
        } else {
          tdTags.textContent = '—';
        }
      }
      tr.appendChild(tdTags);
      
      // Notes
      const tdNotes = document.createElement('td');
      if (isEditing) {
        const input = document.createElement('input');
        input.value = host.notes || '';
        input.style.width = '100%';
        input.className = 'shelfInput';
        input.id = `edit_notes_${host.id}`;
        tdNotes.appendChild(input);
      } else {
        tdNotes.textContent = host.notes ? host.notes.substring(0, 30) + (host.notes.length > 30 ? '...' : '') : '—';
        tdNotes.style.fontSize = '11px';
        tdNotes.className = 'muted';
      }
      tr.appendChild(tdNotes);
      
      // Actions
      const tdActions = document.createElement('td');
      if (isEditing) {
        const saveBtn = document.createElement('button');
        saveBtn.textContent = 'Save';
        saveBtn.className = 'hostsBtnSmall';
        saveBtn.style.padding = '4px 8px';
        saveBtn.style.fontSize = '11px';
        saveBtn.onclick = async () => {
          await saveHostEdits(host.id);
        };
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.className = 'hostsBtnSmall';
        cancelBtn.style.padding = '4px 8px';
        cancelBtn.style.fontSize = '11px';
        cancelBtn.style.marginLeft = '6px';
        cancelBtn.onclick = () => {
          editingHostId = null;
          renderHostsTable();
        };
        tdActions.appendChild(saveBtn);
        tdActions.appendChild(cancelBtn);
      } else {
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.className = 'hostsBtnSmall';
        editBtn.style.padding = '4px 8px';
        editBtn.style.fontSize = '11px';
        editBtn.onclick = () => {
          editingHostId = host.id;
          renderHostsTable();
        };
        const delBtn = document.createElement('button');
        delBtn.textContent = 'Delete';
        delBtn.className = 'hostsBtnSmall';
        delBtn.style.padding = '4px 8px';
        delBtn.style.fontSize = '11px';
        delBtn.style.marginLeft = '6px';
        delBtn.onclick = () => deleteHost(host.id);
        tdActions.appendChild(editBtn);
        tdActions.appendChild(delBtn);
      }
      tr.appendChild(tdActions);
      
      hostsTbody.appendChild(tr);
    }
  }

  async function saveHostEdits(hostId) {
    const nameEl = document.getElementById(`edit_name_${hostId}`);
    const addrEl = document.getElementById(`edit_addr_${hostId}`);
    const typeEl = document.getElementById(`edit_type_${hostId}`);
    const tagsEl = document.getElementById(`edit_tags_${hostId}`);
    const notesEl = document.getElementById(`edit_notes_${hostId}`);

    const tags = tagsEl && String(tagsEl.value || '').trim() !== ''
      ? String(tagsEl.value).split(',').map(s => s.trim()).filter(Boolean)
      : [];

    const payload = {
      name: nameEl ? String(nameEl.value || '').trim() : null,
      address: addrEl ? String(addrEl.value || '').trim() : null,
      type: typeEl ? String(typeEl.value || '').trim() : null,
      tags: tags,
      notes: notesEl ? String(notesEl.value || '').trim() : null,
    };

    if (!payload.name || !payload.address) {
      showError(hostsErr, 'Hostname and IP Address are required');
      return;
    }

    try {
      const updated = await fetchJson(`/api/admin/hosts/${hostId}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      editingHostId = null;
      showError(hostsErr, '');

      pushSystemLog('info', `Host updated: ${payload.name} (${payload.address})`);

      // Update local cache to keep Hosts + Map in sync immediately.
      try {
        const idx = hostsData.findIndex(h => String(h?.id) === String(hostId));
        if (idx >= 0) {
          hostsData[idx] = { ...hostsData[idx], ...updated };
        }
      } catch (e) {
        // ignore
      }

      renderHostsTable();
      renderMapView();

      try {
        window.dispatchEvent(new CustomEvent('ashd:hosts-updated', { detail: { hostId } }));
      } catch (e) {
        // ignore
      }

      // Also refresh from server to ensure authoritative state.
      await loadHosts();
    } catch (e) {
      pushSystemLog('error', `Host update failed (id=${hostId}): ${e.message}`);
      showError(hostsErr, `Failed to update host: ${e.message}`);
    }
  }

  async function addHost(e) {
    e.preventDefault();
    
    const hostName = $('hostName');
    const hostAddress = $('hostAddress');
    const hostType = $('hostType');
    const hostTags = $('hostTags');
    const hostNotes = $('hostNotes');
    
    if (!hostName || !hostAddress) return;
    
    const tags = hostTags && hostTags.value ? [hostTags.value] : [];
    
    const hostData = {
      name: hostName.value.trim(),
      address: hostAddress.value.trim(),
      type: hostType && hostType.value ? hostType.value.trim() : null,
      tags: tags,
      notes: hostNotes && hostNotes.value ? hostNotes.value.trim() : null
    };
    
    if (!hostData.name || !hostData.address) {
      showError(hostsErr, 'Hostname and IP Address are required');
      return;
    }
    
    try {
      await fetchJson('/api/admin/hosts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(hostData)
      });
      
      // Clear form
      hostsForm.reset();
      
      // Reload hosts
      await loadHosts();
      
      pushSystemLog('info', `Host added: ${hostData.name} (${hostData.address})`);
      showError(hostsErr, ''); // Clear errors
    } catch (e) {
      pushSystemLog('error', `Host add failed: ${e.message}`);
      showError(hostsErr, `Failed to add host: ${e.message}`);
    }
  }

  async function deleteHost(hostId) {
    if (!confirm('Are you sure you want to delete this host?')) return;
    
    try {
      await fetchJson(`/api/admin/hosts/${hostId}`, {method: 'DELETE'});
      await loadHosts();
      pushSystemLog('warn', `Host deleted: id=${hostId}`);
      showError(hostsErr, '');
    } catch (e) {
      pushSystemLog('error', `Host delete failed (id=${hostId}): ${e.message}`);
      showError(hostsErr, `Failed to delete host: ${e.message}`);
    }
  }

  async function autoDiscoverHosts() {
    const network = prompt('Enter network to scan (e.g., 192.168.50.0/24 or 10.0.0.0/24):', '192.168.50.0/24');
    if (!network) return;
    
    showError(hostsErr, 'Scanning network... This may take a minute.');
    
    try {
      const result = await fetchJson('/api/admin/hosts/discover', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({network: network, timeout: 0.5})
      });
      
      await loadHosts();

      pushSystemLog('info', `Auto-discover: scanned ${network}, found ${result.discovered}, added ${result.added}`);
      
      showError(hostsErr, `Discovery complete: Found ${result.discovered} hosts, added ${result.added} new hosts`);
      setTimeout(() => showError(hostsErr, ''), 5000);
    } catch (e) {
      pushSystemLog('error', `Auto-discover failed (${network}): ${e.message}`);
      showError(hostsErr, `Discovery failed: ${e.message}`);
    }
  }

  // === Maps Visualization ===
  function renderMapView() {
    if (!mapSvg || hostsData.length === 0) {
      if (mapSvg) mapSvg.innerHTML = '<text x="500" y="320" text-anchor="middle" fill="#666" font-size="14">No hosts to display. Add hosts first.</text>';
      return;
    }
    
    mapSvg.innerHTML = '';
    
    // Create SVG defs for gradients and markers
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    
    // Gradient for nodes
    const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'radialGradient');
    gradient.setAttribute('id', 'nodeGradient');
    gradient.innerHTML = `
      <stop offset="0%" style="stop-color:#78e6ff;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#2080a0;stop-opacity:0.6" />
    `;
    defs.appendChild(gradient);
    
    // Arrow marker
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('markerWidth', '10');
    marker.setAttribute('markerHeight', '10');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', '0 0, 10 3, 0 6');
    polygon.setAttribute('fill', 'rgba(120, 230, 255, 0.3)');
    marker.appendChild(polygon);
    defs.appendChild(marker);
    
    mapSvg.appendChild(defs);
    
    // Calculate layout
    const centerX = 500;
    const centerY = 320;
    const radius = 250;
    
    // Create central hub node
    const hub = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    hub.setAttribute('cx', centerX);
    hub.setAttribute('cy', centerY);
    hub.setAttribute('r', '30');
    hub.setAttribute('fill', 'url(#nodeGradient)');
    hub.setAttribute('stroke', '#78e6ff');
    hub.setAttribute('stroke-width', '2');
    mapSvg.appendChild(hub);
    
    const hubText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    hubText.setAttribute('x', centerX);
    hubText.setAttribute('y', centerY + 5);
    hubText.setAttribute('text-anchor', 'middle');
    hubText.setAttribute('fill', '#e9f9ff');
    hubText.setAttribute('font-size', '12');
    hubText.setAttribute('font-weight', 'bold');
    hubText.textContent = 'ASHD Server';
    mapSvg.appendChild(hubText);
    
    // Position hosts in a circle around the hub
    const hostPos = new Map();
    hostsData.forEach((host, i) => {
      const angle = (i / hostsData.length) * 2 * Math.PI - Math.PI / 2;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);

      hostPos.set(String(host.id), { x, y });
      
      // Connection line
      const tags = Array.isArray(host.tags) ? host.tags : [];
      const isAuto = tags.includes('auto-discovered');
      if (!isAuto) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', centerX);
        line.setAttribute('y1', centerY);
        line.setAttribute('x2', x);
        line.setAttribute('y2', y);
        line.setAttribute('stroke', 'rgba(120, 230, 255, 0.3)');
        line.setAttribute('stroke-width', '1');
        line.setAttribute('stroke-dasharray', '5,5');
        line.setAttribute('marker-end', 'url(#arrowhead)');
        mapSvg.appendChild(line);
      }
      
      // Host node
      const node = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      node.setAttribute('cx', x);
      node.setAttribute('cy', y);
      node.setAttribute('r', '20');
      node.setAttribute('fill', isAuto ? '#ffa500' : '#2080a0');
      node.setAttribute('stroke', '#78e6ff');
      node.setAttribute('stroke-width', String(mapSelectedHostId === host.id ? 3 : 2));
      node.style.cursor = 'pointer';
      node.addEventListener('click', (e) => {
        if (e && (e.ctrlKey || e.metaKey)) {
          window.location.href = `/host/${host.id}`;
          return;
        }

        if (!isLinkingEnabled()) {
          window.location.href = `/host/${host.id}`;
          return;
        }

        if (mapSelectedHostId == null) {
          mapSelectedHostId = host.id;
          renderMapView();
          return;
        }

        if (mapSelectedHostId === host.id) {
          mapSelectedHostId = null;
          renderMapView();
          return;
        }

        const a = String(mapSelectedHostId);
        const b = String(host.id);
        const key = _linkKey(a, b);
        const links = getMapLinks();

        const exists = links.some(l => l && typeof l === 'object' && _linkKey(l.a, l.b) === key);
        const nextLinks = exists
          ? links.filter(l => !(l && typeof l === 'object' && _linkKey(l.a, l.b) === key))
          : links.concat([{ a, b }]);
        setMapLinks(nextLinks);
        mapSelectedHostId = null;
        renderMapView();
      });
      mapSvg.appendChild(node);
      
      // Host name
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', x);
      text.setAttribute('y', y - 30);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('fill', '#e9f9ff');
      text.setAttribute('font-size', '11');
      text.textContent = host.name.length > 15 ? host.name.substring(0, 15) + '...' : host.name;
      mapSvg.appendChild(text);
      
      // Host IP
      const ipText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      ipText.setAttribute('x', x);
      ipText.setAttribute('y', y + 35);
      ipText.setAttribute('text-anchor', 'middle');
      ipText.setAttribute('fill', 'rgba(233, 249, 255, 0.6)');
      ipText.setAttribute('font-size', '10');
      ipText.textContent = host.address;
      mapSvg.appendChild(ipText);
    });

    const links = getMapLinks();
    for (const l of links) {
      if (!l || typeof l !== 'object') continue;
      const a = String(l.a ?? '');
      const b = String(l.b ?? '');
      if (!a || !b) continue;
      const pa = hostPos.get(a);
      const pb = hostPos.get(b);
      if (!pa || !pb) continue;
      const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      ln.setAttribute('x1', pa.x);
      ln.setAttribute('y1', pa.y);
      ln.setAttribute('x2', pb.x);
      ln.setAttribute('y2', pb.y);
      ln.setAttribute('stroke', 'rgba(120, 230, 255, 0.42)');
      ln.setAttribute('stroke-width', '1.5');
      ln.setAttribute('marker-end', 'url(#arrowhead)');
      ln.style.cursor = 'pointer';
      ln.addEventListener('click', (e) => {
        if (e) e.stopPropagation();
        const key = _linkKey(a, b);
        const cur = getMapLinks();
        const next = cur.filter(x => !(x && typeof x === 'object' && _linkKey(x.a, x.b) === key));
        setMapLinks(next);
        mapSelectedHostId = null;
        renderMapView();
      });
      mapSvg.insertBefore(ln, mapSvg.firstChild);
    }
  }

  function autoDiscoverFromMap() {
    autoDiscoverHosts();
  }

  // === Error Display ===
  function showError(el, msg) {
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      el.style.display = 'block';
    } else {
      el.style.display = 'none';
    }
  }

  // === View Switching ===
  function showView(viewName) {
    // Get the main HUD (monitoring view)
    const hud = document.querySelector('.hud');
    
    // Hide all views
    if (hostsView) hostsView.style.display = 'none';
    if (inventoryView) inventoryView.style.display = 'none';
    if (racksView) racksView.style.display = 'none';
    if (mapsView) mapsView.style.display = 'none';
    
    // Show requested view
    if (viewName === 'hosts') {
      if (hud) hud.style.display = 'none';
      if (hostsView) {
        hostsView.style.display = 'block';
        loadHosts();
      }
    } else if (viewName === 'inventory') {
      if (hud) hud.style.display = 'none';
      if (inventoryView) {
        inventoryView.style.display = 'block';
        renderInventory();
      }
    } else if (viewName === 'racks') {
      if (hud) hud.style.display = 'none';
      if (racksView) {
        racksView.style.display = 'block';
        renderRacks();
      }
    } else if (viewName === 'maps') {
      if (hud) hud.style.display = 'none';
      if (mapsView) {
        mapsView.style.display = 'block';
        loadHosts(); // Also loads map view
      }
    } else {
      // Default view - show monitoring HUD
      if (hud) hud.style.display = 'block';
    }
    
    // Update nav active state
    updateNavActive(viewName);
  }
  
  function updateNavActive(viewName) {
    const sideNav = $('sideNav');
    if (!sideNav) return;
    
    const navItems = sideNav.querySelectorAll('[data-action]');
    navItems.forEach(item => {
      if (item.getAttribute('data-action') === viewName) {
        item.setAttribute('aria-current', 'page');
      } else {
        item.removeAttribute('aria-current');
      }
    });
  }

  // === Navigation Handling ===
  function handleNavigation() {
    const sideNav = $('sideNav');
    if (!sideNav) return;
    
    const navItems = sideNav.querySelectorAll('[data-action]');
    navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const action = item.getAttribute('data-action');
        
        if (action === 'hosts' || action === 'maps' || action === 'inventory' || action === 'racks') {
          // Navigate to dedicated views
          window.location.hash = action;
        } else if (action === 'users') {
          // Navigate to users page
          window.location.href = '/users';
        } else if (action === 'user-groups') {
          // Navigate to user groups page
          window.location.href = '/user-groups';
        } else {
          // For other actions (overview, latest, screens, etc.), show monitoring view
          window.location.hash = '';
          showView('overview');
        }
      });
    });
  }

  // === Add Auto-Discovery Buttons ===
  function initAutoDiscovery() {
    if (mapAutoDiscoverBtn) {
      mapAutoDiscoverBtn.onclick = autoDiscoverHosts;
    }

    const hostsRefreshBtn = document.getElementById('hostsRefreshBtn');
    if (hostsRefreshBtn) {
      hostsRefreshBtn.onclick = loadHosts;
    }

    if (mapLayoutSel) {
      mapLayoutSel.onchange = () => {
        mapSelectedHostId = null;
        renderMapView();
      };
    }
  }

  // === User Management ===
  async function fetchCurrentUser() {
    try {
      const response = await fetch('/api/me');
      if (response.ok) {
        const user = await response.json();
        displayCurrentUser(user);
      } else if (response.status === 401) {
        // User not authenticated, redirect to login
        window.location.href = '/login';
      }
    } catch (error) {
      console.error('Failed to fetch current user:', error);
      // Hide user display on error
      const currentUserEl = document.getElementById('currentUser');
      if (currentUserEl) {
        currentUserEl.style.display = 'none';
      }
    }
  }

  function displayCurrentUser(user) {
    const currentUserEl = document.getElementById('currentUser');
    const usernameEl = document.getElementById('username');
    
    if (currentUserEl && usernameEl && user) {
      usernameEl.textContent = user.username || 'Unknown';
      currentUserEl.style.display = 'inline';
      
      // Add user role indicator if admin
      if (user.role === 'admin') {
        usernameEl.title = 'Administrator';
        usernameEl.style.fontWeight = 'bold';
      } else {
        usernameEl.title = 'User';
        usernameEl.style.fontWeight = 'normal';
      }
    }
  }

  // === Initialization ===
  function init() {
    // Fetch and display current user
    fetchCurrentUser();
    
    // Setup form submit
    if (hostsForm) {
      hostsForm.addEventListener('submit', addHost);
    }

    if (invForm) {
      invForm.addEventListener('submit', addInventoryItem);
    }

    if (invRefreshBtn) {
      invRefreshBtn.onclick = renderInventory;
    }

    if (invSearch) {
      invSearch.addEventListener('input', renderInventory);
    }

    if (rackForm) {
      rackForm.addEventListener('submit', addRack);
    }
    if (rackRefreshBtn) {
      rackRefreshBtn.onclick = renderRacks;
    }
    if (shelfAddBtn) {
      shelfAddBtn.onclick = addShelf;
    }
    if (shelfRemoveBtn) {
      shelfRemoveBtn.onclick = removeShelf;
    }
    
    // Setup navigation
    handleNavigation();
    
    // Add auto-discovery buttons
    initAutoDiscovery();
    
    // Check URL hash for initial view
    const hash = window.location.hash.substring(1);
    if (hash === 'hosts') {
      showView('hosts');
    } else if (hash === 'inventory') {
      showView('inventory');
    } else if (hash === 'racks') {
      showView('racks');
    } else if (hash === 'maps') {
      showView('maps');
    } else {
      // Default to monitoring view if no hash
      showView('overview');
    }
    
    // Handle hash changes
    window.addEventListener('hashchange', () => {
      const newHash = window.location.hash.substring(1);
      if (newHash === 'hosts') {
        showView('hosts');
      } else if (newHash === 'inventory') {
        showView('inventory');
      } else if (newHash === 'racks') {
        showView('racks');
      } else if (newHash === 'maps') {
        showView('maps');
      } else {
        // Empty hash or other - show monitoring view
        showView('overview');
      }
    });
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
