(function () {
  function getRowLockedState(checkbox) {
    const row = checkbox.closest("tr");
    if (!row) return null;
    const badge = row.querySelector(".lock-badge");
    if (!badge) return null;
    return badge.dataset.locked === "1";
  }

  function updateActions() {
    const actionSelect = document.querySelector('select[name="action"]');
    if (!actionSelect) return;

    const lockOpt = actionSelect.querySelector('option[value="lock_selected_schemas"]');
    const revOpt = actionSelect.querySelector('option[value="create_revision_from_locked"]');

    // No options to control
    if (!lockOpt && !revOpt) return;

    const checked = Array.from(document.querySelectorAll("tr input.action-select:checked"));
    if (checked.length === 0) {
      // No selection, show everything (default Django behavior)
      if (lockOpt) lockOpt.style.display = "";
      if (revOpt) revOpt.style.display = "";
      return;
    }

    let anyLocked = false;
    let anyUnlocked = false;

    for (const cb of checked) {
      const locked = getRowLockedState(cb);
      if (locked === true) anyLocked = true;
      if (locked === false) anyUnlocked = true;
    }

    // Rules:
    // - Lock action: only if at least one selected is UNLOCKED
    // - Create revision action: only if ALL selected are LOCKED
    const canLock = anyUnlocked;
    const canRev = anyLocked && !anyUnlocked;

    if (lockOpt) lockOpt.style.display = canLock ? "" : "none";
    if (revOpt) revOpt.style.display = canRev ? "" : "none";

    // If currently selected action got hidden, reset dropdown to blank
    const selectedValue = actionSelect.value;
    if ((selectedValue === "lock_selected_schemas" && !canLock) ||
        (selectedValue === "create_revision_from_locked" && !canRev)) {
      actionSelect.value = "";
    }
  }

  function bind() {
    updateActions();

    document.addEventListener("change", function (e) {
      const t = e.target;
      if (!t) return;

      // Row checkboxes + master toggle
      if (t.classList && (t.classList.contains("action-select") || t.id === "action-toggle")) {
        updateActions();
      }

      // Action dropdown itself
      if (t.name === "action") {
        updateActions();
      }
    });

    // Django sometimes toggles all via click without firing change in some skins
    document.addEventListener("click", function (e) {
      const t = e.target;
      if (!t) return;
      if (t.id === "action-toggle") {
        setTimeout(updateActions, 0);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
