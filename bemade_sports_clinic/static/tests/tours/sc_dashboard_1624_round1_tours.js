/*
 * Task 1624, owner UAT round 1 (2026-10-29) — the dashboard in a browser
 * (tests/test_dashboard_tours_1624.py, phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers.
 *
 * « Suivre » a player from its card's « Details » (fetch, no reload), open
 * an « À faire » line into its activity cards, fold out an event's
 * « Details », then « Add my timesheet » on « Feuilles de temps
 * manquantes » lands on the event with its add-timesheet sheet open.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function noHorizontalScroll() {
    const doc = document.documentElement;
    assert(doc.scrollWidth <= doc.clientWidth + 1, `horizontal scroll (${doc.scrollWidth} > ${doc.clientWidth})`);
}

const WATCH = 'section[data-sc-instance="watch"]';
const TODO = 'section[data-sc-instance="todo"]';

tours.add("sc_1624_dashboard_round1", {
    steps: () => [
        {
            content: "The dashboard, in the default order (round 2: zone by zone)",
            trigger: 'section[data-sc-instance="indicators"]',
            run() {
                const ids = [...document.querySelectorAll("section[data-sc-instance]")].map((el) => el.dataset.scInstance);
                assert(ids[0] === "today" && ids[1] === "todo" && ids[2] === "coverage", `order: ${ids}`);
                window.__sc1624NoReload = true;
                noHorizontalScroll();
            },
        },
        {
            content: "Open a player card's « Details »",
            trigger: `${WATCH} .o_sc_player_row button[data-sc-row-expand]`,
            run: "click",
        },
        {
            content: "« Follow » in the details",
            trigger: `${WATCH} .o_sc_row_detail:not([hidden]) button[data-sc-follow][data-sc-followed="0"]`,
            run: "click",
        },
        {
            content: "Followed in place (no reload)",
            trigger: `${WATCH} .o_sc_row_detail:not([hidden]) button[data-sc-follow][data-sc-followed="1"]`,
            run() {
                assert(window.__sc1624NoReload, "the page reloaded");
                const on = this.anchor.querySelector('[data-sc-follow-label="on"]');
                assert(on && !on.hidden, "the « Unfollow » label shows");
            },
        },
        {
            content: "Open « Overdue activities »",
            trigger: `${TODO} details[data-sc-todo="activities_overdue"] > summary`,
            run: "click",
        },
        {
            content: "Its activity cards, with their actions",
            trigger: `${TODO} details[data-sc-todo="activities_overdue"][open] [data-sc-activity-row] button[data-sc-action="activity.reschedule"]`,
            run: "click",
        },
        {
            content: "The « Reschedule » sheet opens on the dashboard",
            trigger: "dialog#sc_activity_reschedule_sheet[open]",
            run() {
                assert(this.anchor.querySelector('input[name="activity_id"]').value, "the activity is set");
                this.anchor.querySelector("[data-sc-sheet-close]").click();
            },
        },
        {
            content: "Fold out an upcoming event's « Details »",
            trigger: 'section[data-sc-instance="coverage"] [data-sc-event-row] button[data-sc-row-expand]',
            run: "click",
        },
        {
            content: "The event's details",
            trigger: 'section[data-sc-instance="coverage"] [data-sc-event-details]:not([hidden]) [data-sc-ev-field="staff"]',
            run() {
                assert(this.anchor.textContent.trim() && this.anchor.textContent.trim() !== "—", "assigned staff");
                noHorizontalScroll();
            },
        },
        {
            content: "« Add my timesheet » on a missing one",
            trigger: 'section[data-sc-instance="missing_timesheets"] a[data-sc-action="dashboard.timesheet.add"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The event page, its add-timesheet sheet open",
            trigger: "dialog#sc_ts_add_sheet[open] form[data-sc-form='timesheet.add']",
        },
    ],
});
