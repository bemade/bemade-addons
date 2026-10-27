/*
 * Task 1721 — the Clinique dossier pane: the resolved injuries fold out and
 * back; « + Ajouter » above the list opens the add panel
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
