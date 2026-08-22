// ============================================================================
// Config
// ============================================================================
const API_BASE = "http://localhost:8000";

// ============================================================================
// State
// ============================================================================
const state = {
  documentId: null,
  filename: null,
  chunkCount: 0,
  chunks: [],           // full chunk text list, index-aligned with backend
  graphBuilt: false,
  vector3dLoaded: false,
  podcastScript: null,  // [{speaker, text}]
  podcastPlaying: false,
  matrixOn: false,
};

// ============================================================================
// DOM references
// ============================================================================
const el = (id) => document.getElementById(id);

const statusBadge = el("statusBadge");
const noDocBanner = el("noDocBanner");

const dropZone = el("dropZone");
const fileInput = el("fileInput");
const uploadError = el("uploadError");
const fileCard = el("fileCard");
const fileName = el("fileName");
const fileMsg = el("fileMsg");
const removeDocBtn = el("removeDocBtn");
const chunkIndexWrap = el("chunkIndexWrap");
const chunkIndexList = el("chunkIndexList");
const chunkCountEl = el("chunkCount");

const chatFeed = el("chatFeed");
const chatForm = el("chatForm");
const userInput = el("userInput");
const askBtn = el("askBtn");

const buildGraphBtn = el("buildGraphBtn");
const buildGraphBtnLabel = el("buildGraphBtnLabel");
const graphStatus = el("graphStatus");
const graphEmpty = el("graphEmpty");
const graphNetworkEl = el("graphNetwork");

const vector3dEmpty = el("vector3dEmpty");
const vector3dPlot = el("vector3dPlot");
const projectQueryForm = el("projectQueryForm");
const vector3dQueryInput = el("vector3dQuery");

const generatePodcastBtn = el("generatePodcastBtn");
const generatePodcastBtnLabel = el("generatePodcastBtnLabel");
const podcastEmpty = el("podcastEmpty");
const podcastScriptWrap = el("podcastScriptWrap");
const podcastControls = el("podcastControls");
const podcastPlayBtn = el("podcastPlayBtn");
const podcastPlayIcon = el("podcastPlayIcon");
const podcastStopBtn = el("podcastStopBtn");
const podcastNowPlaying = el("podcastNowPlaying");

const matrixCanvas = el("matrixCanvas");
const matrixToggle = el("matrixToggle");
const matrixToggleLabel = el("matrixToggleLabel");

// ============================================================================
// Fetch helper
// ============================================================================
async function apiFetch(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch (err) {
    throw new Error(
      `Can't reach the backend at ${API_BASE}. Is it running? ` +
      `(uvicorn main:app --reload --port 8000)`
    );
  }
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    // no/invalid JSON body
  }
  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data;
}

// ============================================================================
// Backend health check
// ============================================================================
async function checkHealth() {
  try {
    await apiFetch("/api/health");
    statusBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500"></span> Backend online`;
    statusBadge.className = "text-xs px-3 py-1.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 flex items-center gap-2";
  } catch (err) {
    statusBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500"></span> Backend unreachable`;
    statusBadge.className = "text-xs px-3 py-1.5 rounded-full bg-rose-950/40 text-rose-400 border border-rose-800/40 flex items-center gap-2";
  }
}
checkHealth();
setInterval(checkHealth, 15000);

// ============================================================================
// Tabs
// ============================================================================
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = {
  workspace: el("panel-workspace"),
  graph: el("panel-graph"),
  vector3d: el("panel-vector3d"),
  podcast: el("panel-podcast"),
};

function activateTab(name) {
  tabButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === name));
  Object.entries(tabPanels).forEach(([key, panelEl]) => panelEl.classList.toggle("hidden", key !== name));

  const needsDoc = name !== "workspace";
  noDocBanner.classList.toggle("hidden", !(needsDoc && !state.documentId));

  if (name === "vector3d" && state.documentId && !state.vector3dLoaded) {
    loadVector3D();
  }
}

tabButtons.forEach((btn) => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));

// ============================================================================
// Upload flow (Workspace & Chat)
// ============================================================================
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
["dragover", "dragenter"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add("border-indigo-500/80"); })
);
["dragleave", "drop"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove("border-indigo-500/80"); })
);
dropZone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleUpload(file);
});
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) handleUpload(file);
});

async function handleUpload(file) {
  uploadError.classList.add("hidden");
  const formData = new FormData();
  formData.append("file", file);

  statusBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span> Processing…`;

  let data;
  try {
    const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: formData });
    data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");
  } catch (err) {
    uploadError.textContent = err.message;
    uploadError.classList.remove("hidden");
    checkHealth();
    return;
  }

  resetDocumentDependentUI();

  state.documentId = data.document_id;
  state.filename = data.filename;
  state.chunkCount = data.chunk_count;

  fileName.textContent = data.filename;
  fileMsg.textContent = `Indexed into ${data.chunk_count} chunks`;
  fileCard.classList.remove("hidden");
  fileCard.classList.add("flex");

  userInput.disabled = false;
  askBtn.disabled = false;
  userInput.placeholder = "Ask a question about your document…";

  buildGraphBtn.disabled = false;
  generatePodcastBtn.disabled = false;
  noDocBanner.classList.add("hidden");

  await loadChunkIndex();
  checkHealth();
}

async function loadChunkIndex() {
  try {
    const data = await apiFetch(`/api/document/${state.documentId}/chunks`);
    state.chunks = data.chunks;
    chunkCountEl.textContent = `(${state.chunks.length})`;
    chunkIndexList.innerHTML = "";
    state.chunks.forEach((chunk, i) => {
      const li = document.createElement("li");
      li.className = "chunk-index-item";
      li.id = `chunk-idx-${i}`;
      li.innerHTML = `<span class="chunk-num">${String(i + 1).padStart(2, "0")}</span><span>${escapeHtml(chunk.slice(0, 90))}${chunk.length > 90 ? "…" : ""}</span>`;
      chunkIndexList.appendChild(li);
    });
    chunkIndexWrap.classList.remove("hidden");
    chunkIndexWrap.classList.add("flex");
  } catch (err) {
    console.error("Failed to load chunk index:", err);
  }
}

removeDocBtn.addEventListener("click", async () => {
  if (!state.documentId) return;
  try {
    await fetch(`${API_BASE}/api/document/${state.documentId}`, { method: "DELETE" });
  } catch (_) { /* best effort */ }
  resetAll();
});

function resetDocumentDependentUI() {
  chatFeed.innerHTML = `
    <div class="flex gap-3">
      <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
        <i class="fa-solid fa-robot text-xs"></i>
      </div>
      <div class="bg-slate-800/80 p-4 rounded-2xl rounded-tl-none max-w-[80%] text-sm border border-slate-700">
        New document loaded. Ask me anything based on its contents.
      </div>
    </div>`;
  graphEmpty.classList.remove("hidden");
  graphNetworkEl.classList.add("hidden");
  graphStatus.textContent = "Extracted from the document by the local LLM. This costs one model call per batch of chunks — build it on demand.";
  state.graphBuilt = false;
  buildGraphBtnLabel.textContent = "Build Knowledge Graph";

  vector3dEmpty.classList.remove("hidden");
  vector3dPlot.classList.add("hidden");
  state.vector3dLoaded = false;

  stopPodcast();
  podcastEmpty.classList.remove("hidden");
  podcastScriptWrap.classList.add("hidden");
  podcastScriptWrap.innerHTML = "";
  podcastControls.classList.add("hidden");
  state.podcastScript = null;
  generatePodcastBtnLabel.textContent = "Generate Script";
}

function resetAll() {
  state.documentId = null;
  state.filename = null;
  state.chunkCount = 0;
  state.chunks = [];

  fileCard.classList.add("hidden");
  fileCard.classList.remove("flex");
  chunkIndexWrap.classList.add("hidden");
  chunkIndexWrap.classList.remove("flex");
  chunkIndexList.innerHTML = "";

  userInput.disabled = true;
  askBtn.disabled = true;
  userInput.placeholder = "Upload a document to start asking questions…";

  buildGraphBtn.disabled = true;
  generatePodcastBtn.disabled = true;

  resetDocumentDependentUI();

  const activeTab = document.querySelector(".tab-btn.active");
  if (activeTab && activeTab.dataset.tab !== "workspace") {
    noDocBanner.classList.remove("hidden");
  }
}
buildGraphBtn.disabled = true;
generatePodcastBtn.disabled = true;

// ============================================================================
// Chat flow (Workspace & Chat)
// ============================================================================
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = userInput.value.trim();
  if (!question || !state.documentId) return;

  appendChatMessage("user", question);
  userInput.value = "";
  const loadingId = appendLoadingBubble();

  try {
    const data = await apiFetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: state.documentId, question }),
    });
    el(loadingId).remove();
    appendChatMessage("bot", data.answer, data.sources, data.found);
  } catch (err) {
    el(loadingId).remove();
    appendChatMessage("bot", err.message, [], false, true);
  }
});

function appendChatMessage(sender, text, sources = [], found = true, isError = false) {
  const wrap = document.createElement("div");
  wrap.className = `flex gap-3 ${sender === "user" ? "justify-end" : ""}`;

  const isBot = sender === "bot";
  let bubbleClasses = isBot
    ? "bg-slate-800/80 border-slate-700 rounded-tl-none"
    : "bg-indigo-600 text-white border-transparent rounded-tr-none";
  if (isBot && isError) bubbleClasses += " error-bubble";
  else if (isBot && !found) bubbleClasses += " not-found-bubble";

  let sourcesHtml = "";
  if (isBot && sources && sources.length > 0) {
    sourcesHtml = `<div class="mt-2 flex flex-wrap gap-1.5">` +
      sources.map((s) => {
        const idx = s.index;
        return `<span class="source-pill" data-chunk-index="${idx}">
          <i class="fa-solid fa-link text-[9px]"></i> chunk ${idx >= 0 ? idx + 1 : "?"} · ${s.score.toFixed(2)}
        </span>`;
      }).join("") +
      `</div>`;
  }

  wrap.innerHTML = `
    ${isBot ? '<div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0"><i class="fa-solid fa-robot text-xs"></i></div>' : ""}
    <div class="${bubbleClasses} p-4 rounded-2xl max-w-[80%] text-sm border">
      <p>${escapeHtml(text)}</p>
      ${sourcesHtml}
    </div>
  `;
  chatFeed.appendChild(wrap);
  chatFeed.scrollTop = chatFeed.scrollHeight;

  wrap.querySelectorAll(".source-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const idx = parseInt(pill.dataset.chunkIndex, 10);
      if (idx >= 0) highlightChunkInIndex(idx);
    });
  });
}

function appendLoadingBubble() {
  const id = "load-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "flex gap-3";
  div.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0"><i class="fa-solid fa-robot text-xs animate-spin"></i></div>
    <div class="bg-slate-800/80 p-4 rounded-2xl rounded-tl-none text-sm border border-slate-700 text-slate-400">
      Searching document &amp; generating answer…
    </div>`;
  chatFeed.appendChild(div);
  chatFeed.scrollTop = chatFeed.scrollHeight;
  return id;
}

function highlightChunkInIndex(idx) {
  document.querySelectorAll(".chunk-index-item.highlighted").forEach((item) => item.classList.remove("highlighted"));
  const target = el(`chunk-idx-${idx}`);
  if (!target) return;
  target.classList.add("highlighted", "flash");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => target.classList.remove("flash"), 900);
}

// ============================================================================
// Knowledge Graph
// ============================================================================
let graphNetworkInstance = null;

buildGraphBtn.addEventListener("click", async () => {
  if (!state.documentId) return;
  buildGraphBtn.disabled = true;
  buildGraphBtnLabel.textContent = "Building… (this may take a while)";
  graphStatus.textContent = "Extracting entities and relationships with the local LLM…";

  try {
    const graph = await apiFetch(`/api/document/${state.documentId}/graph/build`, { method: "POST" });
    renderGraph(graph);
    state.graphBuilt = true;
    buildGraphBtnLabel.textContent = "Rebuild Graph";
    graphStatus.textContent =
      `${graph.nodes.length} entities, ${graph.edges.length} relationships ` +
      `(from ${graph.batches_processed}/${graph.batches_total} chunk batches).`;
  } catch (err) {
    graphStatus.textContent = `Couldn't build the graph: ${err.message}`;
    buildGraphBtnLabel.textContent = "Build Knowledge Graph";
  } finally {
    buildGraphBtn.disabled = false;
  }
});

function renderGraph(graph) {
  graphEmpty.classList.add("hidden");
  graphNetworkEl.classList.remove("hidden");

  if (!graph.nodes.length) {
    graphEmpty.classList.remove("hidden");
    graphNetworkEl.classList.add("hidden");
    graphEmpty.textContent = "No clear entities/relationships were found in this document.";
    return;
  }

  const nodes = new vis.DataSet(graph.nodes.map((n) => ({
    id: n.id,
    label: n.id,
    value: n.weight,
    font: { color: "#e2e8f0", size: 13 },
    color: { background: "#4f46e5", border: "#818cf8", highlight: { background: "#818cf8", border: "#c4b5fd" } },
  })));
  const edges = new vis.DataSet(graph.edges.map((e) => ({
    from: e.source,
    to: e.target,
    label: e.label,
    font: { color: "#94a3b8", size: 10, strokeWidth: 0, background: "#0b0f17" },
    color: { color: "#475569", highlight: "#a78bfa" },
    arrows: "to",
    smooth: { type: "continuous" },
  })));

  const options = {
    nodes: { shape: "dot", scaling: { min: 10, max: 30 } },
    physics: { stabilization: true, barnesHut: { gravitationalConstant: -3000, springLength: 140 } },
    interaction: { hover: true, tooltipDelay: 100 },
  };

  if (graphNetworkInstance) graphNetworkInstance.destroy();
  graphNetworkInstance = new vis.Network(graphNetworkEl, { nodes, edges }, options);
}

// ============================================================================
// 3D Vector Space
// ============================================================================
async function loadVector3D(queryText) {
  if (!state.documentId) return;
  try {
    const qs = queryText ? `?q=${encodeURIComponent(queryText)}` : "";
    const data = await apiFetch(`/api/document/${state.documentId}/vectors3d${qs}`);
    renderVector3D(data);
    state.vector3dLoaded = true;
  } catch (err) {
    vector3dEmpty.textContent = `Couldn't load the vector space: ${err.message}`;
    vector3dEmpty.classList.remove("hidden");
    vector3dPlot.classList.add("hidden");
  }
}

function renderVector3D(data) {
  vector3dEmpty.classList.add("hidden");
  vector3dPlot.classList.remove("hidden");

  const traces = [{
    type: "scatter3d",
    mode: "markers",
    name: "Document chunks",
    x: data.points.map((p) => p.x),
    y: data.points.map((p) => p.y),
    z: data.points.map((p) => p.z),
    text: data.points.map((p) => `Chunk ${p.index + 1}<br>${p.label}`),
    hoverinfo: "text",
    marker: { size: 5, color: "#818cf8", opacity: 0.85, line: { color: "#c4b5fd", width: 0.5 } },
  }];

  if (data.query_point) {
    traces.push({
      type: "scatter3d",
      mode: "markers",
      name: "Your question",
      x: [data.query_point.x],
      y: [data.query_point.y],
      z: [data.query_point.z],
      text: [`Question: ${data.query_point.label}`],
      hoverinfo: "text",
      marker: { size: 9, color: "#f472b6", symbol: "diamond", line: { color: "#fbcfe8", width: 1 } },
    });
  }

  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#94a3b8", size: 11 },
    margin: { l: 0, r: 0, t: 10, b: 0 },
    showlegend: true,
    legend: { font: { color: "#cbd5e1" }, bgcolor: "rgba(0,0,0,0)" },
    scene: {
      xaxis: { title: "", showbackground: false, gridcolor: "#1e293b", zerolinecolor: "#334155" },
      yaxis: { title: "", showbackground: false, gridcolor: "#1e293b", zerolinecolor: "#334155" },
      zaxis: { title: "", showbackground: false, gridcolor: "#1e293b", zerolinecolor: "#334155" },
    },
  };

  Plotly.newPlot(vector3dPlot, traces, layout, { displayModeBar: false, responsive: true });
}

projectQueryForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = vector3dQueryInput.value.trim();
  if (!state.documentId) return;
  loadVector3D(q || undefined);
});

// ============================================================================
// Podcast
// ============================================================================
generatePodcastBtn.addEventListener("click", async () => {
  if (!state.documentId) return;
  stopPodcast(); // don't let a stale script keep talking while a new one loads
  generatePodcastBtn.disabled = true;
  generatePodcastBtnLabel.textContent = "Writing script…";

  try {
    const data = await apiFetch(`/api/document/${state.documentId}/podcast`, { method: "POST" });
    state.podcastScript = data.script;
    renderPodcastScript(data.script);
    generatePodcastBtnLabel.textContent = "Regenerate Script";
  } catch (err) {
    podcastEmpty.textContent = `Couldn't generate a script: ${err.message}`;
    podcastEmpty.classList.remove("hidden");
    generatePodcastBtnLabel.textContent = "Generate Script";
  } finally {
    generatePodcastBtn.disabled = false;
  }
});

// Robust to whatever exact label the LLM used ("Host B", "HOST B", "Speaker 2", ...):
// try to recognize it, and fall back to alternating by position if we can't.
function isHostBSpeaker(speaker, index) {
  const s = (speaker || "").trim().toLowerCase();
  if (s.includes("host b") || s === "b" || s.includes("speaker 2")) return true;
  if (s.includes("host a") || s === "a" || s.includes("speaker 1")) return false;
  return index % 2 === 1;
}

function renderPodcastScript(script) {
  podcastEmpty.classList.add("hidden");
  podcastScriptWrap.classList.remove("hidden");
  podcastControls.classList.remove("hidden");
  podcastScriptWrap.innerHTML = "";

  script.forEach((line, i) => {
    const isHostB = isHostBSpeaker(line.speaker, i);
    const div = document.createElement("div");
    div.className = `podcast-line ${isHostB ? "host-b" : "host-a"}`;
    div.id = `podcast-line-${i}`;
    div.innerHTML = `
      <div class="podcast-avatar">${isHostB ? "B" : "A"}</div>
      <div class="podcast-bubble">
        <p class="text-[10px] uppercase tracking-wider text-slate-500 mb-1">${escapeHtml(line.speaker)}</p>
        <p>${escapeHtml(line.text)}</p>
      </div>`;
    podcastScriptWrap.appendChild(div);
  });
  podcastNowPlaying.textContent = "Ready to play";
}

// --- Playback via the browser's built-in speech synthesis (no server TTS needed) ---
let speechQueueIndex = 0;
// Set right before we deliberately cancel an in-flight utterance (pause/stop),
// so the onend/onerror handler can tell "cancelled by us" apart from "finished
// speaking naturally" and only auto-advance in the latter case.
let suppressAutoAdvance = false;
let voices = [];
function loadVoices() { voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : []; }
if (window.speechSynthesis) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function pickVoice(isHostB) {
  if (!voices.length) return null;
  const enVoices = voices.filter((v) => v.lang && v.lang.startsWith("en"));
  const pool = enVoices.length ? enVoices : voices;
  return isHostB ? pool[pool.length - 1] : pool[0];
}

function speakLine(index) {
  const script = state.podcastScript;
  if (!script || index >= script.length) {
    stopPodcast();
    return;
  }
  document.querySelectorAll(".podcast-line.speaking").forEach((l) => l.classList.remove("speaking"));
  const lineEl = el(`podcast-line-${index}`);
  if (lineEl) {
    lineEl.classList.add("speaking");
    lineEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const line = script[index];
  const isHostB = isHostBSpeaker(line.speaker, index);
  podcastNowPlaying.textContent = `Speaking: ${line.speaker}`;

  if (!window.speechSynthesis) {
    podcastNowPlaying.textContent = "Speech synthesis isn't supported in this browser.";
    return;
  }

  const utterance = new SpeechSynthesisUtterance(line.text);
  const voice = pickVoice(isHostB);
  if (voice) utterance.voice = voice;
  utterance.pitch = isHostB ? 1.15 : 0.95;
  utterance.rate = 1.0;

  const advance = () => {
    if (suppressAutoAdvance) {
      // We cancelled this utterance ourselves (pause/stop) — don't treat
      // it as "finished", and don't skip past the line the user paused on.
      suppressAutoAdvance = false;
      return;
    }
    speechQueueIndex += 1;
    if (state.podcastPlaying) speakLine(speechQueueIndex);
  };
  utterance.onend = advance;
  utterance.onerror = advance;

  window.speechSynthesis.speak(utterance);
}

function playPodcast() {
  if (!state.podcastScript || !state.podcastScript.length) return;
  state.podcastPlaying = true;
  podcastPlayIcon.className = "fa-solid fa-pause text-sm";
  matrixCanvas.classList.add("intensify");
  speakLine(speechQueueIndex);
}

function pausePodcast() {
  state.podcastPlaying = false;
  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    suppressAutoAdvance = true;
    window.speechSynthesis.cancel();
  }
  podcastPlayIcon.className = "fa-solid fa-play text-sm";
  matrixCanvas.classList.remove("intensify");
  podcastNowPlaying.textContent = "Paused";
}

function stopPodcast() {
  state.podcastPlaying = false;
  speechQueueIndex = 0;
  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    suppressAutoAdvance = true;
    window.speechSynthesis.cancel();
  }
  podcastPlayIcon.className = "fa-solid fa-play text-sm";
  matrixCanvas.classList.remove("intensify");
  document.querySelectorAll(".podcast-line.speaking").forEach((l) => l.classList.remove("speaking"));
  podcastNowPlaying.textContent = "Ready to play";
}

podcastPlayBtn.addEventListener("click", () => {
  if (state.podcastPlaying) pausePodcast();
  else playPodcast();
});
podcastStopBtn.addEventListener("click", stopPodcast);

// ============================================================================
// Matrix rain effect
// ============================================================================
const ctx = matrixCanvas.getContext("2d");
const MATRIX_CHARS = "アイウエオカキクケコサシスセソ0123456789ABCDEFRAGGRAPH";
let matrixColumns = [];
let matrixAnimationId = null;

function resizeMatrixCanvas() {
  matrixCanvas.width = window.innerWidth;
  matrixCanvas.height = window.innerHeight;
  const columnCount = Math.floor(matrixCanvas.width / 16);
  matrixColumns = new Array(columnCount).fill(0);
}
window.addEventListener("resize", resizeMatrixCanvas);
resizeMatrixCanvas();

function drawMatrixFrame() {
  ctx.fillStyle = "rgba(11, 15, 23, 0.12)";
  ctx.fillRect(0, 0, matrixCanvas.width, matrixCanvas.height);
  ctx.fillStyle = "#34d399";
  ctx.font = "14px monospace";

  matrixColumns.forEach((y, i) => {
    const char = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
    ctx.fillText(char, i * 16, y);
    if (y > matrixCanvas.height && Math.random() > 0.975) {
      matrixColumns[i] = 0;
    } else {
      matrixColumns[i] = y + 16;
    }
  });
  matrixAnimationId = requestAnimationFrame(drawMatrixFrame);
}

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function setMatrixActive(active) {
  state.matrixOn = active;
  matrixCanvas.classList.toggle("active", active);
  matrixToggleLabel.textContent = active ? "On" : "Off";
  if (prefersReducedMotion) return;
  if (active && !matrixAnimationId) {
    drawMatrixFrame();
  } else if (!active && matrixAnimationId) {
    cancelAnimationFrame(matrixAnimationId);
    matrixAnimationId = null;
  }
}

matrixToggle.addEventListener("change", () => setMatrixActive(matrixToggle.checked));

// ============================================================================
// Utils
// ============================================================================
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

// ============================================================================
// Init
// ============================================================================
activateTab("workspace");
