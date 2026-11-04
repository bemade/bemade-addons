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
            // Review round 1: the slider pill's « Non » (its radio is drawn
            // invisible under the label).
            trigger: `${CARD} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_toggle_pill label:has(input[type="radio"][value="no"])`,
            run() {
                assert(document.querySelector(`${CARD} [data-sc-med-epipen-state="unset"]`), "state not unset");
                assert(document.querySelector(`${ALLERGY} [data-sc-med-epipen-first]`), "no « answer first » hint");
                assert(!document.querySelector(`${ALLERGY} button[data-sc-list-add-toggle]`), "Add shown too early");
                // Review round 2 (owner 2026-10-27): Non | Oui, both neutral
                // while unanswered; the question on the ✓'s line.
                const [no, yes] = document.querySelectorAll(`${CARD} .o_sc_toggle_pill > label`);
                assert(no.dataset.scToggleOpt === "no" && yes.dataset.scToggleOpt === "yes", "not Non | Oui");
                assert(no.getBoundingClientRect().right <= yes.getBoundingClientRect().left + 1, "Non is not left of Oui");
                assert(getComputedStyle(no).backgroundColor === getComputedStyle(yes).backgroundColor,
                    "an option is lit while unanswered");
                const ask = document.querySelector(`${CARD} [data-sc-med-epipen-ask]`).getBoundingClientRect();
                const done = document.querySelector(`${CARD} [data-sc-edit-toggle]`).getBoundingClientRect();
                assert(Math.abs(ask.top - done.top) < 12 && done.left >= ask.right - 1,
                    `the question is not on the ✓'s line (${ask.top} vs ${done.top})`);
                // The level pill sits in the popup's header.
                assert(document.querySelector("dialog[open] .o_sc_sheet_head [data-sc-med-head]"), "no header pill");
                window.__sc1717Accent = getComputedStyle(document.querySelector(".o_sc_app")).getPropertyValue("--sc-accent");
                this.anchor.click();
            },
        },
        {
            content: "« Non » chosen: grey, never the accent green",
            trigger: `${CARD} .o_sc_toggle_pill > label[data-sc-toggle-opt="no"]:has(input:checked)`,
            run() {
                const probe = document.createElement("span");
                probe.style.color = window.__sc1717Accent;
                document.body.append(probe);
                const accent = getComputedStyle(probe).color;
                probe.remove();
                assert(getComputedStyle(this.anchor).backgroundColor !== accent, "« Non » is lit green");
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
