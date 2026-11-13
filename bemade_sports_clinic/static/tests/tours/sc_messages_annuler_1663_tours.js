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
                document.querySelector('[data-pk-section="team.announcement.archive"] button[type="submit"]').click();
            },
        },
        {
            content: "Archived at once; the toast offers « Undo »",
            trigger: '.o_pk_toast:not([hidden]) button[data-pk-toast-action]',
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
            // Task 1736 (deliberate update): the delete is the card's red
            // trash, shown while the activity is being edited.
            content: "The activity card's pencil",
            trigger: '[data-pk-edit-card="activity"] [data-sc-card-icons] button[data-pk-edit-toggle]',
            run: "click",
        },
        {
            content: "« Delete » (the trash) on the activity page",
            trigger: '[data-pk-edit-card="activity"][data-pk-edit-open] button[data-sc-action="activity.cancel"][aria-label="Delete"]:visible',
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
            trigger: ".o_pk_banner:contains(Activity deleted.)",
        },
    ],
});
