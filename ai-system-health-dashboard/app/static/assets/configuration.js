(() => {
  function $(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element: #${id}`);
    return el;
  }

  const els = {
    conn: $('cfgConn'),
    user: $('cfgUser'),
    err: $('cfgErr'),

    appTitle: $('cfgAppTitle'),
    appVersion: $('cfgAppVersion'),
    helpUrl: $('cfgHelpUrl'),

    sampleInterval: $('cfgSampleInterval'),
    historySeconds: $('cfgHistorySeconds'),

    anomWindow: $('cfgAnomWindow'),
    anomZ: $('cfgAnomZ'),

    protoInterval: $('cfgProtoInterval'),
    ntpServer: $('cfgNtpServer'),
    ntpTimeout: $('cfgNtpTimeout'),
    icmpHost: $('cfgIcmpHost'),
    icmpTimeout: $('cfgIcmpTimeout'),
    snmpHost: $('cfgSnmpHost'),
    snmpPort: $('cfgSnmpPort'),
    snmpTimeout: $('cfgSnmpTimeout'),
    snmpCommunitySet: $('cfgSnmpCommunitySet'),
    netflowPort: $('cfgNetflowPort'),

    storageEnabled: $('cfgStorageEnabled'),
    retention: $('cfgRetention'),
    dbBlock: document.getElementById('cfgDbBlock'),
    dbJson: document.getElementById('cfgDbJson'),

    pathsCard: document.getElementById('cfgPathsCard'),
    pathsJson: document.getElementById('cfgPathsJson'),

    sessName: $('cfgSessName'),
    sessAge: $('cfgSessAge'),
    sameSite: $('cfgSameSite'),
    secure: $('cfgSecure'),
    rememberName: $('cfgRememberName'),
    rememberAge: $('cfgRememberAge'),

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
    if (!el) return;
    el.textContent = txt == null ? '—' : String(txt);
  }

  function fmtSeconds(s) {
    if (s == null) return '—';
    const n = Number(s);
    if (!Number.isFinite(n)) return '—';
    if (n >= 86400) return `${Math.round((n / 86400) * 10) / 10} days`;
    if (n >= 3600) return `${Math.round((n / 3600) * 10) / 10} hours`;
    if (n >= 60) return `${Math.round((n / 60) * 10) / 10} minutes`;
    return `${Math.round(n * 10) / 10} seconds`;
  }

  function fmtNumber(n, digits) {
    if (n == null) return '—';
    const v = Number(n);
    if (!Number.isFinite(v)) return '—';
    const d = typeof digits === 'number' ? digits : 2;
    return v.toFixed(d);
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
    els.conn.textContent = 'loading…';
    setupSidebarSearch();

    try {
      const [me, cfg] = await Promise.all([fetchJson('/api/me'), fetchJson('/api/config')]);

      setText(els.user, me && me.username ? me.username : '—');

      setText(els.appTitle, cfg && cfg.app ? cfg.app.title : '—');
      setText(els.appVersion, cfg && cfg.app ? cfg.app.version : '—');
      setText(els.helpUrl, cfg && cfg.app && cfg.app.help_url ? cfg.app.help_url : '—');

      setText(els.sampleInterval, cfg && cfg.sampling ? fmtSeconds(cfg.sampling.sample_interval_seconds) : '—');
      setText(els.historySeconds, cfg && cfg.sampling ? fmtSeconds(cfg.sampling.history_seconds) : '—');

      setText(els.anomWindow, cfg && cfg.anomaly ? fmtSeconds(cfg.anomaly.window_seconds) : '—');
      setText(els.anomZ, cfg && cfg.anomaly ? fmtNumber(cfg.anomaly.z_threshold, 2) : '—');

      setText(els.protoInterval, cfg && cfg.protocols ? fmtSeconds(cfg.protocols.check_interval_seconds) : '—');
      setText(els.ntpServer, cfg && cfg.protocols && cfg.protocols.ntp ? cfg.protocols.ntp.server : '—');
      setText(els.ntpTimeout, cfg && cfg.protocols && cfg.protocols.ntp ? fmtSeconds(cfg.protocols.ntp.timeout_seconds) : '—');
      setText(els.icmpHost, cfg && cfg.protocols && cfg.protocols.icmp ? cfg.protocols.icmp.host : '—');
      setText(els.icmpTimeout, cfg && cfg.protocols && cfg.protocols.icmp ? fmtSeconds(cfg.protocols.icmp.timeout_seconds) : '—');
      setText(els.snmpHost, cfg && cfg.protocols && cfg.protocols.snmp ? (cfg.protocols.snmp.host || '—') : '—');
      setText(els.snmpPort, cfg && cfg.protocols && cfg.protocols.snmp ? cfg.protocols.snmp.port : '—');
      setText(els.snmpTimeout, cfg && cfg.protocols && cfg.protocols.snmp ? fmtSeconds(cfg.protocols.snmp.timeout_seconds) : '—');
      setText(els.snmpCommunitySet, cfg && cfg.protocols && cfg.protocols.snmp ? String(!!cfg.protocols.snmp.community_set) : '—');
      setText(els.netflowPort, cfg && cfg.protocols && cfg.protocols.netflow ? cfg.protocols.netflow.port : '—');

      setText(els.storageEnabled, cfg && cfg.storage ? String(!!cfg.storage.enabled) : '—');
      setText(els.retention, cfg && cfg.storage ? fmtSeconds(cfg.storage.sqlite_retention_seconds) : '—');

      if (els.dbBlock) {
        const hasDbStats = cfg && cfg.storage && cfg.storage.db_stats;
        els.dbBlock.style.display = hasDbStats ? '' : 'none';
        if (els.dbJson && hasDbStats) els.dbJson.textContent = JSON.stringify(cfg.storage.db_stats, null, 2);
      }

      if (els.pathsCard) {
        const hasPaths = cfg && cfg.paths;
        els.pathsCard.style.display = hasPaths ? '' : 'none';
        if (els.pathsJson && hasPaths) els.pathsJson.textContent = JSON.stringify(cfg.paths, null, 2);
      }

      setText(els.sessName, cfg && cfg.auth ? cfg.auth.session_cookie_name : '—');
      setText(els.sessAge, cfg && cfg.auth ? fmtSeconds(cfg.auth.session_max_age_seconds) : '—');
      setText(els.sameSite, cfg && cfg.auth ? cfg.auth.session_cookie_samesite : '—');
      setText(els.secure, cfg && cfg.auth ? String(!!cfg.auth.session_cookie_secure) : '—');
      setText(els.rememberName, cfg && cfg.auth ? cfg.auth.remember_cookie_name : '—');
      setText(els.rememberAge, cfg && cfg.auth ? fmtSeconds(cfg.auth.remember_max_age_seconds) : '—');

      els.conn.textContent = 'ready';
      setErr('');
    } catch (e) {
      els.conn.textContent = 'error';
      setErr(e && e.message ? e.message : 'Failed to load configuration');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
