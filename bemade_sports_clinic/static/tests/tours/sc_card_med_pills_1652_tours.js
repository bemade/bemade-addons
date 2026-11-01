/*
 * Task 1652 — a card's red medical pill opens the popup
 * (tests/test_card_med_pills_1652.py, phone 390 px).
 *
 * The pill is as tall as the status pill beside it; a tap opens the
 * page-level sheet without following the card's link or toggling it; the
 * therapist unticks « Risque vital » on the allergy's card in the popup
 * (task 1677): saved, the card refreshes and its Allergies pill is gone.
 *
 * Real phone taps stay UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
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

// Review round 2 (owner 2026-10-27): every card shows both pills (grey
// included) on their own line under Match / Practice — take the red one.
const PILL = 'button.o_sc_med_urgent[data-sc-med-card-sheet^="sc_med_card_allergy_"]';

tours.add("sc_1652_card_pill", {
    steps: () => [
        {
            content: "Same height as the status pill; tap it",
            trigger: PILL,
            run() {
                window.__sc1652NoReload = "1";
                const pill = document.querySelector(PILL);
                window.__sc1652Sheet = pill.dataset.scMedCardSheet;
                const line = pill.closest(".o_sc_row_status");
                assert(line.matches("[data-sc-row-med]"), "not on the card's medical line");
                const above = line.previousElementSibling;
                const status = above && above.querySelector(".o_sc_status_pill, .o_sc_pill_select");
                assert(status, "no Match / Practice line right above it");
                const diff = Math.abs(pill.getBoundingClientRect().height - status.getBoundingClientRect().height);
                assert(diff <= 1, `heights differ: ${pill.getBoundingClientRect().height} vs ${status.getBoundingClientRect().height}`);
                const details = pill.closest("details");
                window.__sc1652Open = details ? String(details.open) : "none";
                // A real tap lands where the pill is drawn (above the card's
                // stretched link).
                pill.scrollIntoView({ block: "center" });
                const box = pill.getBoundingClientRect();
                const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
                assert(hit && hit.closest("[data-sc-med-card-sheet]") === pill,
                    `a tap on the pill lands on ${hit && hit.outerHTML.slice(0, 80)}`);
                hit.click();
            },
        },
        {
            content: "The popup is open, the card did not toggle, no navigation",
            trigger: 'dialog[id^="sc_med_card_allergy_"][open] [data-sc-med-item] button[data-sc-edit-toggle]',
            run(helpers) {
                assert(window.__sc1652NoReload === "1", "the tap navigated");
                const pill = document.querySelector(PILL);
                const details = pill && pill.closest("details");
                assert((details ? String(details.open) : "none") === window.__sc1652Open, "the card toggled");
                return helpers.click();
            },
        },
        {
            content: "Turn off « Risque vital » (task 1726: a switch — tap its row)",
            trigger: 'dialog[id^="sc_med_card_allergy_"][open] [data-sc-med-item] [data-sc-edit-view="edit"]:not([hidden]) label.o_sc_switch:has(input[data-sc-med-item-field="life_threatening"])',
            run: "click",
        },
        {
            content: "Saved (the popup's pill is yellow); close the popup",
            trigger: 'dialog[id^="sc_med_card_allergy_"][open] [data-sc-med-head][data-sc-med-level="minor"]',
            run() {
                this.anchor.closest("dialog").close();
            },
        },
        {
            content: "The card refreshed: the Allergies pill turned yellow, no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(
                    () => document.querySelector(`button.o_sc_med_minor[data-sc-med-card-sheet="${window.__sc1652Sheet}"]`),
                    "the Allergies pill did not turn yellow"
                );
                assert(window.__sc1652NoReload === "1", "the page reloaded");
                assert(document.querySelector('button[data-sc-med-card-sheet^="sc_med_card_medical_alert_"]'),
                    "the medical-alert pill went");
            },
        },
    ],
});
