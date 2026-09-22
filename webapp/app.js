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
    ["off","normal","max"].forEach(l => {
      const o = document.createElement("option"); o.value = l; o.textContent = "thinking: " + l;
      if (l === (t.thinking || "normal")) o.selected = true; think.appendChild(o);
    });
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
loadConfig().then(() => { loadStats(); loadLog(); });