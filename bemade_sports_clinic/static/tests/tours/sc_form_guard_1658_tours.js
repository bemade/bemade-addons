/*
 * Task 1658 — the app-wide form rule in a browser
 * (tests/test_form_guard_1658.py, phone 390 px): a primary action greyed
 * with its reason until it can succeed; a forced server refusal shows IN the
 * form, the typed values kept, no page change; a valid submit goes through.
 *
 * Real phone taps stay UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function type(el, value) {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function q(selector) {
    const el = document.querySelector(selector);
    assert(el, `missing ${selector}`);
    return el;
}

function submitOf(form) {
    return form.querySelector("[data-sc-guard-submit]") || form.querySelector('button[type="submit"]:not([formaction])');
}

function reasonOf(form) {
    const line = form.querySelector("[data-sc-guard-reason]");
    return line && !line.hidden ? line.textContent.trim() : "";
}

function assertBlocked(form, includes) {
    const submit = submitOf(form);
    assert(submit.getAttribute("aria-disabled") === "true", "the primary action is not greyed");
    const line = form.querySelector("[data-sc-guard-reason]");
    assert(line && submit.getAttribute("aria-describedby") === line.id, "aria-describedby → reason line");
    const reason = reasonOf(form);
    assert(reason && (!includes || reason.includes(includes)), `reason « ${reason} » lacks « ${includes} »`);
    // Never a dead click: clicking keeps the page and flashes the reason.
    const href = window.location.href;
    submit.click();
    assert(window.location.href === href, "a greyed click navigated");
}

function assertReady(form) {
    assert(submitOf(form).getAttribute("aria-disabled") === "false", `still greyed: ${reasonOf(form)}`);
    assert(!reasonOf(form), "a reason is still shown");
}

function errorShown(form, includes) {
    const box = form.querySelector("[data-sc-guard-error]");
    const fieldError = form.querySelector("[data-sc-guard-field-error]");
    const text = ((box && !box.hidden && box.textContent) || (fieldError && fieldError.textContent) || "").trim();
    return Boolean(text) && (!includes || text.includes(includes));
}

// ------------------------------------------------------------- contact
const CONTACT = 'details#sc_contact_add form[data-sc-form="contact.add"]';
tours.add("sc_1658_contact", {
    steps: () => [
        {
            content: "« + Ajouter » of the contacts",
            trigger: 'button.o_sc_list_add[aria-controls="sc_contact_add"]',
            run: "click",
        },
        {
            content: "Open « Add Emergency Contact »: greyed, reason names the missing name",
            trigger: `${CONTACT} [name="name"]`,
            run() {
                const form = q(CONTACT);
                type(form.querySelector('[name="name"]'), "");
                assertBlocked(form, "Name");
            },
        },
        {
            content: "Fill it with an invalid mobile: ready; the server refuses in the form",
            trigger: `${CONTACT} [name="name"]`,
            run() {
                const form = q(CONTACT);
                type(form.querySelector('[name="name"]'), "Synthetic Parent");
                const kind = form.querySelector('[name="contact_type"]');
                type(kind, kind.querySelector("option[value]:not([value=''])").value);
                type(form.querySelector('[name="mobile"]'), "12");
                assertReady(form);
                window.__sc1658Url = window.location.href;
                submitOf(form).click();
            },
        },
        {
            content: "The refusal is in the form, values kept, same page",
            trigger: `${CONTACT} [data-sc-guard-error]:not([hidden])`,
            run() {
                const form = q(CONTACT);
                assert(errorShown(form), "no error text");
                assert(form.querySelector('[name="name"]').value === "Synthetic Parent", "the name was lost");
                assert(form.querySelector('[name="mobile"]').value === "12", "the mobile was lost");
                assert(window.location.href === window.__sc1658Url, "the page changed");
            },
        },
        {
            content: "A valid mobile: saved (the page reloads with the contact)",
            trigger: `${CONTACT} [name="mobile"]`,
            expectUnloadPage: true,
            run() {
                const form = q(CONTACT);
                type(form.querySelector('[name="mobile"]'), "514 555 0142");
                assertReady(form);
                submitOf(form).click();
            },
        },
        {
            content: "The contact is listed",
            trigger: '[data-sc-section="player.contacts"] [data-sc-contact-id]',
        },
    ],
});

// ----------------------------------------------------------- timesheet
const TS = 'dialog#sc_ts_add_sheet form[data-sc-form="timesheet.add"]';
tours.add("sc_1658_timesheet", {
    steps: () => [
        {
            content: "Open the add sheet",
            trigger: 'button[data-sc-action="timesheet.add"][data-sc-sheet-open]',
            run: "click",
        },
        {
            content: "Coverage end before its start: greyed with the reason",
            trigger: `dialog#sc_ts_add_sheet[open] ${TS.replace("dialog#sc_ts_add_sheet ", "")}`,
            run() {
                const form = q(TS);
                type(form.querySelector('[name="travel_start"]'), "2026-03-03T09:00");
                type(form.querySelector('[name="coverage_start"]'), "2026-03-03T10:00");
                type(form.querySelector('[name="coverage_end"]'), "2026-03-03T09:30");
                type(form.querySelector('[name="travel_end"]'), "2026-03-03T12:00");
                assertBlocked(form, "");
            },
        },
        {
            content: "Fixed, but travel time on a clinic: the server refuses in the sheet",
            trigger: `${TS} [name="coverage_end"]`,
            run() {
                const form = q(TS);
                type(form.querySelector('[name="coverage_end"]'), "2026-03-03T11:00");
                assertReady(form);
                window.__sc1658Url = window.location.href;
                submitOf(form).click();
            },
        },
        {
            content: "The refusal is in the sheet, values kept, same page",
            trigger: `${TS} [data-sc-guard-error]:not([hidden])`,
            run() {
                const form = q(TS);
                assert(errorShown(form), "no error text");
                assert(form.querySelector('[name="coverage_end"]').value === "2026-03-03T11:00", "value lost");
                assert(document.querySelector("dialog#sc_ts_add_sheet").open, "the sheet closed");
                assert(window.location.href === window.__sc1658Url, "the page changed");
            },
        },
    ],
});

// -------------------------------------------------------------- injury
const INJ = 'form[data-sc-form="injury.quick"]';
tours.add("sc_1658_injury", {
    steps: () => [
        {
            content: "« + Ajouter » of the injuries",
            trigger: 'button.o_sc_list_add[aria-controls="sc_new_injury"]',
            run: "click",
        },
        {
            content: "Open « Add Injury »: greyed until the visibility is chosen",
            trigger: `details[open] ${INJ}`,
            run() {
                assertBlocked(q(INJ), "");
            },
        },
        {
            content: "Choose and type: ready; a forced refusal (an unknown player) stays in the form",
            trigger: `${INJ} .o_sc_choice_option`,
            run() {
                const form = q(INJ);
                const radio = form.querySelector('input[name="coach_visibility"][value="visible"]');
                radio.checked = true;
                radio.dispatchEvent(new Event("change", { bubbles: true }));
                type(form.querySelector('[name="diagnosis"]'), "Synthetic sprain 1658");
                assertReady(form);
                form.querySelector('[name="patient_id"]').value = "999999999";
                window.__sc1658Url = window.location.href;
                submitOf(form).click();
            },
        },
        {
            content: "The refusal is in the form, the diagnosis kept, same page",
            trigger: `${INJ} [data-sc-guard-error]:not([hidden])`,
            run() {
                const form = q(INJ);
                assert(form.querySelector('[name="diagnosis"]').value === "Synthetic sprain 1658", "value lost");
                assert(window.location.href === window.__sc1658Url, "the page changed");
            },
        },
    ],
});

// ------------------------------------------------------- event create
const EV = 'form[data-sc-form="event.form"]';
tours.add("sc_1658_event", {
    steps: () => [
        {
            content: "Empty form: greyed (name, start, end)",
            trigger: EV,
            run() {
                const form = q(EV);
                type(form.querySelector('[name="name"]'), "");
                assertBlocked(form, "");
            },
        },
        {
            content: "End before start: greyed with the dates reason",
            trigger: `${EV} [name="name"]`,
            run() {
                const form = q(EV);
                type(form.querySelector('[name="name"]'), "Synthetic game 1658");
                type(form.querySelector('[name="date_start"]'), "2026-03-04T18:00");
                type(form.querySelector('[name="date_end"]'), "2026-03-04T17:00");
                assertBlocked(form, "");
            },
        },
        {
            content: "Valid dates but no team: the server refuses in the form",
            trigger: `${EV} [name="date_end"]`,
            run() {
                const form = q(EV);
                type(form.querySelector('[name="date_end"]'), "2026-03-04T20:00");
                form.querySelector('[name="team_ids"]').value = "";
                assertReady(form);
                window.__sc1658Url = window.location.href;
                submitOf(form).click();
            },
        },
        {
            content: "The refusal is in the form, the name kept, same page",
            trigger: `${EV} [data-sc-guard-error]:not([hidden])`,
            run() {
                const form = q(EV);
                assert(form.querySelector('[name="name"]').value === "Synthetic game 1658", "value lost");
                assert(window.location.href === window.__sc1658Url, "the page changed");
            },
        },
    ],
});

// -------------------------------------------------------- announcement
const ANN = 'form[data-sc-guard][action$="/announcement"]';
tours.add("sc_1658_announcement", {
    steps: () => [
        {
            content: "Edit the announcement: empty → greyed",
            trigger: '[data-sc-edit-card="announcement"] [data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Greyed while empty",
            trigger: `${ANN} textarea[name="announcement"]`,
            run() {
                const form = q(ANN);
                type(form.querySelector('textarea[name="announcement"]'), "");
                assertBlocked(form, "");
            },
        },
        {
            content: "Typed: ready; publish",
            trigger: `${ANN} textarea[name="announcement"]`,
            expectUnloadPage: true,
            run() {
                const form = q(ANN);
                type(form.querySelector('textarea[name="announcement"]'), "Synthetic bus at 7 (1658)");
                assertReady(form);
                submitOf(form).click();
            },
        },
        {
            content: "Published",
            trigger: ".o_sc_announcement_body:contains(Synthetic bus at 7 (1658))",
        },
    ],
});

// ---------------------------------------------- activity (reassign sheet)
const RE = 'dialog#sc_activity_reassign_sheet form[data-sc-form="activity.reassign"]';
tours.add("sc_1658_activity", {
    steps: () => [
        {
            content: "Reassign an activity",
            trigger: 'button[data-sc-action="activity.reassign"]',
            run: "click",
        },
        {
            content: "No one chosen: greyed",
            trigger: `dialog#sc_activity_reassign_sheet[open] select[name="new_user_id"]`,
            run() {
                assertBlocked(q(RE), "");
            },
        },
        {
            content: "Someone the server will refuse: the refusal is in the sheet",
            trigger: `${RE} select[name="new_user_id"]`,
            run() {
                const form = q(RE);
                const select = form.querySelector('select[name="new_user_id"]');
                // A real user outside my assignable list (the test passes
                // its id): the server answers ?error=invalid_user.
                const outsider = new URLSearchParams(window.location.search).get("x1658");
                const option = document.createElement("option");
                option.value = outsider;
                option.textContent = "Outsider 1658";
                select.appendChild(option);
                type(select, outsider);
                assertReady(form);
                window.__sc1658Url = window.location.href;
                submitOf(form).click();
            },
        },
        {
            content: "In the sheet, same page",
            trigger: `${RE} [data-sc-guard-error]:not([hidden])`,
            run() {
                assert(document.querySelector("dialog#sc_activity_reassign_sheet").open, "the sheet closed");
                assert(window.location.href === window.__sc1658Url, "the page changed");
            },
        },
    ],
});
