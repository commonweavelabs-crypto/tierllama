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
                    max: "Thinking: MAX (deep, slower)"};
    [ "off","normal","max"].forEach(l => {
      const o = document.createElement("option"); o.value = l; o.textContent = LABELS[l];
      if (l === (t.thinking || "normal")) o.selected = true; think.appendChild(o);
    });
    think.title = "Thinking level for this tier: OFF = answer directly, NORMAL = standard reasoning, MAX = deep reasoning (slower)";
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
  el.textContent = `difficulty=${r.difficulty} timing=${r.timing} lane=${r.lane} confidence=${r.confidence}`;
}
async function loadFleet() {
  const f = await (await fetch("/api/fleet")).json();
  const KIND = {ollama:`<img src="icons/svg/brand-ollama.svg" style="width:14px;height:14px;vertical-align:-2px"> Ollama`, "llama-swap":`<img src="icons/svg/ui-arrow-left-right.svg" style="width:14px;height:14px;vertical-align:-2px"> llama-swap`, unknown:`<img src="icons/svg/ui-circle-help.svg" style="width:14px;height:14px;vertical-align:-2px">`};
  const unnamed = (f.peers || []).some(p => !p.name_user_set && p.name === p.host);  // enrichment still running
  document.getElementById("fleet").innerHTML = (f.peers || []).map(p => `
    <div style="display:flex;justify-content:space-between;padding:.3rem 0;border-bottom:1px solid #2a313a">
      <span><b>${p.name}</b> <span class="muted">${p.name_user_set ? "" : "(auto)"}</span>
        <span class="muted" style="font-size:.78rem">· ${p.host}:${p.port}${p.os ? " · " + p.os : ""}</span>
        <button style="font-size:.65rem;margin-left:.4rem;padding:.05rem .4rem" onclick="renameFleet('${p.host}',${p.port},'${(p.name||"").replace(/'/g,"\\'")}')">rename</button></span>
      <span class="muted">${KIND[p.kind] || p.kind} · ${ (p.models||[]).length } models</span>
    </div>`).join("") || '<div class="muted">scanning…</div>';
  if (unnamed) setTimeout((_ => loadFleet()), 5000);  // names land when the background enrich finishes
}
async function renameFleet(host, port, current) {
  const name = prompt("Name this machine (empty = back to auto hostname):", current);
  if (name === null) return;
  const r = await (await fetch("/api/fleet/name", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({host, port, name: name.trim()})})).json();
  if (!r.ok) alert(r.error || "rename failed");
  loadFleet();
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
      <td>${x.difficulty||""}</td><td>${x.timing||""}</td>
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
async function rescanModels(mode = "price", includeLocal = true, includeSmall = false, useCatalog = false) {
  mode = mode || (window._lastMode || "price");
  window._lastMode = mode;
  const src = useCatalog ? "catalog" : "used";
  // J19.5 hardware gate: the suggestions feature runs the Jev brain — check
  // hardware state BEFORE rating. Never locked out silently; never promised
  // a feature the machine can't run (CPU-only 8b = ~66s/decision, measured).
  const hw = await (await fetch("/api/jev/hardware")).json();
  const gate = document.getElementById("hardwareGate");
  if (!hw.usable) {
    gate.style.display = "block";
    gate.innerHTML = hw.installed
      ? `⚠ <b>Not usable right now:</b> ${hw.reason}. Free up VRAM or run suggestions on a stronger machine — brain (${hw.model}) is installed (${hw.size_mb}MB on disk).`
      : `⚠ <b>Model suggestions need the Jev brain (${hw.model}, ~5.2GB download${hw.gpu ? ", 6GB+ free VRAM" : ""}).</b>
         ${hw.gpu ? "Your GPU reports " + hw.vram_free_mb + "MB free — enough once downloaded." : "No discrete GPU detected — suggested picks will take minutes per decision on this machine."}
         <button style="font-size:.7rem;margin-left:.4rem" onclick="downloadJevBrain(this)">Pull ${hw.model}</button> <span id="pullMsg" class="muted"></span>`;
    document.getElementById("seedStatus").textContent = "Suggestions locked — brain/hardware gate.";
    return;
  }
  gate.style.display = "none";
  const cardT = document.getElementById("inclLocalCard");
  const cardS = document.getElementById("inclSmall");
  if (cardT && cardT.checked !== includeLocal) cardT.checked = includeLocal;
  if (cardS && cardS.checked !== includeSmall) cardS.checked = includeSmall;
  const st = document.getElementById("seedStatus");
  st.textContent = "Rating your models...";
  const loc = includeLocal ? "true" : "false";
  const sm = includeSmall ? "true" : "false";
  const sg = await (await fetch(`/api/suggestions?mode=${mode}&include_local=${loc}&include_small=${sm}&source=${src}`)).json();
  const rc = await (await fetch(`/api/models/rated?mode=${mode}&include_local=${loc}&include_small=${sm}&source=${src}`)).json();
  // J19: unbekannten models warning + benchmark-offer (never leave the user stranded)
  const warn = document.getElementById("unbenchedWarn");
  if (rc.unbenched && rc.unbenched.length) {
    warn.style.display = "block";
    warn.innerHTML = `⚠ ${rc.unbenched.length} model(s) not benchmarked yet — excluded from timing-sensitive suggestions: <b>${rc.unbenched.join(", ")}</b>
      <button style="font-size:.7rem;margin-left:.4rem" onclick="benchmarkMissing()">Benchmark them now</button> <span id="benchMsg"></span>`;
  } else warn.style.display = "none";
  const box = document.getElementById("seedDiff");
  let html = `<div class="muted">Rated from ${rc.pool_size} models (${includeLocal ? "local + cloud" : "CLOUD ONLY"}).</div>`;
  for (const [tier, info] of Object.entries(rc.tiers)) {
    const flag = info.flag ? ` <span class="muted" style="color:#f6ad55">⚠ ${info.flag}</span>` : "";
    const picked = sg.tiers[tier] ? sg.tiers[tier].model + " · " + (sg.tiers[tier].thinking) : "—";
    html += `<div class="tier-row" style="grid-template-columns:110px 1fr;margin:.2rem 0">
      <label>${tier}</label>
      <div><b>${picked}</b>${flag}
        <div class="muted" style="font-size:.72rem;overflow-x:auto;white-space:nowrap">all: ${info.candidates.map(c => `${c.model}${c.cloud?"☁":""} (${c.capability})`).join(" · ")}</div>
      </div></div>`;
  }
  html += `<button class="primary" onclick="applySuggestions('${mode}',${includeLocal},${includeSmall},${useCatalog})">Apply these suggestions</button>`;
  box.innerHTML = html; box.style.display = "block";
  st.textContent = "Review, then apply.";
}
async function benchmarkMissing() {
  const msg = document.getElementById("benchMsg");
  msg.textContent = "benchmarking missing models (this takes a few minutes — they run real prompts)...";
  const rc = await (await fetch(`/api/models/rated?mode=${window._lastMode||"price"}`)).json();
  const r = await (await fetch("/api/bench/run", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({models: rc.unbenched})})).json();
  if (r.started) {
    msg.textContent = "bench running in background — this panel updates when done. Re-scan afterwards.";
    const iv = setInterval(async () => {
      const s = await (await fetch("/api/bench/run")).json();
      if (!s.running) { clearInterval(iv); msg.textContent = s.last_result ? `bench done (${s.last_result} models graded) — re-scan to include them.` : "bench done — re-scan."; }
      else msg.textContent = `testing ${s.current} (${s.done}/${s.total || "?"})...`;
    }, 5000);
  } else msg.textContent = r.reason || r.error || "could not start bench";
}
async function applySuggestions(mode, includeLocal = true, includeSmall = false, useCatalog = false) {
  // never touch user-edited tiers (J10 sacred rule)
  const loc = includeLocal ? "true" : "false";
  const sm = includeSmall ? "true" : "false";
  const src = useCatalog ? "catalog" : "used";
  const sg = await (await fetch(`/api/suggestions?mode=${mode}&include_local=${loc}&include_small=${sm}&source=${src}`)).json();
  const cfg = await (await fetch("/api/config")).json();
  const edited = new Set(cfg.user_edited || []);
  const merged = { ...cfg.tiers };
  for (const [k, v] of Object.entries(sg.tiers)) {
    if (edited.has(k)) continue;
    merged[k] = v;
  }
  const r = await (await fetch("/api/config", {method:"PUT", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({tiers: merged, user_edited: [...edited]})})).json();
  document.getElementById("seedStatus").textContent = r.saved ? "Applied (user-edited tiers untouched) ✓" : "save failed";
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
  tierllama:{bg:"#DA1417", fg:"#fff", label:`<img src="icons/tierllama-logo.png" alt="" style="width:22px;height:22px;border-radius:5px">`},
};
async function loadJevCard() {
  const st = await (await fetch("/api/jev")).json();
  document.getElementById("jevDesc").textContent =
    "Jev is not a chat LLM - it's a System One model that returns typed decisions " +
    "(difficulty, timing) with calibrated confidence in ~80ms, not tokens of prose. " +
    "Every message you send is classified by a Jev-class brain (qwen3:8b) before routing — " +
    "the same brain matches pre-rated models to jobs in the suggestions panel. " +
    "The original Jev is TypeSafe AI's model (Diogo Almeida, ChatGPT co-creator); " +
    "our open-source local brain is a Jev-class qwen3:8b you run yourself - free, Apache-2.0. " + st.price + ".";
  document.getElementById("jevBody").innerHTML = `
    <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:.3rem 0">
      <span class="key-dot ${st.local_available ? "key-ok" : "key-missing"}"></span>
      <b style="font-size:.85rem">Local brain — Jev (qwen3:8b, one brain: classifies prompts + matches models)</b>
      <span class="muted">${st.local_available ? "running on your machine · free" : "not installed yet"}</span>
      ${!st.local_available ? `<button onclick="installJevLocal()" style="font-size:.75rem">Download local brain (ollama pull qwen3:8b, ~5.2GB)</button>` : ""}
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
async function downloadJevBrain(btn) {
  // J19.5: pull the configured Jev brain from the Ollama registry (digest-pinned
  // registry pull, never a random URL). Progress is honest: pull takes minutes.
  const msg = document.getElementById("pullMsg");
  btn.disabled = true;
  msg.textContent = "pulling (5.2GB) — watch 'ollama ps' or this box; on a fast line ~2-4 min...";
  const r = await (await fetch("/api/jev/install-local", {method: "POST"})).json();
  btn.disabled = false;
  if (r.ok) { msg.textContent = "✓ brain ready — re-run Re-scan, gate has lifted."; }
  else msg.textContent = "pull failed: " + (r.error || "?");
}
async function installJevLocal() {
  const r = await (await fetch("/api/jev/install-local", {method:"POST"})).json();
  alert(r.ok ? "Local brain pulled - ready." : "pull failed: " + (r.error||"?"));
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


// ---------- J16 machines ----------
const MACHINE_CLASSES = ["workhorse", "always_on", "night_only", "cloud_scheduled"];
async function loadMachines() {
  const r = await (await fetch("/api/machines")).json();
  const el = document.getElementById("machineList");
  if (!r.machines || !r.machines.length) {
    el.innerHTML = '<div class="muted">No machines yet. Run tierllama discovery or bench to find machines on your network.</div>';
    return;
  }
  el.innerHTML = r.machines.map(m => `
    <div class="tier-row" style="grid-template-columns:1fr auto;margin:.4rem 0">
      <div>
        <b>${m.name}</b> <span class="muted">(${m.host})</span><br>
        <span class="muted">class: ${m.class ? m.class : "not set — pick one:"}</span>
        ${m.class ? '' : `<select onchange="setMachineClass('${m.host}', this.value)">
          <option value="">choose…</option>
          ${MACHINE_CLASSES.map(c => `<option value="${c}">${c}</option>`).join("")}
        </select>`}
        ${m.class && m.class_confirmed_by === "user" ? '<span class="badge" style="font-size:.6rem">user-confirmed</span>' : ''}
        ${m.pairs && m.pairs.length ? '<br><span class="muted">pairs: ' + m.pairs.map(p => `${p.model} (${p.timing_fit}/${p.max_fit}, ${p.tok_s} tok/s)`).join(" · ") + '</span>' : ''}
        ${m.models && m.models.length ? '<br><span class="muted">models seen: ' + m.models.slice(0,4).join(", ") + (m.models.length>4?` +${m.models.length-4}`:'') + '</span>' : ''}
      </div>
    </div>`).join("");
}
async function setMachineClass(host, cls) {
  if (!cls) return;
  const r = await (await fetch("/api/machines/class", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({host, class: cls})})).json();
  loadMachines();
}

// ---------- J13 scheduler (BETA) ----------
async function loadScheduler() {
  const r = await (await fetch("/api/schedule")).json();
  const gate = document.getElementById("schedGate");
  const body = document.getElementById("schedBody");
  const btn = document.getElementById("schedToggleBtn");
  const state = document.getElementById("schedState");
  if (!r.enabled) {
    body.style.display = "none";
    btn.textContent = "Enable scheduler (beta)";
    state.innerHTML = '<span class="muted">Currently OFF. Jobs with deadlines route normally; nothing is scheduled.</span>';
    return;
  }
  body.style.display = "block";
  btn.textContent = "Disable scheduler";
  state.innerHTML = '<span class="muted" style="color:#68d391">Scheduler is ON (beta) — deadline jobs now enter the queue.</span>';
  const cl = document.getElementById("clarify");
  cl.innerHTML = (r.clarify && r.clarify.length) ? r.clarify.map(j => `
    <div class="tier-row" style="grid-template-columns:1fr auto">
      <div><b>${(j.message||"").slice(0,60)}</b><br>
        <span class="muted">date phrase: "${j.when_raw || j.meta?.raw || ""}" — needs confirmation</span></div>
      <div style="display:flex;gap:.4rem">
        <button onclick="schedResolve('${j.id}','schedule')">Schedule</button>
        <button onclick="schedResolve('${j.id}','now')">Run now</button>
        <button onclick="schedResolve('${j.id}','cancel')">Cancel</button>
      </div>
    </div>`).join("") : '<div class="muted">Nothing waiting.</div>';
  const up = document.getElementById("upcoming");
  up.innerHTML = (r.upcoming && r.upcoming.length) ? r.upcoming.map(j => `
    <tr><td>${(j.due_at||"").replace("T"," ").slice(0,16)}</td>
    <td>${(j.message||"").slice(0,50)}</td><td>${j.lane}</td><td>${j.status}</td>
    <td><button onclick="schedResolve('${j.id}','cancel')">✕</button></td></tr>`).join("")
    : '<tr><td colspan="5" class="muted">No upcoming jobs.</td></tr>';
}
async function schedToggle() {
  // read the authoritative state from the API (string-matching status text breaks silently if copy changes)
  const cur = await (await fetch("/api/schedule")).json();
  const r = await (await fetch("/api/schedule/toggle", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({enabled: !cur.enabled})})).json();
  document.getElementById("schedMsg").textContent = r.ok ? (!cur.enabled ? "enabled — beta active" : "disabled") : (r.reason || r.error || "failed");
  loadScheduler();
}
async function schedResolve(id, action) {
  await fetch("/api/schedule/resolve", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({id, action})});
  loadScheduler();
}
// refresh when the tab becomes active:
document.querySelectorAll('nav.tabs button').forEach(b => {
  b.addEventListener("click", () => {
    if (b.dataset.tab === "scheduler") loadScheduler();
    if (b.dataset.tab === "machines") loadMachines();
  });
});
loadScheduler();

// ---------- J14 capability loop (BETA) ----------
async function loadCapability() {
  const r = await (await fetch("/api/capability")).json();
  const btn = document.getElementById("capToggleBtn");
  const summary = document.getElementById("capSummary");
  const bumps = document.getElementById("capBumps");
  if (r.enabled) {
    btn.textContent = "Disable capability loop";
  } else {
    btn.textContent = "Enable capability loop (beta)";
  }
  const o = r.outcomes || {};
  summary.textContent = `outcomes so far: ${o.success || 0} success / ${o.failure || 0} failure / ${o.unknown || 0} unknown · gate ${r.enabled ? "ON (beta)" : "OFF"} · canary ${r.params.canary_pct}%`;
  // J17: seeded evidence + per-class table + dry-run "would bump" strip
  const cls = document.getElementById("capClasses");
  if (cls) {
    cls.innerHTML = (r.classes && r.classes.length)
      ? `<table style="width:100%;font-size:.78rem"><tr style="color:var(--muted)"><th>model@host</th><th>diff</th><th>when</th><th>samples</th><th>failures</th><th>avg lat</th></tr>` +
        r.classes.slice(0, 12).map(c => {
          const [mh, diff, timing, when] = c.key.split("|");
          return `<tr><td>${mh}</td><td>${diff}</td><td>${timing}/${when}</td><td>${c.samples}</td><td>${c.failures}</td><td>${c.avg_latency_s ?? "—"}</td></tr>`;
        }).join("") + "</table>"
      : '<div class="muted">no evidence yet — route something or run the bench.</div>';
  }
  const wb = document.getElementById("capWould");
  if (wb) {
    wb.innerHTML = (r.would_bump && r.would_bump.length)
      ? r.would_bump.map(b => `<div style="color:#f6ad55;font-size:.8rem">⬆ would bump ${b.key.split("|")[0]}: ${b.from} → ${b.to} — ${b.reason}</div>`).join("")
      : '<div class="muted" style="font-size:.8rem">dry-run: nothing would bump right now (no failure streaks).</div>';
  }
  if (r.seeded && r.seeded.seeded > 0) {
    document.getElementById("capMsg").textContent = `seeded ${r.seeded.seeded} outcomes from bench history ✓`;
  }
  bumps.innerHTML = (r.bumps && r.bumps.length)
    ? r.bumps.map(b => `<div class="muted">tired: ${b["class"]} ${b.from} -> ${b.to} — ${b.reason}</div>`).join("")
    : '<div class="muted">No class bumps yet (none forced while the gate is off).</div>';
}
async function capToggle() {
  const cur = await (await fetch("/api/capability")).json();
  const r = await (await fetch("/api/capability/toggle", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({enabled: !cur.enabled})})).json();
  document.getElementById("capMsg").textContent = r.ok ? (!cur.enabled ? "enabled — beta active" : "disabled") : (r.error || "failed");
  loadCapability();
}
document.addEventListener("DOMContentLoaded", loadCapability);
