/* lims_core/static/lims_core/js/workflow.js
   Binds to lims_core/templates/lims_core/workflow_widget.html

   Expects markup:
     .workflow-widget[data-kind][data-id]
       [data-wf-status]
       [data-wf-next]
       [data-wf-comment]
       [data-wf-apply]
       [data-wf-error]
       [data-wf-timeline]
       optional SLA:
         [data-wf-sla-pill], [data-wf-sla-meta], [data-wf-sla-age], [data-wf-sla-remaining]
*/

(function () {
  function getCookie(name) {
    const v = `; ${document.cookie}`;
    const parts = v.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function qs(root, sel) {
    return root.querySelector(sel);
  }

  function qsa(sel) {
    return Array.from(document.querySelectorAll(sel));
  }

  function escapeHtml(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function buildUrls(kind, objectId) {
    const base = `/lims/workflows/${encodeURIComponent(kind)}/${encodeURIComponent(objectId)}`;
    return {
      allowed: `${base}/allowed/`,
      timeline: `${base}/timeline/`,
      transition: `${base}/transition/`,
    };
  }

  function setError(widget, msg) {
    const box = qs(widget, "[data-wf-error]");
    if (!box) return;
    const m = String(msg || "").trim();
    if (!m) {
      box.hidden = true;
      box.textContent = "";
      return;
    }
    box.hidden = false;
    box.textContent = m;
  }

  function setStatus(widget, status, loading) {
    const pill = qs(widget, "[data-wf-status]");
    if (!pill) return;

    const s = String(status || "UNKNOWN");
    pill.textContent = loading ? "Loading…" : s;

    pill.classList.remove("status-loading");
    if (loading) pill.classList.add("status-loading");
  }

  function setSla(widget, sla) {
    const pill = qs(widget, "[data-wf-sla-pill]");
    const meta = qs(widget, "[data-wf-sla-meta]");
    const age = qs(widget, "[data-wf-sla-age]");
    const remaining = qs(widget, "[data-wf-sla-remaining]");

    if (!pill || !meta || !age || !remaining) return;

    if (!sla || !sla.status) {
      pill.hidden = true;
      meta.hidden = true;
      return;
    }

    pill.hidden = false;
    meta.hidden = false;

    pill.textContent = String(sla.status || "").toUpperCase();

    // best-effort presentation
    const ageSec = Number(sla.age_seconds || 0);
    const remSec = (sla.remaining_seconds === null || sla.remaining_seconds === undefined)
      ? null
      : Number(sla.remaining_seconds);

    function fmt(sec) {
      if (!isFinite(sec)) return "";
      const s = Math.max(0, Math.floor(sec));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    }

    age.textContent = ageSec ? `Age: ${fmt(ageSec)}` : "Age: -";
    remaining.textContent = (remSec === null) ? "Remaining: -" : `Remaining: ${fmt(remSec)}`;
  }

  function fillNextSelect(widget, allowed) {
    const sel = qs(widget, "[data-wf-next]");
    const btn = qs(widget, "[data-wf-apply]");
    if (!sel) return;

    sel.innerHTML = "";

    if (!allowed || !allowed.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No allowed transitions";
      sel.appendChild(opt);
      if (btn) btn.disabled = true;
      return;
    }

    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "Select next status…";
    sel.appendChild(opt0);

    allowed.forEach((st) => {
      const opt = document.createElement("option");
      opt.value = String(st);
      opt.textContent = String(st);
      sel.appendChild(opt);
    });

    if (btn) btn.disabled = true;
  }

  function renderTimeline(widget, data) {
    const box = qs(widget, "[data-wf-timeline]");
    if (!box) return;

    // Support a few shapes:
    // A) { events: [...] }
    // B) { timeline: [...] }
    // C) { history: [...] }
    // D) direct list [...]
    let events = [];
    if (Array.isArray(data)) events = data;
    else if (data && Array.isArray(data.events)) events = data.events;
    else if (data && Array.isArray(data.timeline)) events = data.timeline;
    else if (data && Array.isArray(data.history)) events = data.history;

    if (!events.length) {
      box.innerHTML = `<div class="muted">No workflow events yet.</div>`;
      return;
    }

    const html = events.map((e) => {
      const at = e.created_at || e.timestamp || e.at || "";
      const from = e.from_status || e.from || "";
      const to = e.to_status || e.to || "";
      const who =
        (e.performed_by && (e.performed_by.username || e.performed_by)) ||
        e.user ||
        e.actor ||
        "system";
      const role = e.role || "";
      const comment = e.comment || "";

      return `
        <div class="workflow-history-row">
          <div style="display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;">
            <div><strong>${escapeHtml(from)} → ${escapeHtml(to)}</strong></div>
            <div class="muted">${escapeHtml(at)}</div>
          </div>
          <div class="muted" style="margin-top:4px;">
            By: ${escapeHtml(who)}${role ? ` · Role: ${escapeHtml(role)}` : ""}
          </div>
          ${comment ? `<div style="margin-top:6px;">${escapeHtml(comment)}</div>` : ""}
        </div>
      `;
    }).join("");

    box.innerHTML = html;
  }

  async function fetchJson(url, opts) {
    const res = await fetch(url, opts || {});
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (!ct.includes("application/json")) {
      const t = await res.text();
      throw new Error(`Expected JSON but got ${res.status}: ${t.slice(0, 200)}`);
    }
    const data = await res.json();
    if (!res.ok) {
      const msg = (data && (data.detail || data.error || data.message)) || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  async function refresh(widget) {
    const kind = widget.getAttribute("data-kind");
    const objectId = widget.getAttribute("data-id");
    if (!kind || !objectId) return;

    const urls = buildUrls(kind, objectId);

    setError(widget, "");
    setStatus(widget, "", true);

    const allowed = await fetchJson(urls.allowed, {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });

    setStatus(widget, allowed.current || "UNKNOWN", false);
    fillNextSelect(widget, allowed.allowed || []);

    // SLA may or may not exist on this endpoint; support both
    if (allowed && allowed.sla) setSla(widget, allowed.sla);

    try {
      const tl = await fetchJson(urls.timeline, {
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });
      renderTimeline(widget, tl);
      if (tl && tl.sla) setSla(widget, tl.sla);
    } catch (e) {
      // Timeline should never block transitions
      const box = qs(widget, "[data-wf-timeline]");
      if (box) box.innerHTML = `<div class="muted">History unavailable.</div>`;
    }
  }

  async function apply(widget) {
    const kind = widget.getAttribute("data-kind");
    const objectId = widget.getAttribute("data-id");
    if (!kind || !objectId) return;

    const sel = qs(widget, "[data-wf-next]");
    const commentEl = qs(widget, "[data-wf-comment]");
    const btn = qs(widget, "[data-wf-apply]");
    if (!sel) return;

    const toStatus = String(sel.value || "").trim();
    const comment = commentEl ? String(commentEl.value || "").trim() : "";

    if (!toStatus) {
      setError(widget, "Select a target status first.");
      return;
    }

    const urls = buildUrls(kind, objectId);
    const csrf = getCookie("csrftoken");

    if (btn) btn.disabled = true;
    setError(widget, "");

    const body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrf);
    body.set("to_status", toStatus);
    body.set("comment", comment);

    try {
      await fetchJson(urls.transition, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": csrf,
        },
        body: body.toString(),
      });

      if (commentEl) commentEl.value = "";
      await refresh(widget);
    } catch (e) {
      setError(widget, e.message || "Transition failed.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function wire(widget) {
    const sel = qs(widget, "[data-wf-next]");
    const btn = qs(widget, "[data-wf-apply]");

    if (sel && btn) {
      sel.addEventListener("change", () => {
        btn.disabled = !String(sel.value || "").trim();
      });
    }

    if (btn) {
      btn.addEventListener("click", () => apply(widget));
    }

    refresh(widget).catch((e) => setError(widget, e.message || "Widget failed to load."));
  }

  window.NAROLIMS = window.NAROLIMS || {};
  window.NAROLIMS.workflowInit = function () {
    qsa(".workflow-widget[data-kind][data-id]").forEach(wire);
  };

  // auto-init on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.NAROLIMS.workflowInit());
  } else {
    window.NAROLIMS.workflowInit();
  }
})();
