// lims_core/static/lims_core/js/workflow.js

(function () {
  "use strict";

  /* =========================================================
   * Utilities
   * ========================================================= */

  function qs(parent, selector) {
    return parent.querySelector(selector);
  }

  function qsa(parent, selector) {
    return Array.from(parent.querySelectorAll(selector));
  }

  function formatDuration(seconds) {
    if (seconds == null) return "—";

    const abs = Math.abs(seconds);
    const d = Math.floor(abs / 86400);
    const h = Math.floor((abs % 86400) / 3600);
    const m = Math.floor((abs % 3600) / 60);

    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  /* =========================================================
   * Core initializer (ONE CARD)
   * ========================================================= */

  function initWorkflow(card) {
    if (!card || card.dataset.initialized === "1") return;
    card.dataset.initialized = "1";

    const kind = card.dataset.kind;
    const id = card.dataset.id;

    const statusEl = qs(card, "[data-wf-status]");
    const selectEl = qs(card, "[data-wf-next]");
    const commentEl = qs(card, "[data-wf-comment]");
    const applyBtn = qs(card, "[data-wf-apply]");
    const errorEl = qs(card, "[data-wf-error]");
    const timelineEl = qs(card, "[data-wf-timeline]");

    const csrfToken =
      document.querySelector("meta[name='csrf-token']")?.content || "";

    /* ---------------------------------------------------------
     * UI helpers
     * --------------------------------------------------------- */

    function showError(msg) {
      if (!errorEl) return;
      errorEl.textContent = msg;
      errorEl.hidden = false;
    }

    function clearError() {
      if (!errorEl) return;
      errorEl.textContent = "";
      errorEl.hidden = true;
    }

    function setStatus(status) {
      if (!statusEl) return;
      statusEl.textContent = status;
      statusEl.className = `status-pill status-${status.toLowerCase()}`;
    }

    function disableApply(reason) {
      if (!applyBtn) return;
      applyBtn.disabled = true;
      applyBtn.title = reason || "";
    }

    function enableApply() {
      if (!applyBtn) return;
      applyBtn.disabled = false;
      applyBtn.title = "";
    }

    /* ---------------------------------------------------------
     * Load workflow state
     * --------------------------------------------------------- */

    async function loadState() {
      clearError();
      setStatus("Loading");
      selectEl.innerHTML = "";
      disableApply("Loading workflow");

      try {
        const resp = await fetch(`/lims/workflows/${kind}/${id}/`);
        if (!resp.ok) throw new Error("Failed to load workflow");

        const state = await resp.json();
        setStatus(state.status || "UNKNOWN");

        const allowedResp = await fetch(
          `/lims/workflows/${kind}/${id}/allowed/`
        );

        if (!allowedResp.ok) {
          disableApply("Workflow unavailable");
          return;
        }

        const allowed = await allowedResp.json();
        const transitions = allowed.allowed || [];

        if (!transitions.length) {
          disableApply("Terminal state");
          return;
        }

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select next state";
        placeholder.disabled = true;
        placeholder.selected = true;
        selectEl.appendChild(placeholder);

        transitions.forEach(t => {
          const opt = document.createElement("option");
          opt.value = t;
          opt.textContent = t;
          selectEl.appendChild(opt);
        });

        enableApply();
        loadTimeline();

      } catch (err) {
        showError(err.message || "Workflow error");
        disableApply("Error");
      }
    }

    /* ---------------------------------------------------------
     * Timeline
     * --------------------------------------------------------- */

    async function loadTimeline() {
      if (!timelineEl) return;
      timelineEl.innerHTML = "";

      try {
        const resp = await fetch(
          `/lims/workflows/${kind}/${id}/timeline/`
        );
        if (!resp.ok) return;

        const data = await resp.json();

        (data.timeline || []).forEach(t => {
          const row = document.createElement("div");
          row.className = "timeline-row";

          const ts = new Date(t.at);
          const tsStr = isNaN(ts) ? t.at : ts.toLocaleString();

          row.innerHTML = `
            <span class="tl-time">${tsStr}</span>
            <span class="tl-main">
              <strong>${t.from}</strong> → <strong>${t.to}</strong>
            </span>
            <span class="tl-meta">
              ${t.user || "system"}${t.comment ? " · " + t.comment : ""}
            </span>
          `;

          timelineEl.appendChild(row);
        });

      } catch (_) {
        return;
      }
    }

    /* ---------------------------------------------------------
     * Apply transition
     * --------------------------------------------------------- */

    async function applyTransition() {
      clearError();

      const target = selectEl.value;
      const comment = (commentEl?.value || "").trim();

      if (!target) {
        disableApply("No transition selected");
        return;
      }

      applyBtn.disabled = true;
      applyBtn.textContent = "Applying…";

      try {
        const payload = comment
          ? { status: target, comment }
          : { status: target };

        const resp = await fetch(
          `/lims/workflows/${kind}/${id}/`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(payload),
          }
        );

        if (resp.status === 403) {
          showError("Permission denied");
          return;
        }

        if (resp.status === 409) {
          const data = await resp.json();
          showError(data.detail || "Invalid transition");
          return;
        }

        if (!resp.ok) {
          showError("Unexpected error");
          return;
        }

        if (commentEl) commentEl.value = "";
        await loadState();

      } catch (err) {
        showError(err.message || "Transition failed");
      } finally {
        applyBtn.textContent = "Apply";
      }
    }

    /* ---------------------------------------------------------
     * Bind + boot
     * --------------------------------------------------------- */

    if (applyBtn) {
      applyBtn.addEventListener("click", applyTransition);
    }

    loadState();
  }

  /* =========================================================
   * Global mount (THIS WAS MISSING)
   * ========================================================= */

  document.addEventListener("DOMContentLoaded", function () {
    qsa(document, ".workflow-widget").forEach(initWorkflow);
  });

  // Optional explicit export for debugging
  window.initWorkflow = initWorkflow;

})();
