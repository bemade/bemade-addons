/*
 * Task 1655 — the inline « create a player » panel in a browser
 * (tests/test_player_add_inline_1655.py, phone + laptop).
 *
 * sc_1655_add_existing: typing « elodie » / « synthe » lists Élodie (another
 * team); « Add to team » adds her to the pre-filled team.
 * sc_1655_create_new: a new name + date of birth → the check finds nothing →
 * « Create » enabled → the player page, identity card in edit.
 *
 * Real phone typing (keyboard, live results) stays UNVERIFIED until
 * /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const PANEL = "details#sc_player_add[open] form[data-sc-player-add]";

function type(selector, value) {
    const el = document.querySelector(selector);
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

tours.add("sc_1655_add_existing", {
    steps: () => [
        {
            content: "Type an existing name",
            trigger: `${PANEL} [data-sc-player-add-field="first"]`,
            run() {
                type(`${PANEL} [data-sc-player-add-field="first"]`, "elodie");
                type(`${PANEL} [data-sc-player-add-field="last"]`, "synthe");
            },
        },
        {
            content: "Élodie is listed with « Add to team »; Create stays disabled",
            trigger: `${PANEL} li[data-sc-check-player]:not(.o_sc_search_archived) button[data-sc-action="player.link"]`,
            run(helpers) {
                assert(document.querySelector(`${PANEL} [data-sc-player-add-submit]`).getAttribute("aria-disabled") === "true",
                    "Create enabled without a date of birth");
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Added",
            trigger: ".o_sc_app",
        },
    ],
});

tours.add("sc_1655_create_new", {
    steps: () => [
        {
            content: "A new name and date of birth",
            trigger: `${PANEL} [data-sc-player-add-field="first"]`,
            run() {
                type(`${PANEL} [data-sc-player-add-field="first"]`, "Tourist");
                type(`${PANEL} [data-sc-player-add-field="last"]`, "Synthetic");
                type(`${PANEL} [data-sc-player-add-field="dob"]`, "2012-03-04");
            },
        },
        {
            content: "No match: Create enabled",
            trigger: `${PANEL} [data-sc-check-none]`,
        },
        {
            content: "Create",
            trigger: `${PANEL} [data-sc-player-add-submit][aria-disabled="false"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The player page, identity card in edit",
            trigger: '[data-sc-edit-card="identity"][data-sc-edit-open] [data-sc-edit-view="edit"]:not([hidden])',
        },
    ],
});
