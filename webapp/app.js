const TIERS = ["EASY","MEDIUM","HARD","EXPERT"], TIMES = ["NOW","LATER"];
let cfg = null, models = [];

async function loadConfig() {
  cfg = await (await fetch("/api/config")).json();
  const fleet = await (await fetch("/api/fleet")).json();
  models = new Set(["qwen3:4b", "glm-5.3-flash:cloud", "qwen38-27b-iq3s"]);
  (fleet.peers || []).forEach(p => (p.models || []).forEach(m => models.add(m)));
  const el = document.getElementById("tiers"); el.innerHTML = "";
  for (const d of TIERS) for (const tm of TIMES) {
    const key = d + "/" + tm, t = cfg.tiers[key] || {model: "", thinking: "normal"};
    const row = document.createElement("div"); row.className = "tier-row";
    row.innerHTML = `<label>${d} / ${tm}</label>`;
    const sel = document.createElement("select"); sel.className = "modelSel";
    sel.dataset.key = key;
    [...models].sort().forEach(m => {
      const o = document.createElement("option"); o.value = m; o.textContent = m;
      if (m === t.model) o.selected = true; sel.appendChild(o);
    });
    const think = document.createElement("select"); think.className = "thinkSel"; think.dataset.key = key;
    const LABELS = {off: "Thinking: OFF (no reasoning)", normal: "Thinking: NORMAL",
                    max: "Thinking: MAX (deep reasoning, slower)"};
    ["off","normal","max"].forEach(l => {
      const o = document.createElement("option"); o.value = l; o.textContent = LABELS[l];
      if (l === (t.thinking || "normal")) o.selected = true; think.appendChild(o);
    });
    think.className = "thinkSel " + (t.thinking || "normal");
    think.addEventListener("change", () => think.className = "thinkSel " + think.value);
    row.append(sel, think); el.append(row);
  }
}
async function saveConfig() {
  const tiers = {};
  document.querySelectorAll(".modelSel").forEach(s => {
    const k = s.dataset.key; tiers[k] = {provider: "auto", model: s.value,
      thinking: document.querySelector(`.thinkSel[data-key="${k}"]`).value};
  });
  const r = await (await fetch("/api/config", {method:"PUT", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({tiers})})).json();
  document.getElementById("saveStatus").textContent = r.saved ? "saved ✓ (effective next route)" : "save failed";
}
async function testRoute() {
  const msg = document.getElementById("msg").value;
  const r = await (await fetch("/api/route", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({message: msg})})).json();
  const el = document.getElementById("routeOut"); el.style.display = "block";
  el.textContent = `role=${r.role} difficulty=${r.difficulty} timing=${r.timing} lane=${r.lane} confidence=${r.confidence}`;
}
async function loadStats() {
  const s = await (await fetch("/api/savings")).json();
  document.getElementById("savings").innerHTML = s.decisions ?
    `<div class="kpi">${s.saved_pct}% saved</div>
     <div class="muted">${s.decisions} decisions | baseline $${s.baseline_per_mtok}/Mtok → routed $${s.routed_per_mtok}/Mtok</div>`
    : `<div class="muted">no decisions yet — route something!</div>`;
}
async function loadLog() {
  const d = await (await fetch("/api/log?n=20")).json();
  const tb = document.getElementById("log"); tb.innerHTML = "";
  (d.decisions || []).forEach(x => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${x.ts||""}</td><td>${(x.message||"").slice(0,40)}</td>
      <td>${x.role||""}</td><td>${x.difficulty||""}</td><td>${x.timing||""}</td>
      <td>${x.lane||""}</td><td>${x.confidence??""}</td>`;
    tb.append(tr);
  });
}
async function startOptimize() {
  const consent = document.getElementById("consentLocal").checked;
  if (!consent) { document.getElementById("optStatus").textContent = "Please tick the consent box first."; return; }
  const r = await (await fetch("/api/optimize", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({consent_local: consent})})).json();
  if (!r.started) { document.getElementById("optStatus").textContent = r.reason; return; }
  document.getElementById("optBarWrap").style.display = "block";
  pollOptimize();
}
async function pollOptimize() {
  const st = await (await fetch("/api/optimize/status")).json();
  const pct = st.total ? Math.round(st.done / st.total * 100) : 0;
  document.getElementById("optBar").value = pct;
  document.getElementById("optStatus").textContent = st.running
    ? `Testing ${st.current} (${st.done}/${st.total})...`
    : "Done - decision tree updated with measured recommendations.";
  if (st.running) setTimeout(pollOptimize, 3000);
  else { document.getElementById("optDone").textContent = "done - tree refilled"; loadConfig(); }
}
async function rescanModels(mode = "price") {
  const st = document.getElementById("seedStatus");
  st.textContent = "Checking for newer recommendations...";
  const chk = await (await fetch("/api/seed/check")).json();
  if (!chk.staged) { st.textContent = chk.reason || chk.error || "already up to date"; return; }
  const pv = await (await fetch(`/api/seed/preview?mode=${mode}`)).json();
  const box = document.getElementById("seedDiff");
  const noChanges = !pv.changes || !Object.keys(pv.changes).length;
  const noOverrides = !pv.overrides || !Object.keys(pv.overrides).length;
  if (noChanges && noOverrides) { st.textContent = "New data staged (" + chk.version + ") but no tier changes for you."; return; }
  let html2 = `<div class="muted">Mode: ${mode.toUpperCase()} | version ${chk.version}</div>`;
  for (const [tier, c] of Object.entries(pv.changes || {}))
    html2 += `<div>✓ ${tier}: ${c.from} → <b>${c.to}</b></div>`;
  for (const [tier, c] of Object.entries(pv.overrides || {}))
    html2 += `<div>⚠ ${tier} <span class="muted">(you customized this)</span>: ${c.from} → <b>${c.to}</b>
      <label style="font-size:.8rem;margin-left:.5rem"><input type="checkbox" class="ovrTier" data-tier="${tier}" checked> apply anyway</label></div>`;
  html2 += `<button onclick="applyRescan()">Apply selected</button>`;
  box.innerHTML = html2; box.style.display = "block";
  st.textContent = "Review the changes, then apply.";
}
async function applyRescan() {
  const overrides = [...document.querySelectorAll(".ovrTier:checked")].map(c => c.dataset.tier);
  const r = await (await fetch("/api/seed/apply", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({overrides})})).json();
  document.getElementById("seedStatus").textContent = r.applied ? "Applied - tree updated." : (r.reason || "failed");
  document.getElementById("seedDiff").style.display = "none";
  loadConfig();
}
function toggleAdvanced() {
  const c = document.getElementById("advancedCard");
  c.style.display = c.style.display === "none" ? "block" : "none";
}
loadConfig().then(() => { loadStats(); loadLog(); });