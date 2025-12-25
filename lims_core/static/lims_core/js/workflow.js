(function () {
    const container = document.querySelector(".workflow-card");
    if (!container) return;

    const kind = container.dataset.kind;
    const id = container.dataset.id;

    const statusEl = document.getElementById("wf-status");
    const selectEl = document.getElementById("wf-next");
    const applyBtn = document.getElementById("wf-apply");
    const errorEl = document.getElementById("wf-error");
    const timelineEl = document.getElementById("wf-timeline");

    const csrfToken =
        document.querySelector("meta[name='csrf-token']")?.content || "";

    function showError(msg) {
        errorEl.innerText = msg;
        errorEl.style.display = "block";
    }

    function clearError() {
        errorEl.innerText = "";
        errorEl.style.display = "none";
    }

    async function loadState() {
        clearError();
        selectEl.innerHTML = "";
        applyBtn.disabled = true;

        try {
            const stateResp = await fetch(`/lims/workflows/${kind}/${id}/`);
            if (!stateResp.ok) throw new Error("Failed to load workflow state");

            const state = await stateResp.json();
            statusEl.innerText = state.status;

            const allowedResp = await fetch(
                `/lims/workflows/${kind}/${id}/allowed/`
            );
            if (!allowedResp.ok) return;

            const allowed = await allowedResp.json();

            (allowed.allowed || []).forEach(target => {
                const opt = document.createElement("option");
                opt.value = target;
                opt.innerText = target;
                selectEl.appendChild(opt);
            });

            applyBtn.disabled = selectEl.options.length === 0;

            loadTimeline();

        } catch (err) {
            showError(err.message);
        }
    }

    async function loadTimeline() {
        timelineEl.innerHTML = "";

        try {
            const resp = await fetch(
                `/lims/workflows/${kind}/${id}/timeline/`
            );
            if (!resp.ok) return;

            const data = await resp.json();

            data.timeline.forEach(t => {
                const row = document.createElement("div");
                row.className = "timeline-row";
                row.innerText =
                    `${t.at} | ${t.user || "system"} | ${t.from} → ${t.to}`;
                timelineEl.appendChild(row);
            });

        } catch (_) {
            /* timeline failures are non-fatal */
        }
    }

    async function applyTransition() {
        clearError();
        const target = selectEl.value;

        try {
            const resp = await fetch(
                `/lims/workflows/${kind}/${id}/`,
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken
                    },
                    body: JSON.stringify({ status: target })
                }
            );

            if (resp.status === 403) {
                showError("You are not permitted to perform this action.");
                return;
            }

            if (resp.status === 409) {
                const data = await resp.json();
                showError(data.detail || "Invalid transition.");
                return;
            }

            if (!resp.ok) {
                showError("Unexpected error.");
                return;
            }

            loadState();

        } catch (err) {
            showError(err.message);
        }
    }

    applyBtn.addEventListener("click", applyTransition);

    loadState();
})();
