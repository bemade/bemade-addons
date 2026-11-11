/*
 * Owner review 2026-10-14 — app shell form behaviours (progressive
 * enhancement; inert outside .o_pk_app):
 *
 * - filter forms (form[data-pk-autosubmit]: the events list and calendar
 *   filter bar, the clinics and the timesheets filters) apply AS SOON AS
 *   they change: a select / checkbox on change; a date input once its value
 *   is complete — when the user leaves it, presses Enter or picks in the
 *   picker, never while typing (the day « 15 » would apply « 01 » first) and
 *   never with a half-typed value. Text boxes keep « Enter ». The « Apply
 *   filters » button ([data-pk-autosubmit-fallback]) is only hidden here:
 *   without JS it is still there; with JS it stays in the form (visually
 *   hidden) so « Enter » still submits. The filter panel stays open across
 *   the reload a change causes.
 * - Review round 1 (2026-10-26, #1679): a filter panel's « Reset » link
 *   ([data-pk-filter-reset], any filter form: events, calendar, timesheets,
 *   clinics, players) keeps the panel as it was — open stays open across
 *   the reload (closed stays closed: the defaults open nothing).
 */

const DATE_TYPES = ["date", "datetime-local", "time", "month", "week"];
const OPEN_KEY = "pk_filters_open:";

function inApp(el) {
    return Boolean(el && el.closest(".o_pk_app"));
}

function isDateInput(el) {
    return el instanceof HTMLInputElement && DATE_TYPES.includes(el.type);
}

function autosubmitForm(el) {
    const form = el && el.closest && el.closest("form[data-pk-autosubmit]");
    return form && inApp(form) ? form : null;
}

function rememberOpen(form) {
    const details = form.querySelector("details.o_pk_disclosure");
    try {
        if (details && details.open) {
            window.sessionStorage.setItem(OPEN_KEY + (form.dataset.pkSection || ""), "1");
        }
    } catch {
        // Storage refused (private mode): the panel just closes.
    }
}

function applyFilters(form) {
    if (form.dataset.pkSubmitting) {
        return;
    }
    for (const input of form.querySelectorAll("input")) {
        if (isDateInput(input) && input.validity && input.validity.badInput) {
            return; // a half-typed date: wait until it is complete
        }
    }
    form.dataset.pkSubmitting = "1";
    rememberOpen(form);
    if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
    } else {
        form.submit();
    }
}

// Review round 1 (#1679): « Reset » keeps an open filter panel open.
document.addEventListener("click", (ev) => {
    const link = ev.target instanceof Element && ev.target.closest("a[data-pk-filter-reset]");
    const form = link && inApp(link) ? link.closest("form") : null;
    if (form) {
        rememberOpen(form);
    }
});

// A date being typed (keyboard): its « change » is not the final value.
const typing = new WeakSet();

document.addEventListener("keydown", (ev) => {
    const form = autosubmitForm(ev.target);
    if (!form || !isDateInput(ev.target)) {
        return;
    }
    if (ev.key === "Enter") {
        ev.preventDefault();
        typing.delete(ev.target);
        applyFilters(form);
    } else if (ev.key !== "Tab" && ev.key !== "Shift") {
        typing.add(ev.target);
    }
});

document.addEventListener("pointerdown", (ev) => {
    if (autosubmitForm(ev.target) && isDateInput(ev.target)) {
        typing.delete(ev.target); // opening the picker: the next change is a pick
    }
});

document.addEventListener("focusout", (ev) => {
    const form = autosubmitForm(ev.target);
    if (!form || !isDateInput(ev.target)) {
        return;
    }
    typing.delete(ev.target);
    // Applied when it differs from the value the page was loaded with.
    if (ev.target.value !== ev.target.defaultValue) {
        applyFilters(form);
    }
});

document.addEventListener("change", (ev) => {
    const target = ev.target;
    const form = autosubmitForm(target);
    if (!form) {
        return;
    }
    if (isDateInput(target)) {
        if (!typing.has(target)) {
            applyFilters(form); // picked in the picker
        }
        return;
    }
    if (target instanceof HTMLSelectElement || (target instanceof HTMLInputElement
            && ["checkbox", "radio"].includes(target.type))) {
        applyFilters(form);
    }
});

function init() {
    for (const button of document.querySelectorAll(".o_pk_app [data-pk-autosubmit-fallback]")) {
        button.classList.add("visually-hidden");
        button.tabIndex = -1;
    }
    const forms = new Set(document.querySelectorAll(".o_pk_app form[data-pk-autosubmit]"));
    for (const link of document.querySelectorAll(".o_pk_app form a[data-pk-filter-reset]")) {
        forms.add(link.closest("form"));
    }
    for (const form of forms) {
        const key = OPEN_KEY + (form.dataset.pkSection || "");
        let reopen = false;
        try {
            reopen = window.sessionStorage.getItem(key) === "1";
            window.sessionStorage.removeItem(key);
        } catch {
            reopen = false;
        }
        const details = form.querySelector("details.o_pk_disclosure");
        if (reopen && details) {
            details.open = true;
        }
    }
}

// Back from the next page (bfcache): the form may be applied again.
window.addEventListener("pageshow", () => {
    for (const form of document.querySelectorAll("form[data-pk-autosubmit][data-pk-submitting]")) {
        delete form.dataset.pkSubmitting;
    }
});

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
