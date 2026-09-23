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
async function loadFleet() {
  const f = await (await fetch("/api/fleet")).json();
  const KIND = {ollama:`<img src="icons/svg/brand-ollama.svg" style="width:14px;height:14px;vertical-align:-2px"> Ollama`, "llama-swap":`<img src="icons/svg/ui-arrow-left-right.svg" style="width:14px;height:14px;vertical-align:-2px"> llama-swap`, unknown:`<img src="icons/svg/ui-circle-help.svg" style="width:14px;height:14px;vertical-align:-2px">`};
  document.getElementById("fleet").innerHTML = (f.peers || []).map(p => `
    <div style="display:flex;justify-content:space-between;padding:.3rem 0;border-bottom:1px solid #2a313a">
      <span><b>${p.host}</b> <span class="muted">: ${p.port}</span></span>
      <span class="muted">${KIND[p.kind] || p.kind} · ${ (p.models||[]).length } models</span>
    </div>`).join("") || '<div class="muted">scanning…</div>';
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

// ---------- J11: Providers tab ----------
// Brand logos: Simple Icons (CC0) - vendored SVGs in icons/svg/ (no CDN calls).
// openai/xai/groq have no official Simple Icons slug (trademark policy) - keep
// text marks for those. UI icons: Lucide (MIT) - vendored in icons/svg/.
const LOGOS = {
  ollama:   {bg:"#DDD", fg:"#111", label:`<img src="icons/svg/brand-ollama.svg" alt="" style="width:22px;height:22px">`},
  openai:   {bg:"#10A37F", fg:"#fff", label:"AI"},
  xai:      {bg:"#000", fg:"#fff", label:"𝕏"},
  groq:     {bg:"#F55036", fg:"#fff", label:"G"},
  deepseek: {bg:"#4D6BFE", fg:"#fff", label:`<img src="icons/svg/brand-deepseek.svg" alt="" style="width:22px;height:22px">`},
  anthropic:{bg:"#D97757", fg:"#fff", label:`<img src="icons/svg/brand-anthropic.svg" alt="" style="width:22px;height:22px">`},
  gemini:   {bg:"#1a73e8", fg:"#fff", label:`<img src="icons/svg/brand-googlegemini.svg" alt="" style="width:22px;height:22px">`},
  openrouter:{bg:"#8B5CF6", fg:"#fff", label:`<img src="icons/svg/brand-openrouter.svg" alt="" style="width:22px;height:22px">`},
  tierllama:{bg:"#E4573D", fg:"#fff", label:`<img src="icons/tierllama-logo.svg" alt="" style="width:22px;height:22px;border-radius:5px">`},
};
async function loadJevCard() {
  const st = await (await fetch("/api/jev")).json();
  document.getElementById("jevDesc").textContent =
    "Jev is not a chat LLM - it's a System One model that returns typed decisions " +
    "(role, difficulty, timing) with calibrated confidence in ~80ms, not tokens of prose. " +
    "Every message you send is classified by a Jev-style brain before routing. " +
    "The original Jev is TypeSafe AI's model (Diogo Almeida, ChatGPT co-creator); " +
    "our open-source local brain is a Jev-style qwen3:4b you run yourself - free. " + st.price + ".";
  document.getElementById("jevBody").innerHTML = `
    <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:.3rem 0">
      <span class="key-dot ${st.local_available ? "key-ok" : "key-missing"}"></span>
      <b style="font-size:.85rem">Local brain — Jev-style qwen3:4b</b>
      <span class="muted">${st.local_available ? "running on your machine · free" : "not installed yet"}</span>
      ${!st.local_available ? `<button onclick="installJevLocal()" style="font-size:.75rem">Download local brain (ollama pull qwen3:4b)</button>` : ""}
    </div>
    <div style="display:flex;gap:.5rem;align-items:center;margin-top:.3rem;flex-wrap:wrap">
      <span class="key-dot ${st.configured ? "key-ok" : "key-missing"}"></span>
      <b style="font-size:.85rem">Jev Cloud — official (TypeSafe AI)</b>
      <span class="muted">${st.configured ? "key configured · classifier fallback active" : "no hardware? add a key"}</span>
      ${!st.configured ? `<div class="keyrow"><input type="password" id="key_jev" placeholder="Jev Cloud API key">
      <button onclick="saveJevKey()">Save</button></div>` : ""}
    </div>`;
  const tg = document.getElementById("jevToggle");
  if (tg) tg.classList.toggle("on", !!st.configured);
}
async function installJevLocal() {
  const r = await (await fetch("/api/jev/install-local", {method:"POST"})).json();
  alert(r.ok ? "qwen3:4b pulled - local brain ready." : "pull failed: " + (r.error||"?"));
  loadJevCard();
}
async function toggleJev(el) {
  // toggle Jev Cloud as classifier fallback (preference only; key required)
  el.classList.toggle("on");
  await fetch("/api/jev/toggle", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({enabled: el.classList.contains("on")})});
}
async function saveJevKey() {
  const key = document.getElementById("key_jev").value.trim();
  if (!key) return;
  await fetch("/api/providers/key", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({provider:"jev", key})});
  loadJevCard();
}
async function loadProviders() {
  const grid = document.getElementById("provGrid");
  const pv = await (await fetch("/api/providers/all")).json();
  grid.innerHTML = "";
  for (const p of pv.providers) {
    const lg = LOGOS[p.provider] || {bg:"#3a434e", fg:"#fff", label:p.provider[0].toUpperCase()};
    const keyOk = p.key_ready;
    const card = document.createElement("div");
    card.className = "prov-card";
    card.innerHTML = `
      <div class="prov-head">
        <div class="prov-logo" style="background:${lg.bg};color:${lg.fg}">${lg.label}</div>
        <div style="flex:1">
          <b style="text-transform:capitalize">${p.provider}</b><br>
          <span class="muted">${p.enabled ? "enabled" : "disabled"}</span>
        </div>
        <button class="toggle ${p.enabled ? "on" : ""}" data-provider="${p.provider}" onclick="toggleProvider(this)"></button>
      </div>
      <div style="font-size:.8rem;margin:.3rem 0">
        <span class="key-dot ${keyOk ? "key-ok" : "key-missing"}"></span>
        ${p.api_key_env === "NONE" ? "local — no key ever needed" : keyOk ? "key found: " + p.api_key_env : "missing key: " + p.api_key_env}
      </div>
      ${p.api_key_env !== "NONE" && !keyOk ? `
      <div class="keyrow">
        <input type="password" id="key_${p.provider}" placeholder="paste ${p.provider} API key">
        <button onclick="saveKey('${p.provider}')">Save</button>
      </div>` : ""}
      <div class="muted" style="margin-top:.4rem">models: ${(Object.values(p.models || []).join(", ") || (p.provider === "ollama-local" ? "your machine's local models (auto-discovered)" : "—")).slice(0, 60)}${Object.values(p.models || []).join(", ").length > 60 ? "…" : ""}</div>
      <div class="muted">cost: $${p.cost_per_mtok_input}/in · $${p.cost_per_mtok_output}/out per Mtok</div>
    `;
    grid.appendChild(card);
  }
}
async function toggleProvider(el) {
  const name = el.dataset.provider;
  const on = !el.classList.contains("on");
  await fetch("/api/providers/toggle", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({provider:name, enabled:on})});
  loadJevCard();
loadProviders();
loadStats(); loadFleet(); loadLog();
}
async function saveKey(name) {
  const key = document.getElementById("key_" + name).value.trim();
  if (!key) return;
  const r = await (await fetch("/api/providers/key", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({provider:name, key})})).json();
  loadJevCard();
loadProviders();
loadStats(); loadFleet(); loadLog();
}
loadJevCard();
loadProviders();
loadStats(); loadFleet(); loadLog();
