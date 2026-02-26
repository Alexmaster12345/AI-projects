/* ============================================================
   VM-Switch Manager — Frontend JS
   ============================================================ */

// ---- State ----
let currentTab   = "dashboard";
let editingPort  = null;
let cliHistory   = [];
let cliHistoryIdx = -1;

// ---- Tab switching ----
function switchTab(tab, el) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById("tab-" + tab).classList.add("active");
  if (el) el.classList.add("active");
  currentTab = tab;
  const titles = {
    dashboard: "Dashboard", ports: "Ports", vlans: "VLANs",
    routing: "Routing", mac: "MAC Table", stp: "Spanning Tree", cli: "CLI"
  };
  document.getElementById("tabTitle").textContent = titles[tab] || tab;
  loadTab(tab);
  if (tab === "cli") {
    setTimeout(() => document.getElementById("cli-input").focus(), 50);
  }
}

function loadTab(tab) {
  if (tab === "dashboard") loadDashboard();
  else if (tab === "ports")   loadPorts();
  else if (tab === "vlans")   loadVlans();
  else if (tab === "routing") loadRouting();
  else if (tab === "mac")     loadMac();
  else if (tab === "stp")     loadStp();
}

// ---- Refresh ----
function refreshAll() { loadTab(currentTab); }

// ---- Dashboard ----
async function loadDashboard() {
  const [status, ports, mac] = await Promise.all([
    fetch("/api/status").then(r => r.json()),
    fetch("/api/ports").then(r => r.json()),
    fetch("/api/mac-table").then(r => r.json()),
  ]);

  document.getElementById("stat-up").textContent    = status.ports_up;
  document.getElementById("stat-down").textContent  = status.ports_down;
  document.getElementById("stat-vlans").textContent = status.vlan_count;
  document.getElementById("stat-uptime").textContent= status.uptime;
  document.getElementById("hdr-hostname").textContent = status.hostname;
  document.getElementById("hdr-ports-up").textContent = status.ports_up + " up";
  document.getElementById("hdr-ports-down").textContent = status.ports_down + " down";
  document.getElementById("sb-uptime").textContent  = "Up " + status.uptime;

  document.getElementById("info-hostname").textContent = status.hostname;
  document.getElementById("info-model").textContent    = status.model;
  document.getElementById("info-stp").textContent      = status.stp_mode;
  document.getElementById("info-time").textContent     = status.time;

  // Port panel
  const panel = document.getElementById("port-panel");
  panel.innerHTML = "";
  ports.forEach(p => {
    const cls = p.admin === "down" ? "admin-down" : (p.status === "up" ? "up" : "down");
    const label = p.id.replace("Gi0/", "");
    const el = document.createElement("div");
    el.className = "port-dot " + cls;
    el.title = `${p.id} | ${p.status} | VLAN ${p.vlan} | ${p.description || "no desc"}`;
    el.textContent = label;
    el.onclick = () => { switchTab("ports", document.querySelector('[data-tab="ports"]')); openPortEdit(p.id); };
    panel.appendChild(el);
  });

  // MAC table
  const tb = document.querySelector("#dash-mac-table tbody");
  tb.innerHTML = "";
  mac.slice(0, 8).forEach(e => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${e.vlan}</td><td><code>${e.mac}</code></td><td>${e.port}</td><td>${badge(e.type)}</td>`;
    tb.appendChild(tr);
  });
}

// ---- Ports ----
async function loadPorts() {
  const ports = await fetch("/api/ports").then(r => r.json());
  const tb = document.querySelector("#ports-table tbody");
  tb.innerHTML = "";
  ports.forEach(p => {
    const statusCls = p.status === "up" ? "pill-up" : "pill-down";
    const modeCls   = p.mode === "trunk" ? "pill-trunk" : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><b>${p.id}</b></td>
      <td><span class="${statusCls}">${p.status.toUpperCase()}</span></td>
      <td><span class="${p.admin === 'down' ? 'pill-down' : 'pill-up'}">${p.admin}</span></td>
      <td><span class="${modeCls}">${p.mode}</span></td>
      <td>${p.vlan}</td>
      <td>${p.speed} Mbps</td>
      <td>${p.description || "<span style='color:var(--text3)'>—</span>"}</td>
      <td>
        <button class="act-btn act-edit" onclick="openPortEdit('${p.id}')">Edit</button>
        <button class="act-btn act-del"  onclick="toggleShutdown('${p.id}','${p.admin}')">${p.admin === "up" ? "Shutdown" : "No Shut"}</button>
      </td>`;
    tb.appendChild(tr);
  });
}

function openPortEdit(portId) {
  editingPort = portId;
  fetch("/api/ports/" + portId).then(r => r.json()).then(p => {
    document.getElementById("edit-port-id").textContent = portId;
    document.getElementById("ep-desc").value   = p.description || "";
    document.getElementById("ep-admin").value  = p.admin;
    document.getElementById("ep-mode").value   = p.mode;
    document.getElementById("ep-vlan").value   = p.vlan;
    document.getElementById("ep-speed").value  = p.speed;
    document.getElementById("ep-duplex").value = p.duplex;
    const panel = document.getElementById("port-edit-panel");
    panel.style.display = "block";
    panel.scrollIntoView({ behavior: "smooth" });
  });
}

function closePortEdit() {
  editingPort = null;
  document.getElementById("port-edit-panel").style.display = "none";
}

async function savePort() {
  if (!editingPort) return;
  const admin  = document.getElementById("ep-admin").value;
  const status = admin === "down" ? "down" : "up";
  const payload = {
    description: document.getElementById("ep-desc").value,
    admin,
    status,
    mode:   document.getElementById("ep-mode").value,
    vlan:   parseInt(document.getElementById("ep-vlan").value),
    speed:  document.getElementById("ep-speed").value,
    duplex: document.getElementById("ep-duplex").value,
  };
  await fetch("/api/ports/" + editingPort, { method: "PATCH", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload) });
  closePortEdit();
  loadPorts();
}

async function toggleShutdown(portId, currentAdmin) {
  const newAdmin = currentAdmin === "up" ? "down" : "up";
  await fetch("/api/ports/" + portId, {
    method: "PATCH",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ admin: newAdmin, status: newAdmin })
  });
  loadPorts();
}

// ---- VLANs ----
async function loadVlans() {
  const vlans = await fetch("/api/vlans").then(r => r.json());
  const tb = document.querySelector("#vlan-table tbody");
  tb.innerHTML = "";
  vlans.sort((a,b) => a.id - b.id).forEach(v => {
    const tr = document.createElement("tr");
    const statusCls = v.active ? "pill-up" : "pill-down";
    tr.innerHTML = `
      <td><b>${v.id}</b></td>
      <td>${v.name}</td>
      <td><span class="${statusCls}">${v.active ? "active" : "suspended"}</span></td>
      <td>${v.ports.join(", ") || "—"}</td>
      <td>
        ${v.id > 1 ? `<button class="act-btn act-del" onclick="deleteVlan(${v.id})">Delete</button>` : ""}
      </td>`;
    tb.appendChild(tr);
  });
}

function showVlanCreate() {
  const p = document.getElementById("vlan-create-panel");
  p.style.display = p.style.display === "none" ? "block" : "none";
}

async function createVlan() {
  const id   = parseInt(document.getElementById("new-vlan-id").value);
  const name = document.getElementById("new-vlan-name").value || `VLAN${String(id).padStart(4,"0")}`;
  if (!id || id < 2 || id > 4094) { alert("VLAN ID must be 2-4094"); return; }
  await fetch("/api/vlans", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({id, name}) });
  document.getElementById("vlan-create-panel").style.display = "none";
  loadVlans();
}

async function deleteVlan(vid) {
  if (!confirm(`Delete VLAN ${vid}?`)) return;
  await fetch("/api/vlans/" + vid, { method: "DELETE" });
  loadVlans();
}

// ---- Routing ----
async function loadRouting() {
  const ifaces = await fetch("/api/interfaces").then(r => r.json());
  const tb = document.querySelector("#routing-table tbody");
  tb.innerHTML = "";
  ifaces.forEach(iv => {
    const tr = document.createElement("tr");
    const statusCls = iv.status === "up" ? "pill-up" : "pill-down";
    tr.innerHTML = `<td><b>${iv.id}</b></td><td><code>${iv.ip}</code></td><td>${iv.mask}</td><td><span class="${statusCls}">${iv.status}</span></td>`;
    tb.appendChild(tr);
  });
}

// ---- MAC Table ----
async function loadMac() {
  const mac = await fetch("/api/mac-table").then(r => r.json());
  const tb = document.querySelector("#mac-table-full tbody");
  tb.innerHTML = "";
  mac.forEach(e => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${e.vlan}</td><td><code>${e.mac}</code></td><td>${badge(e.type)}</td><td>${e.port}</td>`;
    tb.appendChild(tr);
  });
}

async function clearMac() {
  await cliSend("clear mac address-table dynamic");
  loadMac();
}

// ---- Spanning Tree ----
async function loadStp() {
  const stp = await fetch("/api/spanning-tree").then(r => r.json());
  const tb = document.getElementById("stp-info");
  tb.innerHTML = `
    <tr><td>Mode</td><td><b>${stp.mode}</b></td></tr>
    <tr><td>Status</td><td><span class="${stp.enabled ? 'pill-up':'pill-down'}">${stp.enabled ? "Enabled":"Disabled"}</span></td></tr>
    <tr><td>Root Bridge</td><td>${stp.root}</td></tr>
    <tr><td>Bridge Priority</td><td>${stp.priority}</td></tr>
  `;
}

// ---- Helpers ----
function badge(type) {
  const cls = type === "static" ? "badge badge-green" : "badge";
  return `<span class="${cls}" style="font-size:11px">${type}</span>`;
}

// ---- CLI ----
async function cliSend(cmd) {
  const res = await fetch("/api/cli", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ command: cmd })
  });
  return res.json();
}

function cliAppend(text, cls) {
  const out = document.getElementById("cli-output");
  const el  = document.createElement("div");
  el.className = cls || "cli-line-out";
  el.textContent = text;
  out.appendChild(el);
  out.scrollTop = out.scrollHeight;
}

function cliSetPrompt(p) {
  document.getElementById("cli-prompt").textContent = p + " ";
}

async function cliExec(cmd) {
  if (!cmd.trim()) return;
  cliHistory.unshift(cmd);
  cliHistoryIdx = -1;
  cliAppend(document.getElementById("cli-prompt").textContent + cmd, "cli-line-cmd");
  const res = await cliSend(cmd);
  if (res.output) {
    const isErr = res.output.startsWith("%");
    res.output.split("\n").forEach(line => {
      cliAppend(line, isErr ? "cli-line-err" : "cli-line-out");
    });
  }
  cliSetPrompt(res.prompt);
  // refresh header if hostname might have changed
  if (cmd.toLowerCase().startsWith("hostname")) {
    fetch("/api/status").then(r=>r.json()).then(s => {
      document.getElementById("hdr-hostname").textContent = s.hostname;
    });
  }
}

function cliQuick(cmd) {
  const input = document.getElementById("cli-input");
  input.value = cmd;
  input.focus();
}

// ---- CLI keyboard handler ----
document.addEventListener("DOMContentLoaded", () => {
  // init CLI
  fetch("/api/cli/prompt").then(r => r.json()).then(d => cliSetPrompt(d.prompt));
  cliAppend("VM-Switch CLI Emulator — type 'enable' to enter privileged mode", "cli-line-info");
  cliAppend("", "cli-line-out");

  const input = document.getElementById("cli-input");

  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      const cmd = input.value;
      input.value = "";
      await cliExec(cmd);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (cliHistoryIdx < cliHistory.length - 1) {
        cliHistoryIdx++;
        input.value = cliHistory[cliHistoryIdx];
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (cliHistoryIdx > 0) {
        cliHistoryIdx--;
        input.value = cliHistory[cliHistoryIdx];
      } else {
        cliHistoryIdx = -1;
        input.value = "";
      }
    } else if (e.key === "Tab") {
      e.preventDefault();
      // Simple tab completion for common commands
      const val = input.value.toLowerCase().trim();
      const completions = [
        "show version","show interfaces","show vlan","show mac-address-table",
        "show spanning-tree","show running-config","show ip interface",
        "enable","configure terminal","interface","hostname","exit","end",
        "write memory","reload","ping","traceroute"
      ];
      const match = completions.find(c => c.startsWith(val));
      if (match) input.value = match;
    } else if (e.ctrlKey && e.key === "c") {
      input.value = "";
      cliAppend("^C", "cli-line-err");
    } else if (e.ctrlKey && e.key === "z") {
      input.value = "";
      await cliExec("end");
    } else if (e.ctrlKey && e.key === "l") {
      document.getElementById("cli-output").innerHTML = "";
    }
  });

  // Initial dashboard load
  loadDashboard();
});
