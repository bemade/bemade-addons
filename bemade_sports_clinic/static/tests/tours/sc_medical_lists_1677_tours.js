/*
 * Task 1677 — the structured allergy / condition lists in a browser
 * (tests/test_medical_lists_tours_1677.py, phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers.
 *
 * - sc_1677_allergies_tp: a therapist opens the Allergies popup (yellow, one
 *   allergy): the EpiPen card's pencil, ticks EpiPen — its note appears —
 *   types the note, closes with the ✓; « + Ajouter » adds « Arachides »
 *   (the panel closes, the card appears); its pencil, « Risque vital »
 *   ticked -> the popup's pill and the header pill turn red (the header one
 *   names « Arachides »); the trash can removes it -> yellow again. No
 *   reload.
 * - sc_1677_conditions_tp: the Medical alert popup (grey): « + Ajouter » a
 *   life-threatening condition with its first-aid note -> red, the card
 *   shows the first aid.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const PILLS = '[data-sc-section="player.medical"]';
const ALLERGY = 'dialog[open] [data-sc-section="medical.allergy"]';
const CONDITION = 'dialog[open] [data-sc-section="medical.medical_alert"]';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function q(selector) {
    return document.querySelector(selector);
}

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function setValue(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

function headTone(sheet) {
    const head = q(`${sheet} [data-sc-med-head]`);
    return head && head.dataset.scMedLevel;
}

tours.add("sc_1677_allergies_tp", {
    steps: () => [
        {
            content: "The yellow Allergies pill",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_minor`,
            run() {
                window.__sc1677NoReload = true;
                this.anchor.click();
            },
        },
        {
            content: "The popup: its pill, the EpiPen card, the list",
            trigger: `${ALLERGY} [data-sc-med-head][data-sc-med-level="minor"]`,
            run() {
                assert(q(`${ALLERGY} [data-sc-med-item]`), "the allergy card");
                assert(!q(`${ALLERGY} select, ${ALLERGY} owl-component`), "a level selector / island");
            },
        },
        {
            content: "The EpiPen card's pencil",
            trigger: `${ALLERGY} [data-sc-section="medical.allergy.epipen"] [data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Tick EpiPen: its note appears",
            trigger: `${ALLERGY} [data-sc-section="medical.allergy.epipen"] [data-sc-edit-view="edit"]:not([hidden]) input[data-sc-med-set="allergy_epipen"]`,
            async run() {
                const note = q(`${ALLERGY} [data-sc-med-epipen-note-field]`);
                assert(note.hidden, "the note shows while EpiPen is unticked");
                this.anchor.click();
                await waitFor(() => !note.hidden, "the note field");
            },
        },
        {
            content: "Type where it is",
            trigger: `${ALLERGY} [data-sc-med-epipen-note-field]:not([hidden]) input[data-sc-med-set="allergy_epipen_note"]`,
            run() {
                setValue(this.anchor, "Sac, poche avant");
                this.anchor.blur();
            },
        },
        {
            content: "The ✓ closes the EpiPen card",
            trigger: `${ALLERGY} [data-sc-section="medical.allergy.epipen"] [data-sc-edit-toggle][aria-expanded="true"]`,
            run: "click",
        },
        {
            content: "The read view shows EpiPen and its note; the header pill its icon",
            trigger: `${ALLERGY} [data-sc-section="medical.allergy.epipen"] [data-sc-med-epipen-note]`,
            async run() {
                assert(this.anchor.textContent.includes("Sac, poche avant"), "the note");
                await waitFor(() => q(`${PILLS} button[data-sc-med-pill="allergy"] [data-sc-med-epipen]`), "the EpiPen icon");
            },
        },
        {
            content: "« + Ajouter »",
            trigger: `${ALLERGY} .o_sc_list_header button[data-sc-list-add-toggle]`,
            run: "click",
        },
        {
            content: "Type the allergy",
            trigger: `${ALLERGY} details[open] form[data-sc-med-add] input[name="name"]`,
            run: "edit Arachides",
        },
        {
            content: "Add",
            trigger: `${ALLERGY} details[open] form[data-sc-med-add] button[type="submit"]`,
            run: "click",
        },
        {
            content: "The card appears; the panel is closed and empty",
            trigger: `${ALLERGY} [data-sc-med-item][data-sc-med-vital="0"]:not(:first-child)`,
            async run() {
                assert(this.anchor.textContent.includes("Arachides"), "the new card");
                const panel = q(`${ALLERGY} details.o_sc_med_add_panel`);
                await waitFor(() => !panel.open, "the add panel closes");
                assert(panel.querySelector('input[name="name"]').value === "", "the form is not reset");
                assert(headTone(ALLERGY) === "minor", `head: ${headTone(ALLERGY)}`);
            },
        },
        {
            content: "Its pencil",
            trigger: `${ALLERGY} [data-sc-med-item]:not(:first-child) [data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Tick « Risque vital »",
            trigger: `${ALLERGY} [data-sc-med-item]:not(:first-child) [data-sc-edit-view="edit"]:not([hidden]) input[data-sc-med-item-field="life_threatening"]`,
            run: "click",
        },
        {
            content: "The popup's pill turns red, live",
            trigger: `${ALLERGY} [data-sc-med-head][data-sc-med-level="urgent"]`,
        },
        {
            content: "The header pill turns red and names « Arachides »",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_urgent`,
            run() {
                assert(this.anchor.textContent.includes("Arachides"), "the pill names the item");
                assert(window.__sc1677NoReload, "the page reloaded");
            },
        },
        {
            content: "The trash can",
            trigger: `${ALLERGY} [data-sc-med-item]:not(:first-child) [data-sc-edit-view="edit"]:not([hidden]) button[data-sc-med-item-delete]`,
            run: "click",
        },
        {
            content: "Gone: yellow again",
            trigger: `${ALLERGY} [data-sc-med-head][data-sc-med-level="minor"]`,
            async run() {
                await waitFor(() => document.querySelectorAll(`${ALLERGY} [data-sc-med-item]`).length === 1, "one card left");
                await waitFor(() => q(`${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_minor`), "the yellow header pill");
                assert(window.__sc1677NoReload, "the page reloaded");
            },
        },
    ],
});

tours.add("sc_1677_conditions_tp", {
    steps: () => [
        {
            content: "The grey Medical alert pill",
            trigger: `${PILLS} button[data-sc-med-pill="medical_alert"].o_sc_med_none`,
            run() {
                window.__sc1677NoReload = true;
                this.anchor.click();
            },
        },
        {
            content: "Grey, the « no known condition » box, no EpiPen card",
            trigger: `${CONDITION} input[data-sc-med-set="medical_none_confirmed"]`,
            run() {
                assert(headTone(CONDITION) === "unset", `head: ${headTone(CONDITION)}`);
                assert(!q(`${CONDITION} [data-sc-section="medical.allergy.epipen"]`), "an EpiPen card");
            },
        },
        {
            content: "« + Ajouter »",
            trigger: `${CONDITION} .o_sc_list_header button[data-sc-list-add-toggle]`,
            run: "click",
        },
        {
            content: "Type the condition",
            trigger: `${CONDITION} details[open] form[data-sc-med-add] input[name="name"]`,
            run: "edit Asthme",
        },
        {
            content: "Risque vital",
            trigger: `${CONDITION} details[open] form[data-sc-med-add] input[name="life_threatening"]`,
            run: "click",
        },
        {
            content: "The first aid",
            trigger: `${CONDITION} details[open] form[data-sc-med-add] textarea[name="first_aid_note"]`,
            run: "edit Ventolin, 2 inhalations",
        },
        {
            content: "Add",
            trigger: `${CONDITION} details[open] form[data-sc-med-add] button[type="submit"]`,
            run: "click",
        },
        {
            content: "Red, the card with its first aid; the box is gone",
            trigger: `${CONDITION} [data-sc-med-item][data-sc-med-vital="1"] [data-sc-med-first-aid]`,
            async run() {
                assert(this.anchor.textContent.includes("Ventolin"), "the first aid");
                await waitFor(() => headTone(CONDITION) === "urgent", "the red head pill");
                await waitFor(() => !q(`${CONDITION} input[data-sc-med-set="medical_none_confirmed"]`), "the none box");
                await waitFor(() => q(`${PILLS} button[data-sc-med-pill="medical_alert"].o_sc_med_urgent`), "the red header pill");
                assert(window.__sc1677NoReload, "the page reloaded");
            },
        },
    ],
});
