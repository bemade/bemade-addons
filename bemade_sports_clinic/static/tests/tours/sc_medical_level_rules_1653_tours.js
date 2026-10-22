/*
 * Task 1653 — the allergy popup's level rules in a browser
 * (tests/test_medical_level_rules_1653.py).
 *
 * Unset: the « — Choose — » placeholder shows and can't be picked; « Not
 * urgent » then the placeholder is still locked; « None known » empties and
 * disables the details and EpiPen; « Urgent » enables them again.
 *
 * Phone / laptop click-through stays UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const SHEET = 'dialog[id^="sc_med_player_allergy_"]';
const EDIT = `${SHEET}[open] [data-sc-edit-view="edit"]:not([hidden])`;
const LEVEL = `${EDIT} .o_sc_autosave[data-sc-field="allergy_level"] select`;
const DETAILS = `${EDIT} .o_sc_autosave[data-sc-field="allergy_details"] textarea`;

function pick(select, value) {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
}

tours.add("sc_1653_levels", {
    steps: () => [
        {
            content: "Open the Allergies popup",
            trigger: '[data-sc-section="player.medical"] button[data-sc-med-pill="allergy"]',
            run: "click",
        },
        {
            content: "Its pencil",
            trigger: `${SHEET}[open] button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Unset: the placeholder shows, locked; pick « Not urgent »",
            trigger: LEVEL,
            run() {
                const empty = this.anchor.querySelector('option[value=""]');
                assert(empty && empty.disabled, "the « — Choose — » placeholder is selectable");
                assert(this.anchor.value === "", "an unset level does not show the placeholder");
                pick(this.anchor, "minor");
            },
        },
        {
            content: "Saved; pick « None known »",
            trigger: `${EDIT} .o_sc_autosave[data-sc-field="allergy_level"][data-sc-state="saved"] select`,
            run() {
                const empty = this.anchor.querySelector('option[value=""]');
                assert(!empty || empty.disabled, "« Not specified » became selectable");
                pick(this.anchor, "none");
            },
        },
        {
            content: "« None known »: details and EpiPen emptied and disabled",
            trigger: `${EDIT} .o_sc_autosave[data-sc-field="allergy_details"]:has(textarea:disabled)`,
            run() {
                const details = this.anchor.querySelector("textarea");
                assert(details.value === "", `details kept: ${details.value}`);
                const epipen = document.querySelector(`${EDIT} .o_sc_autosave[data-sc-field="allergy_epipen"] button`);
                assert(epipen && epipen.disabled, "EpiPen still editable");
                pick(document.querySelector(LEVEL), "urgent");
            },
        },
        {
            content: "« Urgent »: enabled again",
            trigger: `${DETAILS}:enabled`,
            run() {
                const epipen = document.querySelector(`${EDIT} .o_sc_autosave[data-sc-field="allergy_epipen"] button`);
                assert(!epipen.disabled, "EpiPen still locked");
            },
        },
        {
            content: "Saved",
            trigger: `${EDIT} .o_sc_autosave[data-sc-field="allergy_level"][data-sc-state="saved"]`,
        },
    ],
});
