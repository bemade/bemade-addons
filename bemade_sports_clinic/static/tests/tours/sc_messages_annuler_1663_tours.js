/*
 * Task 1663 — « Annuler » after an announcement archive, and an activity's
 * « Delete » with its confirm (tests/test_messages_annuler_1663.py, phone).
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

tours.add("sc_1663_announcement_undo", {
    steps: () => [
        {
            content: "The announcement is there; archive it",
            trigger: ".o_sc_announcement_body:contains(Synthetic tour announcement)",
            expectUnloadPage: true,
            run() {
                document.querySelector('[data-sc-section="team.announcement.archive"] button[type="submit"]').click();
            },
        },
        {
            content: "Archived at once; the toast offers « Undo »",
            trigger: '.o_sc_toast:not([hidden]) button[data-sc-toast-action]',
            expectUnloadPage: true,
            run() {
                assert(!document.querySelector(".o_sc_announcement_body"), "the announcement is still shown");
                assert(!window.location.search.includes("announcement_archived"), "the address still offers the undo");
                this.anchor.click();
            },
        },
        {
            content: "The announcement is back",
            trigger: ".o_sc_announcement_body:contains(Synthetic tour announcement)",
        },
    ],
});

tours.add("sc_1663_activity_delete", {
    steps: () => [
        {
            content: "« Delete » on the activity page",
            trigger: 'button[data-sc-action="activity.cancel"]:contains(Delete)',
            run: "click",
        },
        {
            content: "The confirm: « Delete this activity? » / « Yes, delete »",
            trigger: "#sc_activity_cancel_sheet[open] button[data-sc-action='activity.cancel.confirm']",
            expectUnloadPage: true,
            run() {
                const sheet = document.getElementById("sc_activity_cancel_sheet");
                assert(sheet.textContent.includes("Delete this activity?"), "confirm message missing");
                assert(this.anchor.textContent.trim() === "Yes, delete", `button reads ${this.anchor.textContent}`);
                this.anchor.click();
            },
        },
        {
            content: "Deleted: the page says so",
            trigger: ".o_sc_banner:contains(Activity deleted.)",
        },
    ],
});
