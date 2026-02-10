(() => {
  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element: #${id}`);
    return el;
  }

  const els = {
    conn: $('invConn'),
    user: $('invUser'),
    err: $('invErr'),

    count: $('invCount'),
    ref: $('invRef'),

    manageCard: document.getElementById('invManageCard'),
    addForm: document.getElementById('invAddForm'),
    name: document.getElementById('invName'),
    category: document.getElementById('invCategory'),
    location: document.getElementById('invLocation'),
    qty: document.getElementById('invQty'),
    notes: document.getElementById('invNotes'),
    addBtn: document.getElementById('invAddBtn'),
    refreshBtn: document.getElementById('invRefreshBtn'),

    search: document.getElementById('invSearch'),
    tbody: document.getElementById('invTbody'),
    actHead: document.getElementById('invActHead'),

    sideNav: document.getElementById('sideNav'),
    sideSearch: document.getElementById('sideSearch'),
  };

  let items = [];
  let isAdmin = false;

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

  function fmtLocalTs(tsMs) {
    try {
      return new Date(tsMs).toLocaleString();
    } catch (_) {
      return '—';
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

  function norm(s) {
    return (s == null ? '' : String(s)).trim().toLowerCase();
  }

  function renderTable() {
    if (!els.tbody) return;

    const q = norm(els.search && els.search.value);
    const filtered = !q
      ? items
      : items.filter((it) => {
          const hay = [it.name, it.category, it.location, it.notes].map(norm).join(' · ');
          return hay.includes(q);
        });

    els.tbody.innerHTML = '';

    if (!filtered.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = isAdmin ? 6 : 5;
      td.className = 'muted';
      td.textContent = q ? 'No matching items.' : 'No inventory items yet.';
      tr.appendChild(td);
      els.tbody.appendChild(tr);
      return;
    }

    for (const it of filtered) {
      const tr = document.createElement('tr');

      const tdName = document.createElement('td');
      tdName.textContent = it && it.name ? String(it.name) : '—';

      const tdCat = document.createElement('td');
      tdCat.textContent = it && it.category ? String(it.category) : '—';

      const tdLoc = document.createElement('td');
      tdLoc.textContent = it && it.location ? String(it.location) : '—';

      const tdQty = document.createElement('td');
      tdQty.className = 'qty';
      tdQty.textContent = it && it.quantity != null ? String(it.quantity) : '0';

      const tdNotes = document.createElement('td');
      tdNotes.textContent = it && it.notes ? String(it.notes) : '—';

      tr.appendChild(tdName);
      tr.appendChild(tdCat);
      tr.appendChild(tdLoc);
      tr.appendChild(tdQty);
      tr.appendChild(tdNotes);

      if (isAdmin) {
        const tdAct = document.createElement('td');
        tdAct.className = 'act';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'invRemoveBtn';
        btn.textContent = 'Remove';
        btn.addEventListener('click', async () => {
          const id = it && it.id != null ? String(it.id) : null;
          if (!id) return;
          const ok = confirm(`Remove item #${id} (${it.name || 'item'})?`);
          if (!ok) return;
          try {
            setConn('removing…');
            await fetchJson(`/api/admin/inventory/${encodeURIComponent(id)}`, { method: 'DELETE' });
            await loadItems();
            setConn('ready');
          } catch (e) {
            setConn('error');
            setErr(e && e.message ? e.message : 'Failed to remove item');
          }
        });
        tdAct.appendChild(btn);
        tr.appendChild(tdAct);
      }

      els.tbody.appendChild(tr);
    }
  }

  async function loadItems() {
    const data = await fetchJson('/api/inventory');
    items = Array.isArray(data) ? data : [];

    try {
      els.count.textContent = String(items.length);
      els.ref.textContent = fmtLocalTs(Date.now());
    } catch (_) {
      // ignore
    }

    renderTable();
  }

  function bindUi() {
    if (els.search) {
      els.search.addEventListener('input', () => {
        try {
          renderTable();
        } catch (_) {
          // ignore
        }
      });
    }

    if (els.refreshBtn) {
      els.refreshBtn.addEventListener('click', async () => {
        try {
          setErr('');
          setConn('refreshing…');
          await loadItems();
          setConn('ready');
        } catch (e) {
          setConn('error');
          setErr(e && e.message ? e.message : 'Failed to refresh');
        }
      });
    }

    if (els.addForm) {
      els.addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!isAdmin) return;

        const name = els.name ? String(els.name.value || '').trim() : '';
        const category = els.category ? String(els.category.value || '').trim() : '';
        const location = els.location ? String(els.location.value || '').trim() : '';
        const notes = els.notes ? String(els.notes.value || '').trim() : '';
        const qtyRaw = els.qty ? String(els.qty.value || '').trim() : '1';

        if (!name) {
          setErr('Name is required');
          return;
        }

        let quantity = 1;
        try {
          const n = Number(qtyRaw);
          quantity = Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : 1;
        } catch (_) {
          quantity = 1;
        }

        const payload = {
          name,
          category: category || null,
          location: location || null,
          quantity,
          notes: notes || null,
        };

        try {
          setErr('');
          setConn('adding…');
          if (els.addBtn) els.addBtn.disabled = true;

          await fetchJson('/api/admin/inventory', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(payload),
          });

          if (els.name) els.name.value = '';
          if (els.category) els.category.value = '';
          if (els.location) els.location.value = '';
          if (els.qty) els.qty.value = '1';
          if (els.notes) els.notes.value = '';

          await loadItems();
          setConn('ready');
        } catch (e) {
          setConn('error');
          setErr(e && e.message ? e.message : 'Failed to add item');
        } finally {
          if (els.addBtn) els.addBtn.disabled = false;
        }
      });
    }
  }

  async function init() {
    setConn('loading…');
    setupSidebarSearch();
    bindUi();

    try {
      const me = await fetchJson('/api/me');
      els.user.textContent = me && me.username ? String(me.username) : '—';
      isAdmin = me && String(me.role || '').toLowerCase() === 'admin';

      if (els.manageCard) els.manageCard.style.display = isAdmin ? '' : 'none';
      if (els.actHead) els.actHead.style.display = isAdmin ? '' : 'none';

      await loadItems();
      setConn('ready');
      setErr('');
    } catch (e) {
      setConn('error');
      setErr(e && e.message ? e.message : 'Failed to load inventory');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
