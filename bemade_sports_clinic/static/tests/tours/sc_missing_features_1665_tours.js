/*
 * Task 1665 — « Add My Timesheet » with an own timesheet already on the
 * event opens THAT card in edit; the toast offers « Add another timesheet »,
 * which opens the add sheet (tests/test_missing_features_1665.py, phone).
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

tours.add("sc_1665_timesheet_existing", {
    steps: () => [
        {
            content: "« Add My Timesheet »",
            trigger: 'button[data-sc-action="timesheet.add"][data-sc-sheet-open]',
            run: "click",
        },
        {
            content: "The existing card is in edit, the add sheet stays closed",
            trigger: "[data-sc-timesheet-id][data-sc-edit-card][data-sc-edit-open]",
            run() {
                const sheet = document.getElementById("sc_ts_add_sheet");
                assert(!sheet.open, "the add sheet opened instead");
            },
        },
        {
            content: "The toast offers « Add another timesheet »",
            trigger: ".o_sc_toast:not([hidden]) button[data-sc-toast-action]:contains(Add another timesheet)",
            run: "click",
        },
        {
            content: "The add sheet is open",
            trigger: "#sc_ts_add_sheet[open] button[data-sc-action='timesheet.add.submit']",
        },
    ],
});
