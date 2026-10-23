/*
 * Task 1654 — the life-threatening items in a browser
 * (tests/test_critical_items_tours_1654.py, phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers.
 *
 * - sc_1654_critical_tp: a therapist opens the Allergies popup (« Not
 *   urgent »), its pencil, adds « Arachides » with EpiPen: the family turns
 *   « Urgent » in place (level field, list, red pill naming the item, EpiPen
 *   icon); removing the item brings it back to « Not urgent » — no reload.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const PILLS = '[data-sc-section="player.medical"]';
const CARD = "dialog[open] [data-sc-edit-card='medical-allergy']";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function pill() {
    return document.querySelector(`${PILLS} button[data-sc-med-pill="allergy"]`);
}

tours.add("sc_1654_critical_tp", {
    steps: () => [
        {
            content: "The Allergies pill is yellow",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_minor`,
            run() {
                window.__sc1654NoReload = true;
                this.anchor.click();
            },
        },
        {
            content: "The popup's pencil",
            trigger: `${CARD} [data-sc-action='medical.edit']`,
            run: "click",
        },
        {
            content: "Type the item",
            trigger: `${CARD} form[data-sc-critical-add] input[name='name']`,
            run: "edit Arachides",
        },
        {
            content: "Tick EpiPen",
            trigger: `${CARD} form[data-sc-critical-add] input[name='epipen']`,
            run: "click",
        },
        {
            content: "« Add »",
            trigger: `${CARD} form[data-sc-critical-add] button[type='submit']`,
            run: "click",
        },
        {
            content: "The item is listed with its EpiPen icon",
            trigger: `${CARD} .o_sc_critical [data-sc-critical-item] [data-sc-med-epipen]`,
            run() {
                const item = this.anchor.closest("[data-sc-critical-item]");
                assert(item.textContent.includes("Arachides"), "the item's name");
                const form = document.querySelector(`${CARD} form[data-sc-critical-add]`);
                assert(form.elements.name.value === "", "the form is not reset");
            },
        },
        {
            content: "The level field follows: « Urgent »",
            trigger: `${CARD} .o_sc_autosave[data-sc-field='allergy_level'] select`,
            run() {
                assert(this.anchor.value === "urgent", `level: ${this.anchor.value}`);
            },
        },
        {
            content: "The header pill turns red and names the item",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_urgent`,
            run() {
                assert(this.anchor.textContent.includes("Arachides"), "the pill names the item");
                assert(this.anchor.querySelector("[data-sc-med-epipen]"), "the EpiPen icon");
                assert(window.__sc1654NoReload, "the page reloaded");
            },
        },
        {
            content: "Remove the item",
            trigger: `${CARD} button[data-sc-critical-delete]`,
            run: "click",
        },
        {
            content: "Back to « Not urgent »: yellow pill, empty list",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_minor`,
            run() {
                assert(!document.querySelector(`${CARD} [data-sc-critical-item]`), "the item is still listed");
                assert(window.__sc1654NoReload, "the page reloaded");
            },
        },
    ],
});
