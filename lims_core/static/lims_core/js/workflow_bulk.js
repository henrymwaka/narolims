(function () {
  const cfg = window.NAROLIMS_UI || {};

  const bulkUrl = cfg.bulkUrl || "/lims/workflows/sample/bulk/";
  const statusesUrl = cfg.statusesUrl || "/lims/workflows/sample/";
  const labId = cfg.labId || "";

  const checkAll = document.getElementById("check-all");
  const targetEl = document.getElementById("bulk-target");
  const commentEl = document.getElementById("bulk-comment");
  const applyBtn = document.getElementById("bulk-apply");
  const countEl = document.getElementById("bulk-count");
  const errEl = document.getElementById("bulk-error");
  const resultEl = document.getElementById("bulk-result");
  const statusCountEl = document.getElementById("bulk-status-count");

  function rowChecks() {
    return Array.from(document.querySelectorAll(".row-check"));
  }

  if (!applyBtn || !targetEl) return;

  function csrfToken() {
    const meta = document.querySelector("meta[name='csrf-token']");
    if (meta && meta.content) return meta.content;

    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : "";
  }

  function selectedIds() {
    return rowChecks()
      .filter(c => c.checked)
      .map(c => parseInt(c.value, 10))
      .filter(n => Number.isFinite(n));
  }

  function setError(msg) {
    if (!errEl) return;
    errEl.style.display = "block";
    errEl.textContent = msg;
  }

  function clearError() {
    if (!errEl) return;
    errEl.style.display = "none";
    errEl.textContent = "";
  }

  function setResult(msg) {
    if (!resultEl) return;
    resultEl.style.display = "block";
    resultEl.textContent = msg;
  }

  function clearResult() {
    if (!resultEl) return;
    resultEl.style.display = "none";
    resultEl.textContent = "";
  }

  function setStatusCount(n) {
    if (!statusCountEl) return;
    statusCountEl.textContent = String(n);
  }

  function getDropdownStatusCount() {
    // Count options excluding placeholder empty value
    if (!targetEl) return 0;
    return Array.from(targetEl.options || [])
      .filter(o => (o.value || "").trim() !== "")
      .length;
  }

  function setBusy(isBusy, label) {
    applyBtn.dataset.busy = isBusy ? "1" : "0";
    if (label) applyBtn.textContent = label;
    else applyBtn.textContent = isBusy ? "Applying..." : "Apply to selected";
  }

  function refreshUi() {
    const ids = selectedIds();
    if (countEl) countEl.textContent = `${ids.length} selected`;
    const hasTarget = (targetEl.value || "").trim().length > 0;
    applyBtn.disabled = !(ids.length > 0 && hasTarget) || applyBtn.dataset.busy === "1";
  }

  function normalizeStatuses(data) {
    if (!data) return [];
    if (Array.isArray(data.statuses)) return data.statuses;
    if (Array.isArray(data.states)) return data.states;

    if (data.workflow) {
      if (Array.isArray(data.workflow.statuses)) return data.workflow.statuses;
      if (Array.isArray(data.workflow.states)) return data.workflow.states;
    }
    if (data.data) {
      if (Array.isArray(data.data.statuses)) return data.data.statuses;
      if (Array.isArray(data.data.states)) return data.data.states;
    }
    return [];
  }

  function coerceStatusStrings(list) {
    return (list || [])
      .map(x => {
        if (typeof x === "string") return x.trim();
        if (x && typeof x === "object") {
          return String(x.code || x.id || x.name || x.value || "").trim();
        }
        return "";
      })
      .filter(Boolean);
  }

  async function loadStatuses() {
    // If Django already rendered statuses into the dropdown, reflect that immediately.
    // This prevents "statuses: 0" during JS load or API issues.
    setStatusCount(getDropdownStatusCount());

    try {
      const resp = await fetch(statusesUrl, {
        method: "GET",
        credentials: "same-origin",
        headers: { "Accept": "application/json" }
      });

      const ctype = (resp.headers.get("content-type") || "").toLowerCase();
      const text = await resp.text();

      // If we got HTML instead of JSON, it's usually a login redirect or an error page.
      // Keep the server-rendered dropdown/count and do not clobber anything.
      if (!ctype.includes("application/json")) {
        if (!resp.ok) setError(`Cannot load statuses (HTTP ${resp.status}).`);
        return;
      }

      let data = null;
      try { data = JSON.parse(text); } catch (_) {}

      if (!resp.ok) {
        const msg =
          (data && (data.detail || data.error)) ||
          `Cannot load statuses (HTTP ${resp.status}).`;
        setError(msg);
        return;
      }

      const raw = normalizeStatuses(data);
      const statuses = coerceStatusStrings(raw);

      // Do not force count to 0 when API returns nothing.
      // Just keep whatever the template already rendered.
      if (!statuses.length) {
        setError("Workflow statuses could not be read from the server response.");
        return;
      }

      const current = (targetEl.value || "").trim();

      // Rebuild dropdown from API
      targetEl.innerHTML = "";
      const ph = document.createElement("option");
      ph.value = "";
      ph.textContent = "-- choose --";
      targetEl.appendChild(ph);

      statuses.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        targetEl.appendChild(opt);
      });

      setStatusCount(statuses.length);

      if (current && statuses.includes(current)) targetEl.value = current;
      else targetEl.value = "";

      clearError();
      refreshUi();
    } catch (e) {
      // Keep server rendered statuses/count. Only show a helpful message.
      setError("Unable to load workflow statuses. Check login/session or API permissions.");
    }
  }

  async function bulkApply() {
    clearError();
    clearResult();

    const ids = selectedIds();
    const target = (targetEl.value || "").trim();
    const comment = commentEl ? (commentEl.value || "").trim() : "";

    if (!ids.length) return setError("Select at least one sample.");
    if (!target) return setError("Choose a target status.");

    setBusy(true);
    refreshUi();

    const payload = {
      kind: "sample",
      target_status: target,
      object_ids: ids,
      comment: comment
    };

    try {
      const resp = await fetch(bulkUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrfToken(),
          ...(labId ? { "X-LABORATORY": String(labId) } : {})
        },
        body: JSON.stringify(payload)
      });

      const text = await resp.text();
      let data = null;
      try { data = JSON.parse(text); } catch (_) {}

      if (!resp.ok) {
        const msg =
          (data && (data.detail || data.error)) ||
          `Bulk transition failed (HTTP ${resp.status}).`;
        setError(msg);
        return;
      }

      // Update table (best effort)
      if (data && Array.isArray(data.results)) {
        data.results.forEach(r => {
          const tr = document.querySelector(`tr[data-sample-id="${r.object_id}"]`);
          if (!tr) return;

          const cell = tr.querySelector(".status-cell");
          if (cell) cell.textContent = r.to || target;

          const cb = tr.querySelector(".row-check");
          if (cb) cb.checked = false;
        });
      } else {
        ids.forEach(id => {
          const tr = document.querySelector(`tr[data-sample-id="${id}"]`);
          if (!tr) return;

          const cell = tr.querySelector(".status-cell");
          if (cell) cell.textContent = target;

          const cb = tr.querySelector(".row-check");
          if (cb) cb.checked = false;
        });
      }

      if (checkAll) checkAll.checked = false;

      const ok = (data && typeof data.ok_count === "number") ? data.ok_count : ids.length;
      const skipped = (data && typeof data.skipped_count === "number") ? data.skipped_count : 0;

      setResult(`Done. ok=${ok}, skipped=${skipped}`);
    } catch (e) {
      setError(e.message || "Unexpected error.");
    } finally {
      setBusy(false);
      refreshUi();
    }
  }

  if (checkAll) {
    checkAll.addEventListener("change", () => {
      rowChecks().forEach(c => { c.checked = checkAll.checked; });
      refreshUi();
    });
  }

  document.addEventListener("change", (e) => {
    const t = e.target;
    if (!t) return;

    if (t.classList && t.classList.contains("row-check")) {
      refreshUi();
      return;
    }
    if (t.id === "bulk-target") {
      refreshUi();
      return;
    }
  });

  applyBtn.addEventListener("click", bulkApply);

  // Init
  applyBtn.dataset.busy = "0";
  refreshUi();
  loadStatuses();
})();
