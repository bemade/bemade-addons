/*
 * Task 1617 — the timesheets filters panel open on every visit
 * (tests/test_timesheet_filters_open_tours_1617.py), laptop 1366 px and
 * phone 360 px. Language-independent triggers (data attributes, names).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const FORM = 'form[data-sc-section="timesheets.filters"]';
const PANEL = `${FORM} details.o_sc_disclosure`;
const HEADER = '.o_sc_list_header[data-sc-section="timesheets.header"]';

function checkOpenLayout() {
    const details = document.querySelector(PANEL);
    assert(details && details.open, "the filters panel is not open on arrival");
    const header = document.querySelector(HEADER);
    const top = header.getBoundingClientRect().top + window.scrollY;
    console.log(`sc_1617: list header top ${Math.round(top)}px / viewport ${window.innerHeight}px`);
    if (window.innerWidth < 576) {
        // Phone: the compact « Group by » row keeps the panel short.
        const group = document.querySelector(`${PANEL} fieldset[data-sc-section="timesheets.group"]`);
        const select = group.querySelector("select");
        const legend = group.querySelector("legend");
        const s = select.getBoundingClientRect();
        const l = legend.getBoundingClientRect();
        assert(Math.abs((s.top + s.height / 2) - (l.top + l.height / 2)) < 8 && l.right <= s.left,
            "the « Group by » legend and select are not on one row");
        assert(top <= 470, `the open panel pushes the list too far down (${Math.round(top)}px)`);
    }
    assert(top + 44 <= window.innerHeight,
        `the open panel pushes the list header off the first screen (${Math.round(top)}px)`);
    assert(document.documentElement.scrollWidth <= window.innerWidth + 0.5,
        "the page scrolls sideways");
}

tours.add("sc_1617_timesheet_filters", {
    steps: () => [
        {
            content: "Open on arrival, the list header still on the first screen",
            trigger: `${PANEL}[open]`,
            run: checkOpenLayout,
        },
        {
            content: "Collapse the panel",
            trigger: `${PANEL}[open] > summary`,
            run: "click",
        },
        {
            content: "Collapsed",
            trigger: `${PANEL}:not([open])`,
            run() {
                window.location.href = "/my/sc/timesheets";
            },
            expectUnloadPage: true,
        },
        {
            content: "Open again on the next visit",
            trigger: `${PANEL}[open]`,
            run: checkOpenLayout,
        },
        {
            content: "A filter change applies the filters",
            trigger: `${PANEL}[open] select[name="group_by"]`,
            run: "select team",
            expectUnloadPage: true,
        },
        {
            content: "Applied, the panel open",
            trigger: `${PANEL}[open] select[name="group_by"]`,
            run() {
                assert(new URLSearchParams(window.location.search).get("group_by") === "team",
                    "the group by was not applied");
            },
        },
    ],
});
