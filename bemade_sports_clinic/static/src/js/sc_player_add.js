/*
 * Task 1655 — the inline « create a player » panel (inert outside .o_sc_app).
 *
 * form[data-sc-player-add]: once a first AND a last name are typed, the
 * existence check (GET /my/app/player-check, 300 ms after the last key; a
 * newer request aborts the older one) lists the matching players under the
 * fields, refined by the date of birth and the chosen team. « Create » is
 * enabled only when the check has answered for the CURRENT name / date of
 * birth / teams and found no player with the same name and date of birth.
 */
const DEBOUNCE_MS = 300;
const timers = new WeakMap();
const inflight = new WeakMap();

function fields(form) {
    const get = (key) => (form.querySelector(`[data-sc-player-add-field="${key}"]`) || {}).value || "";
    return {
        first: get("first").trim(),
        last: get("last").trim(),
        dob: get("dob").trim(),
        teams: (form.querySelector("[data-sc-player-add-teams]") || {}).value || "",
    };
}

function keyOf(values) {
    return JSON.stringify(values);
}

function refreshSubmit(form) {
    const submit = form.querySelector("[data-sc-player-add-submit]");
    if (!submit) {
        return;
    }
    const values = fields(form);
    const ready =
        values.first && values.last && values.dob &&
        form.dataset.scCheckedKey === keyOf(values) &&
        form.dataset.scCheckedExact !== "1";
    submit.disabled = !ready;
}

async function check(form) {
    const values = fields(form);
    const region = form.querySelector("[data-sc-player-check]");
    if (!region) {
        return;
    }
    const previous = inflight.get(form);
    if (previous) {
        previous.abort();
    }
    const controller = new AbortController();
    inflight.set(form, controller);
    const query = new URLSearchParams({
        first: values.first, last: values.last, dob: values.dob, team_ids: values.teams,
    });
    try {
        const response = await fetch(`/my/app/player-check?${query}`, {
            credentials: "same-origin",
            signal: controller.signal,
            headers: { "X-Requested-With": "XMLHttpRequest", Accept: "text/html" },
        });
        if (!response.ok || inflight.get(form) !== controller) {
            return;
        }
        region.innerHTML = await response.text();
        const results = region.querySelector("[data-sc-check-results]");
        if (results && results.dataset.scReady === "1") {
            form.dataset.scCheckedKey = keyOf(values);
            form.dataset.scCheckedExact = results.dataset.scExact || "0";
        } else {
            delete form.dataset.scCheckedKey;
        }
    } catch {
        // aborted / offline: the button stays as it was
    } finally {
        if (inflight.get(form) === controller) {
            inflight.delete(form);
        }
        refreshSubmit(form);
    }
}

function schedule(form) {
    clearTimeout(timers.get(form));
    refreshSubmit(form);
    timers.set(form, setTimeout(() => check(form), DEBOUNCE_MS));
}

function playerForm(target) {
    const form = target && target.closest && target.closest("form[data-sc-player-add]");
    return form && form.closest(".o_sc_app") ? form : null;
}

document.addEventListener("input", (ev) => {
    const form = playerForm(ev.target);
    if (form && ev.target.matches("[data-sc-player-add-field]")) {
        schedule(form);
    }
});

document.addEventListener("change", (ev) => {
    const form = playerForm(ev.target);
    if (form && ev.target.matches("[data-sc-player-add-field], [data-sc-player-add-teams]")) {
        schedule(form);
    }
});

// The submit itself re-checks nothing: a stale result keeps it disabled.
document.addEventListener(
    "submit",
    (ev) => {
        const form = playerForm(ev.target);
        if (ev.submitter && ev.submitter.hasAttribute("formaction")) {
            return; // the check's « Add to team » / « Reactivate and add »
        }
        if (form && form.querySelector("[data-sc-player-add-submit]")?.disabled) {
            ev.preventDefault();
        }
    },
    true
);

// A panel re-opened with typed values (a refused create): check at once.
function boot() {
    for (const form of document.querySelectorAll(".o_sc_app form[data-sc-player-add]")) {
        const values = fields(form);
        if (values.first && values.last) {
            check(form);
        }
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
} else {
    boot();
}
