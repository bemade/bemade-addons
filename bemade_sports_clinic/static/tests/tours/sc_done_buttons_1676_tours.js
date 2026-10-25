/*
 * Task 1676 — « Terminé » buttons optional per user (default hidden); the
 * head pencil is a ✓ in edit mode that closes the card; the injury card's
 * foot is « Supprimer la blessure » on the left
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

const IDENTITY = '[data-sc-edit-card="identity"]';
const PENCIL = `${IDENTITY} button[data-sc-edit-toggle]`;
const NOTE = 'details.o_sc_injury_item[open] [data-sc-edit-card="injury-notes-external"]';

tours.add("sc_1676_info_check", {
    steps: () => [
        {
            content: "Settings off: the app hides « Done »; open a player info card (pencil)",
            trigger: PENCIL,
            run(helpers) {
                assert(document.querySelector('.o_sc_app[data-sc-hide-done="1"]'), "Done not hidden by default");
                window.__sc1676Label = this.anchor.getAttribute("aria-label");
                return helpers.click();
            },
        },
        {
            content: "Edit mode: no visible « Done », the pencil is a ✓",
            trigger: `${IDENTITY}[data-sc-edit-open] ${"button[data-sc-edit-toggle]"}[data-sc-edit-toggle-done]`,
            run() {
                const done = document.querySelector(`${IDENTITY} [data-sc-edit-done]`);
                assert(done && !visible(done), "« Done » is visible");
                for (const button of document.querySelectorAll(".o_sc_app [data-sc-edit-done].o_sc_btn_primary")) {
                    assert(!visible(button), "a « Done » is visible somewhere");
                }
                assert(this.anchor.getAttribute("aria-label") !== window.__sc1676Label, "the ✓ kept the pencil's label");
                assert(this.anchor.querySelector("svg path[d='M20 6L9 17l-5-5']"), "no ✓ icon");
                assert(this.anchor.getAttribute("aria-expanded") === "true", "aria-expanded");
            },
        },
        {
            content: "Tap the ✓",
            trigger: `${IDENTITY} button[data-sc-edit-toggle-done]`,
            run: "click",
        },
        {
            content: "Closed: the read view is back, the ✓ is a pencil again",
            trigger: `${IDENTITY}:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
            run() {
                const toggle = document.querySelector(PENCIL);
                assert(!toggle.dataset.scEditToggleDone, "still a ✓");
                assert(toggle.getAttribute("aria-label") === window.__sc1676Label, "label not restored");
                assert(toggle.getAttribute("aria-expanded") === "false", "aria-expanded");
            },
        },
    ],
});

tours.add("sc_1676_injury_check", {
    steps: () => [
        {
            content: "The injury foot: « Delete injury » on the left, no « Done »",
            trigger: "details.o_sc_injury_item[open] .o_sc_injury_card_actions button[data-sc-action='injury.delete']",
            run() {
                const foot = this.anchor.closest(".o_sc_injury_card_actions");
                assert(!foot.querySelector("[data-sc-injury-done]"), "the bottom « Done » is back");
                const footBox = foot.getBoundingClientRect();
                const box = this.anchor.getBoundingClientRect();
                assert(box.left - footBox.left < footBox.right - box.right, "« Delete injury » is not on the left");
            },
        },
        {
            content: "The external note's pencil",
            trigger: `${NOTE} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "The ✓ closes the note",
            trigger: `${NOTE}[data-sc-edit-open] button[data-sc-edit-toggle-done]`,
            run: "click",
        },
        {
            content: "Closed",
            trigger: `${NOTE}:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
        },
        {
            content: "« Delete injury » opens its confirm",
            trigger: "details.o_sc_injury_item[open] .o_sc_injury_card_actions button[data-sc-action='injury.delete']",
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
                assert(!document.querySelector(".o_sc_app[data-sc-hide-done]"), "Done hidden while the setting is on");
                return helpers.click();
            },
        },
        {
            content: "« Done » is visible and closes the card",
            trigger: `${IDENTITY}[data-sc-edit-open] button[data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "Closed",
            trigger: `${IDENTITY}:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
        },
    ],
});
