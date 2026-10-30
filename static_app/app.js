/**
 * AdaptShield v2.0 — VOID SENTINEL Controller & Multi-View Engine
 * Tasks: 6-Views Router, Draggable Telemetry Terminal, Drag & Drop Overhaul, Security Logs
 */

// ═══════════════════════════ 1. STATE & STORAGE ═══════════════════════════
const STORAGE_KEY = "adaptshield_sessions";
const ACTIVE_SESSION_KEY = "adaptshield_active_session_id";
const LOGS_STORAGE_KEY = "adaptshield_security_logs";
const THEME_KEY = "as-theme";

let sessions = [];
let securityLogs = [];
let activeSessionId = null;
let attachedFile = null;
let currentTelemetryTimeout = null;
let availableModels = [];
let currentView = "workspace";

// ═══════════════════════════ 2. THEME & RUNTIME CONTROLLER ═══════════════════════════
(function initThemeAndRuntime() {
  const stored = localStorage.getItem(THEME_KEY);
  const pref = (stored === "light" || stored === "dark") ? stored :
    (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  document.documentElement.setAttribute("data-theme", pref);

  // Detect Desktop Mode (SOC Mode)
  const isDesktop = new URLSearchParams(window.location.search).get("mode") === "desktop" ||
                    window.pywebview !== undefined;
  if (isDesktop) {
    document.addEventListener("DOMContentLoaded", () => {
      const modeBadge = document.getElementById("modeBadge");
      const brandVersion = document.getElementById("brandVersion");
      const runtimeModeEl = document.getElementById("settingsRuntimeMode");
      if (modeBadge) modeBadge.hidden = false;
      if (brandVersion) brandVersion.textContent = "SOC v2.0";
      if (runtimeModeEl) runtimeModeEl.textContent = "Native Windows Desktop SOC (pywebview)";
    });
  }
})();

const themeToggle = document.getElementById("themeToggle");
if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
  });
}

// ═══════════════════════════ 3. MULTI-VIEW NAVIGATION ROUTER ═══════════════════════════
function switchView(viewName) {
  currentView = viewName;

  // Update Navigation Tabs
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    if (tab.dataset.view === viewName) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  // Update View Panels
  const viewPanels = {
    overview: document.getElementById("viewOverview"),
    workspace: document.getElementById("viewWorkspace"),
    scanner: document.getElementById("viewScanner"),
    intelligence: document.getElementById("viewIntelligence"),
    logs: document.getElementById("viewLogs"),
    settings: document.getElementById("viewSettings")
  };

  Object.keys(viewPanels).forEach(key => {
    const el = viewPanels[key];
    if (el) {
      if (key === viewName) {
        el.classList.add("active");
      } else {
        el.classList.remove("active");
      }
    }
  });

  if (viewName === "logs") {
    renderSecurityLogs();
  }
}

// ═══════════════════════════ 4. SESSIONS ARCHITECTURE ═══════════════════════════
function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    sessions = raw ? JSON.parse(raw) : [];
  } catch (e) {
    sessions = [];
  }

  if (!Array.isArray(sessions) || sessions.length === 0) {
    const defaultSession = createNewSessionObject("Default Shield Session");
    sessions = [defaultSession];
    saveSessions();
  }

  activeSessionId = localStorage.getItem(ACTIVE_SESSION_KEY) || sessions[0].id;
  if (!sessions.find(s => s.id === activeSessionId)) {
    activeSessionId = sessions[0].id;
  }

  // Load Security Logs
  try {
    const rawLogs = localStorage.getItem(LOGS_STORAGE_KEY);
    securityLogs = rawLogs ? JSON.parse(rawLogs) : [];
  } catch (e) {
    securityLogs = [];
  }

  // Background sync with server
  syncSessionsWithBackend();
}

function saveSessions() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
  renderSessionList();
}

function getActiveSession() {
  return sessions.find(s => s.id === activeSessionId) || sessions[0];
}

function createNewSessionObject(title = "New Shield Session") {
  return {
    id: "sess_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6),
    title: title,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: []
  };
}

function createNewSession() {
  const newSess = createNewSessionObject("New Shield Session");
  sessions.unshift(newSess);
  activeSessionId = newSess.id;
  saveSessions();
  renderChatMessages();
  switchView("workspace");
  showToast("New shield session created");

  const promptBox = document.getElementById("promptBox");
  if (promptBox) promptBox.focus();
}

function renameSession(sessionId) {
  const sess = sessions.find(s => s.id === sessionId);
  if (!sess) return;
  const newTitle = prompt("Rename session:", sess.title);
  if (newTitle && newTitle.trim()) {
    sess.title = newTitle.trim();
    sess.updated_at = new Date().toISOString();
    saveSessions();
    if (sess.id === activeSessionId) {
      updateActiveHeaderTitle(sess.title);
    }
    showToast("Session renamed");
  }
}

function deleteSession(sessionId) {
  if (sessions.length <= 1) {
    showToast("Cannot delete the only session.");
    return;
  }
  if (!confirm("Are you sure you want to delete this session?")) return;

  const idx = sessions.findIndex(s => s.id === sessionId);
  if (idx !== -1) {
    sessions.splice(idx, 1);
    if (activeSessionId === sessionId) {
      activeSessionId = sessions[0].id;
    }
    saveSessions();
    renderChatMessages();
    showToast("Session deleted");

    // Also delete from backend
    fetch(`/api/sessions/${sessionId}`, { method: "DELETE" }).catch(() => {});
  }
}

function selectSession(sessionId) {
  if (activeSessionId === sessionId) return;
  activeSessionId = sessionId;
  localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
  renderSessionList();
  renderChatMessages();
  switchView("workspace");
}

function updateActiveHeaderTitle(title) {
  const header = document.getElementById("activeSessionHeader");
  if (header) {
    header.textContent = title;
  }
}

// ═══════════════════════════ 5. SESSIONS RENDERING ═══════════════════════════
function renderSessionList() {
  const container = document.getElementById("sessionGroups");
  if (!container) return;
  container.innerHTML = "";

  const now = new Date();
  const todaySessions = [];
  const past7DaysSessions = [];
  const olderSessions = [];

  sessions.forEach(sess => {
    const updatedAt = new Date(sess.updated_at || sess.created_at || now);
    const diffDays = Math.floor((now - updatedAt) / (1000 * 60 * 60 * 24));

    if (diffDays <= 0) {
      todaySessions.push(sess);
    } else if (diffDays <= 7) {
      past7DaysSessions.push(sess);
    } else {
      olderSessions.push(sess);
    }
  });

  const appendGroup = (title, groupItems) => {
    if (groupItems.length === 0) return;

    const groupHeader = document.createElement("div");
    groupHeader.className = "session-group-header";
    groupHeader.textContent = title;
    container.appendChild(groupHeader);

    const list = document.createElement("div");
    list.className = "session-list";

    groupItems.forEach(sess => {
      const item = document.createElement("div");
      item.className = `session-item ${sess.id === activeSessionId ? "active" : ""}`;

      const titleSpan = document.createElement("span");
      titleSpan.className = "session-item-title";
      titleSpan.textContent = sess.title || "Untitled Session";
      titleSpan.title = sess.title;
      item.appendChild(titleSpan);

      const actions = document.createElement("div");
      actions.className = "session-item-actions";

      const renameBtn = document.createElement("button");
      renameBtn.className = "btn-session-action rename-btn";
      renameBtn.innerHTML = "✎";
      renameBtn.title = "Rename session";
      renameBtn.onclick = (e) => {
        e.stopPropagation();
        renameSession(sess.id);
      };
      actions.appendChild(renameBtn);

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn-session-action";
      deleteBtn.innerHTML = "✕";
      deleteBtn.title = "Delete session";
      deleteBtn.onclick = (e) => {
        e.stopPropagation();
        deleteSession(sess.id);
      };
      actions.appendChild(deleteBtn);

      item.appendChild(actions);

      item.onclick = () => selectSession(sess.id);
      list.appendChild(item);
    });

    container.appendChild(list);
  };

  appendGroup("Today", todaySessions);
  appendGroup("Previous 7 Days", past7DaysSessions);
  appendGroup("Older", olderSessions);

  const activeSess = getActiveSession();
  if (activeSess) {
    updateActiveHeaderTitle(activeSess.title);
  }
}

// ═══════════════════════════ 6. CHAT STREAM RENDERING ═══════════════════════════
function renderChatMessages() {
  const chatLog = document.getElementById("chatLog");
  const emptyState = document.getElementById("chatEmptyState");
  if (!chatLog) return;

  chatLog.innerHTML = "";

  const activeSess = getActiveSession();
  const msgs = activeSess ? activeSess.messages : [];

  if (!msgs || msgs.length === 0) {
    if (emptyState) {
      chatLog.appendChild(emptyState);
    }
    return;
  }

  msgs.forEach((msg, idx) => {
    appendMessageToDOM(msg, idx);
  });

  scrollChatToBottom();
}

function appendMessageToDOM(msg, idx) {
  const chatLog = document.getElementById("chatLog");
  const emptyState = document.getElementById("chatEmptyState");
  if (!chatLog) return;

  if (emptyState && emptyState.parentElement === chatLog) {
    emptyState.remove();
  }

  const isUser = msg.role === "user";
  const row = document.createElement("div");
  row.className = `msg-row ${isUser ? "msg-row-user" : "msg-row-bot"}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = isUser ? "U" : "🛡️";
  row.appendChild(avatar);

  const bubble = document.createElement("div");
  bubble.className = `msg-bubble ${msg.blocked ? "bubble-blocked" : ""}`;

  // Header row for bot messages with Telemetry chip
  if (!isUser) {
    const headRow = document.createElement("div");
    headRow.className = "msg-header-row";

    const name = document.createElement("span");
    name.className = "msg-role-name";
    name.textContent = "AdaptShield Defense";
    headRow.appendChild(name);

    if (msg.telemetry) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "msg-chip-telemetry";
      chip.innerHTML = `<span>⚡ Telemetry</span>`;
      chip.onclick = () => openTelemetryPopup(msg.telemetry);
      headRow.appendChild(chip);
    }

    bubble.appendChild(headRow);

    if (msg.blocked) {
      const blockBanner = document.createElement("div");
      blockBanner.className = "msg-blocked-banner";
      blockBanner.innerHTML = `<span>🚫 PAYLOAD INTERCEPTED</span>`;
      bubble.appendChild(blockBanner);
    }
  }

  // Attachment badge if user uploaded a document
  if (isUser && msg.file_info) {
    const badge = document.createElement("div");
    badge.className = "msg-attachment-badge";
    badge.innerHTML = `<span>📎 ${escapeHtml(msg.file_info.name)}</span>`;
    bubble.appendChild(badge);
  }

  // Content
  const body = document.createElement("div");
  body.className = "msg-content";
  body.innerHTML = renderMarkdown(msg.content);
  bubble.appendChild(body);

  row.appendChild(bubble);
  chatLog.appendChild(row);
}

function scrollChatToBottom() {
  const viewport = document.getElementById("chatViewport");
  if (viewport) {
    viewport.scrollTop = viewport.scrollHeight;
  }
}

// ═══════════════════════════ 7. DRAGGABLE macOS TERMINAL POPUP ═══════════════════════════
function openTelemetryPopup(telemetry) {
  if (!telemetry) return;

  if (currentTelemetryTimeout) {
    clearTimeout(currentTelemetryTimeout);
    currentTelemetryTimeout = null;
  }

  const popup = document.getElementById("macosTerminalPopup");
  const bar = document.getElementById("termCountdownBar");
  if (!popup) return;

  // Populate terminal fields
  const verdict = telemetry.verdict || "SAFE";
  document.getElementById("termVerdict").textContent = verdict;
  document.getElementById("termScore").textContent = `${telemetry.final_score ?? "0.00"} (${Math.round((telemetry.final_score ?? 0) * 100)}%)`;
  document.getElementById("termMLProb").textContent = `${((telemetry.ml_classifier_prob ?? 0) * 100).toFixed(2)}%`;
  document.getElementById("termSemSim").textContent = `${(telemetry.semantic_similarity ?? 0).toFixed(3)} cosine`;

  const kws = Array.isArray(telemetry.layer1_keywords) && telemetry.layer1_keywords.length > 0
    ? telemetry.layer1_keywords.slice(0, 3).join(", ")
    : "None";
  document.getElementById("termKeywords").textContent = kws;

  const docFlags = telemetry.layer2_document_flags || "N/A (Direct Text Prompt)";
  document.getElementById("termDocFlags").textContent = docFlags;

  const latency = telemetry.latency_ms ?? 0.8;
  document.getElementById("termLatency").textContent = `${latency.toFixed(2)} ms`;

  // Set Verdict Theme Class
  popup.className = `macos-terminal-popup verdict-${verdict.toLowerCase()}`;
  popup.hidden = false;
  popup.classList.remove("popup-hidden");

  // Lifecycle rules:
  if (bar) {
    bar.classList.remove("active");
  }

  if (verdict === "SAFE") {
    // SAFE: Display for ~1.4s then smoothly fade out
    currentTelemetryTimeout = setTimeout(() => {
      fadeTerminalPopup();
    }, 1400);
  } else if (verdict === "WARN") {
    // WARN: 8-second countdown progress bar then fade out
    if (bar) {
      void bar.offsetWidth; // Force CSS animation restart
      bar.classList.add("active");
    }
    currentTelemetryTimeout = setTimeout(() => {
      fadeTerminalPopup();
    }, 8000);
  } else if (verdict === "MALICIOUS" || verdict === "BLOCK") {
    // MALICIOUS: Stay persistently on screen indefinitely until next prompt or red close click
  }
}

function fadeTerminalPopup() {
  const popup = document.getElementById("macosTerminalPopup");
  if (!popup) return;
  popup.classList.add("popup-hidden");
  setTimeout(() => {
    if (popup.classList.contains("popup-hidden")) {
      popup.hidden = true;
    }
  }, 300);
}

function dismissTerminalPopup() {
  if (currentTelemetryTimeout) {
    clearTimeout(currentTelemetryTimeout);
    currentTelemetryTimeout = null;
  }
  const popup = document.getElementById("macosTerminalPopup");
  if (popup) {
    popup.classList.add("popup-hidden");
    popup.hidden = true;
  }
}

// Task 2: Draggable Terminal Window Logic via Header Bar
function initDraggableTerminal() {
  const popup = document.getElementById("macosTerminalPopup");
  const header = document.getElementById("terminalHeader");
  const closeBtn = document.getElementById("termCloseBtn");
  if (!popup || !header) return;

  let isDragging = false;
  let startX = 0, startY = 0;
  let initialLeft = 0, initialTop = 0;

  header.addEventListener("mousedown", (e) => {
    // Prevent drag if user is clicking the red close button
    if (e.target === closeBtn || closeBtn.contains(e.target)) {
      return;
    }

    isDragging = true;
    header.style.cursor = "grabbing";
    document.body.style.userSelect = "none";

    const rect = popup.getBoundingClientRect();
    initialLeft = rect.left;
    initialTop = rect.top;
    startX = e.clientX;
    startY = e.clientY;

    popup.style.right = "auto";
    popup.style.bottom = "auto";
    popup.style.left = initialLeft + "px";
    popup.style.top = initialTop + "px";
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    let newLeft = initialLeft + dx;
    let newTop = initialTop + dy;

    // Viewport bounds clamp
    const maxLeft = window.innerWidth - popup.offsetWidth - 8;
    const maxTop = window.innerHeight - popup.offsetHeight - 8;
    newLeft = Math.max(8, Math.min(newLeft, maxLeft));
    newTop = Math.max(8, Math.min(newTop, maxTop));

    popup.style.left = newLeft + "px";
    popup.style.top = newTop + "px";
  });

  window.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      header.style.cursor = "grab";
      document.body.style.userSelect = "";
    }
  });

  // Task 2: Red close button dismissal
  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      dismissTerminalPopup();
    });
  }
}

// ═══════════════════════════ 8. COMPOSER & FILE ATTACHMENTS ═══════════════════════════
const ALLOWED_EXTS = [".pdf", ".docx", ".html", ".htm", ".eml", ".txt"];

function validateAndSetFile(file) {
  if (!file) return false;
  const ext = "." + (file.name || "").split(".").pop().toLowerCase();
  if (!ALLOWED_EXTS.includes(ext)) {
    showToast(`Unsupported file type (${ext}). Allowed: .pdf, .docx, .html, .eml, .txt`);
    clearAttachedFile();
    return false;
  }

  attachedFile = file;

  const preview = document.getElementById("attachmentPreview");
  const nameEl = document.getElementById("fileName");
  const typeEl = document.getElementById("fileBadgeType");
  const badge = document.getElementById("attachmentBadge");

  if (nameEl) nameEl.textContent = file.name;
  if (typeEl) typeEl.textContent = ext.replace(".", "").toUpperCase();
  if (badge) {
    badge.className = `attachment-badge badge-${ext.replace(".", "")}`;
  }
  if (preview) preview.hidden = false;
  return true;
}

function clearAttachedFile() {
  attachedFile = null;
  const fileInput = document.getElementById("fileInput");
  const preview = document.getElementById("attachmentPreview");
  const nameEl = document.getElementById("fileName");

  if (fileInput) fileInput.value = "";
  if (nameEl) nameEl.textContent = "";
  if (preview) preview.hidden = true;
}

// ═══════════════════════════ 9. SEND MESSAGE & API FLOW ═══════════════════════════
async function sendMessage(text) {
  const cleanText = (text || "").trim();
  if (!cleanText && !attachedFile) return;

  // On new message submission, immediately clear previous persistent popup
  dismissTerminalPopup();

  const session = getActiveSession();
  const fileToUpload = attachedFile;
  clearAttachedFile();

  const promptBox = document.getElementById("promptBox");
  if (promptBox) {
    promptBox.value = "";
    promptBox.style.height = "";
  }

  // 1. Record user message
  const userMsg = {
    role: "user",
    content: cleanText || (fileToUpload ? `[Attached file: ${fileToUpload.name}]` : ""),
    file_info: fileToUpload ? { name: fileToUpload.name, size: fileToUpload.size } : null,
    timestamp: new Date().toISOString()
  };
  session.messages.push(userMsg);

  // Auto-generate session title
  if (session.messages.length === 1 || session.title === "New Shield Session" || session.title === "Default Shield Session") {
    let titleCandidate = cleanText || (fileToUpload ? fileToUpload.name : "Shield Session");
    if (titleCandidate.length > 28) {
      titleCandidate = titleCandidate.substring(0, 26) + "…";
    }
    session.title = titleCandidate;
    updateActiveHeaderTitle(titleCandidate);
  }

  session.updated_at = new Date().toISOString();
  saveSessions();
  appendMessageToDOM(userMsg, session.messages.length - 1);
  scrollChatToBottom();

  // 2. Prepare API payload
  const modelSelect = document.getElementById("modelSelect");
  const selectedModel = modelSelect ? modelSelect.value : (availableModels[0] || "llama-3.3-70b-versatile");

  const formData = new FormData();
  formData.append("message", cleanText);
  formData.append("model", selectedModel);

  const historyPayload = session.messages.slice(-8, -1).map(m => ({
    role: m.role,
    content: m.content
  }));
  formData.append("history", JSON.stringify(historyPayload));

  if (fileToUpload) {
    formData.append("file", fileToUpload);
  }

  const sendBtn = document.getElementById("sendBtn");
  if (sendBtn) sendBtn.disabled = true;

  const t0 = performance.now();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      body: formData
    });

    const elapsedMs = performance.now() - t0;
    const data = await res.json();

    if (!res.ok && !data.scores) {
      const errText = data.error || `Server error (${res.status})`;
      const errBotMsg = {
        role: "bot",
        content: `Error: ${errText}`,
        blocked: false,
        timestamp: new Date().toISOString()
      };
      session.messages.push(errBotMsg);
      session.updated_at = new Date().toISOString();
      saveSessions();
      appendMessageToDOM(errBotMsg, session.messages.length - 1);
      return;
    }

    const scores = data.scores || {};
    const telemetry = scores.telemetry || {
      verdict: scores.decision === "BLOCK" ? "MALICIOUS" : scores.decision,
      final_score: scores.final_score || 0.0,
      r1: scores.r1 || 0.0,
      r2: scores.r2 || 0.0,
      divergence: scores.divergence || 0.0,
      ml_classifier_prob: scores.r1 || 0.0,
      semantic_similarity: 0.0,
      layer1_keywords: scores.keywords || [],
      layer2_document_flags: fileToUpload ? "Scanned" : "N/A (Direct Text Prompt)",
      latency_ms: elapsedMs
    };
    telemetry.latency_ms = elapsedMs;

    const botMsg = {
      role: "bot",
      content: data.reply || (data.blocked ? data.reason : ""),
      blocked: !!data.blocked,
      reason: data.reason,
      scores: scores,
      telemetry: telemetry,
      timestamp: new Date().toISOString()
    };

    session.messages.push(botMsg);
    session.updated_at = new Date().toISOString();
    saveSessions();
    appendMessageToDOM(botMsg, session.messages.length - 1);
    scrollChatToBottom();

    // Record Security Log Entry
    recordSecurityLog({
      timestamp: new Date().toLocaleTimeString(),
      type: fileToUpload ? "Document" : "Prompt",
      excerpt: cleanText.substring(0, 48) || (fileToUpload ? fileToUpload.name : ""),
      final_score: telemetry.final_score,
      ml_prob: telemetry.ml_classifier_prob,
      l2_flags: telemetry.layer2_document_flags,
      verdict: telemetry.verdict,
      telemetry: telemetry
    });

    // Trigger macOS Terminal Heuristic Popup!
    openTelemetryPopup(telemetry);

    // Sync session to backend
    syncSessionToBackend(session);

  } catch (err) {
    const errorMsg = {
      role: "bot",
      content: `Network error: Could not reach AdaptShield server (${err.message}).`,
      blocked: false,
      timestamp: new Date().toISOString()
    };
    session.messages.push(errorMsg);
    saveSessions();
    appendMessageToDOM(errorMsg, session.messages.length - 1);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

// ═══════════════════════════ 10. SECURITY LOGS RECORDING & FILTERING ═══════════════════════════
function recordSecurityLog(logEntry) {
  securityLogs.unshift(logEntry);
  if (securityLogs.length > 100) securityLogs.pop();
  try {
    localStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify(securityLogs));
  } catch (e) {}

  if (currentView === "logs") {
    renderSecurityLogs();
  }
}

function renderSecurityLogs(filterQuery = "") {
  const tbody = document.getElementById("securityLogsTbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const query = (filterQuery || "").toLowerCase();
  const filtered = securityLogs.filter(log => {
    if (!query) return true;
    return (log.excerpt && log.excerpt.toLowerCase().includes(query)) ||
           (log.verdict && log.verdict.toLowerCase().includes(query)) ||
           (log.type && log.type.toLowerCase().includes(query));
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="text-align: center; padding: 24px;">No evaluation logs matching "${escapeHtml(query)}".</td></tr>`;
    return;
  }

  filtered.forEach(log => {
    const tr = document.createElement("tr");

    const vLower = (log.verdict || "SAFE").toLowerCase();
    const verdictClass = vLower.includes("block") || vLower.includes("malicious") ? "malicious" :
                         (vLower.includes("warn") ? "warn" : "safe");

    tr.innerHTML = `
      <td>${escapeHtml(log.timestamp)}</td>
      <td><span class="file-badge-type">${escapeHtml(log.type)}</span></td>
      <td>${escapeHtml(log.excerpt || "Direct Input")}</td>
      <td><strong>${(log.final_score ?? 0).toFixed(3)}</strong></td>
      <td>${((log.ml_prob ?? 0) * 100).toFixed(1)}%</td>
      <td>${escapeHtml(String(log.l2_flags || "None"))}</td>
      <td><span class="log-verdict ${verdictClass}">${escapeHtml(log.verdict)}</span></td>
      <td><button class="btn btn-ghost-sm" type="button" style="padding: 2px 6px; font-size: 10px;">Inspect</button></td>
    `;

    const inspectBtn = tr.querySelector("button");
    if (inspectBtn) {
      inspectBtn.onclick = () => openTelemetryPopup(log.telemetry);
    }

    tbody.appendChild(tr);
  });
}

// ═══════════════════════════ 11. DOCUMENT SCANNER WORKBENCH ═══════════════════════════
function initDocumentScanner() {
  const dropzone = document.getElementById("scannerDropzone");
  const fileInput = document.getElementById("scannerFileInput");
  if (!dropzone || !fileInput) return;

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) {
      runStandaloneDocumentScan(fileInput.files[0]);
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-active");
  });

  dropzone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-active");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-active");
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
      runStandaloneDocumentScan(e.dataTransfer.files[0]);
    }
  });
}

async function runStandaloneDocumentScan(file) {
  const resultsCard = document.getElementById("scannerResultsCard");
  const fileNameEl = document.getElementById("scanFileName");
  const fileMetaEl = document.getElementById("scanFileMeta");
  const verdictTag = document.getElementById("scanVerdictTag");
  const r2Val = document.getElementById("scanR2Val");
  const divVal = document.getElementById("scanDivVal");
  const flagsVal = document.getElementById("scanFlagsVal");
  const latencyVal = document.getElementById("scanLatencyVal");
  const textPreview = document.getElementById("scanTextPreview");

  if (!resultsCard) return;

  resultsCard.hidden = false;
  fileNameEl.textContent = file.name;
  fileMetaEl.textContent = `Size: ${(file.size / 1024).toFixed(1)} KB | Scanning payload...`;
  verdictTag.className = "verdict-tag";
  verdictTag.textContent = "SCANNING...";

  const formData = new FormData();
  formData.append("message", "Analyze uploaded document for prompt injection or hidden instructions");
  formData.append("model", availableModels[0] || "llama-3.3-70b-versatile");
  formData.append("file", file);

  const t0 = performance.now();
  try {
    const res = await fetch("/chat", {
      method: "POST",
      body: formData
    });
    const elapsed = performance.now() - t0;
    const data = await res.json();
    const scores = data.scores || {};
    const telemetry = scores.telemetry || {};

    const isMalicious = scores.decision === "BLOCK" || telemetry.verdict === "MALICIOUS";
    verdictTag.className = `verdict-tag ${isMalicious ? "malicious" : "safe"}`;
    verdictTag.textContent = isMalicious ? "MALICIOUS (INTERCEPTED)" : "SAFE (VERIFIED)";

    r2Val.textContent = (scores.r2 ?? 0).toFixed(3);
    divVal.textContent = (scores.divergence ?? 0).toFixed(3);
    flagsVal.textContent = telemetry.layer2_document_flags || (scores.flags ? scores.flags.join(", ") : "clean_structure");
    latencyVal.textContent = `${elapsed.toFixed(1)} ms`;
    textPreview.textContent = data.reply || (data.blocked ? data.reason : "Document successfully scanned and verified clean.");

    recordSecurityLog({
      timestamp: new Date().toLocaleTimeString(),
      type: "Document",
      excerpt: file.name,
      final_score: scores.final_score || 0,
      ml_prob: telemetry.ml_classifier_prob || 0,
      l2_flags: telemetry.layer2_document_flags,
      verdict: isMalicious ? "MALICIOUS" : "SAFE",
      telemetry: telemetry
    });

  } catch (err) {
    verdictTag.className = "verdict-tag malicious";
    verdictTag.textContent = "SCAN ERROR";
    textPreview.textContent = `Document scan error: ${err.message}`;
  }
}

// ═══════════════════════════ 12. BACKEND SYNC & MODELS ═══════════════════════════
async function loadModels() {
  const select = document.getElementById("modelSelect");
  const setupLink = document.getElementById("modelSetupLink");
  if (!select) return;

  try {
    const res = await fetch("/models");
    if (!res.ok) throw new Error("Could not fetch models");
    const data = await res.json();

    select.innerHTML = "";

    if (!data.groq_key_set) {
      if (setupLink) setupLink.hidden = false;
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No Groq API Key set";
      opt.disabled = true;
      opt.selected = true;
      select.appendChild(opt);
      return;
    }

    if (setupLink) setupLink.hidden = true;
    availableModels = data.models || [];

    if (availableModels.length === 0) {
      const opt = document.createElement("option");
      opt.value = "llama-3.3-70b-versatile";
      opt.textContent = "llama-3.3-70b-versatile (Default)";
      select.appendChild(opt);
      availableModels = ["llama-3.3-70b-versatile"];
    } else {
      availableModels.forEach((m, idx) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (idx === 0) opt.selected = true;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    if (select) {
      select.innerHTML = '<option value="llama-3.3-70b-versatile" selected>llama-3.3-70b-versatile (Offline Fallback)</option>';
      availableModels = ["llama-3.3-70b-versatile"];
    }
  }
}

async function syncSessionsWithBackend() {
  try {
    const res = await fetch("/api/sessions");
    if (!res.ok) return;
    const data = await res.json();
    const serverSessions = data.sessions || [];

    if (serverSessions.length > 0 && sessions.length <= 1 && sessions[0].messages.length === 0) {
      const fullSessions = await Promise.all(
        serverSessions.slice(0, 15).map(async s => {
          try {
            const sRes = await fetch(`/api/sessions/${s.id}`);
            return sRes.ok ? await sRes.json() : null;
          } catch (e) {
            return null;
          }
        })
      );
      const valid = fullSessions.filter(Boolean);
      if (valid.length > 0) {
        sessions = valid;
        activeSessionId = sessions[0].id;
        saveSessions();
        renderChatMessages();
      }
    }
  } catch (e) {}
}

async function syncSessionToBackend(session) {
  try {
    await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(session)
    });
  } catch (e) {}
}

// ═══════════════════════════ 13. EVENT LISTENERS INITIALIZATION ═══════════════════════════
function setupEventListeners() {
  // Sidebar toggles
  const sidebar = document.getElementById("sidebar");
  const collapseBtn = document.getElementById("sidebarCollapseBtn");
  const expandBtn = document.getElementById("sidebarExpandBtn");
  const newSessionBtn = document.getElementById("newSessionBtn");

  if (collapseBtn && sidebar && expandBtn) {
    collapseBtn.onclick = () => {
      sidebar.classList.add("collapsed");
      expandBtn.hidden = false;
    };
    expandBtn.onclick = () => {
      sidebar.classList.remove("collapsed");
      expandBtn.hidden = true;
    };
  }

  if (newSessionBtn) {
    newSessionBtn.onclick = createNewSession;
  }

  // Clear chat
  const clearChatBtn = document.getElementById("clearChatBtn");
  if (clearChatBtn) {
    clearChatBtn.onclick = () => {
      const session = getActiveSession();
      if (session) {
        session.messages = [];
        session.updated_at = new Date().toISOString();
        saveSessions();
        renderChatMessages();
        showToast("Conversation cleared");
      }
    };
  }

  // Suggestion chips
  document.querySelectorAll(".suggestion-chip").forEach(chip => {
    chip.onclick = () => {
      const prompt = chip.dataset.prompt;
      const promptBox = document.getElementById("promptBox");
      if (promptBox && prompt) {
        promptBox.value = prompt;
        promptBox.style.height = "";
        promptBox.style.height = Math.min(promptBox.scrollHeight, 140) + "px";
        promptBox.focus();
      }
    };
  });

  // Navigation rail clicks
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      switchView(tab.dataset.view);
    });
  });

  // Chat Form & Prompt Box
  const form = document.getElementById("chatForm");
  const promptBox = document.getElementById("promptBox");
  const fileInput = document.getElementById("fileInput");
  const fileRemoveBtn = document.getElementById("fileRemoveBtn");

  if (form) {
    form.onsubmit = (e) => {
      e.preventDefault();
      sendMessage(promptBox ? promptBox.value : "");
    };
  }

  if (promptBox) {
    promptBox.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(promptBox.value);
      }
    });

    promptBox.addEventListener("input", () => {
      promptBox.style.height = "";
      promptBox.style.height = Math.min(promptBox.scrollHeight, 140) + "px";
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        validateAndSetFile(fileInput.files[0]);
      }
    });
  }

  if (fileRemoveBtn) {
    fileRemoveBtn.onclick = clearAttachedFile;
  }

  // Task 1: Non-intrusive Window Dropzone Handling (Never covers the composer during typing!)
  const windowDropOverlay = document.getElementById("windowDropOverlay");
  let windowDragCounter = 0;

  window.addEventListener("dragenter", (e) => {
    e.preventDefault();
    if (e.dataTransfer && Array.from(e.dataTransfer.types).includes("Files")) {
      windowDragCounter++;
      if (windowDropOverlay) windowDropOverlay.classList.add("is-active");
    }
  });

  window.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = "copy";
    }
  });

  window.addEventListener("dragleave", (e) => {
    e.preventDefault();
    windowDragCounter--;
    if (windowDragCounter <= 0) {
      windowDragCounter = 0;
      if (windowDropOverlay) windowDropOverlay.classList.remove("is-active");
    }
  });

  window.addEventListener("drop", (e) => {
    e.preventDefault();
    windowDragCounter = 0;
    if (windowDropOverlay) windowDropOverlay.classList.remove("is-active");

    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      if (currentView === "scanner") {
        runStandaloneDocumentScan(dt.files[0]);
      } else {
        validateAndSetFile(dt.files[0]);
        switchView("workspace");
      }
    }
  });

  // Security logs filter input
  const logsSearch = document.getElementById("logsSearchInput");
  if (logsSearch) {
    logsSearch.addEventListener("input", () => {
      renderSecurityLogs(logsSearch.value);
    });
  }

  // Export logs JSON
  const exportLogsBtn = document.getElementById("exportLogsBtn");
  if (exportLogsBtn) {
    exportLogsBtn.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(securityLogs, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `adaptshield_security_logs_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Security logs exported as JSON");
    });
  }

  // Clear all sessions button in Settings
  const clearAllBtn = document.getElementById("clearAllSessionsBtn");
  if (clearAllBtn) {
    clearAllBtn.addEventListener("click", () => {
      if (!confirm("Are you sure you want to clear all sessions and logs?")) return;
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(LOGS_STORAGE_KEY);
      localStorage.removeItem(ACTIVE_SESSION_KEY);
      loadSessions();
      renderChatMessages();
      renderSecurityLogs();
      showToast("All sessions and logs cleared");
    });
  }

  // Task 2: Initialize Draggable Terminal
  initDraggableTerminal();

  // Initialize Document Scanner
  initDocumentScanner();
}

// ═══════════════════════════ 14. TOAST & UTILITIES ═══════════════════════════
function showToast(message) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.2s";
    setTimeout(() => toast.remove(), 250);
  }, 2400);
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderMarkdown(raw) {
  if (!raw) return "";
  let s = escapeHtml(raw);

  // Code blocks ```...```
  s = s.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`;
  });

  // Inline code `...`
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bold **...**
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // Italic *...*
  s = s.replace(/(^|[^\*])\*([^\*]+)\*([^\*]|$)/g, "$1<em>$2</em>$3");

  // Paragraphs & Linebreaks
  s = s.replace(/\n\n+/g, "</p><p>");
  s = s.replace(/\n/g, "<br>");

  return `<p>${s}</p>`;
}

// ═══════════════════════════ 15. INITIALIZATION ═══════════════════════════
document.addEventListener("DOMContentLoaded", () => {
  loadSessions();
  renderSessionList();
  renderChatMessages();
  loadModels();
  setupEventListeners();
});
