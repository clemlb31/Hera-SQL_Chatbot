// --- Theme Management ---
function initTheme() {
  const saved = localStorage.getItem("prisme-theme");
  if (saved) {
    document.documentElement.setAttribute("data-theme", saved);
  }
  // Otherwise, let prefers-color-scheme handle it (no data-theme attribute)
}

function toggleTheme() {
  const root = document.documentElement;
  const current = root.getAttribute("data-theme");

  if (current === "dark") {
    root.setAttribute("data-theme", "light");
    localStorage.setItem("prisme-theme", "light");
  } else if (current === "light") {
    root.setAttribute("data-theme", "dark");
    localStorage.setItem("prisme-theme", "dark");
  } else {
    // No explicit theme — detect current system preference and switch to opposite
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const next = isDark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("prisme-theme", next);
  }
}

initTheme();

// --- Application State ---
const state = {
  conversationId: null,
  pendingSql: null,
  isLoading: false,
};

// --- DOM References ---
const textarea = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const modelSelect = document.getElementById("model-select");

// --- Input handling ---
textarea.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

textarea.addEventListener("input", () => {
  // Auto-resize textarea
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px";
  sendBtn.disabled = !textarea.value.trim();
});

sendBtn.addEventListener("click", handleSend);

// --- Suggestion click handler ---
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("suggestion")) {
    const text = e.target.textContent.trim();
    textarea.value = text;
    textarea.dispatchEvent(new Event("input"));
    handleSend();
  }
});

// --- Core functions ---

async function handleSend() {
  const message = textarea.value.trim();
  if (!message || state.isLoading) return;

  textarea.value = "";
  textarea.style.height = "auto";
  sendBtn.disabled = true;

  await sendMessage(message);
}

async function sendMessage(userMessage) {
  window.ui.addUserMessage(userMessage);
  state.isLoading = true;

  // Create streaming message container
  const streamDiv = window.ui.createStreamingMessage();

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMessage,
        conversation_id: state.conversationId,
        model: modelSelect.value,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let accThinking = "";
    let accContent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));

          if (event.type === "init") {
            state.conversationId = event.conversation_id;
          } else if (event.type === "token") {
            if (event.thinking) accThinking += event.thinking;
            if (event.content) accContent += event.content;
            window.ui.updateStreamingContent(streamDiv, accThinking, accContent);
          } else if (event.type === "done") {
            const parsed = event.parsed;
            state.conversationId = event.conversation_id;
            window.ui.finalizeStreamingMessage(streamDiv, parsed);
            if (parsed.type === "confirm_sql" && parsed.sql) {
              state.pendingSql = parsed.sql;
            }
          } else if (event.type === "error") {
            window.ui.finalizeStreamingAsError(streamDiv, event.message);
          }
        } catch (_) {
          // Ignore malformed SSE lines
        }
      }
    }
  } catch (error) {
    window.ui.finalizeStreamingAsError(
      streamDiv,
      `Erreur de connexion au serveur : ${error.message}`
    );
  } finally {
    state.isLoading = false;
  }
}

async function confirmExecution() {
  if (!state.pendingSql || state.isLoading) return;

  window.ui.disableActionButtons();
  window.ui.showTypingIndicator();
  state.isLoading = true;

  try {
    const response = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.conversationId,
        sql: state.pendingSql,
        model: modelSelect.value,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();

    window.ui.hideTypingIndicator();

    if (data.corrections && data.corrections.length > 0) {
      window.ui.addBotCorrections(data.corrections);
    }
    if (data.type === "results") {
      window.ui.addBotMessageWithResults(data.message, data.results);
    } else if (data.type === "warning") {
      window.ui.addBotWarningMessage(data.warnings, data.sql);
    } else if (data.type === "error") {
      window.ui.addBotErrorMessage(data.message);
    }
  } catch (error) {
    window.ui.hideTypingIndicator();
    window.ui.addBotErrorMessage(
      `Erreur lors de l'exécution : ${error.message}`
    );
  } finally {
    state.isLoading = false;
  }
}

function modifyQuery() {
  window.ui.disableActionButtons();
  window.ui.addBotMessage(
    "Que souhaitez-vous modifier dans cette requête ?"
  );
  textarea.focus();
}

function cancelQuery() {
  window.ui.disableActionButtons();
  state.pendingSql = null;
  window.ui.addBotMessage("Requête annulée. Posez-moi une autre question !");
  textarea.focus();
}

async function forceExecution(sql) {
  window.ui.disableActionButtons();
  window.ui.showTypingIndicator();
  state.isLoading = true;

  try {
    const response = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.conversationId,
        sql: sql,
        model: modelSelect.value,
        force: true,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    window.ui.hideTypingIndicator();

    if (data.type === "results") {
      window.ui.addBotMessageWithResults(data.message, data.results);
    } else {
      window.ui.addBotErrorMessage(data.message);
    }
  } catch (error) {
    window.ui.hideTypingIndicator();
    window.ui.addBotErrorMessage(`Erreur lors de l'exécution : ${error.message}`);
  } finally {
    state.isLoading = false;
  }
}

function exportResults(format) {
  if (!state.pendingSql) return;
  let url = `/api/export?sql=${encodeURIComponent(state.pendingSql)}&format=${format}`;
  if (format === "pdf" && state.conversationId) {
    url += `&conversation_id=${encodeURIComponent(state.conversationId)}`;
  }
  window.open(url, "_blank");
}

function newConversation() {
  state.conversationId = null;
  state.pendingSql = null;
  state.isLoading = false;

  const chatMessages = document.getElementById("chat-messages");
  chatMessages.innerHTML = `
    <div id="welcome" class="welcome">
      <h2>Bienvenue sur <span>Prisme</span></h2>
      <p>Interrogez vos données d'anomalies en langage naturel.</p>
      <div class="welcome-suggestions">
        <div class="suggestion">Combien d'anomalies par type d'objet métier ?</div>
        <div class="suggestion">Quelles sont les anomalies détectées en 2024 ?</div>
        <div class="suggestion">Top 10 des typologies les plus fréquentes</div>
        <div class="suggestion">Anomalies avec hotfix actif</div>
      </div>
    </div>
  `;
}

// --- Auto-completion ---

let suggestionsTimeout = null;
let selectedSuggestionIdx = -1;

textarea.addEventListener("input", () => {
  clearTimeout(suggestionsTimeout);
  const words = textarea.value.split(/\s+/);
  const lastWord = words[words.length - 1];

  if (lastWord.length < 2) {
    hideSuggestions();
    return;
  }

  suggestionsTimeout = setTimeout(() => fetchSuggestions(lastWord), 300);
});

textarea.addEventListener("keydown", (e) => {
  const dropdown = document.getElementById("suggestions-dropdown");
  if (!dropdown || dropdown.style.display === "none") return;

  const items = dropdown.querySelectorAll(".suggestion-item");
  if (!items.length) return;

  if (e.key === "ArrowDown") {
    e.preventDefault();
    selectedSuggestionIdx = Math.min(selectedSuggestionIdx + 1, items.length - 1);
    highlightSuggestion(items);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    selectedSuggestionIdx = Math.max(selectedSuggestionIdx - 1, 0);
    highlightSuggestion(items);
  } else if ((e.key === "Enter" || e.key === "Tab") && selectedSuggestionIdx >= 0) {
    e.preventDefault();
    applySuggestion(items[selectedSuggestionIdx].dataset.text);
  } else if (e.key === "Escape") {
    hideSuggestions();
  }
});

async function fetchSuggestions(query) {
  try {
    const response = await fetch(`/api/suggestions?q=${encodeURIComponent(query)}`);
    if (!response.ok) return;
    const suggestions = await response.json();
    if (suggestions.length === 0) {
      hideSuggestions();
      return;
    }
    showSuggestions(suggestions);
  } catch (_) {
    hideSuggestions();
  }
}

function showSuggestions(suggestions) {
  let dropdown = document.getElementById("suggestions-dropdown");
  if (!dropdown) {
    dropdown = document.createElement("div");
    dropdown.id = "suggestions-dropdown";
    dropdown.className = "suggestions-dropdown";
    document.querySelector(".input-wrapper").appendChild(dropdown);
  }

  selectedSuggestionIdx = -1;
  dropdown.style.display = "block";
  dropdown.innerHTML = suggestions
    .map(
      (s) =>
        `<div class="suggestion-item" data-text="${s.text}" onclick="window.app.applySuggestion('${s.text.replace(/'/g, "\\'")}')">
          <span class="suggestion-text">${s.text}</span>
          <span class="suggestion-category">${s.category}</span>
        </div>`
    )
    .join("");
}

function hideSuggestions() {
  const dropdown = document.getElementById("suggestions-dropdown");
  if (dropdown) dropdown.style.display = "none";
  selectedSuggestionIdx = -1;
}

function highlightSuggestion(items) {
  items.forEach((item, i) => {
    item.classList.toggle("active", i === selectedSuggestionIdx);
  });
}

function applySuggestion(text) {
  const words = textarea.value.split(/\s+/);
  words[words.length - 1] = text;
  textarea.value = words.join(" ") + " ";
  textarea.dispatchEvent(new Event("input"));
  hideSuggestions();
  textarea.focus();
}

// --- Sidebar / Conversation History ---

function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
  document.getElementById("sidebar-backdrop").classList.toggle("open");
  loadConversationList();
}

async function loadConversationList() {
  try {
    const response = await fetch("/api/conversations");
    if (!response.ok) return;
    const conversations = await response.json();
    const list = document.getElementById("conversation-list");

    if (conversations.length === 0) {
      list.innerHTML = '<p class="sidebar-empty">Aucune conversation</p>';
      return;
    }

    list.innerHTML = conversations.map((c) => {
      const title = c.first_message
        ? c.first_message.substring(0, 60) + (c.first_message.length > 60 ? "..." : "")
        : "Conversation vide";
      const date = new Date(c.updated_at).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
      const isActive = c.id === state.conversationId ? " active" : "";
      return `
        <div class="conversation-item${isActive}" onclick="window.app.loadConversation('${c.id}')">
          <div class="conversation-title">${title}</div>
          <div class="conversation-meta">
            <span>${date}</span>
            <button class="btn-delete-conv" onclick="event.stopPropagation(); window.app.deleteConversation('${c.id}')" title="Supprimer">&times;</button>
          </div>
        </div>
      `;
    }).join("");
  } catch (_) {}
}

async function loadConversation(convId) {
  try {
    const response = await fetch(`/api/conversations/${convId}`);
    if (!response.ok) return;
    const conv = await response.json();

    state.conversationId = convId;
    state.pendingSql = conv.pending_sql;

    const chatMessages = document.getElementById("chat-messages");
    chatMessages.innerHTML = "";

    for (const msg of conv.history) {
      if (msg.role === "user") {
        window.ui.addUserMessage(msg.content);
      } else {
        window.ui.addBotMessage(msg.content);
      }
    }

    // Close sidebar on mobile
    if (window.innerWidth < 768) {
      toggleSidebar();
    }

    loadConversationList();
  } catch (_) {}
}

async function deleteConversation(convId) {
  try {
    await fetch(`/api/conversations/${convId}`, { method: "DELETE" });
    if (convId === state.conversationId) {
      newConversation();
    }
    loadConversationList();
  } catch (_) {}
}

// --- Dashboard ---

let dashboardLoaded = false;

function toggleDashboard() {
  const panel = document.getElementById("dashboard-panel");
  if (panel.style.display === "none") {
    panel.style.display = "block";
    if (!dashboardLoaded) loadDashboard();
  } else {
    panel.style.display = "none";
  }
}

async function loadDashboard() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) return;
    const data = await response.json();
    dashboardLoaded = true;
    renderDashboard(data);
  } catch (_) {}
}

function renderDashboard(data) {
  const container = document.getElementById("dashboard-kpis");

  function fmt(n) {
    return n.toLocaleString("fr-FR");
  }

  function renderBars(items) {
    if (!items.length) return "";
    const max = Math.max(...items.map((i) => i.count));
    return items
      .map(
        (item) => `
        <div class="dashboard-bar">
          <span class="dashboard-bar-label" title="${item.label}">${item.label}</span>
          <div class="dashboard-bar-track">
            <div class="dashboard-bar-fill" style="width: ${(item.count / max) * 100}%"></div>
          </div>
          <span class="dashboard-bar-count">${fmt(item.count)}</span>
        </div>`
      )
      .join("");
  }

  container.innerHTML = `
    <div class="kpi-card">
      <div class="kpi-value">${fmt(data.total_anomalies)}</div>
      <div class="kpi-label">Anomalies</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">${fmt(data.hotfix_count)}</div>
      <div class="kpi-label">Hotfix actifs</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">${data.typology_count}</div>
      <div class="kpi-label">Typologies</div>
    </div>
    <div class="dashboard-grid" style="grid-column: 1 / -1;">
      <div class="dashboard-section">
        <h4>Top objets metier</h4>
        <div class="dashboard-bars">${renderBars(data.top_business_objects)}</div>
      </div>
      <div class="dashboard-section">
        <h4>Top typologies</h4>
        <div class="dashboard-bars">${renderBars(data.top_typologies)}</div>
      </div>
    </div>
  `;
}

// Expose functions for UI buttons
window.app = {
  confirmExecution,
  forceExecution,
  modifyQuery,
  cancelQuery,
  exportResults,
  newConversation,
  applySuggestion,
  toggleSidebar,
  loadConversation,
  deleteConversation,
  toggleDashboard,
  toggleTheme,
};
