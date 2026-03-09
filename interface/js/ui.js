// --- DOM References ---
const chatMessages = document.getElementById("chat-messages");
const chatContainer = document.getElementById("chat-container");

// --- SQL Syntax Highlighting ---
function highlightSQL(sql) {
  const keywords =
    /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|LIKE|BETWEEN|ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT|OFFSET|AS|DISTINCT|CASE|WHEN|THEN|ELSE|END|NULL|IS|UNION|ALL|EXISTS|DESC|ASC|CAST|COALESCE)\b/gi;
  const functions =
    /\b(COUNT|SUM|AVG|MIN|MAX|ROUND|LENGTH|SUBSTR|TRIM|UPPER|LOWER|DATE|STRFTIME|IFNULL|NULLIF|TYPEOF|REPLACE|INSTR|PRINTF|GROUP_CONCAT)\b/gi;
  const strings = /('[^']*')/g;
  const numbers = /\b(\d+\.?\d*)\b/g;

  let result = sql
    .replace(strings, '<span class="sql-string">$1</span>')
    .replace(keywords, '<span class="sql-keyword">$1</span>')
    .replace(functions, '<span class="sql-function">$1</span>');

  // Only highlight numbers not inside a span
  result = result.replace(
    /(?<!<[^>]*)(?<!")\b(\d+\.?\d*)\b(?![^<]*>)/g,
    '<span class="sql-number">$1</span>'
  );

  return result;
}

// --- Thinking Block ---

function renderThinking(thinking) {
  if (!thinking) return "";
  return `
    <div class="thinking-block">
      <button class="thinking-toggle" onclick="toggleThinking(this)">
        <span class="arrow">&#9654;</span> Réflexion
      </button>
      <div class="thinking-content">${escapeHtml(thinking)}</div>
    </div>
  `;
}

function toggleThinking(btn) {
  btn.classList.toggle("open");
  const content = btn.nextElementSibling;
  content.classList.toggle("visible");
}

// --- Message Rendering ---

function addUserMessage(text) {
  removeWelcome();
  const div = document.createElement("div");
  div.className = "message message-user";
  div.innerHTML = `
    <div class="message-avatar">U</div>
    <div class="message-content">
      <p>${escapeHtml(text)}</p>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function addBotMessage(text, thinking) {
  const div = createBotMessage();
  div.querySelector(".message-content").innerHTML = renderThinking(thinking) + formatMessage(text);
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function addBotMessageWithSQL(text, sql, thinking) {
  const div = createBotMessage();
  const content = div.querySelector(".message-content");

  content.innerHTML = `
    ${renderThinking(thinking)}
    ${formatMessage(text)}
    <div class="sql-block">
      <div class="sql-header">
        <span>SQL</span>
        <button class="btn-copy" onclick="copySQL(this, '${escapeForAttr(sql)}')">Copier</button>
      </div>
      <div class="sql-code">${highlightSQL(escapeHtml(sql))}</div>
    </div>
    <div class="action-buttons">
      <button class="btn btn-primary" onclick="window.app.confirmExecution()">Exécuter</button>
      <button class="btn btn-secondary" onclick="window.app.modifyQuery()">Modifier</button>
      <button class="btn btn-ghost" onclick="window.app.cancelQuery()">Annuler</button>
    </div>
  `;

  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function detectChartType(columns, rows) {
  if (!rows || rows.length < 2 || rows.length > 50) return null;
  if (columns.length < 2) return null;

  // Check if second column is numeric
  const isNumeric = rows.every((r) => {
    const v = r[1];
    return v !== null && v !== "" && !isNaN(Number(v));
  });
  if (!isNumeric) return null;

  if (columns.length === 2) {
    const isDate = /dat|date|time|month|year|mois|annee/i.test(columns[0]);
    return isDate ? "line" : "bar";
  }

  return null;
}

let chartCounter = 0;

function renderChart(container, chartType, columns, rows) {
  const canvas = document.createElement("canvas");
  canvas.style.maxHeight = "300px";
  container.appendChild(canvas);

  const labels = rows.map((r) => String(r[0] ?? ""));
  const data = rows.map((r) => Number(r[1]));

  // Read theme-aware colors from CSS variables
  const style = getComputedStyle(document.documentElement);
  const chartText = style.getPropertyValue("--chart-text").trim() || "#4a4a52";
  const chartGrid = style.getPropertyValue("--chart-grid").trim() || "rgba(0,0,0,0.06)";

  new Chart(canvas, {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: columns[1],
        data: data,
        backgroundColor: chartType === "bar"
          ? "rgba(92, 26, 126, 0.6)"
          : "rgba(92, 26, 126, 0.15)",
        borderColor: "#5C1A7E",
        borderWidth: 2,
        tension: 0.3,
        fill: chartType === "line",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          ticks: { color: chartText, maxRotation: 45, font: { size: 11 } },
          grid: { color: chartGrid },
        },
        y: {
          ticks: { color: chartText, font: { size: 11 } },
          grid: { color: chartGrid },
        },
      },
    },
  });
}

function addBotMessageWithResults(text, results) {
  const div = createBotMessage();
  const content = div.querySelector(".message-content");

  let tableHtml = "";
  let chartBtnHtml = "";
  if (results && results.columns && results.rows && results.rows.length > 0) {
    const truncatedNote = results.truncated
      ? `<span style="color: var(--warning); margin-left: 8px">(${results.total_count} total, ${results.rows.length} affichés)</span>`
      : "";

    const chartType = detectChartType(results.columns, results.rows);
    const chartId = `chart-${++chartCounter}`;

    tableHtml = `
      <div class="results-container">
        <div class="results-header">
          <span>${results.total_count} résultat(s) ${truncatedNote}</span>
        </div>
        <div class="results-scroll">
          <table class="results-table">
            <thead>
              <tr>${results.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr>
            </thead>
            <tbody>
              ${results.rows
                .map(
                  (row) =>
                    `<tr>${row.map((cell) => `<td title="${escapeForAttr(String(cell ?? ""))}">${escapeHtml(String(cell ?? ""))}</td>`).join("")}</tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    if (chartType) {
      chartBtnHtml = `
        <div class="chart-container" id="${chartId}" style="display:none; padding: 16px 0; height: 320px;"></div>
        <button class="btn btn-secondary btn-chart-toggle" data-chart-id="${chartId}" data-chart-type="${chartType}"
          data-columns='${JSON.stringify(results.columns)}' data-rows='${JSON.stringify(results.rows)}'>
          Afficher le graphique
        </button>
      `;
    }
  }

  content.innerHTML = `
    ${formatMessage(text)}
    ${tableHtml}
    ${chartBtnHtml}
    <div class="action-buttons">
      <button class="btn btn-secondary" onclick="window.app.exportResults('csv')">Export CSV</button>
      <button class="btn btn-secondary" onclick="window.app.exportResults('xlsx')">Export Excel</button>
      <button class="btn btn-secondary" onclick="window.app.exportResults('pdf')">Export PDF</button>
    </div>
  `;

  // Bind chart toggle
  const chartBtn = content.querySelector(".btn-chart-toggle");
  if (chartBtn) {
    chartBtn.addEventListener("click", function () {
      const container = document.getElementById(this.dataset.chartId);
      if (container.style.display === "none") {
        container.style.display = "block";
        if (!container.querySelector("canvas")) {
          renderChart(
            container,
            this.dataset.chartType,
            JSON.parse(this.dataset.columns),
            JSON.parse(this.dataset.rows)
          );
        }
        this.textContent = "Masquer le graphique";
      } else {
        container.style.display = "none";
        this.textContent = "Afficher le graphique";
      }
    });
  }

  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function addBotCorrections(corrections) {
  const div = createBotMessage();
  const content = div.querySelector(".message-content");

  const items = corrections
    .map(
      (c) =>
        `<li style="margin-bottom: 6px;">
          <span style="color: var(--error);">Erreur :</span> ${escapeHtml(c.error)}<br>
          <span style="color: var(--text-muted);">SQL corrigé automatiquement</span>
        </li>`
    )
    .join("");

  content.innerHTML = `
    <div class="thinking-block">
      <button class="thinking-toggle" onclick="toggleThinking(this)">
        <span class="arrow">&#9654;</span> Correction automatique (${corrections.length})
      </button>
      <div class="thinking-content">
        <ul style="padding-left: 16px; margin: 4px 0;">${items}</ul>
      </div>
    </div>
  `;

  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function addBotWarningMessage(warnings, sql) {
  const div = createBotMessage();
  const content = div.querySelector(".message-content");

  const warningList = warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("");

  content.innerHTML = `
    <div style="color: var(--warning); margin-bottom: 8px;">
      <strong>⚠ Attention :</strong>
      <ul style="margin: 4px 0; padding-left: 20px;">${warningList}</ul>
    </div>
    <div class="action-buttons">
      <button class="btn btn-primary" onclick="window.app.forceExecution('${escapeForAttr(sql)}')">Exécuter quand même</button>
      <button class="btn btn-ghost" onclick="window.app.cancelQuery()">Annuler</button>
    </div>
  `;

  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function addBotErrorMessage(text) {
  const div = createBotMessage();
  div.querySelector(".message-content").innerHTML = `
    <p style="color: var(--error)">${formatMessage(text)}</p>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function showTypingIndicator() {
  removeTypingIndicator();
  const div = createBotMessage();
  div.id = "typing-indicator";
  div.querySelector(".message-content").innerHTML = `
    <div class="typing-indicator">
      <div class="dot"></div>
      <div class="dot"></div>
      <div class="dot"></div>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function hideTypingIndicator() {
  removeTypingIndicator();
}

// --- Streaming ---

function createStreamingMessage() {
  removeWelcome();
  const div = createBotMessage();
  div.classList.add("streaming");
  div.querySelector(".message-content").innerHTML = `
    <div class="streaming-thinking" style="display:none;"></div>
    <div class="streaming-content"></div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function updateStreamingContent(div, thinking, content) {
  const thinkEl = div.querySelector(".streaming-thinking");
  const contentEl = div.querySelector(".streaming-content");

  if (thinking) {
    thinkEl.style.display = "block";
    thinkEl.innerHTML = `
      <div class="thinking-block">
        <button class="thinking-toggle open" onclick="toggleThinking(this)">
          <span class="arrow">&#9654;</span> Réflexion
        </button>
        <div class="thinking-content visible">${escapeHtml(thinking)}</div>
      </div>
    `;
  }

  if (content) {
    contentEl.innerHTML = formatMessage(content);
  }

  scrollToBottom();
}

function finalizeStreamingMessage(div, parsed) {
  div.classList.remove("streaming");
  const content = div.querySelector(".message-content");

  const thinking = parsed.thinking || "";

  switch (parsed.type) {
    case "confirm_sql":
      content.innerHTML = `
        ${renderThinking(thinking)}
        ${formatMessage(parsed.message)}
        <div class="sql-block">
          <div class="sql-header">
            <span>SQL</span>
            <button class="btn-copy" onclick="copySQL(this, '${escapeForAttr(parsed.sql || "")}')">Copier</button>
          </div>
          <div class="sql-code">${highlightSQL(escapeHtml(parsed.sql || ""))}</div>
        </div>
        <div class="action-buttons">
          <button class="btn btn-primary" onclick="window.app.confirmExecution()">Exécuter</button>
          <button class="btn btn-secondary" onclick="window.app.modifyQuery()">Modifier</button>
          <button class="btn btn-ghost" onclick="window.app.cancelQuery()">Annuler</button>
        </div>
      `;
      break;
    case "error":
      content.innerHTML = `<p style="color: var(--error)">${formatMessage(parsed.message)}</p>`;
      break;
    default:
      content.innerHTML = renderThinking(thinking) + formatMessage(parsed.message);
  }

  scrollToBottom();
}

function finalizeStreamingAsError(div, message) {
  div.classList.remove("streaming");
  div.querySelector(".message-content").innerHTML = `
    <p style="color: var(--error)">${formatMessage(message)}</p>
  `;
  scrollToBottom();
}

// --- Helpers ---

function createBotMessage() {
  const div = document.createElement("div");
  div.className = "message message-bot";
  div.innerHTML = `
    <div class="message-avatar">P</div>
    <div class="message-content"></div>
  `;
  return div;
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function removeWelcome() {
  const el = document.getElementById("welcome");
  if (el) el.remove();
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function escapeForAttr(text) {
  return text.replace(/'/g, "\\'").replace(/"/g, "&quot;").replace(/\n/g, "\\n");
}

function formatMessage(text) {
  // Simple markdown-like formatting
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n- /g, "\n<br>- ")
    .replace(/\n/g, "<br>");
}

function copySQL(btn, sql) {
  const decoded = sql.replace(/\\n/g, "\n").replace(/\\'/g, "'").replace(/&quot;/g, '"');
  navigator.clipboard.writeText(decoded).then(() => {
    btn.textContent = "Copié !";
    setTimeout(() => (btn.textContent = "Copier"), 1500);
  });
}

function disableActionButtons() {
  chatMessages.querySelectorAll(".action-buttons .btn").forEach((btn) => {
    btn.disabled = true;
    btn.style.opacity = "0.5";
    btn.style.pointerEvents = "none";
  });
}

// Export for use in app.js
window.ui = {
  addUserMessage,
  addBotMessage,
  addBotMessageWithSQL,
  addBotMessageWithResults,
  addBotCorrections,
  addBotWarningMessage,
  addBotErrorMessage,
  showTypingIndicator,
  hideTypingIndicator,
  disableActionButtons,
  createStreamingMessage,
  updateStreamingContent,
  finalizeStreamingMessage,
  finalizeStreamingAsError,
};
