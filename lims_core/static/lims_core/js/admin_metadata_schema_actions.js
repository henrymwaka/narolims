(function () {
  function getSelectedRows() {
    return Array.from(document.querySelectorAll("#result_list tbody tr"))
      .filter((tr) => {
        const cb = tr.querySelector('input.action-select[type="checkbox"]');
        return cb && cb.checked;
      });
  }

  function computeSelectionState(rows) {
    let any = false;
    let anyLocked = false;
    let anyUnlocked = false;

    rows.forEach((tr) => {
      any = true;
      const badge = tr.querySelector(".lock-badge");
      const locked = badge && badge.getAttribute("data-locked") === "1";
      if (locked) anyLocked = true;
      else anyUnlocked = true;
    });

    return { any, anyLocked, anyUnlocked };
  }

  function setOptionVisible(selectEl, value, visible) {
    const opt = Array.from(selectEl.options).find((o) => o.value === value);
    if (!opt) return;
    opt.hidden = !visible;
    opt.disabled = !visible;

    if (!visible && selectEl.value === value) {
      selectEl.value = "";
    }
  }

  function updateActions() {
    const actionSelect = document.querySelector('select[name="action"]');
    if (!actionSelect) return;

    const rows = getSelectedRows();
    const state = computeSelectionState(rows);

    // Default: show both if nothing selected
    if (!state.any) {
      setOptionVisible(actionSelect, "lock_selected_schemas", true);
      setOptionVisible(actionSelect, "create_revision_from_locked", true);
      return;
    }

    // Lock: show if at least one selected is unlocked
    setOptionVisible(actionSelect, "lock_selected_schemas", state.anyUnlocked);

    // Create revision: show only if all selected are locked (meaning none unlocked)
    setOptionVisible(actionSelect, "create_revision_from_locked", state.anyLocked && !state.anyUnlocked);
  }

  function bind() {
    updateActions();

    document.addEventListener("change", function (e) {
      if (e.target && e.target.matches('input.action-select[type="checkbox"], #action-toggle')) {
        updateActions();
      }
    });

    // Some admin themes trigger click only, so cover both
    document.addEventListener("click", function (e) {
      if (e.target && e.target.matches('input.action-select[type="checkbox"], #action-toggle')) {
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
