/*
 * Task 1679 — events & timesheets polish (tests/test_events_polish_1679.py,
 * phone 390 px). Real phone taps stay UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(el) {
    const rect = el.getBoundingClientRect();
    return rect.width > 1 && rect.height > 1 && getComputedStyle(el).visibility !== "hidden";
}

tours.add("sc_1679_group_by_once", {
    steps: () => [
        {
            content: "Open the filters",
            trigger: 'form[data-pk-section="events.filters"] summary.o_pk_disclosure_summary',
            run: "click",
        },
        {
            content: "« Group by » is shown once (the legend)",
            trigger: 'fieldset[data-pk-section="events.group"] select#sc_ev_group:visible',
            run() {
                const group = document.querySelector('fieldset[data-pk-section="events.group"]');
                const shown = [...group.querySelectorAll("legend, label")].filter(
                    (el) => visible(el) && el.textContent.trim() === "Group by"
                );
                assert(shown.length === 1, `« Group by » shown ${shown.length} times`);
                assert(shown[0].tagName === "LEGEND", "the visible one must be the legend");
            },
        },
    ],
});

tours.add("sc_1679_toast_clear", {
    steps: () => [
        {
            content: "« Add My Timesheet »",
            trigger: 'button[data-sc-action="timesheet.add"][data-pk-sheet-open]',
            run: "click",
        },
        {
            content: "The toast is up",
            trigger: ".o_pk_toast:not([hidden]) button[data-pk-toast-action]",
        },
        {
            content: "The open card's buttons are above the toast",
            trigger: "[data-sc-timesheet-id][data-pk-edit-card][data-pk-edit-open]",
            run() {
                const card = document.querySelector("[data-sc-timesheet-id][data-pk-edit-card][data-pk-edit-open]");
                const toast = document.querySelector(".o_pk_toast:not([hidden])");
                const bottom = card.getBoundingClientRect().bottom;
                const top = toast.getBoundingClientRect().top;
                console.log(`sc_1679: card bottom ${bottom}, toast top ${top}`);
                assert(bottom < top, `the card (bottom ${bottom}) is under the toast (top ${top})`);
            },
        },
    ],
});

// Review round 1 (2026-10-26): « Reset » keeps an open filter panel open
// (any filter form carrying a[data-pk-filter-reset]).
function resetKeepsOpen(section) {
    const form = `form[data-pk-section="${section}"]`;
    return [
        {
            content: "Open the filters (if closed)",
            trigger: `${form} summary.o_pk_disclosure_summary`,
            run() {
                const details = document.querySelector(`${form} details.o_pk_disclosure`);
                if (!details.open) {
                    details.querySelector("summary").click();
                }
            },
        },
        {
            content: "Tap « Reset »",
            trigger: `${form} a[data-pk-filter-reset]:visible`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The panel is still open after the reload",
            trigger: `${form} details.o_pk_disclosure[open]`,
            run() {
                assert(!document.querySelector(`${form}[data-pk-submitting]`), "a fresh page is expected");
            },
        },
    ];
}

tours.add("sc_1679_reset_keeps_open_events", { steps: () => resetKeepsOpen("events.filters") });
tours.add("sc_1679_reset_keeps_open_players", { steps: () => resetKeepsOpen("players.search") });
tours.add("sc_1679_reset_keeps_open_clinics", { steps: () => resetKeepsOpen("clinics.filters") });

// Review round 1 (2026-10-26): a date input never sticks out of its cell
// (iOS gives it an intrinsic width; the app resets its appearance).
tours.add("sc_1679_date_inputs_fit", {
    steps: () => [
        {
            content: "Open the filters",
            trigger: 'form[data-pk-section="events.filters"] summary.o_pk_disclosure_summary',
            run: "click",
        },
        {
            content: "« From » / « To » fit their cells, appearance reset",
            trigger: "#sc_ev_from:visible",
            run() {
                for (const id of ["sc_ev_from", "sc_ev_to"]) {
                    const input = document.getElementById(id);
                    const cell = input.closest(".o_pk_field").getBoundingClientRect();
                    const box = input.getBoundingClientRect();
                    const style = getComputedStyle(input);
                    assert(box.right <= cell.right + 0.5 && box.left >= cell.left - 0.5,
                        `${id} (${box.left}-${box.right}) overflows its cell (${cell.left}-${cell.right})`);
                    assert(style.minWidth === "0px", `${id} min-width ${style.minWidth}`);
                    assert(["none", ""].includes(style.appearance || style.webkitAppearance || ""),
                        `${id} appearance ${style.appearance}`);
                }
            },
        },
    ],
});
