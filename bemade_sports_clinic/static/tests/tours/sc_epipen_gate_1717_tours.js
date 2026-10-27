/*
 * Task 1717 — the EpiPen question gates the allergies
 * (tests/test_epipen_gate_1717.py, phone + laptop): a new player's
 * Allergies popup reads « Not provided », its EpiPen card asks Yes / No
 * first, the Add control waits; answering « No » opens the list in place.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const PILLS = '[data-sc-section="player.medical"]';
const ALLERGY = 'dialog[open] [data-sc-section="medical.allergy"]';
const CARD = `${ALLERGY} [data-sc-section="medical.allergy.epipen"]`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

tours.add("sc_1717_epipen_first", {
    steps: () => [
        {
            content: "The Allergies pill",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"]`,
            run() {
                window.__sc1717NoReload = true;
                this.anchor.click();
            },
        },
        {
            content: "Not provided; the question shows; no Add control",
            trigger: `${CARD} [data-sc-edit-view="edit"]:not([hidden]) input[type="radio"][value="no"]`,
            run() {
                assert(document.querySelector(`${CARD} [data-sc-med-epipen-state="unset"]`), "state not unset");
                assert(document.querySelector(`${ALLERGY} [data-sc-med-epipen-first]`), "no « answer first » hint");
                assert(!document.querySelector(`${ALLERGY} button[data-sc-list-add-toggle]`), "Add shown too early");
                this.anchor.click();
            },
        },
        {
            content: "Answered « No »: the Add control appears in place",
            trigger: `${ALLERGY} button[data-sc-list-add-toggle]`,
            run() {
                assert(window.__sc1717NoReload, "the page reloaded");
                assert(!document.querySelector(`${ALLERGY} [data-sc-med-epipen-first]`), "the hint stays");
            },
        },
    ],
});
