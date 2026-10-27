/*
 * Review fixes 2026-10-24 (owner policy) — the event form's « assign » guard
 * rule in a browser (tests/test_review_fixes_1024_assign.py, phone 390 px):
 * assignees on a team the user staffs → ready; switch the team to one the
 * user does not staff → « Create » greyed with the clinic-admin reason; no
 * assignees → ready again (creating the event itself stays open).
 * The ids come in the URL (?x1024=<own team>,<other team>,<colleague>).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");
const EV = 'form[data-sc-event-form="1"]';

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

function ids() {
    const [own, other, colleague] = (new URLSearchParams(window.location.search).get("x1024") || "").split(",");
    return { own, other, colleague };
}

function state(form) {
    const submit = form.querySelector('button[type="submit"]:not([formaction])');
    const line = form.querySelector("[data-sc-guard-reason]");
    return {
        blocked: submit.getAttribute("aria-disabled") === "true",
        reason: line && !line.hidden ? line.textContent.trim() : "",
    };
}

tours.add("sc_1024_event_assign", {
    steps: () => [
        {
            content: "Own team + a colleague: ready",
            trigger: `${EV} [name="name"]`,
            run() {
                const form = document.querySelector(EV);
                const { own, colleague } = ids();
                type(form.querySelector('[name="name"]'), "Synthetic game 1024");
                type(form.querySelector('[name="date_start"]'), "2026-03-04T18:00");
                type(form.querySelector('[name="date_end"]'), "2026-03-04T20:00");
                type(form.querySelector('[name="team_ids"]'), own);
                type(form.querySelector('[name="assigned_staff_ids"]'), colleague);
                const now = state(form);
                assert(!now.blocked, `greyed on the own team: ${now.reason}`);
            },
        },
        {
            content: "Another team's event with assignees: greyed with the clinic-admin reason",
            trigger: `${EV} [name="name"]`,
            run() {
                const form = document.querySelector(EV);
                type(form.querySelector('[name="team_ids"]'), ids().other);
                const now = state(form);
                assert(now.blocked, "not greyed on another team's event");
                assert(now.reason.includes("clinic administration"), `reason « ${now.reason} »`);
            },
        },
        {
            content: "No assignees: ready (the event itself may be created)",
            trigger: `${EV} [name="name"]`,
            run() {
                const form = document.querySelector(EV);
                type(form.querySelector('[name="assigned_staff_ids"]'), "");
                const now = state(form);
                assert(!now.blocked, `still greyed: ${now.reason}`);
            },
        },
    ],
});
