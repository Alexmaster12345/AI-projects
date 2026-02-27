/* WAF Dashboard — frontend JS */
'use strict';

// ── State ───────────────────────────────────────────────────────────────────
let eventsFilter = '';   // '' | '1' | '0'
let eventsPaused = false;
let hourlyChart  = null;
let typeChart    = null;

// ── Helpers ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const fmt = n => n == null ? '—' : n.toLocaleString();

function tagClass(tag) {
  if (!tag) return '';
  const t = tag.toLowerCase();
  if (t.includes('sqli') || t.includes('sql')) return 'tag-sqli';
  if (t.includes('xss'))                        return 'tag-xss';
  if (t.includes('lfi') || t.includes('trav'))  return 'tag-lfi';
  if (t.includes('rfi'))                        return 'tag-rfi';
  if (t.includes('rce') || t.includes('exec'))  return 'tag-rce';
  if (t.includes('scanner') || t.includes('bot')) return 'tag-scanner';
  if (t.includes('webshell') || t.includes('shell')) return 'tag-webshell';
  if (t.includes('admin'))                      return 'tag-admin';
  if (t.includes('sensitive'))                  return 'tag-sensitive';
  if (t.includes('protocol'))                   return 'tag-protocol';
  return '';
}

function shortTag(tag) {
  if (!tag) return 'Other';
  const parts = tag.split('/');
  return parts[parts.length - 1] || tag;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function timeStr(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString();
  } catch { return isoStr.slice(11, 19) || isoStr; }
}

// ── Tab switching ────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    const tab = item.dataset.tab;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    item.classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
    $('pageTitle').textContent = item.textContent.trim().replace(/^[^\w]+/, '');
    if (tab === 'events') refreshEvents();
    if (tab === 'rules')  refreshRules();
    if (tab === 'logs')   refreshLogs();
  });
});

// ── Status polling ───────────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    const dot = $('nginxDot');
    const label = $('nginxStatusLabel');
    if (d.nginx === 'active') {
      dot.className = 'status-dot active';
      label.textContent = 'nginx active';
    } else {
      dot.className = 'status-dot error';
      label.textContent = `nginx ${d.nginx}`;
    }
    $('uptimeBadge').textContent = `Uptime: ${d.uptime || '—'}`;
    $('statRules').textContent = fmt(d.rules_loaded || 803);
    $('statBlocked').textContent = fmt(d.blocked);
    $('statAllowed').textContent = fmt(d.allowed);
    const total = (d.blocked || 0) + (d.allowed || 0);
    $('statRate').textContent = total ? ((d.blocked / total) * 100).toFixed(1) + '%' : '—';
  } catch (e) {
    console.error('status error', e);
  }
}

// ── Stats / charts ───────────────────────────────────────────────────────────
async function refreshStats() {
  try {
    const d = await fetch('/api/stats').then(r => r.json());

    // Hourly chart
    const labels = d.hourly.map(h => h.hour);
    const data   = d.hourly.map(h => h.blocked);
    if (!hourlyChart) {
      const ctx = document.getElementById('hourlyChart').getContext('2d');
      hourlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Blocked',
            data,
            backgroundColor: 'rgba(248,81,73,0.5)',
            borderColor: '#f85149',
            borderWidth: 1,
            borderRadius: 3,
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: '#7d8590', maxTicksLimit: 8 }, grid: { color: '#21262d' } },
            y: { ticks: { color: '#7d8590' }, grid: { color: '#21262d' }, beginAtZero: true }
          }
        }
      });
    } else {
      hourlyChart.data.labels = labels;
      hourlyChart.data.datasets[0].data = data;
      hourlyChart.update('none');
    }

    // Attack type doughnut
    const typeLabels = Object.keys(d.attack_types);
    const typeData   = Object.values(d.attack_types);
    const palette = ['#f85149','#58a6ff','#c792ea','#50fa7b','#ffb86c','#8be9fd','#ff79c6','#f1fa8c','#69ff47','#aaa'];
    if (typeLabels.length === 0) {
      // No data yet — show placeholder
    } else {
      if (!typeChart) {
        const ctx2 = document.getElementById('typeChart').getContext('2d');
        typeChart = new Chart(ctx2, {
          type: 'doughnut',
          data: {
            labels: typeLabels,
            datasets: [{ data: typeData, backgroundColor: palette, borderWidth: 0 }]
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { position: 'right', labels: { color: '#e6edf3', font: { size: 11 } } }
            }
          }
        });
      } else {
        typeChart.data.labels = typeLabels;
        typeChart.data.datasets[0].data = typeData;
        typeChart.update('none');
      }
    }

    // Top IPs table
    const tbody = $('topIpsTable').querySelector('tbody');
    const maxCount = d.top_ips.length ? d.top_ips[0].count : 1;
    tbody.innerHTML = d.top_ips.map((row, i) => `
      <tr>
        <td>${i + 1}</td>
        <td style="font-family:monospace;color:var(--yellow)">${escHtml(row.ip)}</td>
        <td><strong style="color:var(--red)">${fmt(row.count)}</strong></td>
        <td><div class="bar-bg"><div class="bar-fill" style="width:${Math.round(row.count/maxCount*100)}%"></div></div></td>
      </tr>`).join('') || '<tr><td colspan="4" style="color:var(--text-muted);text-align:center;padding:1.5rem">No data yet</td></tr>';

  } catch (e) { console.error('stats error', e); }
}

// ── Events ───────────────────────────────────────────────────────────────────
async function refreshEvents() {
  if (eventsPaused) return;
  try {
    const url = `/api/events?limit=80${eventsFilter ? '&blocked=' + eventsFilter : ''}`;
    const events = await fetch(url).then(r => r.json());
    const tbody = $('eventsTbody');
    if (!events.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);text-align:center;padding:2rem">No events yet — send some traffic to port 80</td></tr>';
      return;
    }
    tbody.innerHTML = events.map(ev => {
      const blocked = ev.blocked;
      const statusClass = blocked ? 'status-blocked' : 'status-allowed';
      const statusLabel = blocked ? `🛑 ${ev.status}` : `✅ ${ev.status}`;
      return `<tr>
        <td>${timeStr(ev.ts)}</td>
        <td class="ip-cell">${escHtml(ev.ip)}</td>
        <td class="${statusClass}">${statusLabel}</td>
        <td class="uri-cell" title="${escHtml(ev.uri)}">${escHtml(ev.uri)}</td>
      </tr>`;
    }).join('');
  } catch (e) { console.error('events error', e); }
}

// Event filter buttons
$('filterAll').addEventListener('click', () => { eventsFilter = ''; refreshEvents(); });
$('filterBlocked').addEventListener('click', () => { eventsFilter = '1'; refreshEvents(); });
$('filterAllowed').addEventListener('click', () => { eventsFilter = '0'; refreshEvents(); });
$('pauseBtn').addEventListener('click', () => {
  eventsPaused = !eventsPaused;
  $('pauseBtn').textContent = eventsPaused ? '▶ Resume' : '⏸ Pause';
});

// ── Rules ─────────────────────────────────────────────────────────────────────
async function refreshRules() {
  try {
    const rules = await fetch('/api/rules').then(r => r.json());
    if (rules.error) {
      $('rulesTbody').innerHTML = `<tr><td colspan="5" style="color:var(--red);padding:1rem">${escHtml(rules.error)}</td></tr>`;
      return;
    }
    $('ruleCount').textContent = `${rules.length} rules`;
    $('rulesTbody').innerHTML = rules.map(r => {
      const tc = tagClass(r.tag);
      const label = shortTag(r.tag);
      return `<tr>
        <td><code style="color:var(--blue)">${r.id}</code></td>
        <td><span class="tag-pill ${tc}">${escHtml(label)}</span></td>
        <td>${escHtml(r.msg)}</td>
        <td style="font-family:monospace;font-size:.75rem;color:var(--text-muted)">${escHtml(r.variables)}</td>
        <td style="font-family:monospace;font-size:.72rem;color:var(--text-muted);max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(r.operator)}">${escHtml(r.operator)}</td>
      </tr>`;
    }).join('');
  } catch (e) { console.error('rules error', e); }
}

// ── Logs ──────────────────────────────────────────────────────────────────────
async function refreshLogs() {
  await Promise.all([refreshAccessLog(), refreshAuditLog()]);
}

async function refreshAccessLog() {
  try {
    const d = await fetch('/api/logs/raw?n=100').then(r => r.json());
    const viewer = $('accessLogViewer');
    viewer.innerHTML = (d.lines || []).reverse().map(line => {
      const blocked = / (4[01][34]|429) /.test(line);
      const cls = blocked ? 'log-line-blocked' : 'log-line-allowed';
      return `<div class="${cls}">${escHtml(line)}</div>`;
    }).join('');
  } catch (e) {
    $('accessLogViewer').textContent = 'Error loading log';
  }
}

async function refreshAuditLog() {
  try {
    const d = await fetch('/api/logs/audit?n=80').then(r => r.json());
    const viewer = $('auditLogViewer');
    viewer.innerHTML = (d.lines || []).reverse().map(line =>
      `<div>${escHtml(line)}</div>`
    ).join('') || '<div style="color:var(--text-muted)">Audit log is empty (no blocked requests yet)</div>';
  } catch (e) {
    $('auditLogViewer').textContent = 'Error loading audit log';
  }
}

$('refreshAccessLog').addEventListener('click', refreshAccessLog);
$('refreshAuditLog').addEventListener('click', refreshAuditLog);

// ── Engine mode ───────────────────────────────────────────────────────────────
$('applyEngine').addEventListener('click', async () => {
  const mode = $('engineMode').value;
  $('applyEngine').disabled = true;
  $('applyEngine').innerHTML = '<span class="spinner"></span>';
  try {
    const r = await fetch('/api/engine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    }).then(r => r.json());
    if (r.ok) {
      $('applyEngine').textContent = '✓';
      setTimeout(() => { $('applyEngine').textContent = 'Apply'; $('applyEngine').disabled = false; }, 1500);
    } else {
      alert('Error: ' + r.error);
      $('applyEngine').textContent = 'Apply';
      $('applyEngine').disabled = false;
    }
  } catch (e) {
    $('applyEngine').textContent = 'Apply';
    $('applyEngine').disabled = false;
  }
});

// ── Test suite ────────────────────────────────────────────────────────────────
$('runTestBtn').addEventListener('click', async () => {
  const btn = $('runTestBtn');
  const out = $('testOutput');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Running...';
  out.innerHTML = '<div style="color:var(--text-muted)">Running test suite, please wait...</div>';

  try {
    const d = await fetch('/api/test', { method: 'POST' }).then(r => r.json());
    if (d.error) {
      out.innerHTML = `<div style="color:var(--red)">Error: ${escHtml(d.error)}</div>`;
    } else {
      out.innerHTML = d.output.split('\n').map(line => {
        let cls = '';
        if (line.includes('[BLOCKED]'))     cls = 'line-pass';
        else if (line.includes('[ALLOWED]') && line.includes('WAF miss')) cls = 'line-allowed';
        else if (line.includes('Results:') || line.includes('effectiveness')) cls = 'line-result';
        return `<div class="${cls}">${escHtml(line)}</div>`;
      }).join('');
    }
  } catch (e) {
    out.innerHTML = `<div style="color:var(--red)">Request failed: ${escHtml(String(e))}</div>`;
  }

  btn.textContent = '▶ Run Tests';
  btn.disabled = false;
});

// ── Polling ───────────────────────────────────────────────────────────────────
function pollAll() {
  refreshStatus();
  refreshStats();
  const activeTab = document.querySelector('.nav-item.active')?.dataset.tab;
  if (activeTab === 'events') refreshEvents();
}

pollAll();
setInterval(pollAll, 5000);
// Auto-refresh events faster when on that tab
setInterval(() => {
  const activeTab = document.querySelector('.nav-item.active')?.dataset.tab;
  if (activeTab === 'events') refreshEvents();
}, 2000);
