/*
 * Task 1655 — the inline « create a player » panel (inert outside .o_sc_app).
 *
 * form[data-sc-player-add]: once a first AND a last name are typed, the
 * existence check (GET /my/app/player-check, 300 ms after the last key; a
 * newer request aborts the older one) lists the matching players under the
 * fields, refined by the date of birth and the chosen team.
 *
 * Owner review 2026-10-22:
 * - « Create » stays greyed (aria-disabled, never a dead click) until it can
 *   succeed, with the reason under it (aria-describedby): what is missing
 *   (« Complete: first name, last name, date of birth »), the check still
 *   running, an exact name + date-of-birth twin, a same-name player the
 *   user can't open (security review 2026-10-23), or a half-filled
 *   emergency contact;
 * - the create posts with fetch: ANY refusal of the server (a twin created
 *   meanwhile, an invalid mobile…) shows in the panel — under its field, or
 *   next to « Create » — the panel stays open with every typed value; only
 *   a success leaves the page (the new player's page).
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
// Task 1658: the greyed button + reason line are the shared form guard's.
import { guardFlash, guardRefresh } from "@bemade_sports_clinic/js/sc_form_guard";

const DEBOUNCE_MS = 300;
const timers = new WeakMap();
const inflight = new WeakMap();
const posting = new WeakSet();

function fields(form) {
    const get = (key) => (form.querySelector(`[data-sc-player-add-field="${key}"]`) || {}).value || "";
    return {
        first: get("first").trim(),
        last: get("last").trim(),
        dob: get("dob").trim(),
        teams: (form.querySelector("[data-sc-player-add-teams]") || {}).value || "",
    };
}

function contact(form) {
    const get = (key) => ((form.querySelector(`[data-sc-player-add-ec="${key}"]`) || {}).value || "").trim();
    return { name: get("name"), mobile: get("mobile") };
}

function keyOf(values) {
    return JSON.stringify(values);
}

function reasons(form) {
    return (form.querySelector("[data-sc-player-add-reasons]") || {}).dataset || {};
}

/** Why « Create » can't succeed yet ("" = it can). */
function blocker(form) {
    const values = fields(form);
    const text = reasons(form);
    const missing = [];
    if (!values.first) {
        missing.push(text.first);
    }
    if (!values.last) {
        missing.push(text.last);
    }
    if (!values.dob) {
        missing.push(text.dob);
    }
    if (text.teamRequired === "1" && !values.teams.trim()) {
        missing.push(text.team);
    }
    if (missing.length) {
        return `${text.missing} ${missing.join(", ")}`;
    }
    if (form.dataset.scCheckedKey === keyOf(values) && form.dataset.scCheckedExact === "1") {
        return text.exact;
    }
    // Security review 2026-10-23: a same-name player the user can't open —
    // the server refuses the create whatever the date of birth.
    if (form.dataset.scCheckedKey === keyOf(values) && form.dataset.scCheckedTwin === "1") {
        return text.twin;
    }
    const ec = contact(form);
    if (Boolean(ec.name) !== Boolean(ec.mobile)) {
        return text.ec;
    }
    if (form.dataset.scCheckedKey !== keyOf(values)) {
        return text.checking;
    }
    return "";
}

function refreshSubmit(form) {
    // Task 1658: the panel's own reasons (check-as-you-type, twins, the
    // emergency contact pair), shown by the shared guard.
    const busy = posting.has(form);
    const reason = busy ? "" : blocker(form);
    guardRefresh(form, reason, busy);
    // Task 1674: only similar players found — « Create » stays enabled, the
    // reason line asks to check them first.
    if (!busy && !reason && form.dataset.scCheckedNear === "1") {
        const line = form.querySelector("[data-sc-guard-reason]");
        if (line) {
            line.textContent = reasons(form).near || "";
            line.hidden = !line.textContent;
        }
    }
}

// --------------------------------------------------------------- errors
function clearErrors(form) {
    for (const el of form.querySelectorAll("[data-sc-player-add-field-error]")) {
        el.remove();
    }
    for (const el of form.querySelectorAll('[aria-invalid="true"]')) {
        el.removeAttribute("aria-invalid");
    }
    const box = form.querySelector("[data-sc-player-add-error]");
    if (box) {
        box.textContent = "";
        box.hidden = true;
    }
}

function showError(form, message, field) {
    clearErrors(form);
    const input = field && form.querySelector(`[name="${field}"]`);
    if (input) {
        const ec = input.closest("details[data-sc-player-add-ec-box]");
        if (ec) {
            ec.open = true;
        }
        const note = document.createElement("p");
        note.className = "o_sc_field_message o_sc_field_error";
        note.setAttribute("role", "alert");
        note.dataset.scPlayerAddFieldError = field;
        note.textContent = message;
        input.setAttribute("aria-invalid", "true");
        input.insertAdjacentElement("afterend", note);
        input.focus({ preventScroll: true });
        note.scrollIntoView({ block: "nearest" });
        return;
    }
    const box = form.querySelector("[data-sc-player-add-error]");
    if (box) {
        box.textContent = message;
        box.hidden = false;
        box.scrollIntoView({ block: "nearest" });
    }
}

// ---------------------------------------------------------------- check
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
            form.dataset.scCheckedTwin = results.dataset.scTwinElsewhere || "0";
            form.dataset.scCheckedNear = results.dataset.scNear || "0";
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
    if (!form) {
        return;
    }
    if (ev.target.matches("[data-sc-player-add-field]")) {
        schedule(form);
    } else if (ev.target.matches("[data-sc-player-add-ec]")) {
        refreshSubmit(form);
    }
});

document.addEventListener("change", (ev) => {
    const form = playerForm(ev.target);
    if (!form) {
        return;
    }
    if (ev.target.matches("[data-sc-player-add-field], [data-sc-player-add-teams]")) {
        schedule(form);
    } else if (ev.target.matches("[data-sc-player-add-ec]")) {
        refreshSubmit(form);
    }
});

// --------------------------------------------------------------- create
async function create(form) {
    posting.add(form);
    refreshSubmit(form);
    clearErrors(form);
    const data = Object.fromEntries(new FormData(form).entries());
    try {
        const result = await scFetch(form.getAttribute("action"), { method: "POST", data, toast: false, timeout: 30000 });
        if (result && result.redirect) {
            // Task 1672: the panel resets before the page changes (back on
            // the team page, reopening it shows an empty form).
            form.dispatchEvent(new CustomEvent("sc:create-success", { bubbles: true }));
            window.location.assign(result.redirect);
            return;
        }
        showError(form, reasons(form).generic || "");
    } catch (error) {
        const payload = (error && error.payload) || {};
        showError(form, payload.message || reasons(form).generic || "", payload.field || "");
        // A twin created meanwhile: the check lists it (« Open » / « Add »).
        delete form.dataset.scCheckedKey;
        check(form);
    } finally {
        posting.delete(form);
        refreshSubmit(form);
    }
}

document.addEventListener(
    "submit",
    (ev) => {
        const form = playerForm(ev.target);
        if (!form) {
            return;
        }
        if (ev.submitter && ev.submitter.hasAttribute("formaction")) {
            return; // the check's « Add to team » / « Reactivate and add »
        }
        ev.preventDefault();
        if (posting.has(form)) {
            return;
        }
        const reason = blocker(form);
        if (reason) {
            // Never a dead click: the reason line says why (and is read out).
            refreshSubmit(form);
            guardFlash(form);
            return;
        }
        create(form);
    },
    true
);

// Task 1672: the check's first content, to put back on a reset.
const checkHints = new WeakMap();

document.addEventListener("sc:form-reset", (ev) => {
    const form = playerForm(ev.target);
    if (!form) {
        return;
    }
    const previous = inflight.get(form);
    if (previous) {
        previous.abort();
        inflight.delete(form);
    }
    clearTimeout(timers.get(form));
    delete form.dataset.scCheckedKey;
    delete form.dataset.scCheckedExact;
    delete form.dataset.scCheckedTwin;
    delete form.dataset.scCheckedNear;
    const region = form.querySelector("[data-sc-player-check]");
    if (region && checkHints.has(region)) {
        region.innerHTML = checkHints.get(region);
    }
    clearErrors(form);
    refreshSubmit(form);
});

// A panel re-opened with typed values (a refused create): check at once.
function boot() {
    for (const form of document.querySelectorAll(".o_sc_app form[data-sc-player-add]")) {
        const region = form.querySelector("[data-sc-player-check]");
        if (region && !checkHints.has(region) && !region.querySelector("[data-sc-check-results]")) {
            checkHints.set(region, region.innerHTML);
        }
        const values = fields(form);
        refreshSubmit(form);
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
