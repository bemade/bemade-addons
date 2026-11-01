/*
 * Task 1584 — the event page as a clinic admin (not assigned): every
 * therapist's timesheet, each card naming its therapist, read-only, and the
 * labelled missing-timesheet banner
 * (tests/test_app_shell_event_timesheets_1584.py). Language-independent
 * triggers.
 */
import { registry } from "@web/core/registry";

const SECTION = '.o_sc_app [data-sc-section="event.timesheets"]';

registry.category("web_tour.tours").add("sc_1584_event_timesheets_admin", {
    steps: () => [
        {
            content: "The first therapist's card names them",
            trigger: `${SECTION} [data-sc-timesheet-id] [data-sc-timesheet-employee]:contains("PC TP")`,
        },
        {
            content: "The second therapist's card names them too",
            trigger: `${SECTION} [data-sc-timesheet-id] [data-sc-timesheet-employee]:contains("SC84 Second Therapist")`,
        },
        {
            content: "The missing-timesheet banner is labelled and names who is missing",
            trigger: `${SECTION} [data-sc-missing-timesheets]:has(strong):contains("P77 Internal TP")`,
        },
        {
            content: "Other therapists' timesheets are read-only (no pencil)",
            trigger: `${SECTION} .o_sc_list`,
            run() {
                const cards = document.querySelectorAll(`${SECTION} [data-sc-timesheet-id]`);
                if (cards.length !== 2) {
                    throw new Error(`expected 2 timesheet cards, got ${cards.length}`);
                }
                if (document.querySelector(`${SECTION} [data-sc-edit-toggle]`)) {
                    throw new Error("a pencil is offered on another therapist's timesheet");
                }
            },
        },
    ],
});
