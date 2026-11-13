/*
 * Task 1676 — « Terminé » buttons optional per user (default hidden); the
 * head pencil is a ✓ in edit mode that closes the card; the injury card's
 * « Supprimer la blessure » (task 1736: its top bar's trash, while editing)
 * (tests/test_done_buttons_pref_1676.py, phone + laptop).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(el) {
    if (!el) {
        return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

const IDENTITY = '[data-pk-edit-card="identity"]';
const PENCIL = `${IDENTITY} button[data-pk-edit-toggle]`;
const NOTE = 'details.o_sc_injury_item[open] [data-pk-edit-card="injury-notes-external"]';

tours.add("sc_1676_info_check", {
    steps: () => [
        {
            content: "Settings off: the app hides « Done »; open a player info card (pencil)",
            trigger: PENCIL,
            run(helpers) {
                assert(document.querySelector('.o_pk_app[data-sc-hide-done="1"]'), "Done not hidden by default");
                window.__sc1676Label = this.anchor.getAttribute("aria-label");
                return helpers.click();
            },
        },
        {
            content: "Edit mode: no visible « Done », the pencil is a ✓",
            trigger: `${IDENTITY}[data-pk-edit-open] ${"button[data-pk-edit-toggle]"}[data-pk-edit-toggle-done]`,
            run() {
                const done = document.querySelector(`${IDENTITY} [data-pk-edit-done]`);
                assert(done && !visible(done), "« Done » is visible");
                for (const button of document.querySelectorAll(".o_pk_app [data-pk-edit-done].o_pk_btn_primary")) {
                    assert(!visible(button), "a « Done » is visible somewhere");
                }
                assert(this.anchor.getAttribute("aria-label") !== window.__sc1676Label, "the ✓ kept the pencil's label");
                assert(this.anchor.querySelector("svg path[d='M20 6L9 17l-5-5']"), "no ✓ icon");
                assert(this.anchor.getAttribute("aria-expanded") === "true", "aria-expanded");
            },
        },
        {
            content: "Tap the ✓",
            trigger: `${IDENTITY} button[data-pk-edit-toggle-done]`,
            run: "click",
        },
        {
            content: "Closed: the read view is back, the ✓ is a pencil again",
            trigger: `${IDENTITY}:not([data-pk-edit-open]) [data-pk-edit-view="read"]:not([hidden])`,
            run() {
                const toggle = document.querySelector(PENCIL);
                assert(!toggle.dataset.pkEditToggleDone, "still a ✓");
                assert(toggle.getAttribute("aria-label") === window.__sc1676Label, "label not restored");
                assert(toggle.getAttribute("aria-expanded") === "false", "aria-expanded");
            },
        },
    ],
});

tours.add("sc_1676_injury_check", {
    steps: () => [
        {
            // Task 1736 (deliberate update): « Delete injury » is the top
            // bar's red trash (shown while the Details are edited), no foot.
            content: "No foot (no « Done »); « Delete injury » is the top bar's trash (hidden until editing)",
            trigger: "details.o_sc_injury_item[open] > summary button[data-pk-edit-toggle][data-pk-edit-for='injury-details']",
            run() {
                const card = this.anchor.closest("details");
                assert(!card.querySelector(".o_sc_injury_card_actions"), "the foot is back");
                assert(!card.querySelector("[data-sc-injury-done]"), "the bottom « Done » is back");
                const trash = card.querySelector(":scope > summary button.o_pk_card_trash[data-sc-action='injury.delete']");
                assert(trash, "no « Delete injury » in the top bar");
                assert(!visible(trash), "the trash shows in read mode");
            },
        },
        {
            content: "The external note's pencil",
            trigger: `${NOTE} button[data-pk-edit-toggle]`,
            run: "click",
        },
        {
            content: "The ✓ closes the note",
            trigger: `${NOTE}[data-pk-edit-open] button[data-pk-edit-toggle-done]`,
            run: "click",
        },
        {
            content: "Closed",
            trigger: `${NOTE}:not([data-pk-edit-open]) [data-pk-edit-view="read"]:not([hidden])`,
        },
        {
            content: "The Details pencil (top bar)",
            trigger: "details.o_sc_injury_item[open] > summary button[data-pk-edit-toggle][data-pk-edit-for='injury-details']",
            run: "click",
        },
        {
            content: "« Delete injury » (the trash, now shown) opens its confirm",
            trigger: "details.o_sc_injury_item[open] > summary button.o_pk_card_trash[data-sc-action='injury.delete']:visible",
            run: "click",
        },
        {
            content: "The confirm sheet is open",
            trigger: "dialog[id^='sc_delete_injury_sheet_'][open]",
        },
    ],
});

tours.add("sc_1676_info_done_on", {
    steps: () => [
        {
            content: "Setting on: open a player info card",
            trigger: PENCIL,
            run(helpers) {
                assert(!document.querySelector(".o_pk_app[data-sc-hide-done]"), "Done hidden while the setting is on");
                return helpers.click();
            },
        },
        {
            content: "« Done » is visible and closes the card",
            trigger: `${IDENTITY}[data-pk-edit-open] button[data-pk-edit-done]`,
            run: "click",
        },
        {
            content: "Closed",
            trigger: `${IDENTITY}:not([data-pk-edit-open]) [data-pk-edit-view="read"]:not([hidden])`,
        },
    ],
});
