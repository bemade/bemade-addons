/*
 * Task 1630 — the player header's « Allergies » / « Medical alert » pills in
 * a browser (tests/test_medical_alerts_tours_1630.py, phone 390 px and
 * laptop 1366 px). Synthetic data; language-independent triggers.
 *
 * - (sc_1630_medical_tp, the level editor, was replaced by task 1677's
 *   structured lists: sc_medical_lists_1677_tours.js.)
 * - sc_1630_medical_coach: a coach sees ONLY the red « Medical alert » pill
 *   (no grey / outline pill); its popup shows the details, without any
 *   pencil or editor.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const PILLS = '[data-sc-section="player.medical"]';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

tours.add("sc_1630_medical_coach", {
    steps: () => [
        {
            content: "Only the red Medical alert pill",
            trigger: `${PILLS} button[data-sc-med-pill="medical_alert"].o_sc_med_urgent`,
            run() {
                const pills = document.querySelectorAll(`${PILLS} button[data-sc-med-pill]`);
                assert(pills.length === 1, `${pills.length} pills shown to a coach`);
                assert(!document.querySelector(".o_sc_med_none, .o_sc_med_unset"), "a grey / outline pill");
                this.anchor.click();
            },
        },
        {
            content: "Its popup: the condition, no pencil, no editor",
            trigger: "dialog[open] [data-sc-section='medical.medical_alert']",
            run() {
                assert(this.anchor.textContent.includes("Synthetic asthma"), "details missing");
                const dialog = this.anchor.closest("dialog");
                assert(!dialog.querySelector("[data-sc-edit-toggle], [data-sc-action='medical.edit']"), "a pencil");
                assert(!dialog.querySelector(".o_sc_autosave, owl-component"), "an editor");
            },
        },
        {
            content: "Close it",
            trigger: "dialog[open] [data-sc-sheet-close]",
            run: "click",
        },
    ],
});

/*
 * Review round 1 (owner 2026-10-22) — sc_1630_card_pills: on the team
 * roster, a red player's card shows the compact « Allergies » (EpiPen) and
 * « Medical alert » pills; nothing overflows the phone width. Task 1652: a
 * tap ON a pill lands on the pill (above the card's stretched link) and
 * opens its popup, not the player.
 */
tours.add("sc_1630_card_pills", {
    steps: () => [
        {
            content: "The red pills on the roster card",
            trigger: '[data-sc-section="team.roster"] .o_sc_row_status [data-sc-med-pill="allergy"].o_sc_med_urgent',
            run() {
                const row = this.anchor.closest(".o_sc_link_row");
                assert(row.querySelector('.o_sc_row_status [data-sc-med-pill="medical_alert"].o_sc_med_urgent'),
                    "no medical-alert pill");
                assert(this.anchor.querySelector("[data-sc-med-epipen] svg"), "no EpiPen icon");
                this.anchor.scrollIntoView({ block: "center" });
                const box = this.anchor.getBoundingClientRect();
                const rowBox = row.getBoundingClientRect();
                assert(box.height <= 24, `pill not compact: ${box.height}px`);
                assert(box.right <= rowBox.right + 1, "the pill overflows the card");
                assert(document.documentElement.scrollWidth <= window.innerWidth + 1, "horizontal page scroll");
                const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
                assert(hit && hit.closest("[data-sc-med-card-sheet]") === this.anchor,
                    `a tap on the pill lands on ${hit && hit.outerHTML.slice(0, 80)}`);
                hit.click();
            },
        },
        {
            content: "Task 1652: its popup opens (read-only for a coach)",
            trigger: 'dialog[id^="sc_med_card_allergy_"][open]',
            run() {
                assert(!this.anchor.querySelector("[data-sc-edit-toggle]"), "a coach gets a pencil");
            },
        },
    ],
});
