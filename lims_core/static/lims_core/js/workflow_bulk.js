(function () {
  const cfg = window.NAROLIMS_UI || {};
  const bulkUrl = cfg.bulkUrl || "/lims/workflows/sample/bulk/";
  const labId = cfg.labId || "";

  const checkAll = document.getElementById("check-all");
  const rowChecks = Array.from(document.querySelectorAll(".row-check"));
  const targetEl = document.getElementById("bulk-target");
  const commentEl = document.getElementById("bulk-comment");
  const applyBtn = document.getElementById("bulk-apply");
  const countEl = document.getElementById("bulk-count");
  const errEl = document.getElementById("bulk-error");
  const resultEl = document.getElementById("bulk-result");

  if (!applyBtn || rowChecks.length === 0) return;

  function csrfToken() {
    const meta = document.querySelector("meta[name='csrf-token']");
    if (meta && meta.content) return meta.content;

    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : "";
  }

  function selectedIds() {
    return rowChecks.filter(c => c.checked).map(c => parseInt(c.value, 10));
  }

  function setError(msg) {
    errEl.style.display = "block";
    errEl.textContent = msg;
  }

  function clearError() {
    errEl.style.display = "none";
    errEl.textContent = "";
  }

  function setResult(obj) {
    resultEl.style.display = "block";
    resultEl.textContent = JSON.stringify(obj, null, 2);
  }

  function clearResult() {
    resultEl.style.display = "none";
    resultEl.textContent = "";
  }

  function refreshUi() {
    const ids = selectedIds();
    countEl.textContent = `${ids.length} selected`;
    applyBtn.disabled = !(ids.length > 0 && targetEl.value);
  }

  async function bulkApply() {
    clearError();
    clearResult();

    const ids = selectedIds();
    const target = (targetEl.value || "").trim();
    const comment = (commentEl.value || "").trim();

    if (!ids.length) return setError("Select at least one sample.");
    if (!target) return setError("Choose a target status.");

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
          "X-CSRFToken": csrfToken(),
          ...(labId ? { "X-LABORATORY": String(labId) } : {})
        },
        body: JSON.stringify(payload)
      });

      const text = await resp.text();
      let data = null;
      try { data = JSON.parse(text); } catch (_) { /* keep raw */ }

      if (!resp.ok) {
        if (data && (data.detail || data.error)) {
          return setError(data.detail || data.error);
        }
        return setError(`Bulk transition failed (HTTP ${resp.status}).`);
      }

      setResult(data || { ok: true, raw: text });

      // Update table statuses for items that moved (or skipped)
      if (data && Array.isArray(data.results)) {
        data.results.forEach(r => {
          const tr = document.querySelector(`tr[data-sample-id="${r.object_id}"]`);
          if (!tr) return;
          const cell = tr.querySelector(".status-cell");
          if (!cell) return;
          cell.textContent = r.to || target;
        });
      }
    } catch (e) {
      setError(e.message || "Unexpected error.");
    }
  }

  if (checkAll) {
    checkAll.addEventListener("change", () => {
      rowChecks.forEach(c => { c.checked = checkAll.checked; });
      refreshUi();
    });
  }

  rowChecks.forEach(c => c.addEventListener("change", refreshUi));
  targetEl.addEventListener("change", refreshUi);
  applyBtn.addEventListener("click", bulkApply);

  refreshUi();
})();
