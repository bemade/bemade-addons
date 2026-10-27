/*
 * Task 1721 — the Clinique dossier pane: the resolved injuries fold out and
 * back; « + Ajouter » above the list opens the add panel; a resolved
 * injury set back to « Actif » moves to the active list; a note's ✓ sits
 * top right
 * (tests/test_clinic_player_pane_1721.py, phone + laptop).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const PANE = '[data-sc-section="clinic.dossier"]';
const FOLD = `${PANE} details[data-sc-resolved-injuries]`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

tours.add("sc_1721_clinic_pane", {
    steps: () => [
        {
            content: "The player card on top; the resolved injury hidden",
            trigger: `${PANE} [data-sc-section="clinic.dossier.player"] .o_sc_player_row`,
            run() {
                const fold = document.querySelector(FOLD);
                assert(fold && !fold.open, "the resolved injuries are not folded");
                const old = [...fold.querySelectorAll(".o_sc_list > *")];
                assert(old.length && !old[0].checkVisibility(), "a resolved card shows");
            },
        },
        {
            content: "Show the resolved injuries",
            trigger: `${FOLD} > summary`,
            run: "click",
        },
        {
            content: "They show; fold them back",
            trigger: `${FOLD}[open] .o_sc_list:contains("Synthetic old knee")`,
            run() {
                document.querySelector(`${FOLD} > summary`).click();
            },
        },
        {
            content: "Folded again",
            trigger: `${FOLD}:not([open])`,
        },
        {
            content: "« + Ajouter » above the injuries",
            trigger: `${PANE} button[data-sc-list-add-toggle][aria-controls="sc_clinic_injury_add"]`,
            run: "click",
        },
        {
            content: "The add panel is open",
            trigger: `${PANE} details#sc_clinic_injury_add[open] form`,
        },
    ],
});

// Review round 1 (owner 2026-10-27): a resolved injury set back to « Actif »
// joins the active list at once (no reload), the fold-out's count follows.
const LISTS = `${PANE} [data-sc-section="clinic.dossier.injury_lists"]`;
const ACTIVE = `${LISTS} [data-sc-section="clinic.dossier.injury_list"]`;

tours.add("sc_1721_resolved_back_to_active", {
    steps: () => [
        {
            content: "Mark the page (a reload would drop it); open the fold-out",
            trigger: `${FOLD} > summary`,
            run() {
                window.__sc1721NoReload = true;
                this.anchor.click();
            },
        },
        {
            content: "The resolved card's status pill",
            trigger: `${FOLD}[open] [data-sc-fragment-item] [data-sc-pill-select][data-sc-pill-key="stage"] button[data-sc-menu-toggle]`,
            run: "click",
        },
        {
            content: "« Active »",
            trigger: `${FOLD} [data-sc-pill-key="stage"] [role="menu"]:not([hidden]) button[data-sc-pill-value="active"]`,
            run: "click",
        },
        {
            content: "The card moved to the active list; no fold-out left; no reload",
            trigger: `${ACTIVE} [data-sc-fragment-item]:contains("Synthetic old knee")`,
            run() {
                assert(window.__sc1721NoReload, "the page reloaded");
                assert(!document.querySelector(FOLD), "the fold-out is still there");
            },
        },
    ],
});

// Review round 1: editing a note — the ✓ stays at the card's top right.
tours.add("sc_1721_note_check_top_right", {
    steps: () => [
        {
            content: "A note's pencil",
            trigger: `${PANE} .o_sc_note_card[data-sc-edit-card] .o_sc_note_head button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "The ✓ at the top right of the card",
            trigger: `${PANE} .o_sc_note_card[data-sc-edit-open] .o_sc_note_head button[data-sc-edit-toggle-done]`,
            run() {
                const card = this.anchor.closest(".o_sc_note_card").getBoundingClientRect();
                const check = this.anchor.getBoundingClientRect();
                assert(card.right - check.right < 24, `the ✓ is not on the right (${card.right - check.right}px)`);
                assert(check.top - card.top < 24, `the ✓ is not at the top (${check.top - card.top}px)`);
            },
        },
    ],
});
