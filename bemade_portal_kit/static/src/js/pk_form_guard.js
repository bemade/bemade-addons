/*
 * The app-wide form rule (moved to the kit by task 5370, P4b): a form's
 * primary action stays greyed (aria-disabled + aria-describedby, never a
 * dead click) with a short reason line until it can succeed; a server
 * refusal shows INSIDE the form, the typed values kept, no page change.
 * Inert outside .o_pk_app.
 *
 * Declarative, on the form (form[data-pk-guard]):
 *
 * - a field marked required (the HTML « required » attribute, or
 *   data-pk-required) must hold a value (a checkbox ticked; a radio group:
 *   one of its buttons checked; a file input: a file). Its name in the
 *   reason is data-pk-required's value when it is a label, else the text of
 *   its <label> (for=id, else the field's own label);
 * - data-pk-guard-rules='[…]' (JSON), each rule {"type": …} evaluated by
 *   the rule of that name in registry.category("pk_guard_rules"). The kit
 *   registers:
 *     {"type": "required", "field": "note", "label": "…"}
 *         a named field (e.g. one an OWL component renders) must hold a
 *         value;
 *     {"type": "together", "fields": ["a", "b"], "key": "…"}
 *         all or none of these named fields filled;
 *     {"type": "after", "field": "date_end", "than": "date_start", "message": "…"}
 *         the field's value is not before the other's (ISO dates sort);
 *     {"type": "not_future", "field": "resolution_date", "message": "…"}
 *         a date not after today (the device's day).
 *   A rule's text: "message", or "key" naming a hidden
 *   <span data-pk-guard-msg="<key>"> of the form (translated there).
 *   A consumer adds its own rules to the same registry; an entry is
 *   { missing(rule, ctx) -> the label of a missing value, or "" } or
 *   { check(rule, ctx) -> the reason the form is held, or "" }, where ctx =
 *   { form, named(name), hasValue(el), labelOf(el), message(rule), today() }.
 *   The missing values are listed first (« Complete: A, B »), then the
 *   fields' own blocks (data-pk-guard-block), then the first check that
 *   holds the form, in the form's order. An unknown type is ignored;
 * - the texts: the reason's prefix and the generic / offline errors come
 *   from the page's [data-pk-guard-texts] host (data-missing, -generic,
 *   -offline, translated there; the kit's own texts otherwise); a form may
 *   override them (data-pk-guard-missing / -generic / -offline). The host
 *   also names the URL params a refusal may come back in
 *   (data-pk-guard-error-params="error other_error"; default « error »);
 * - the submit button [data-pk-guard-submit] (default: the form's first
 *   submit button) gets aria-disabled and aria-describedby → the reason line
 *   [data-pk-guard-reason]; [data-pk-guard-error] is the server-error slot
 *   (the pk_form_guard_slots template renders both; created here when
 *   absent);
 * - with JS the form is novalidate: the reason line replaces the browser's
 *   bubbles (without JS the native validation stays);
 * - data-pk-guard-mode="fetch": the form is posted with fetch to its OWN
 *   action with its OWN fields (every form keeps its POST contract); the
 *   answer is read: a refusal (the page it lands on carries the error —
 *   [data-pk-flash-error] (its text, or the message it carries as its
 *   value: a toast), [data-pk-error-for] / [data-pk-field-error] (under that
 *   field), an error param, or an HTTP error) is shown in the form and
 *   nothing else moves; a success navigates to where the server sent it.
 *   The request carries X-Pk-Guard so that page does not consume its
 *   one-time session state (PortalKitApp._pk_guard_probe()). Default mode
 *   « native »: only the disabled state + reason (the native POST and its
 *   no-JS fallback stay as they are);
 * - data-pk-guard-mode="manual": a form whose own script drives it (its own
 *   checks and submit) — the guard leaves it alone and the script uses the
 *   exported helpers (guardRefresh, guardFlash, guardShowError…).
 *
 * The client rules are a convenience: the server validations stay the
 * source of truth (and every server refusal surfaces in-form).
 */
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export const GUARD_HEADER = "X-Pk-Guard";
const guardRules = registry.category("pk_guard_rules");
const posting = new WeakSet();

function inApp(form) {
    return Boolean(form && form.closest && form.closest(".o_pk_app"));
}

function isManual(form) {
    return form.dataset.pkGuardMode === "manual";
}

export function guardForm(target) {
    const form = target && target.closest && target.closest("form[data-pk-guard]");
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

function textsHost() {
    return document.querySelector("[data-pk-guard-texts]");
}

function texts(form) {
    const shared = (textsHost() || {}).dataset || {};
    const generic = form.dataset.pkGuardGeneric || shared.generic || String(_t("This could not be saved. Please check the form and try again."));
    return {
        missing: form.dataset.pkGuardMissing || shared.missing || String(_t("Complete:")),
        generic,
        offline:
            form.dataset.pkGuardOffline ||
            shared.offline ||
            String(_t("No connection. Nothing was sent; try again when you are back online.")),
    };
}

/** The URL params a refusal may come back in: « error » + the texts host's. */
export function guardErrorParams() {
    const host = textsHost();
    const extra = ((host && host.dataset.pkGuardErrorParams) || "").split(/\s+/).filter(Boolean);
    return ["error", ...extra.filter((name) => name !== "error")];
}

function labelOf(el, form) {
    const own = el.dataset.pkRequired;
    if (own && own !== "1") {
        return own;
    }
    const fieldset = (el.type === "radio" || el.type === "checkbox") && el.closest("fieldset");
    const legend = fieldset && fieldset.querySelector("legend");
    if (legend) {
        return legend.textContent.replace(/\s+/g, " ").trim();
    }
    const byFor = el.id && form.querySelector(`label[for="${el.id}"]`);
    const label = byFor || (el.closest(".o_pk_field") || el.parentElement || form).querySelector("label, .o_pk_field_label");
    return ((label && label.textContent) || el.name || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
}

function named(form, name) {
    return form.querySelector(`[name="${name}"]`);
}

function rules(form) {
    if (!form.dataset.pkGuardRules) {
        return [];
    }
    try {
        return JSON.parse(form.dataset.pkGuardRules) || [];
    } catch {
        return [];
    }
}

function today() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function ruleContext(form) {
    return {
        form,
        named: (name) => named(form, name),
        hasValue: (el) => hasValue(el, form),
        labelOf: (el) => labelOf(el, form),
        message: (rule) =>
            rule.message ||
            ((rule.key && form.querySelector(`[data-pk-guard-msg="${rule.key}"]`)) || {}).textContent ||
            "",
        today,
    };
}

function ruleOf(rule) {
    return (rule && rule.type && guardRules.get(rule.type, null)) || null;
}

/** Why the form can't succeed yet ("" = it can). */
export function guardReason(form) {
    const missing = [];
    const seen = new Set();
    for (const el of form.querySelectorAll("[required], [data-pk-required]")) {
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
    const ctx = ruleContext(form);
    const formRules = rules(form);
    for (const rule of formRules) {
        const entry = ruleOf(rule);
        const label = entry && entry.missing ? entry.missing(rule, ctx) : "";
        if (label && !seen.has(label)) {
            missing.push(label);
            seen.add(label);
        }
    }
    if (missing.length) {
        return `${texts(form).missing} ${missing.join(", ")}`.trim();
    }
    // Task 1723: a field that refuses its own input (a tags box with typed
    // text matching nothing) blocks with its message.
    for (const el of form.querySelectorAll("[data-pk-guard-block]")) {
        if (el.dataset.pkGuardBlock && !el.closest("[hidden]")) {
            return el.dataset.pkGuardBlock;
        }
    }
    for (const rule of formRules) {
        const entry = ruleOf(rule);
        const reason = entry && entry.check ? (entry.check(rule, ctx) || "").trim() : "";
        if (reason) {
            return reason;
        }
    }
    return "";
}

// The kit's rules.
guardRules.add("required", {
    missing(rule, ctx) {
        const el = ctx.named(rule.field);
        const label = rule.label || (el ? ctx.labelOf(el) : rule.field);
        return !el || !ctx.hasValue(el) ? label : "";
    },
});
guardRules.add("together", {
    check(rule, ctx) {
        const filled = (rule.fields || []).map((name) => {
            const el = ctx.named(name);
            return Boolean(el && (el.value || "").trim());
        });
        return filled.some(Boolean) && !filled.every(Boolean) ? ctx.message(rule) : "";
    },
});
guardRules.add("after", {
    check(rule, ctx) {
        const a = ctx.named(rule.field);
        const b = ctx.named(rule.than);
        return a && b && a.value && b.value && a.value < b.value ? ctx.message(rule) : "";
    },
});
guardRules.add("not_future", {
    check(rule, ctx) {
        const el = ctx.named(rule.field);
        return el && el.value && el.value.slice(0, 10) > ctx.today() ? ctx.message(rule) : "";
    },
});

let slotSeq = 0;

/** The reason line + error slot (pk_form_guard_slots), created when the
 * template did not render them. */
function ensureSlots(form) {
    const submit = submitButton(form);
    if (!submit) {
        return;
    }
    const anchor = submit.closest(".o_pk_form_actions") || submit;
    if (!form.querySelector("[data-pk-guard-error]")) {
        const box = document.createElement("p");
        box.className = "o_pk_field_message o_pk_field_error";
        box.setAttribute("role", "alert");
        box.dataset.pkGuardError = "1";
        box.hidden = true;
        anchor.insertAdjacentElement("beforebegin", box);
    }
    if (!form.querySelector("[data-pk-guard-reason]")) {
        const line = document.createElement("p");
        line.className = "o_pk_hint o_pk_guard_reason";
        line.id = `pk_guard_reason_${++slotSeq}`;
        line.setAttribute("aria-live", "polite");
        line.dataset.pkGuardReason = "1";
        line.hidden = true;
        anchor.insertAdjacentElement("afterend", line);
    }
}

function submitButton(form) {
    return form.querySelector("[data-pk-guard-submit]") || form.querySelector('button[type="submit"]:not([formaction])');
}

function reasonLine(form) {
    return form.querySelector("[data-pk-guard-reason]");
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
        line.classList.remove("o_pk_reason_flash");
        void line.offsetWidth; // restart the cue
        line.classList.add("o_pk_reason_flash");
    }
}

export function guardClearError(form) {
    for (const el of form.querySelectorAll("[data-pk-guard-field-error]")) {
        el.remove();
    }
    for (const el of form.querySelectorAll('[aria-invalid="true"][data-pk-guard-invalid]')) {
        el.removeAttribute("aria-invalid");
        delete el.dataset.pkGuardInvalid;
    }
    const box = form.querySelector("[data-pk-guard-error]");
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
        note.className = "o_pk_field_message o_pk_field_error";
        note.setAttribute("role", "alert");
        note.dataset.pkGuardFieldError = field;
        note.textContent = message;
        input.setAttribute("aria-invalid", "true");
        input.dataset.pkGuardInvalid = "1";
        input.insertAdjacentElement("afterend", note);
        note.scrollIntoView({ block: "nearest" });
        return;
    }
    const box = form.querySelector("[data-pk-guard-error]");
    if (box) {
        box.textContent = message;
        box.hidden = false;
        box.scrollIntoView({ block: "nearest" });
    }
}

/** The refusal carried by the page a fetch-posted form landed on, or null. */
export function guardRefusal(responseUrl, html, status) {
    const doc = new DOMParser().parseFromString(html || "", "text/html");
    const flashes = [...doc.querySelectorAll("[data-pk-flash-error]")];
    // A refusal banner: its text.
    const banner = flashes.find((el) => el.textContent.trim());
    if (banner) {
        return { message: banner.textContent.trim().replace(/\s+/g, " ") };
    }
    // Task 1723: a server-side refusal rendered under its field — read it,
    // so a refused create shows its message and keeps what was typed (never
    // a silent empty reload).
    const fieldError = doc.querySelector("[data-pk-error-for], [data-pk-field-error]");
    if (fieldError && fieldError.textContent.trim()) {
        return {
            message: fieldError.textContent.trim(),
            field: fieldError.dataset.pkErrorFor || fieldError.dataset.pkFieldError || "",
        };
    }
    // A refusal carried as the marker's value (e.g. an error toast, whose
    // text the page's script writes later).
    const carried = flashes.find((el) => el.dataset.pkFlashError && el.dataset.pkFlashError !== "1");
    if (carried) {
        return { message: carried.dataset.pkFlashError };
    }
    let url = null;
    try {
        url = new URL(responseUrl, window.location.origin);
    } catch {
        url = null;
    }
    for (const key of guardErrorParams()) {
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
            headers: { [GUARD_HEADER]: "1", Accept: "text/html" },
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
        form.dispatchEvent(new CustomEvent("pk:create-success", { bubbles: true }));
        // Task 1741: a target that differs from this page by its #fragment
        // only would not load (a same-document navigation): the page would
        // stay stale and its pending notification would pop on a LATER page.
        // Reload instead.
        const here = new URL(window.location.href);
        const there = new URL(target, here);
        if (there.hash && there.href.split("#")[0] === here.href.split("#")[0]) {
            window.history.replaceState(window.history.state, "", there.href);
            window.location.reload();
            return;
        }
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
        if (!form || isManual(form)) {
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
        if (form.dataset.pkGuardMode === "fetch") {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            post(form, ev.submitter);
        }
    },
    true
);

function refreshFrom(ev) {
    const form = guardForm(ev.target);
    if (form && !isManual(form)) {
        guardRefresh(form);
    }
}
document.addEventListener("input", refreshFrom);
document.addEventListener("change", refreshFrom);
document.addEventListener("focusout", refreshFrom);

const watched = new WeakSet();

// Task 1672: an add panel reset after a create — no stale error / reason.
document.addEventListener("pk:form-reset", (ev) => {
    const form = guardForm(ev.target);
    if (form && !isManual(form)) {
        guardClearError(form);
        guardRefresh(form);
    }
});

export function guardBoot(root = document) {
    for (const form of root.querySelectorAll(".o_pk_app form[data-pk-guard]")) {
        if (isManual(form)) {
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
// Fragments re-render parts of the page: re-arm new forms.
document.addEventListener("pk:fragments", () => guardBoot());
