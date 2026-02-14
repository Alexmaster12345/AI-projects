from __future__ import annotations

import json
from typing import Any, Dict, List


def render_index(*, alerts: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> str:
    # Server-rendered fallback snapshot (also used for first paint).
    initial_state = {
        "alerts": alerts,
        "events": events,
    }

    template = r"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SIEM</title>
    <style>
      :root {
        color-scheme: dark;

        --bg: Canvas;
        --fg: CanvasText;
        --muted: GrayText;
        --accent: AccentColor;
        --accentText: AccentColorText;

        /* Subtle “design system” built from system colors only */
        --page: color-mix(in srgb, Canvas 94%, CanvasText 6%);
        --panel: Canvas;
        --line: color-mix(in srgb, GrayText 45%, Canvas 55%);
        --lineSoft: color-mix(in srgb, GrayText 25%, Canvas 75%);
        --hover: color-mix(in srgb, AccentColor 8%, Canvas 92%);
        --zebra: color-mix(in srgb, Canvas 96%, CanvasText 4%);

        --r: 14px;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        background: var(--page);
        color: var(--fg);
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif;
        line-height: 1.35;
      }

      a { color: var(--accent); text-decoration: none; }
      a:hover { text-decoration: underline; }

      .wrap { max-width: 1240px; margin: 0 auto; padding: 18px; }

      .shell {
        display: grid;
        grid-template-columns: 260px 1fr;
        gap: 14px;
        align-items: start;
        margin-top: 14px;
      }

      @media (max-width: 980px) {
        .shell { grid-template-columns: 1fr; }
      }

      .nav {
        background: var(--panel);
        border: 1px solid var(--lineSoft);
        border-radius: var(--r);
        overflow: hidden;
        position: sticky;
        top: 64px;
      }

      .nav-head {
        padding: 12px;
        border-bottom: 1px solid var(--lineSoft);
      }

      .nav-title {
        margin: 0;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--fg) 82%, var(--muted) 18%);
      }

      .nav-items {
        padding: 8px;
        display: grid;
        gap: 8px;
      }

      .nav-btn {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        width: 100%;
        padding: 10px 10px;
        border: 1px solid var(--lineSoft);
        border-radius: 12px;
        background: var(--panel);
        color: inherit;
        cursor: pointer;
        text-align: left;
      }

      .nav-btn:hover { border-color: var(--accent); }

      .nav-btn:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }

      .nav-btn:disabled:hover { border-color: var(--lineSoft); }

      .nav-btn.active {
        border-color: var(--accent);
        background: color-mix(in srgb, var(--accent) 10%, var(--panel) 90%);
      }

      .nav-badge {
        font-size: 12px;
        padding: 2px 8px;
        border: 1px solid var(--lineSoft);
        border-radius: 999px;
        color: var(--muted);
      }

      .toolbox {
        display: grid;
        gap: 12px;
      }

      .tool {
        background: var(--panel);
        border: 1px solid var(--lineSoft);
        border-radius: var(--r);
        overflow: hidden;
      }

      .tool-head {
        padding: 12px;
        border-bottom: 1px solid var(--lineSoft);
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
      }

      .tool-title {
        margin: 0;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--fg) 82%, var(--muted) 18%);
      }

      .tool-body {
        padding: 12px;
        display: grid;
        gap: 10px;
      }

      textarea {
        width: 100%;
        min-height: 110px;
        resize: vertical;
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
        color: inherit;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 12px;
        line-height: 1.4;
        outline: none;
      }

      textarea:focus { border-color: var(--accent); }

      .tool-actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }

      .hint {
        font-size: 12px;
        color: var(--muted);
      }

      .topbar {
        position: sticky;
        top: 0;
        z-index: 10;
        background: color-mix(in srgb, var(--page) 92%, var(--panel) 8%);
        border-bottom: 1px solid var(--lineSoft);
        backdrop-filter: blur(6px);
      }

      .topbar-inner {
        max-width: 1240px;
        margin: 0 auto;
        padding: 14px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }

      .brand {
        display: grid;
        gap: 2px;
      }

      h1 {
        margin: 0;
        font-size: 16px;
        letter-spacing: 0.02em;
      }

      .muted { color: var(--muted); }
      .status { font-size: 12px; }
      .links { font-size: 12px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

      .chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border: 1px solid var(--lineSoft);
        border-radius: 999px;
        background: var(--panel);
        color: inherit;
      }

      .toolbar {
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 10px;
        margin-top: 14px;
      }

      input[type="search"] {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
        color: inherit;
        outline: none;
      }

      input[type="search"]:focus {
        border-color: var(--accent);
      }

      button {
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
        color: inherit;
        cursor: pointer;
      }

      button:hover { border-color: var(--accent); }
      button:active { transform: translateY(0.5px); }
      
      .btn-live { position: relative; }
      .btn-live.active {
        border-color: var(--accent);
        background: color-mix(in srgb, var(--accent) 15%, var(--panel) 85%);
        animation: pulse 2s ease-in-out infinite;
      }
      .btn-live.active::before {
        content: "🟢";
        position: absolute;
        left: 10px;
      }
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
      }
      
      .updating {
        animation: fadeUpdate 0.3s ease-in-out;
      }
      @keyframes fadeUpdate {
        0% { opacity: 1; }
        50% { opacity: 0.6; }
        100% { opacity: 1; }
      }
      
      .live-indicator {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--accent) 10%, var(--panel) 90%);
        font-size: 11px;
        border: 1px solid var(--lineSoft);
      }
      
      .live-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--accent);
        animation: blink 2s ease-in-out infinite;
      }
      
      @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
      }

      .kpis {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 12px;
      }

      .kpi {
        background: var(--panel);
        border: 1px solid var(--lineSoft);
        border-radius: var(--r);
        padding: 10px 12px;
        min-width: 150px;
      }

      .kpi .n { font-size: 18px; font-weight: 750; }
      .kpi .l { font-size: 12px; color: var(--muted); }

      .grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 14px;
        margin-top: 12px;
      }

      .dash-grid {
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 14px;
        margin-top: 12px;
        align-items: start;
      }

      .dash-left {
        display: grid;
        gap: 14px;
      }

      .dash-right {
        display: grid;
        gap: 14px;
      }

      @media (max-width: 980px) {
        .dash-grid { grid-template-columns: 1fr; }
      }

      .viz {
        border: 1px solid var(--lineSoft);
        border-radius: 12px;
        background: color-mix(in srgb, var(--panel) 92%, var(--page) 8%);
        overflow: hidden;
      }

      .viz canvas {
        width: 100%;
        height: 260px;
        display: block;
      }

      .health {
        display: grid;
        grid-template-columns: 110px 1fr;
        gap: 12px;
        align-items: center;
      }

      .gauge {
        width: 110px;
        height: 110px;
        border-radius: 999px;
        border: 1px solid var(--lineSoft);
        background: color-mix(in srgb, var(--panel) 92%, var(--page) 8%);
        display: grid;
        place-items: center;
        position: relative;
      }

      .gauge svg { width: 96px; height: 96px; }

      .gauge .gtxt {
        position: absolute;
        text-align: center;
        font-size: 12px;
        line-height: 1.15;
      }

      .kvlist { display: grid; gap: 6px; }
      .kvrow { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; }

      .stream {
        border: 1px solid var(--lineSoft);
        border-radius: 12px;
        background: color-mix(in srgb, var(--panel) 92%, var(--page) 8%);
        padding: 10px 12px;
        max-height: 240px;
        overflow: auto;
        font-size: 12px;
        line-height: 1.45;
        white-space: pre-wrap;
      }

      .card {
        background: var(--panel);
        border: 1px solid var(--lineSoft);
        border-radius: var(--r);
        overflow: hidden;
      }

      .card-head {
        padding: 12px 12px 10px 12px;
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
        border-bottom: 1px solid var(--lineSoft);
      }

      .card h2 {
        margin: 0;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--fg) 82%, var(--muted) 18%);
      }

      .table-wrap { overflow: auto; }

      table { border-collapse: collapse; width: 100%; font-size: 12px; }
      th, td { border-top: 1px solid var(--lineSoft); padding: 8px 10px; vertical-align: top; }

      thead th {
        position: sticky;
        top: 0;
        background: var(--panel);
        border-top: none;
        border-bottom: 1px solid var(--lineSoft);
        text-align: left;
        font-weight: 650;
        white-space: nowrap;
      }

      tbody tr:nth-child(2n) td { background: var(--zebra); }
      tbody tr:hover td { background: var(--hover); }

      tbody tr.selected td {
        background: color-mix(in srgb, var(--accent) 12%, var(--panel) 88%) !important;
      }

      .mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      }

      .row-msg { white-space: pre-wrap; word-break: break-word; min-width: 380px; }

      .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 2px 8px;
        border: 1px solid var(--line);
        border-radius: 999px;
        font-size: 11px;
        line-height: 1.6;
        background: color-mix(in srgb, var(--panel) 86%, var(--accent) 14%);
      }

      .pill::before {
        content: "";
        width: 7px;
        height: 7px;
        border-radius: 999px;
        background: var(--accent);
      }

      .sev-high { border-color: color-mix(in srgb, crimson 40%, var(--line) 60%); background: color-mix(in srgb, crimson 10%, var(--panel) 90%); }
      .sev-high::before { background: crimson; }
      .sev-medium { border-color: color-mix(in srgb, goldenrod 45%, var(--line) 55%); background: color-mix(in srgb, goldenrod 10%, var(--panel) 90%); }
      .sev-medium::before { background: goldenrod; }
      .sev-low { border-color: color-mix(in srgb, seagreen 45%, var(--line) 55%); background: color-mix(in srgb, seagreen 10%, var(--panel) 90%); }
      .sev-low::before { background: seagreen; }

      .footer { margin-top: 14px; font-size: 12px; color: var(--muted); }
      .err { margin-top: 10px; padding: 10px; border: 1px solid var(--line); border-radius: var(--r); background: var(--panel); }

      .drawer {
        position: fixed;
        top: 0;
        right: 0;
        height: 100vh;
        width: min(520px, 92vw);
        background: var(--panel);
        border-left: 1px solid var(--lineSoft);
        box-shadow: 0 0 0 1px var(--lineSoft);
        transform: translateX(100%);
        transition: transform 160ms ease;
        z-index: 30;
        display: grid;
        grid-template-rows: auto 1fr auto;
      }

      .drawer.open { transform: translateX(0); }

      .drawer-head {
        padding: 14px;
        border-bottom: 1px solid var(--lineSoft);
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 10px;
      }

      .drawer-title {
        margin: 0;
        font-size: 13px;
        letter-spacing: 0.02em;
      }

      .drawer-sub {
        margin-top: 6px;
        font-size: 12px;
        color: var(--muted);
      }

      .drawer-body {
        padding: 14px;
        overflow: auto;
      }

      .kv {
        display: grid;
        grid-template-columns: 120px 1fr;
        gap: 8px 10px;
        margin-bottom: 12px;
        font-size: 12px;
      }

      .kv .k { color: var(--muted); }
      .kv .v { word-break: break-word; }

      .json {
        border: 1px solid var(--lineSoft);
        border-radius: 12px;
        padding: 10px;
        background: color-mix(in srgb, var(--panel) 92%, var(--page) 8%);
        font-size: 12px;
        line-height: 1.4;
        overflow: auto;
      }

      .drawer-foot {
        padding: 12px 14px;
        border-top: 1px solid var(--lineSoft);
        display: flex;
        justify-content: flex-end;
        gap: 10px;
      }
    </style>
  </head>
  <body>
    <div class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <h1>VOLVIX</h1>
          <div class="status muted" id="statusBar">
            <span id="status">Loading…</span>
            <span id="liveCounter" style="display:none;" class="live-indicator">
              <span class="live-dot"></span>
            </span>
          </div>
        </div>
        <div class="links">
          <span class="chip"><span class="muted">SOC</span> <span id="who">analyst</span></span>
          <a class="chip" href="/docs" title="Open API docs">API docs</a>
          <button class="chip" id="btnSettings" type="button" title="Settings (placeholder)">Settings</button>
        </div>
      </div>
    </div>

    <div class="wrap">
      <div class="shell">
        <aside class="nav" aria-label="navigation">
          <div class="nav-head">
            <div class="nav-title">Navigation</div>
          </div>
          <div class="nav-items">
            <button class="nav-btn active" id="navDashboard" type="button">
              <span>Dashboard</span>
              <span class="nav-badge">Live</span>
            </button>
            <button class="nav-btn" id="navThreats" type="button">
              <span>Threats</span>
              <span class="nav-badge" id="navAlertsCount">0</span>
            </button>
            <button class="nav-btn" id="navLogs" type="button">
              <span>Logs</span>
              <span class="nav-badge" id="navEventsCount">0</span>
            </button>
            <button class="nav-btn" id="navVulns" type="button">
              <span>Vulnerabilities</span>
              <span class="nav-badge">Beta</span>
            </button>
            <button class="nav-btn" id="navReports" type="button">
              <span>Reports</span>
              <span class="nav-badge">Beta</span>
            </button>
            <button class="nav-btn" id="navTools" type="button">
              <span>Tools</span>
              <span class="nav-badge">Local</span>
            </button>
            <button class="nav-btn" type="button" disabled>
              <span>Configuration</span>
              <span class="nav-badge">Soon</span>
            </button>
          </div>
        </aside>

        <main>
          <div class="toolbar" id="toolbar" style="display:none;">
            <input id="q" type="search" placeholder="Search events (message, host, source, ip, agent_id)…" autocomplete="off" />
            <button id="btnSearch" title="Search">Search</button>
            <button id="btnRefresh" title="Reload latest">Refresh</button>
            <button id="btnLive" class="btn-live" title="Toggle live auto-refresh (5s)">🔴 Live</button>
          </div>

          <section class="dash-grid" aria-label="dashboard" id="panelDashboard">
            <div class="dash-left">
              <section class="card" aria-label="global threat map">
                <div class="card-head">
                  <h2>Global Threat Map</h2>
                  <div class="muted" style="font-size:12px;" id="mapSubtitle">Loading...</div>
                </div>
                <div class="tool-body">
                  <div class="viz"><canvas id="mapCanvas" width="1200" height="520"></canvas></div>
                  <div class="hint" id="mapHint">Real-time threat activity from alerts</div>
                </div>
              </section>

              <section class="card" aria-label="event volume and trends">
                <div class="card-head">
                  <h2>Event Volume & Trends</h2>
                  <div class="muted" style="font-size:12px;" id="trendSubtitle">Last 14 days</div>
                </div>
                <div class="tool-body">
                  <div class="viz"><canvas id="trendCanvas" width="1200" height="520"></canvas></div>
                </div>
              </section>

              <section class="card" aria-label="real-time event stream">
                <div class="card-head">
                  <h2>Real-time Event Stream</h2>
                  <div class="muted" style="font-size:12px;">Latest messages</div>
                </div>
                <div class="tool-body">
                  <div class="stream mono" id="streamBox">Loading…</div>
                </div>
              </section>
            </div>

            <div class="dash-right">
              <section class="card" aria-label="system health overview">
                <div class="card-head">
                  <h2>System Health Overview</h2>
                  <div class="muted" style="font-size:12px;">Alert pressure</div>
                </div>
                <div class="tool-body">
                  <div class="health">
                    <div class="gauge" aria-label="overall threat level">
                      <svg viewBox="0 0 100 100" role="img" aria-label="gauge">
                        <circle cx="50" cy="50" r="38" fill="none" stroke="color-mix(in srgb, GrayText 35%, Canvas 65%)" stroke-width="10" />
                        <circle id="gaugeArc" cx="50" cy="50" r="38" fill="none" stroke="var(--accent)" stroke-width="10" stroke-linecap="round"
                          stroke-dasharray="0 999" transform="rotate(-90 50 50)" />
                      </svg>
                      <div class="gtxt">
                        <div class="muted" style="font-size:11px; letter-spacing:0.06em;">LEVEL</div>
                        <div style="font-weight:800;" id="gaugeLabel">—</div>
                      </div>
                    </div>
                    <div class="kvlist" id="healthKV"></div>
                  </div>
                </div>
              </section>

              <section class="card" aria-label="critical problems">
                <div class="card-head">
                  <h2>Critical Problems</h2>
                  <div class="muted" style="font-size:12px;">Top detections</div>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>rule</th>
                        <th>title</th>
                        <th>count</th>
                        <th>sev</th>
                      </tr>
                    </thead>
                    <tbody id="critBody"></tbody>
                  </table>
                </div>
              </section>

              <div class="kpis" aria-label="summary">
                <div class="kpi">
                  <div class="n" id="kpiAlerts">0</div>
                  <div class="l">threats loaded</div>
                </div>
                <div class="kpi">
                  <div class="n" id="kpiEvents">0</div>
                  <div class="l">logs loaded</div>
                </div>
              </div>
            </div>
          </section>

          <div class="grid">
            <section class="card" aria-label="vulnerabilities" id="panelVulns" style="display:none;">
              <div class="card-head">
                <h2>Vulnerabilities</h2>
                <div class="muted" style="font-size:12px;">Inventory & findings (not configured)</div>
              </div>
              <div class="tool-body">
                <div class="hint">No vulnerability scanner/inventory feed is configured in this MVP.</div>
                <div class="hint">Connect a feed (e.g., SBOM, CVE scanner output, or asset inventory) to populate this panel.</div>
              </div>
            </section>

            <section class="card" aria-label="reports" id="panelReports" style="display:none;">
              <div class="card-head">
                <h2>Reports</h2>
                <div class="muted" style="font-size:12px;">Exports & summaries (not configured)</div>
              </div>
              <div class="tool-body">
                <div class="hint">No scheduled reporting is configured in this MVP.</div>
                <div class="hint">Use Tools → Export to download alerts/events JSON.</div>
              </div>
            </section>

            <section class="card" aria-label="threats" id="panelAlerts" style="display:none;">
              <div class="card-head">
                <h2>Threats</h2>
                <div class="tool-actions" style="align-items:center;">
                  <button id="btnAlertsDownload" type="button" title="Download current threats as JSON">Download</button>
                  <button id="btnAlertsClear" type="button" title="Clear currently loaded threats">Clear</button>
                </div>
                <div class="muted" style="font-size:12px;">Prioritized detections</div>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>id</th>
                      <th>ts</th>
                      <th>severity</th>
                      <th>rule</th>
                      <th>title</th>
                      <th>event</th>
                      <th>ips</th>
                      <th>agent_id</th>
                    </tr>
                  </thead>
                  <tbody id="alertsBody"></tbody>
                </table>
              </div>
            </section>

            <section class="card" aria-label="logs" id="panelEvents" style="display:none;">
              <div class="card-head">
                <h2>Logs</h2>
                <div class="tool-actions" style="align-items:center;">
                  <button id="btnEventsDownload" type="button" title="Download current logs as JSON">Download</button>
                  <button id="btnEventsClear" type="button" title="Clear currently loaded logs">Clear</button>
                </div>
                <div class="muted" style="font-size:12px;">Raw telemetry</div>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>id</th>
                      <th>ts</th>
                      <th>source</th>
                      <th>host</th>
                      <th>severity</th>
                      <th>message</th>
                      <th>ips</th>
                      <th>agent_id</th>
                    </tr>
                  </thead>
                  <tbody id="eventsBody"></tbody>
                </table>
              </div>
            </section>

            <section class="toolbox" aria-label="tools" id="panelTools" style="display:none;">
              <div class="tool">
                <div class="tool-head">
                  <div class="tool-title">Crypto</div>
                  <div class="hint">Hashes / checksums (server-side)</div>
                </div>
                <div class="tool-body">
                  <div class="tool-actions" style="align-items:center;">
                    <select id="cryptoFormat" style="padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:inherit;min-width:150px;">
                      <option value="text" selected>text (UTF-8)</option>
                      <option value="hex">hex</option>
                      <option value="base64">base64</option>
                    </select>
                    <select id="cryptoAlg" style="padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:inherit;min-width:260px;">
                      <option value="ALL" selected>ALL (compute everything)</option>
                      <option>NTLM</option>
                      <option>MD2</option>
                      <option>MD4</option>
                      <option>MD5</option>
                      <option>MD6-128</option>
                      <option>MD6-256</option>
                      <option>MD6-512</option>
                      <option>RipeMD-128</option>
                      <option>RipeMD-160</option>
                      <option>RipeMD-256</option>
                      <option>RipeMD-320</option>
                      <option>SHA1</option>
                      <option>SHA-224</option>
                      <option>SHA-256</option>
                      <option>SHA-384</option>
                      <option>SHA-512</option>
                      <option>SHA3-224</option>
                      <option>SHA3-256</option>
                      <option>SHA3-384</option>
                      <option>SHA3-512</option>
                      <option>CRC16</option>
                      <option>CRC32</option>
                      <option>Adler32</option>
                      <option>Whirlpool</option>
                    </select>
                    <button id="btnCryptoRun" type="button">Compute</button>
                    <button id="btnCryptoCopy" type="button">Copy</button>
                    <button id="btnCryptoClear" type="button">Clear</button>
                  </div>
                  <textarea id="cryptoInput" placeholder="Paste input…"></textarea>
                  <textarea id="cryptoOutput" placeholder="Results…" readonly></textarea>
                  <div class="hint">Tip: leave input_format=text for NTLM (it hashes the password as UTF-16LE). Some legacy algorithms may be unsupported.</div>
                </div>
              </div>

              <div class="tool">
                <div class="tool-head">
                  <div class="tool-title">IOC Extractor</div>
                  <div class="hint">Extract IPs, domains, URLs, hashes</div>
                </div>
                <div class="tool-body">
                  <textarea id="iocInput" placeholder="Paste an alert/event message, email, or log snippet…"></textarea>
                  <div class="tool-actions">
                    <button id="btnIocExtract" type="button">Extract</button>
                    <button id="btnIocCopy" type="button">Copy</button>
                    <button id="btnIocClear" type="button">Clear</button>
                  </div>
                  <textarea id="iocOutput" placeholder="IOCs will appear here…" readonly></textarea>
                </div>
              </div>

              <div class="tool">
                <div class="tool-head">
                  <div class="tool-title">Base64</div>
                  <div class="hint">Decode/encode quickly</div>
                </div>
                <div class="tool-body">
                  <textarea id="b64Input" placeholder="Paste base64 or plain text…"></textarea>
                  <div class="tool-actions">
                    <button id="btnB64Decode" type="button">Decode</button>
                    <button id="btnB64Encode" type="button">Encode</button>
                    <button id="btnB64Copy" type="button">Copy</button>
                    <button id="btnB64Clear" type="button">Clear</button>
                  </div>
                  <textarea id="b64Output" placeholder="Output…" readonly></textarea>
                </div>
              </div>

              <div class="tool">
                <div class="tool-head">
                  <div class="tool-title">Export</div>
                  <div class="hint">Download current alerts/events as JSON</div>
                </div>
                <div class="tool-body">
                  <div class="tool-actions">
                    <button id="btnExportAlerts" type="button">Download alerts.json</button>
                    <button id="btnExportEvents" type="button">Download events.json</button>
                  </div>
                  <div class="hint">Exports what’s currently loaded in the dashboard.</div>
                </div>
              </div>

              <div class="tool">
                <div class="tool-head">
                  <div class="tool-title">Virus Scan</div>
                  <div class="hint">Runs ClamAV (clamscan) and streams logs</div>
                </div>
                <div class="tool-body">
                  <div class="tool-actions" style="align-items:center;">
                    <input id="scanPath" type="search" placeholder="Path to scan (file or directory)…" autocomplete="off" />
                    <label class="hint" style="display:flex;align-items:center;gap:8px;">
                      <input id="scanRecursive" type="checkbox" />
                      recursive
                    </label>
                    <button id="btnScanStart" type="button">Scan</button>
                    <button id="btnScanStop" type="button">Stop log</button>
                  </div>
                  <textarea id="scanLog" placeholder="Scan logs…" readonly></textarea>
                  <div class="hint" id="scanStatus">Idle</div>
                </div>
              </div>

              <div class="tool">
                <div class="tool-head">
                  <div class="tool-title">Network Monitor</div>
                  <div class="hint">Packet summary or full PCAP capture (tcpdump)</div>
                </div>
                <div class="tool-body">
                  <div class="tool-actions" style="align-items:center;">
                    <select id="netIface" style="padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:inherit;min-width:160px;">
                      <option value="">loading…</option>
                    </select>
                    <input id="netFilter" type="search" placeholder="BPF filter (e.g. tcp port 443)" autocomplete="off" />
                    <button id="btnNetStart" type="button">Start summary</button>
                    <button id="btnNetCapture" type="button">Capture PCAP</button>
                    <button id="btnNetStop" type="button">Stop</button>
                    <button id="btnNetDownload" type="button" disabled>Download PCAP</button>
                  </div>
                  <textarea id="netLog" placeholder="Packet summaries…" readonly></textarea>
                  <div class="hint" id="netStatus">Idle</div>
                  <div class="hint">Leave filter blank to capture all traffic (all protocols). Packet capture may require root/capabilities.</div>
                </div>
              </div>
            </section>
          </div>

          <div id="error" class="err" style="display:none;"></div>

          <div class="footer">
            Tip: POST JSON events to <span class="mono">/ingest</span> or run the tail collector.
          </div>
        </main>
      </div>
    </div>

    <aside class="drawer" id="drawer" aria-label="details" aria-hidden="true">
      <div class="drawer-head">
        <div>
          <div class="drawer-title" id="drawerTitle">Details</div>
          <div class="drawer-sub" id="drawerSub">Select an item to inspect</div>
        </div>
        <button id="drawerClose" type="button" title="Close">Close</button>
      </div>
      <div class="drawer-body">
        <div class="kv" id="drawerKV"></div>
        <div class="json mono" id="drawerJson">{}</div>
      </div>
      <div class="drawer-foot">
        <button id="drawerCopy" type="button" title="Copy JSON">Copy JSON</button>
      </div>
    </aside>

    <script>
      const initial = __INITIAL_STATE__;

      const statusEl = document.getElementById('status');
      const errEl = document.getElementById('error');
      const qEl = document.getElementById('q');
      const btnSearch = document.getElementById('btnSearch');
      const btnRefresh = document.getElementById('btnRefresh');
      const btnLive = document.getElementById('btnLive');
      const liveCounter = document.getElementById('liveCounter');
      let liveInterval = null;
      let isLive = false;
      const alertsBody = document.getElementById('alertsBody');
      const eventsBody = document.getElementById('eventsBody');
      const kpiAlerts = document.getElementById('kpiAlerts');
      const kpiEvents = document.getElementById('kpiEvents');

      const navDashboard = document.getElementById('navDashboard');
      const navThreats = document.getElementById('navThreats');
      const navLogs = document.getElementById('navLogs');
      const navVulns = document.getElementById('navVulns');
      const navReports = document.getElementById('navReports');
      const navTools = document.getElementById('navTools');
      const navAlertsCount = document.getElementById('navAlertsCount');
      const navEventsCount = document.getElementById('navEventsCount');
      const toolbar = document.getElementById('toolbar');
      const panelDashboard = document.getElementById('panelDashboard');
      const panelVulns = document.getElementById('panelVulns');
      const panelReports = document.getElementById('panelReports');
      const panelAlerts = document.getElementById('panelAlerts');
      const panelEvents = document.getElementById('panelEvents');
      const panelTools = document.getElementById('panelTools');

      const btnSettings = document.getElementById('btnSettings');

      const mapCanvas = document.getElementById('mapCanvas');
      const trendCanvas = document.getElementById('trendCanvas');
      const mapSubtitle = document.getElementById('mapSubtitle');
      const trendSubtitle = document.getElementById('trendSubtitle');
      const mapHint = document.getElementById('mapHint');
      const streamBox = document.getElementById('streamBox');
      const critBody = document.getElementById('critBody');
      const gaugeArc = document.getElementById('gaugeArc');
      const gaugeLabel = document.getElementById('gaugeLabel');
      const healthKV = document.getElementById('healthKV');

      const drawer = document.getElementById('drawer');
      const drawerClose = document.getElementById('drawerClose');
      const drawerCopy = document.getElementById('drawerCopy');
      const drawerTitle = document.getElementById('drawerTitle');
      const drawerSub = document.getElementById('drawerSub');
      const drawerKV = document.getElementById('drawerKV');
      const drawerJson = document.getElementById('drawerJson');

      let currentAlerts = [];
      let currentEvents = [];
      let selected = null; // { type: 'alert'|'event', id: number }

      const iocInput = document.getElementById('iocInput');
      const iocOutput = document.getElementById('iocOutput');
      const btnIocExtract = document.getElementById('btnIocExtract');
      const btnIocCopy = document.getElementById('btnIocCopy');
      const btnIocClear = document.getElementById('btnIocClear');

      const b64Input = document.getElementById('b64Input');
      const b64Output = document.getElementById('b64Output');
      const btnB64Decode = document.getElementById('btnB64Decode');
      const btnB64Encode = document.getElementById('btnB64Encode');
      const btnB64Copy = document.getElementById('btnB64Copy');
      const btnB64Clear = document.getElementById('btnB64Clear');

      const btnExportAlerts = document.getElementById('btnExportAlerts');
      const btnExportEvents = document.getElementById('btnExportEvents');

      const btnAlertsDownload = document.getElementById('btnAlertsDownload');
      const btnAlertsClear = document.getElementById('btnAlertsClear');
      const btnEventsDownload = document.getElementById('btnEventsDownload');
      const btnEventsClear = document.getElementById('btnEventsClear');

      const cryptoFormat = document.getElementById('cryptoFormat');
      const cryptoAlg = document.getElementById('cryptoAlg');
      const btnCryptoRun = document.getElementById('btnCryptoRun');
      const btnCryptoCopy = document.getElementById('btnCryptoCopy');
      const btnCryptoClear = document.getElementById('btnCryptoClear');
      const cryptoInput = document.getElementById('cryptoInput');
      const cryptoOutput = document.getElementById('cryptoOutput');

      const scanPath = document.getElementById('scanPath');
      const scanRecursive = document.getElementById('scanRecursive');
      const btnScanStart = document.getElementById('btnScanStart');
      const btnScanStop = document.getElementById('btnScanStop');
      const scanLog = document.getElementById('scanLog');
      const scanStatus = document.getElementById('scanStatus');
      const netIface = document.getElementById('netIface');
      const netFilter = document.getElementById('netFilter');
      const btnNetStart = document.getElementById('btnNetStart');
      const btnNetCapture = document.getElementById('btnNetCapture');
      const btnNetStop = document.getElementById('btnNetStop');
      const btnNetDownload = document.getElementById('btnNetDownload');
      const netLog = document.getElementById('netLog');
      const netStatus = document.getElementById('netStatus');

      let netSessionId = null;
      let netPoll = null;

      function setNetDownloadEnabled(enabled) {
        if (!btnNetDownload) return;
        btnNetDownload.disabled = !enabled;
      }

      let scanPoll = null;

      function escapeHtml(s) {
        return String(s ?? '')
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#39;');
      }
      function stopNetPolling() {
        if (netPoll) {
          clearInterval(netPoll);
          netPoll = null;
        }
      }

      function pill(severity) {
        const s = String(severity ?? '').trim();
        if (!s) return '<span class="muted">—</span>';
        const norm = s.toLowerCase();
        const cls = norm === 'high' ? 'sev-high' : (norm === 'medium' ? 'sev-medium' : (norm === 'low' ? 'sev-low' : ''));
        return `<span class="pill ${cls}">${escapeHtml(norm)}</span>`;
      }

      function renderAlerts(items) {
        currentAlerts = items;
        kpiAlerts.textContent = String(items.length);
        navAlertsCount.textContent = String(items.length);
        if (!items.length) {
          alertsBody.innerHTML = `<tr><td colspan="8" class="muted">No alerts</td></tr>`;
          return;
        }
        alertsBody.innerHTML = items.map(a => `
          <tr data-type="alert" data-id="${escapeHtml(a.id)}">
            <td class="mono">${escapeHtml(a.id)}</td>
            <td class="mono">${escapeHtml(a.ts)}</td>
            <td>${pill(a.severity)}</td>
            <td class="mono">${escapeHtml(a.rule_id)}</td>
            <td>${escapeHtml(a.title)}</td>
            <td class="mono">${escapeHtml(a.event_id)}</td>
            <td class="mono">${escapeHtml(a.event_ips ?? '')}</td>
            <td class="mono">${escapeHtml(a.event_agent_id ?? '')}</td>
          </tr>
        `).join('');
      }

      function renderEvents(items) {
        currentEvents = items;
        kpiEvents.textContent = String(items.length);
        navEventsCount.textContent = String(items.length);
        if (!items.length) {
          eventsBody.innerHTML = `<tr><td colspan="8" class="muted">No events</td></tr>`;
          return;
        }
        eventsBody.innerHTML = items.map(e => `
          <tr data-type="event" data-id="${escapeHtml(e.id)}">
            <td class="mono">${escapeHtml(e.id)}</td>
            <td class="mono">${escapeHtml(e.ts)}</td>
            <td>${escapeHtml(e.source)}</td>
            <td>${escapeHtml(e.host ?? '')}</td>
            <td>${pill(e.severity)}</td>
            <td class="row-msg">${escapeHtml(e.message)}</td>
            <td class="mono">${escapeHtml(e.ips ?? '')}</td>
            <td class="mono">${escapeHtml(e.agent_id ?? '')}</td>
          </tr>
        `).join('');
      }

      function setActiveView(view) {
        const showDashboard = view === 'dashboard';
        const showThreats = view === 'threats';
        const showLogs = view === 'logs';
        const showVulns = view === 'vulns';
        const showReports = view === 'reports';
        const showTools = view === 'tools';

        panelDashboard.style.display = showDashboard ? '' : 'none';
        panelVulns.style.display = showVulns ? '' : 'none';
        panelReports.style.display = showReports ? '' : 'none';
        panelAlerts.style.display = showThreats ? '' : 'none';
        panelEvents.style.display = showLogs ? '' : 'none';
        panelTools.style.display = showTools ? '' : 'none';

        toolbar.style.display = (showThreats || showLogs) ? '' : 'none';

        navDashboard.classList.toggle('active', showDashboard);
        navThreats.classList.toggle('active', showThreats);
        navLogs.classList.toggle('active', showLogs);
        navVulns.classList.toggle('active', showVulns);
        navReports.classList.toggle('active', showReports);
        navTools.classList.toggle('active', showTools);
      }

      function sevRank(s) {
        const t = String(s || '').toLowerCase();
        if (t === 'critical') return 4;
        if (t === 'high') return 3;
        if (t === 'medium') return 2;
        if (t === 'low') return 1;
        return 0;
      }

      function computeHealth(alerts) {
        const counts = { critical: 0, high: 0, medium: 0, low: 0, other: 0 };
        for (const a of (alerts || [])) {
          const k = String(a.severity || '').toLowerCase();
          if (k in counts) counts[k] += 1;
          else counts.other += 1;
        }

        const score = (counts.critical * 4) + (counts.high * 3) + (counts.medium * 2) + (counts.low * 1);
        // Normalize very loosely for a demo gauge.
        const pct = Math.max(0, Math.min(100, Math.round((score / 40) * 100)));
        let label = 'LOW';
        if (pct >= 75) label = 'CRITICAL';
        else if (pct >= 50) label = 'HIGH';
        else if (pct >= 25) label = 'ELEVATED';

        return { counts, pct, label };
      }

      function renderCriticalProblems(alerts) {
        const m = new Map();
        for (const a of (alerts || [])) {
          const key = String(a.rule_id || '—');
          const prev = m.get(key) || { rule_id: key, title: String(a.title || ''), severity: String(a.severity || ''), count: 0 };
          prev.count += 1;
          // Keep the highest severity seen for the rule.
          if (sevRank(a.severity) > sevRank(prev.severity)) prev.severity = String(a.severity || '');
          if (!prev.title && a.title) prev.title = String(a.title);
          m.set(key, prev);
        }
        const rows = Array.from(m.values()).sort((a,b) => (sevRank(b.severity) - sevRank(a.severity)) || (b.count - a.count)).slice(0, 8);
        if (!rows.length) {
          critBody.innerHTML = `<tr><td colspan="4" class="muted">No alerts</td></tr>`;
          return;
        }
        critBody.innerHTML = rows.map(r => `
          <tr>
            <td class="mono">${escapeHtml(r.rule_id)}</td>
            <td>${escapeHtml(r.title || '—')}</td>
            <td class="mono">${escapeHtml(r.count)}</td>
            <td>${pill(r.severity)}</td>
          </tr>
        `).join('');
      }

      function renderStream(events) {
        const items = (events || []).slice(0, 60);
        if (!items.length) {
          streamBox.textContent = 'No events yet.';
          return;
        }
        streamBox.textContent = items.map(e => {
          const ts = String(e.ts || '').slice(0, 19).replace('T', ' ');
          const src = String(e.source || '');
          const host = String(e.host || '');
          const msg = String(e.message || '');
          const left = [ts, src, host].filter(Boolean).join(' · ');
          return `${left}\n${msg}`;
        }).join('\n\n');
      }

      function drawMap() {
        if (!mapCanvas) return;
        const ctx = mapCanvas.getContext('2d');
        if (!ctx) return;
        const w = mapCanvas.width;
        const h = mapCanvas.height;
        ctx.clearRect(0,0,w,h);

        // Background grid
        ctx.globalAlpha = 1;
        ctx.fillStyle = 'rgba(0,0,0,0)';
        ctx.strokeStyle = 'rgba(127,127,127,0.18)';
        ctx.lineWidth = 1;
        for (let x=0; x<=w; x+=80) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h); ctx.stroke(); }
        for (let y=0; y<=h; y+=80) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke(); }

        // Extract IPs from alerts and events
        const ips = new Set();
        for (const a of currentAlerts) {
          const ipStr = String(a.ips || '');
          if (ipStr) ipStr.split(',').forEach(ip => ips.add(ip.trim()));
        }
        for (const e of currentEvents.slice(0, 50)) {
          const ipStr = String(e.ips || '');
          if (ipStr) ipStr.split(',').forEach(ip => ips.add(ip.trim()));
        }
        
        const ipArray = Array.from(ips).filter(ip => ip && ip !== 'null');
        
        // Update subtitle
        if (mapSubtitle) {
          mapSubtitle.textContent = `${ipArray.length} unique IPs detected`;
        }

        if (ipArray.length === 0) {
          ctx.fillStyle = 'rgba(127,127,127,0.4)';
          ctx.font = '14px system-ui';
          ctx.textAlign = 'center';
          ctx.fillText('No active threats detected', w/2, h/2);
          return;
        }

        // Hash function for consistent positioning
        const hashIP = (ip) => {
          let hash = 0;
          for (let i = 0; i < ip.length; i++) {
            hash = ((hash << 5) - hash) + ip.charCodeAt(i);
            hash = hash & hash;
          }
          return Math.abs(hash);
        };

        // Create points from real IPs
        const pts = ipArray.slice(0, 25).map(ip => {
          const hash = hashIP(ip);
          const x = 60 + ((hash % 1000) / 1000) * (w - 120);
          const y = 50 + ((Math.floor(hash / 1000) % 1000) / 1000) * (h - 100);
          return { x, y, ip, severity: 'high' };
        });

        // Check alert severity for coloring
        const sevMap = new Map();
        for (const a of currentAlerts) {
          const ipStr = String(a.ips || '');
          const sev = String(a.severity || 'low');
          if (ipStr) {
            ipStr.split(',').forEach(ip => {
              const cleanIp = ip.trim();
              if (!sevMap.has(cleanIp) || sev === 'critical' || (sev === 'high' && sevMap.get(cleanIp) !== 'critical')) {
                sevMap.set(cleanIp, sev);
              }
            });
          }
        }

        pts.forEach(p => p.severity = sevMap.get(p.ip) || 'low');

        // Hub point (center)
        const hub = { x: w/2, y: h/2 };

        // Draw connections to hub
        pts.forEach(p => {
          const color = p.severity === 'critical' ? 'rgba(220, 38, 38, 0.4)' : 
                       p.severity === 'high' ? 'rgba(234, 88, 12, 0.35)' :
                       p.severity === 'medium' ? 'rgba(234, 179, 8, 0.3)' : 'rgba(127,127,127,0.25)';
          ctx.strokeStyle = color;
          ctx.lineWidth = 2;
          
          const midx = (hub.x + p.x)/2;
          const midy = (hub.y + p.y)/2 - 30;
          ctx.beginPath();
          ctx.moveTo(hub.x, hub.y);
          ctx.quadraticCurveTo(midx, midy, p.x, p.y);
          ctx.stroke();
        });

        // Draw points
        pts.forEach(p => {
          const fillColor = p.severity === 'critical' ? 'rgba(220, 38, 38, 0.8)' : 
                           p.severity === 'high' ? 'rgba(234, 88, 12, 0.75)' :
                           p.severity === 'medium' ? 'rgba(234, 179, 8, 0.7)' : 'rgba(127,127,127,0.65)';
          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 5, 0, Math.PI*2);
          ctx.fill();
          
          // Pulse effect for critical
          if (p.severity === 'critical') {
            ctx.strokeStyle = 'rgba(220, 38, 38, 0.3)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(p.x, p.y, 9, 0, Math.PI*2);
            ctx.stroke();
          }
        });

        // Draw hub
        ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
        ctx.beginPath();
        ctx.arc(hub.x, hub.y, 8, 0, Math.PI*2);
        ctx.fill();
      }

      function drawTrends(events) {
        if (!trendCanvas) return;
        const ctx = trendCanvas.getContext('2d');
        if (!ctx) return;
        const w = trendCanvas.width;
        const h = trendCanvas.height;
        ctx.clearRect(0,0,w,h);

        const days = 14;
        const buckets = [];
        const now = new Date();
        now.setHours(0,0,0,0);
        for (let i=days-1;i>=0;i--) {
          const d = new Date(now.getTime() - i*86400000);
          buckets.push({ key: d.toISOString().slice(0,10), count: 0, alerts: 0 });
        }
        const idx = new Map(buckets.map((b,i)=>[b.key,i]));
        
        // Count events
        for (const e of (events || [])) {
          const key = String(e.ts || '').slice(0,10);
          const i = idx.get(key);
          if (i !== undefined) buckets[i].count += 1;
        }
        
        // Count alerts
        for (const a of (currentAlerts || [])) {
          const key = String(a.ts || '').slice(0,10);
          const i = idx.get(key);
          if (i !== undefined) buckets[i].alerts += 1;
        }

        const totalEvents = buckets.reduce((sum, b) => sum + b.count, 0);
        const totalAlerts = buckets.reduce((sum, b) => sum + b.alerts, 0);
        
        if (trendSubtitle) {
          trendSubtitle.textContent = `${totalEvents} events, ${totalAlerts} alerts (14 days)`;
        }

        const max = Math.max(1, ...buckets.map(b=>b.count));
        
        // Grid lines
        ctx.strokeStyle = 'rgba(127,127,127,0.18)';
        ctx.lineWidth = 1;
        for (let y=0; y<=4; y++) {
          const yy = 30 + (h-70)*(y/4);
          ctx.beginPath(); ctx.moveTo(60, yy); ctx.lineTo(w-20, yy); ctx.stroke();
        }

        // Events line
        ctx.strokeStyle = 'rgba(59, 130, 246, 0.7)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        buckets.forEach((b,i) => {
          const x = 60 + (w-80) * (i/(days-1));
          const y = 30 + (h-70) * (1 - (b.count/max));
          if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
        });
        ctx.stroke();

        // Events points
        ctx.fillStyle = 'rgba(59, 130, 246, 0.85)';
        buckets.forEach((b,i)=>{
          const x = 60 + (w-80) * (i/(days-1));
          const y = 30 + (h-70) * (1 - (b.count/max));
          ctx.beginPath(); ctx.arc(x,y,4,0,Math.PI*2); ctx.fill();
        });
        
        // Alerts overlay (different scale for visibility)
        const maxAlerts = Math.max(1, ...buckets.map(b=>b.alerts));
        if (maxAlerts > 0) {
          ctx.strokeStyle = 'rgba(220, 38, 38, 0.7)';
          ctx.lineWidth = 2;
          ctx.beginPath();
          buckets.forEach((b,i) => {
            const x = 60 + (w-80) * (i/(days-1));
            const y = 30 + (h-70) * (1 - (b.alerts/maxAlerts));
            if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
          });
          ctx.stroke();

          // Alert points
          ctx.fillStyle = 'rgba(220, 38, 38, 0.85)';
          buckets.forEach((b,i)=>{
            const x = 60 + (w-80) * (i/(days-1));
            const y = 30 + (h-70) * (1 - (b.alerts/maxAlerts));
            if (b.alerts > 0) {
              ctx.beginPath(); ctx.arc(x,y,5,0,Math.PI*2); ctx.fill();
            }
          });
        }

        // Labels
        ctx.fillStyle = 'rgba(127,127,127,0.6)';
        ctx.font = '11px system-ui';
        ctx.textAlign = 'left';
        ctx.fillText('Events', 10, 50);
        ctx.fillStyle = 'rgba(220, 38, 38, 0.8)';
        ctx.fillText('Alerts', 10, 70);
      }

      function renderDashboard() {
        const h = computeHealth(currentAlerts);
        gaugeLabel.textContent = h.label;
        // Gauge arc length: circumference = 2πr, r=38.
        const circ = 2 * Math.PI * 38;
        const on = (circ * (h.pct / 100));
        gaugeArc.setAttribute('stroke-dasharray', `${on} ${Math.max(0, circ - on)}`);

        healthKV.innerHTML = [
          ['Critical', h.counts.critical],
          ['High', h.counts.high],
          ['Medium', h.counts.medium],
          ['Low', h.counts.low],
        ].map(([k,v]) => `<div class="kvrow"><span class="muted">${escapeHtml(k)}</span><span class="mono">${escapeHtml(v)}</span></div>`).join('');

        renderCriticalProblems(currentAlerts);
        renderStream(currentEvents);
        drawMap();
        drawTrends(currentEvents);
      }

      function closeDrawer() {
        drawer.classList.remove('open');
        drawer.setAttribute('aria-hidden', 'true');
      }

      function openDrawer() {
        drawer.classList.add('open');
        drawer.setAttribute('aria-hidden', 'false');
      }

      function setSelectedRow(type, id) {
        selected = { type, id };
        document.querySelectorAll('tbody tr.selected').forEach(tr => tr.classList.remove('selected'));
        const tr = document.querySelector(`tbody tr[data-type="${type}"][data-id="${CSS.escape(String(id))}"]`);
        if (tr) tr.classList.add('selected');
      }

      function renderDetails(item, type) {
        drawerTitle.textContent = type === 'alert' ? 'Alert details' : 'Event details';
        drawerSub.textContent = type === 'alert'
          ? `rule ${item.rule_id} · event ${item.event_id}`
          : `source ${item.source ?? '—'} · host ${item.host ?? '—'}`;

        const pairs = [];
        if (type === 'alert') {
          pairs.push(['id', item.id], ['ts', item.ts], ['severity', item.severity], ['rule_id', item.rule_id], ['title', item.title], ['event_id', item.event_id]);
        } else {
          pairs.push(['id', item.id], ['ts', item.ts], ['source', item.source], ['host', item.host ?? ''], ['severity', item.severity ?? ''], ['message', item.message]);
        }

        drawerKV.innerHTML = pairs.map(([k,v]) => `
          <div class="k">${escapeHtml(k)}</div>
          <div class="v mono">${escapeHtml(v)}</div>
        `).join('');

        drawerJson.textContent = JSON.stringify(item, null, 2);
      }

      function findById(items, id) {
        const n = Number(id);
        return items.find(x => Number(x.id) === n);
      }

      function setError(message) {
        if (!message) {
          errEl.style.display = 'none';
          errEl.textContent = '';
          return;
        }
        errEl.style.display = 'block';
        errEl.textContent = message;
      }

      async function loadLatest() {
        setError('');
        statusEl.textContent = 'Loading latest…';
        
        // Add visual feedback
        const dashGrid = document.querySelector('.dash-grid');
        if (dashGrid) dashGrid.classList.add('updating');
        
        try {
          // Prefer the consolidated bootstrap endpoint.
          let alerts = null;
          let events = null;
          try {
            const resp = await fetch('/web/bootstrap?limit=50&hours=24');
            if (!resp.ok) throw new Error('bootstrap request failed');
            const data = await resp.json();
            alerts = data.alerts || [];
            events = data.events || [];
          } catch (e) {
            // Fallback to legacy endpoints.
            const [alertsResp, eventsResp] = await Promise.all([
              fetch('/alerts?limit=50'),
              fetch('/events?limit=50'),
            ]);
            if (!alertsResp.ok) throw new Error('alerts request failed');
            if (!eventsResp.ok) throw new Error('events request failed');
            alerts = await alertsResp.json();
            events = await eventsResp.json();
          }

          renderAlerts(alerts || []);
          renderEvents(events || []);
          renderDashboard();
          
          const now = new Date();
          const timeStr = now.toLocaleTimeString();
          statusEl.textContent = isLive ? `Live • Updated ${timeStr}` : `Updated ${timeStr}`;
          
          // Remove visual feedback after animation
          setTimeout(() => {
            if (dashGrid) dashGrid.classList.remove('updating');
          }, 300);
        } catch (e) {
          setError(String(e));
          statusEl.textContent = 'Error';
          if (dashGrid) dashGrid.classList.remove('updating');
        }
      }

      async function runSearch() {
        const q = qEl.value.trim();
        if (!q) {
          await loadLatest();
          return;
        }
        setError('');
        statusEl.textContent = 'Searching…';
        try {
          const resp = await fetch(`/search?q=${encodeURIComponent(q)}&limit=100`);
          if (!resp.ok) throw new Error('search request failed');
          const events = await resp.json();
          renderEvents(events);
          renderDashboard();
          setActiveView('logs');
          statusEl.textContent = `Search results for “${q}”`;
        } catch (e) {
          setError(String(e));
          statusEl.textContent = 'Error';
        }
      }

      // Initial render
      renderAlerts(initial.alerts || []);
      renderEvents(initial.events || []);
      statusEl.textContent = 'Loaded (snapshot)';
      renderDashboard();
      // Replace with live data
      loadLatest();

      setActiveView('dashboard');
      
      // Auto-enable live mode on page load
      function toggleLive() {
        isLive = !isLive;
        if (isLive) {
          btnLive.classList.add('active');
          if (liveCounter) liveCounter.style.display = 'inline-flex';
          qEl.value = '';
          loadLatest();
          liveInterval = setInterval(() => {
            if (isLive) {
              loadLatest();
            }
          }, 5000);
          statusEl.textContent = 'Live mode enabled (5s refresh)';
        } else {
          btnLive.classList.remove('active');
          if (liveCounter) liveCounter.style.display = 'none';
          if (liveInterval) {
            clearInterval(liveInterval);
            liveInterval = null;
          }
          statusEl.textContent = 'Live mode disabled';
        }
      }

      btnRefresh.addEventListener('click', (ev) => { ev.preventDefault(); qEl.value=''; loadLatest(); });
      btnSearch.addEventListener('click', (ev) => { ev.preventDefault(); runSearch(); });
      btnLive.addEventListener('click', (ev) => { ev.preventDefault(); toggleLive(); });
      qEl.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); runSearch(); } });

      navDashboard.addEventListener('click', () => { renderDashboard(); setActiveView('dashboard'); });
      navThreats.addEventListener('click', () => setActiveView('threats'));
      navLogs.addEventListener('click', () => setActiveView('logs'));
      navVulns.addEventListener('click', () => setActiveView('vulns'));
      navReports.addEventListener('click', () => setActiveView('reports'));
      navTools.addEventListener('click', () => setActiveView('tools'));

      btnSettings.addEventListener('click', () => {
        statusEl.textContent = 'Settings is a placeholder in this MVP';
      });

      drawerClose.addEventListener('click', () => closeDrawer());
      drawerCopy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(drawerJson.textContent || '');
          statusEl.textContent = 'Copied JSON to clipboard';
        } catch (e) {
          statusEl.textContent = 'Copy failed';
        }
      });
      async function loadInterfaces() {
        try {
          const r = await fetch('/soc/net/interfaces');
          const data = await r.json();
          if (!data.ok) throw new Error(data.error || 'interfaces failed');
          const items = data.interfaces || [];
          netIface.innerHTML = '';
          if (!items.length) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'no interfaces';
            netIface.appendChild(opt);
            return;
          }
          for (const name of items) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            netIface.appendChild(opt);
          }
          // pick a common default
          const prefer = ['eth0','en0','ens33','wlan0','lo'];
          for (const p of prefer) {
            if (items.includes(p)) { netIface.value = p; break; }
          }
        } catch (e) {
          netIface.innerHTML = '<option value="">error</option>';
          netStatus.textContent = 'Failed to load interfaces';
        }
      }

      async function pollNet(sessionId) {
        try {
          const r = await fetch(`/soc/net/${encodeURIComponent(sessionId)}`);
          const data = await r.json();
          if (!data.ok) {
            netStatus.textContent = `Error: ${data.error || 'unknown'}`;
            stopNetPolling();
            return;
          }
          netLog.value = data.log || '';
          netLog.scrollTop = netLog.scrollHeight;

          const isPcap = (data.mode === 'pcap');
          const pcapBytes = Number(data.pcap_bytes || 0);
          setNetDownloadEnabled(isPcap && (pcapBytes > 0));

          if (data.error) {
            netStatus.textContent = `Error: ${data.error}`;
            // If it smells like a privilege issue, keep the tools view visible.
            if (String(data.error || '').toLowerCase().includes('permission')) {
              setActiveView('tools');
            }
          } else if (data.done) {
            if (isPcap) {
              netStatus.textContent = `Stopped (code ${data.return_code}) — PCAP ${pcapBytes} bytes`;
            } else {
              netStatus.textContent = `Stopped (code ${data.return_code})`;
            }
            stopNetPolling();
          } else {
            if (isPcap) {
              netStatus.textContent = `Capturing PCAP… (${pcapBytes} bytes)`;
            } else {
              netStatus.textContent = 'Running…';
            }
          }
        } catch (e) {
          netStatus.textContent = 'Error polling monitor';
          stopNetPolling();
        }
      }

      async function startNet(mode) {
        stopNetPolling();
        const iface = (netIface.value || '').trim();
        const filter = (netFilter.value || '').trim();
        if (!iface) {
          netStatus.textContent = 'Select an interface';
          setActiveView('tools');
          return;
        }
        netLog.value = '';
        setNetDownloadEnabled(false);
        netStatus.textContent = (mode === 'pcap') ? 'Starting PCAP capture…' : 'Starting…';
        setActiveView('tools');
        try {
          const r = await fetch('/soc/net/start', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ interface: iface, filter, mode }),
          });
          const data = await r.json();
          if (!data.ok) {
            netStatus.textContent = `Error: ${data.error || 'unknown'}`;
            return;
          }
          netSessionId = data.session_id;
          netStatus.textContent = (mode === 'pcap')
            ? `Capturing (session ${netSessionId})`
            : `Running (session ${netSessionId})`;
          await pollNet(netSessionId);
          netPoll = setInterval(() => pollNet(netSessionId), 1200);
        } catch (e) {
          netStatus.textContent = 'Error starting monitor';
        }
      }

      btnNetStart.addEventListener('click', async () => {
        await startNet('summary');
      });

      btnNetCapture.addEventListener('click', async () => {
        await startNet('pcap');
      });

      btnNetStop.addEventListener('click', async () => {
        if (!netSessionId) {
          stopNetPolling();
          netStatus.textContent = 'Idle';
          setNetDownloadEnabled(false);
          return;
        }
        try {
          await fetch(`/soc/net/stop/${encodeURIComponent(netSessionId)}`, { method: 'POST' });
        } catch (e) {
          // ignore
        }
        stopNetPolling();
        netStatus.textContent = 'Stopping…';
      });

      btnNetDownload.addEventListener('click', () => {
        if (!netSessionId) return;
        // Triggers a browser download of the .pcap file.
        window.location.href = `/soc/net/download/${encodeURIComponent(netSessionId)}`;
      });

      document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') closeDrawer();
      });

      function onRowClick(ev) {
        const tr = ev.target.closest('tr[data-type][data-id]');
        if (!tr) return;
        const type = tr.getAttribute('data-type');
        const id = tr.getAttribute('data-id');
        if (!type || !id) return;

        const item = type === 'alert' ? findById(currentAlerts, id) : findById(currentEvents, id);
        if (!item) return;
        setSelectedRow(type, item.id);
        renderDetails(item, type);
        openDrawer();
      }

      alertsBody.addEventListener('click', onRowClick);
      eventsBody.addEventListener('click', onRowClick);

      function uniqSorted(list) {
        return Array.from(new Set(list)).sort((a,b) => a.localeCompare(b));
      }

      function extractIOCs(text) {
        const t = String(text || '');
        const ips = (t.match(/\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b/g) || []);
        const urls = (t.match(/\bhttps?:\/\/[^\s"'<>]+/gi) || []);
        const domains = (t.match(/\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63})\b/gi) || [])
          .filter(d => !d.toLowerCase().startsWith('http'));
        const md5 = (t.match(/\b[a-f0-9]{32}\b/gi) || []);
        const sha1 = (t.match(/\b[a-f0-9]{40}\b/gi) || []);
        const sha256 = (t.match(/\b[a-f0-9]{64}\b/gi) || []);
        return {
          ips: uniqSorted(ips),
          urls: uniqSorted(urls),
          domains: uniqSorted(domains),
          md5: uniqSorted(md5),
          sha1: uniqSorted(sha1),
          sha256: uniqSorted(sha256),
        };
      }

      function downloadJson(filename, obj) {
        const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 500);
      }

      function clearSelectionIfType(type) {
        if (!selected) return;
        if (selected.type !== type) return;
        selected = null;
        closeDrawer();
      }

      btnIocExtract.addEventListener('click', () => {
        const res = extractIOCs(iocInput.value);
        const out = [];
        if (res.urls.length) out.push('[urls]', ...res.urls, '');
        if (res.domains.length) out.push('[domains]', ...res.domains, '');
        if (res.ips.length) out.push('[ips]', ...res.ips, '');
        if (res.md5.length) out.push('[md5]', ...res.md5, '');
        if (res.sha1.length) out.push('[sha1]', ...res.sha1, '');
        if (res.sha256.length) out.push('[sha256]', ...res.sha256, '');
        iocOutput.value = out.length ? out.join('\n') : 'No IOCs found.';
        setActiveView('tools');
      });

      btnIocClear.addEventListener('click', () => { iocInput.value=''; iocOutput.value=''; });
      btnIocCopy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(iocOutput.value || '');
          statusEl.textContent = 'Copied IOCs to clipboard';
        } catch (e) {
          statusEl.textContent = 'Copy failed';
        }
      });

      function b64EncodeUtf8(s) {
        const bytes = new TextEncoder().encode(String(s ?? ''));
        let binary = '';
        bytes.forEach(b => { binary += String.fromCharCode(b); });
        return btoa(binary);
      }

      function b64DecodeUtf8(s) {
        const binary = atob(String(s ?? '').trim());
        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
        return new TextDecoder().decode(bytes);
      }

      btnB64Encode.addEventListener('click', () => {
        try {
          b64Output.value = b64EncodeUtf8(b64Input.value);
          setActiveView('tools');
        } catch (e) {
          b64Output.value = 'Encode error';
        }
      });

      btnB64Decode.addEventListener('click', () => {
        try {
          b64Output.value = b64DecodeUtf8(b64Input.value);
          setActiveView('tools');
        } catch (e) {
          b64Output.value = 'Decode error (invalid base64?)';
        }
      });

      btnB64Clear.addEventListener('click', () => { b64Input.value=''; b64Output.value=''; });

      // Crypto tool
      function cryptoAllList() {
        // Must match the dropdown options (excluding ALL)
        return [
          'NTLM',
          'MD2',
          'MD4',
          'MD5',
          'MD6-128',
          'MD6-256',
          'MD6-512',
          'RipeMD-128',
          'RipeMD-160',
          'RipeMD-256',
          'RipeMD-320',
          'SHA1',
          'SHA-224',
          'SHA-256',
          'SHA-384',
          'SHA-512',
          'SHA3-224',
          'SHA3-256',
          'SHA3-384',
          'SHA3-512',
          'CRC16',
          'CRC32',
          'Adler32',
          'Whirlpool',
        ];
      }

      btnCryptoClear.addEventListener('click', () => {
        cryptoInput.value = '';
        cryptoOutput.value = '';
        if (cryptoAlg) cryptoAlg.value = 'ALL';
        setActiveView('tools');
      });

      btnCryptoCopy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(cryptoOutput.value || '');
          statusEl.textContent = 'Copied crypto results to clipboard';
        } catch (e) {
          statusEl.textContent = 'Copy failed';
        }
      });

      btnCryptoRun.addEventListener('click', async () => {
        const input = String(cryptoInput.value || '');
        const input_format = String(cryptoFormat.value || 'text');
        const selected = String(cryptoAlg?.value || 'ALL');
        const algorithms = (selected === 'ALL') ? cryptoAllList() : [selected];
        if (!algorithms.length) {
          cryptoOutput.value = 'Select an algorithm.';
          setActiveView('tools');
          return;
        }
        cryptoOutput.value = 'Computing…';
        setActiveView('tools');
        try {
          const r = await fetch('/soc/crypto/digests', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ input, input_format, algorithms }),
          });
          const data = await r.json();
          if (!data.ok) {
            cryptoOutput.value = `Error: ${data.error || 'unknown'}`;
            return;
          }
          const res = data.results || {};
          const lines = [];
          for (const name of algorithms) {
            const r0 = res[name];
            if (!r0) { lines.push(`${name}: (no result)`); continue; }
            if (!r0.ok) {
              lines.push(`${name}: ERROR: ${r0.error || 'failed'}`);
              continue;
            }
            const note = r0.note ? `  (${r0.note})` : '';
            lines.push(`${name}: ${r0.hex || ''}${note}`);
          }
          cryptoOutput.value = lines.join('\n');
        } catch (e) {
          cryptoOutput.value = `Error: ${String(e)}`;
        }
      });
      btnB64Copy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(b64Output.value || '');
          statusEl.textContent = 'Copied output to clipboard';
        } catch (e) {
          statusEl.textContent = 'Copy failed';
        }
      });

      btnExportAlerts.addEventListener('click', () => downloadJson('alerts.json', currentAlerts));
      btnExportEvents.addEventListener('click', () => downloadJson('events.json', currentEvents));

      if (btnAlertsDownload) {
        btnAlertsDownload.addEventListener('click', () => downloadJson('alerts.json', currentAlerts));
      }
      if (btnEventsDownload) {
        btnEventsDownload.addEventListener('click', () => downloadJson('events.json', currentEvents));
      }
      if (btnAlertsClear) {
        btnAlertsClear.addEventListener('click', () => {
          clearSelectionIfType('alert');
          renderAlerts([]);
          renderDashboard();
          statusEl.textContent = 'Cleared threats (local view)';
        });
      }
      if (btnEventsClear) {
        btnEventsClear.addEventListener('click', () => {
          clearSelectionIfType('event');
          renderEvents([]);
          renderDashboard();
          statusEl.textContent = 'Cleared logs (local view)';
        });
      }
      // Load network interfaces once at startup
      loadInterfaces();

      function stopScanPolling() {
        if (scanPoll) {
          clearInterval(scanPoll);
          scanPoll = null;
        }
      }

      async function pollScan(scanId) {
        try {
          const r = await fetch(`/soc/scan/${encodeURIComponent(scanId)}`);
          const data = await r.json();
          if (!data.ok) {
            scanStatus.textContent = `Error: ${data.error || 'unknown'}`;
            stopScanPolling();
            return;
          }

          scanLog.value = data.log || '';
          scanLog.scrollTop = scanLog.scrollHeight;

          if (data.error) {
            scanStatus.textContent = `Error: ${data.error}`;
          } else if (data.done) {
            scanStatus.textContent = `Done (code ${data.return_code})`;
            stopScanPolling();
          } else {
            scanStatus.textContent = 'Running…';
          }
        } catch (e) {
          scanStatus.textContent = 'Error polling scan';
          stopScanPolling();
        }
      }

      btnScanStop.addEventListener('click', () => {
        stopScanPolling();
        scanStatus.textContent = 'Stopped log polling';
      });

      btnScanStart.addEventListener('click', async () => {
        stopScanPolling();
        const path = (scanPath.value || '').trim();
        if (!path) {
          scanStatus.textContent = 'Enter a path to scan';
          setActiveView('tools');
          return;
        }
        scanLog.value = '';
        scanStatus.textContent = 'Starting…';
        setActiveView('tools');
        try {
          const r = await fetch('/soc/scan', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ path, recursive: !!scanRecursive.checked }),
          });
          const data = await r.json();
          if (!data.ok) {
            scanStatus.textContent = `Error: ${data.error || 'unknown'}`;
            return;
          }
          const scanId = data.scan_id;
          scanStatus.textContent = `Running (scan_id ${scanId})`;
          await pollScan(scanId);
          scanPoll = setInterval(() => pollScan(scanId), 1200);
        } catch (e) {
          scanStatus.textContent = 'Error starting scan';
        }
      });
    </script>
  </body>
</html>
"""

    return template.replace("__INITIAL_STATE__", json.dumps(initial_state))
