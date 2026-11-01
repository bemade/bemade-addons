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
 *   running, an exact name + date-of-birth twin not confirmed with « Create
 *   anyway », an unlikely date of birth not confirmed (task 1716), or a
 *   half-filled emergency contact;
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

/**
 * Task 1716 (review round 2, owner 2026-10-27): an override is accepted for
 * the IDENTITY it was shown for — first name, last name, date of birth (and,
 * for « Create anyway », the matched twins) — never for the whole form: a
 * team, a contact or anything else changed afterwards keeps it.
 */
function identityKey(form) {
    const { first, last, dob } = fields(form);
    return JSON.stringify([first, last, dob]);
}

function acceptKeys(form) {
    const identity = identityKey(form);
    return { dob: identity, force: `${identity}|${form.dataset.scCheckedExactIds || ""}` };
}

function accepted(form) {
    const keys = acceptKeys(form);
    return { dob: form.dataset.scDobOkKey === keys.dob, force: form.dataset.scForceKey === keys.force };
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
    // Task 1716: a twin and an unlikely date of birth are warnings — each
    // confirmed for THESE values (« Create anyway », « The date is correct »).
    const key = keyOf(values);
    const ok = accepted(form);
    if (form.dataset.scCheckedKey === key && form.dataset.scCheckedDobWarn === "1" && !ok.dob) {
        return text.dobWarn;
    }
    if (form.dataset.scCheckedKey === key && form.dataset.scCheckedExact === "1" && !ok.force) {
        return text.exact;
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

/** Task 1716: the confirmations posted with the create, for the accepted identity only. */
function syncConfirmations(form) {
    const ok = accepted(form);
    const force = form.querySelector("[data-sc-player-add-force]");
    if (force) {
        force.value = ok.force ? "1" : "0";
    }
    const dobOk = form.querySelector("[data-sc-player-add-dob-ok]");
    if (dobOk) {
        dobOk.value = ok.dob ? "1" : "0";
    }
}

function refreshSubmit(form) {
    // Task 1658: the panel's own reasons (check-as-you-type, twins, the
    // emergency contact pair), shown by the shared guard.
    syncConfirmations(form);
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
            form.dataset.scCheckedExactIds = results.dataset.scExactIds || "";
            form.dataset.scCheckedDobWarn = results.dataset.scDobWarn || "0";
            form.dataset.scCheckedNear = results.dataset.scNear || "0";
        } else {
            delete form.dataset.scCheckedKey;
            delete form.dataset.scCheckedExactIds;
        }
        showAccepted(form);
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

// Task 1716: « Create anyway » / « The date is correct » in the check.
document.addEventListener("click", (ev) => {
    const button =
        ev.target.closest && ev.target.closest("[data-sc-player-add-force-btn], [data-sc-player-add-dob-confirm]");
    const form = button && playerForm(button);
    if (!form) {
        return;
    }
    ev.preventDefault();
    const keys = acceptKeys(form);
    if (button.matches("[data-sc-player-add-force-btn]")) {
        form.dataset.scForceKey = keys.force;
    } else {
        form.dataset.scDobOkKey = keys.dob;
    }
    showAccepted(form);
    refreshSubmit(form);
});

/**
 * Review round 1 (owner 2026-10-27): an accepted override is no longer a
 * button — « ✓ Accepted by the user » takes its place, for the identity it
 * was accepted for (round 2: a re-check after a team change keeps it).
 */
function showAccepted(form) {
    const ok = accepted(form);
    const buttons = {
        force: "[data-sc-player-add-force-btn]",
        dob: "[data-sc-player-add-dob-confirm]",
    };
    let moveFocus = false;
    for (const [kind, selector] of Object.entries(buttons)) {
        for (const button of form.querySelectorAll(selector)) {
            if (ok[kind] && button.contains(document.activeElement)) {
                moveFocus = true;
            }
            button.hidden = ok[kind];
        }
        for (const note of form.querySelectorAll(`[data-sc-check-accepted="${kind}"]`)) {
            note.hidden = !ok[kind];
        }
    }
    if (moveFocus) {
        const submit = form.querySelector('button[type="submit"]:not([formaction])');
        if (submit) {
            submit.focus({ preventScroll: true });
        }
    }
}

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
    delete form.dataset.scCheckedExactIds;
    delete form.dataset.scCheckedDobWarn;
    delete form.dataset.scCheckedNear;
    delete form.dataset.scForceKey;
    delete form.dataset.scDobOkKey;
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
