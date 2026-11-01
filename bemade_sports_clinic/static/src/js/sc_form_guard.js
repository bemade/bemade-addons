/*
 * Task 1658 — the app-wide form rule (owner, from the #1655 review):
 * a form's primary action stays greyed (aria-disabled + aria-describedby,
 * never a dead click) with a short reason line until it can succeed; a
 * server refusal shows INSIDE the form, the typed values kept, no page
 * change. Inert outside .o_sc_app.
 *
 * Declarative, on the form (form[data-sc-guard]):
 *
 * - a field marked required (the HTML « required » attribute, or
 *   data-sc-required) must hold a value (a checkbox ticked; a radio group:
 *   one of its buttons checked; a file input: a file). Its name in the
 *   reason is data-sc-required's value when it is a label, else the text of
 *   its <label> (for=id, else the field's own label);
 * - data-sc-guard-rules='[…]' (JSON):
 *     {"type": "required", "field": "note", "label": "…"}
 *         a named field (e.g. one an OWL autosave component renders) must
 *         hold a value;
 *     (a rule's text: "message", or "key" naming a hidden
 *     <span data-sc-guard-msg="<key>"> of the form — translated there)
 *     {"type": "together", "fields": ["ec_name", "ec_mobile"], "key": "…"}
 *         all or none of these named fields filled;
 *     {"type": "after", "field": "date_end", "than": "date_start", "message": "…"}
 *         the field's value is not before the other's (ISO dates sort);
 *     {"type": "not_future", "field": "resolution_date", "message": "…"}
 *         a date not after today (the device's day);
 *     {"type": "assign", "staff": "assigned_staff_ids", "teams": "team_ids",
 *      "allowed": [team ids], "staff0": "csv", "teams0": "csv", "key": "…"}
 *         review fixes 2026-10-24 (owner policy, the server's
 *         sports.event._sc_check_assignment): when the assignees (CSV field
 *         ``staff``) differ from ``staff0``, or the teams differ from
 *         ``teams0`` while there are assignees, every chosen team must be
 *         one of ``allowed`` (the teams the user staffs);
 * - the reason's prefix (« Complétez : ») and the generic / offline errors
 *   come from the layout's [data-sc-guard-texts] (translated there), a form
 *   may override them (data-sc-guard-missing / -generic / -offline);
 * - the submit button [data-sc-guard-submit] (default: the form's first
 *   submit button) gets aria-disabled and aria-describedby → the reason line
 *   [data-sc-guard-reason]; [data-sc-guard-error] is the server-error slot
 *   (the sc_form_guard_slots macro renders both; created here when absent);
 * - with JS the form is novalidate: the reason line replaces the browser's
 *   bubbles (without JS the native validation stays);
 * - data-sc-guard-mode="fetch": the form is posted with fetch to its OWN
 *   action with its OWN fields (every form keeps its POST contract); the
 *   answer is read: a refusal (the page it lands on carries the error —
 *   [data-sc-flash-error], [data-sc-error-for], an ?error= / ?ts_error=
 *   parameter or an error toast) is shown in the form and nothing else
 *   moves; a success navigates to where the server sent it. The request
 *   carries X-Sc-Guard so that page does not consume the pending session
 *   toast / proposal: the real navigation shows them. Default mode
 *   « native »: only the disabled state + reason (the native POST and its
 *   no-JS fallback stay as they are).
 *
 * The client rules are a convenience: the server validations stay the
 * source of truth (and every server refusal surfaces in-form).
 * sc_player_add.js (#1655) keeps its own check-as-you-type and JSON create
 * and uses this module's reason / error helpers.
 */

const ERROR_PARAMS = ["error", "ts_error"];
const posting = new WeakSet();

function inApp(form) {
    return Boolean(form && form.closest && form.closest(".o_sc_app"));
}

export function guardForm(target) {
    const form = target && target.closest && target.closest("form[data-sc-guard]");
    return form && inApp(form) ? form : null;
}

function hasValue(el, form) {
    if (el.type === "checkbox") {
        return el.checked;
    }
    if (el.type === "radio") {
        return Boolean(form.querySelector(`input[type="radio"][name="${el.name}"]:checked`));
    }
    if (el.type === "file") {
        return Boolean(el.files && el.files.length);
    }
    return Boolean((el.value || "").trim());
}

function texts(form) {
    const shared = (document.querySelector("[data-sc-guard-texts]") || {}).dataset || {};
    return {
        missing: form.dataset.scGuardMissing || shared.missing || "",
        generic: form.dataset.scGuardGeneric || shared.generic || "",
        offline: form.dataset.scGuardOffline || shared.offline || shared.generic || "",
    };
}

function labelOf(el, form) {
    const own = el.dataset.scRequired;
    if (own && own !== "1") {
        return own;
    }
    const fieldset = (el.type === "radio" || el.type === "checkbox") && el.closest("fieldset");
    const legend = fieldset && fieldset.querySelector("legend");
    if (legend) {
        return legend.textContent.replace(/\s+/g, " ").trim();
    }
    const byFor = el.id && form.querySelector(`label[for="${el.id}"]`);
    const label = byFor || (el.closest(".o_sc_field") || el.parentElement || form).querySelector("label, .o_sc_field_label");
    return ((label && label.textContent) || el.name || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
}

function named(form, name) {
    return form.querySelector(`[name="${name}"]`);
}

function rules(form) {
    if (!form.dataset.scGuardRules) {
        return [];
    }
    try {
        return JSON.parse(form.dataset.scGuardRules) || [];
    } catch {
        return [];
    }
}

function today() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Why the form can't succeed yet ("" = it can). */
export function guardReason(form) {
    const missing = [];
    const seen = new Set();
    for (const el of form.querySelectorAll("[required], [data-sc-required]")) {
        if (el.disabled || el.type === "hidden" || el.closest("[hidden]") || el.closest("fieldset[disabled]")) {
            continue;
        }
        const label = labelOf(el, form);
        if (seen.has(label)) {
            continue;
        }
        if (!hasValue(el, form)) {
            missing.push(label);
            seen.add(label);
        }
    }
    for (const rule of rules(form)) {
        if (rule.type !== "required") {
            continue;
        }
        const el = named(form, rule.field);
        const label = rule.label || (el ? labelOf(el, form) : rule.field);
        if (!seen.has(label) && (!el || !hasValue(el, form))) {
            missing.push(label);
            seen.add(label);
        }
    }
    if (missing.length) {
        return `${texts(form).missing} ${missing.join(", ")}`.trim();
    }
    // Task 1723: a field that refuses its own input (a tags box with typed
    // text matching nothing) blocks with its message.
    for (const el of form.querySelectorAll("[data-sc-guard-block]")) {
        if (el.dataset.scGuardBlock && !el.closest("[hidden]")) {
            return el.dataset.scGuardBlock;
        }
    }
    const message = (rule) =>
        rule.message || ((rule.key && form.querySelector(`[data-sc-guard-msg="${rule.key}"]`)) || {}).textContent || "";
    for (const rule of rules(form)) {
        if (rule.type === "together") {
            const filled = rule.fields.map((name) => {
                const el = named(form, name);
                return Boolean(el && (el.value || "").trim());
            });
            if (filled.some(Boolean) && !filled.every(Boolean)) {
                return message(rule).trim();
            }
        } else if (rule.type === "after") {
            const a = named(form, rule.field);
            const b = named(form, rule.than);
            if (a && b && a.value && b.value && a.value < b.value) {
                return message(rule).trim();
            }
        } else if (rule.type === "assign") {
            const ids = (value) =>
                new Set(String(value || "").split(",").map((part) => part.trim()).filter(Boolean));
            const same = (a, b) => a.size === b.size && [...a].every((item) => b.has(item));
            const staff = ids((named(form, rule.staff) || {}).value);
            const teams = ids((named(form, rule.teams) || {}).value);
            const allowed = new Set((rule.allowed || []).map(String));
            const changed = !same(staff, ids(rule.staff0)) || (staff.size && !same(teams, ids(rule.teams0)));
            if (changed && ![...teams].every((team) => allowed.has(team))) {
                return message(rule).trim();
            }
        } else if (rule.type === "not_future") {
            const el = named(form, rule.field);
            if (el && el.value && el.value.slice(0, 10) > today()) {
                return message(rule).trim();
            }
        }
    }
    return "";
}

let slotSeq = 0;

/** The reason line + error slot (sc_form_guard_slots), created when the
 * template did not render them. */
function ensureSlots(form) {
    const submit = submitButton(form);
    if (!submit) {
        return;
    }
    const anchor = submit.closest(".o_sc_form_actions") || submit;
    if (!form.querySelector("[data-sc-guard-error]")) {
        const box = document.createElement("p");
        box.className = "o_sc_field_message o_sc_field_error";
        box.setAttribute("role", "alert");
        box.dataset.scGuardError = "1";
        box.hidden = true;
        anchor.insertAdjacentElement("beforebegin", box);
    }
    if (!form.querySelector("[data-sc-guard-reason]")) {
        const line = document.createElement("p");
        line.className = "o_sc_hint o_sc_guard_reason";
        line.id = `sc_guard_reason_${++slotSeq}`;
        line.setAttribute("aria-live", "polite");
        line.dataset.scGuardReason = "1";
        line.hidden = true;
        anchor.insertAdjacentElement("afterend", line);
    }
}

function submitButton(form) {
    return form.querySelector("[data-sc-guard-submit]") || form.querySelector('button[type="submit"]:not([formaction])');
}

function reasonLine(form) {
    return form.querySelector("[data-sc-guard-reason]");
}

/** Grey / ungrey the primary action and write the reason line. */
export function guardRefresh(form, reason = undefined, busy = false) {
    const submit = submitButton(form);
    if (!submit) {
        return;
    }
    const isBusy = busy || posting.has(form);
    const why = isBusy ? "" : reason === undefined ? guardReason(form) : reason;
    const blocked = Boolean(why) || isBusy;
    submit.setAttribute("aria-disabled", blocked ? "true" : "false");
    const line = reasonLine(form);
    if (line) {
        if (line.id && !submit.getAttribute("aria-describedby")) {
            submit.setAttribute("aria-describedby", line.id);
        }
        if (line.textContent !== why) {
            line.textContent = why;
        }
        line.hidden = !why;
    }
}

/** The « never a dead click » cue on the reason line. */
export function guardFlash(form) {
    const line = reasonLine(form);
    if (line) {
        line.classList.remove("o_sc_reason_flash");
        void line.offsetWidth; // restart the cue
        line.classList.add("o_sc_reason_flash");
    }
}

export function guardClearError(form) {
    for (const el of form.querySelectorAll("[data-sc-guard-field-error]")) {
        el.remove();
    }
    for (const el of form.querySelectorAll('[aria-invalid="true"][data-sc-guard-invalid]')) {
        el.removeAttribute("aria-invalid");
        delete el.dataset.scGuardInvalid;
    }
    const box = form.querySelector("[data-sc-guard-error]");
    if (box) {
        box.textContent = "";
        box.hidden = true;
    }
}

/** A server refusal, in the form: under its field when known, else in the
 * form's error slot. Nothing typed is touched. */
export function guardShowError(form, message, field = "") {
    guardClearError(form);
    const input = field && named(form, field);
    if (input) {
        const note = document.createElement("p");
        note.className = "o_sc_field_message o_sc_field_error";
        note.setAttribute("role", "alert");
        note.dataset.scGuardFieldError = field;
        note.textContent = message;
        input.setAttribute("aria-invalid", "true");
        input.dataset.scGuardInvalid = "1";
        input.insertAdjacentElement("afterend", note);
        note.scrollIntoView({ block: "nearest" });
        return;
    }
    const box = form.querySelector("[data-sc-guard-error]");
    if (box) {
        box.textContent = message;
        box.hidden = false;
        box.scrollIntoView({ block: "nearest" });
    }
}

/** The refusal carried by the page a fetch-posted form landed on, or null. */
export function guardRefusal(responseUrl, html, status) {
    const doc = new DOMParser().parseFromString(html || "", "text/html");
    const flash = doc.querySelector("[data-sc-flash-error]");
    if (flash && flash.textContent.trim()) {
        return { message: flash.textContent.trim().replace(/\s+/g, " ") };
    }
    // Task 1723: the event form renders its server-side time refusals as
    // [data-sc-field-error="<field>"] — read both, so a refused create shows
    // its message and keeps what was typed (never a silent empty reload).
    const fieldError = doc.querySelector("[data-sc-error-for], [data-sc-field-error]");
    if (fieldError && fieldError.textContent.trim()) {
        return {
            message: fieldError.textContent.trim(),
            field: fieldError.dataset.scErrorFor || fieldError.dataset.scFieldError || "",
        };
    }
    const toast = doc.querySelector('.o_sc_toast[data-sc-notify][data-sc-notify-tone="error"]');
    if (toast) {
        return { message: toast.dataset.scNotify };
    }
    let url = null;
    try {
        url = new URL(responseUrl, window.location.origin);
    } catch {
        url = null;
    }
    for (const key of ERROR_PARAMS) {
        const value = url && url.searchParams.get(key);
        if (value) {
            return { message: value };
        }
    }
    if (status >= 400) {
        return { message: "" };
    }
    return null;
}

async function post(form, submitter) {
    posting.add(form);
    guardRefresh(form);
    guardClearError(form);
    const data = new FormData(form);
    if (submitter && submitter.name) {
        data.set(submitter.name, submitter.value);
    }
    const action = (submitter && submitter.getAttribute("formaction")) || form.getAttribute("action") || window.location.href;
    let navigating = false;
    try {
        const response = await fetch(action, {
            method: "POST",
            body: data,
            credentials: "same-origin",
            headers: { "X-Sc-Guard": "1", Accept: "text/html" },
        });
        const html = await response.text();
        const refusal = guardRefusal(response.url, html, response.status);
        if (refusal) {
            guardShowError(form, refusal.message || texts(form).generic, refusal.field || "");
            return;
        }
        // Success: where the server sent it (the fragment of the form's
        // return_url, which fetch drops, put back).
        let target = response.url || window.location.href;
        const back = form.querySelector('input[name="return_url"]');
        const hash = back && back.value.includes("#") ? back.value.slice(back.value.indexOf("#")) : "";
        if (hash && !target.includes("#")) {
            target += hash;
        }
        navigating = true;
        // Task 1672: an add panel resets before the page changes (back on
        // this page, the form is empty again).
        form.dispatchEvent(new CustomEvent("sc:create-success", { bubbles: true }));
        window.location.assign(target);
    } catch {
        guardShowError(form, texts(form).offline);
    } finally {
        if (!navigating) {
            posting.delete(form);
            guardRefresh(form);
        }
    }
}

document.addEventListener(
    "submit",
    (ev) => {
        const form = guardForm(ev.target);
        if (!form || form.matches("[data-sc-player-add]")) {
            return;
        }
        if (posting.has(form)) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            return;
        }
        const reason = guardReason(form);
        if (reason) {
            // Never a dead click: the reason line says why (and is read out).
            ev.preventDefault();
            ev.stopImmediatePropagation();
            guardRefresh(form, reason);
            guardFlash(form);
            return;
        }
        if (form.dataset.scGuardMode === "fetch") {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            post(form, ev.submitter);
        }
    },
    true
);

function refreshFrom(ev) {
    const form = guardForm(ev.target);
    if (form && !form.matches("[data-sc-player-add]")) {
        guardRefresh(form);
    }
}
document.addEventListener("input", refreshFrom);
document.addEventListener("change", refreshFrom);
document.addEventListener("focusout", refreshFrom);

const watched = new WeakSet();

// Task 1672: an add panel reset after a create — no stale error / reason.
document.addEventListener("sc:form-reset", (ev) => {
    const form = guardForm(ev.target);
    if (form && !form.matches("[data-sc-player-add]")) {
        guardClearError(form);
        guardRefresh(form);
    }
});

export function guardBoot(root = document) {
    for (const form of root.querySelectorAll(".o_sc_app form[data-sc-guard]")) {
        if (form.matches("[data-sc-player-add]")) {
            continue;
        }
        if (!watched.has(form)) {
            form.noValidate = true;
            ensureSlots(form);
        }
        guardRefresh(form);
        if (!watched.has(form)) {
            // OWL fields mount (and restore their device drafts) after load:
            // re-evaluate when the form's content changes.
            watched.add(form);
            let pending = false;
            new MutationObserver(() => {
                if (!pending) {
                    pending = true;
                    window.requestAnimationFrame(() => {
                        pending = false;
                        guardRefresh(form);
                    });
                }
            }).observe(form, { childList: true, subtree: true });
        }
    }
}
// A sheet / card opened: its form is evaluated on the spot.
document.addEventListener("click", () => window.requestAnimationFrame(() => guardBoot()));
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => guardBoot());
} else {
    guardBoot();
}
// Fragments (task 1611) re-render parts of the page: re-arm new forms.
document.addEventListener("sc:fragments", () => guardBoot());
