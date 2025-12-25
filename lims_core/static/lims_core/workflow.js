(function () {
    /*
      Workflow UI widget
      ------------------
      - Uses Django SESSION authentication (cookies)
      - Sends CSRF token for PATCH
      - Expects backend GET + PATCH endpoints to exist
    */

    const KIND = window.WORKFLOW_KIND;
    const OBJECT_ID = window.WORKFLOW_OBJECT_ID;

    // Base API path served by Django
    const API_BASE = "/lims/workflows";

    // DOM elements
    const statusEl = document.getElementById("wf-status");
    const selectEl = document.getElementById("wf-next");
    const buttonEl = document.getElementById("wf-apply");
    const timelineEl = document.getElementById("wf-timeline");

    // --------------------------------------------------
    // CSRF helper
    // --------------------------------------------------
    function getCsrfToken() {
        // prefer meta tag (you already render it)
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return meta.content;

        // fallback: cookie named "csrftoken"
        const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    // --------------------------------------------------
    // Generic API helper (SESSION AUTH, CSRF aware)
    // --------------------------------------------------
    async function api(url, options = {}) {
        const method = (options.method || "GET").toUpperCase();
        const headers = {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        };

        // Only send CSRF for unsafe methods
        if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
            const csrf = getCsrfToken();
            if (csrf) headers["X-CSRFToken"] = csrf;
        }

        const resp = await fetch(url, {
            credentials: "same-origin", // critical for Django session auth
            headers,
            ...options,
        });

        // If backend returns HTML (common when redirected to login), show it cleanly
        const contentType = resp.headers.get("content-type") || "";

        if (!resp.ok) {
            if (contentType.includes("application/json")) {
                throw await resp.json();
            }
            const text = await resp.text();
            throw { detail: resp.statusText, status: resp.status, body: text };
        }

        if (contentType.includes("application/json")) {
            return resp.json();
        }

        // Unexpected success but not JSON
        return { detail: "OK", status: resp.status };
    }

    // --------------------------------------------------
    // Load current workflow state
    // --------------------------------------------------
    async function loadState() {
        const data = await api(`${API_BASE}/${KIND}/${OBJECT_ID}/`);
        statusEl.textContent = data.status;
        statusEl.className = `status-pill ${data.status}`;
    }

    // --------------------------------------------------
    // Load allowed transitions
    // --------------------------------------------------
    async function loadAllowed() {
        const data = await api(`${API_BASE}/${KIND}/${OBJECT_ID}/allowed/`);
        selectEl.innerHTML = "";

        if (!data.allowed || data.allowed.length === 0) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "No transitions available";
            selectEl.appendChild(opt);
            buttonEl.disabled = true;
            return;
        }

        data.allowed.forEach((state) => {
            const opt = document.createElement("option");
            opt.value = state;
            opt.textContent = state;
            selectEl.appendChild(opt);
        });

        buttonEl.disabled = false;
    }

    // --------------------------------------------------
    // Load workflow timeline
    // --------------------------------------------------
    async function loadTimeline() {
        const data = await api(`${API_BASE}/${KIND}/${OBJECT_ID}/timeline/`);
        timelineEl.innerHTML = "";

        (data.timeline || []).forEach((row) => {
            const div = document.createElement("div");
            div.className = "timeline-entry";
            div.textContent = `${row.at} • ${row.user || "system"}: ${row.from} → ${row.to}`;
            timelineEl.appendChild(div);
        });
    }

    // --------------------------------------------------
    // Apply transition
    // --------------------------------------------------
    buttonEl.addEventListener("click", async () => {
        const next = selectEl.value;
        if (!next) return;

        buttonEl.disabled = true;

        try {
            await api(`${API_BASE}/${KIND}/${OBJECT_ID}/`, {
                method: "PATCH",
                body: JSON.stringify({ status: next }),
            });
            await refresh();
        } catch (err) {
            console.error("Workflow PATCH error:", err);

            // show something visible without breaking the UI
            alert(err.detail || "Transition failed (see console).");
        } finally {
            buttonEl.disabled = false;
        }
    });

    // --------------------------------------------------
    // Refresh widget
    // --------------------------------------------------
    async function refresh() {
        try {
            await loadState();
            await loadAllowed();
            await loadTimeline();
        } catch (err) {
            console.error("Workflow widget error:", err);

            // If we got redirected to login or got HTML, make it obvious
            if (err && err.status === 403) {
                alert("Forbidden: you are authenticated but not allowed for this action.");
            } else if (err && err.status === 302) {
                alert("Not logged in (session missing).");
            }
        }
    }

    // Initial load
    refresh();
})();
