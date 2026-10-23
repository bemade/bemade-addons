/*
 * Task 1630 — the player header's « Allergies » / « Medical alert » pills in
 * a browser (tests/test_medical_alerts_tours_1630.py, phone 390 px and
 * laptop 1366 px). Synthetic data; language-independent triggers.
 *
 * - sc_1630_medical_tp: a therapist taps the Allergies pill, the popup
 *   opens with the details; its pencil opens the editor; the level set to
 *   urgent and EpiPen ticked save field by field; after « Done » the popup's
 *   read view and the header pill (red, EpiPen icon) follow — no reload.
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

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function pill(key) {
    return document.querySelector(`${PILLS} button[data-sc-med-pill="${key}"]`);
}

tours.add("sc_1630_medical_tp", {
    steps: () => [
        {
            content: "Two pills; the Allergies one is yellow, without EpiPen",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_minor`,
            run() {
                window.__sc1630NoReload = true;
                assert(pill("medical_alert"), "the Medical alert pill (Not specified) is missing");
                assert(pill("medical_alert").classList.contains("o_sc_med_unset"), "Not specified tone");
                assert(!this.anchor.querySelector("[data-sc-med-epipen]"), "EpiPen icon while unticked");
                this.anchor.click();
            },
        },
        {
            content: "The popup opens with the details",
            trigger: "dialog[open] [data-sc-edit-card='medical-allergy'] [data-sc-edit-view='read']",
            run() {
                assert(this.anchor.textContent.includes("Synthetic kiwi"), "details missing");
            },
        },
        {
            content: "The therapist's pencil",
            trigger: "dialog[open] [data-sc-edit-card='medical-allergy'] [data-sc-action='medical.edit']",
            run: "click",
        },
        {
            content: "Set the level to urgent",
            trigger: "dialog[open] [data-sc-edit-view='edit']:not([hidden]) .o_sc_autosave[data-sc-field='allergy_level'] select",
            run() {
                this.anchor.value = "urgent";
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Saved",
            trigger: "dialog[open] .o_sc_autosave[data-sc-field='allergy_level'][data-sc-state='saved']",
        },
        {
            // Review round 1: the icon-only pencil stays visible while
            // editing, at the top right of the content, clear of the close ✕.
            content: "The pencil stays, top right, clear of the close button",
            trigger: "dialog[open] [data-sc-edit-card='medical-allergy'] [data-sc-action='medical.edit'][aria-expanded='true']",
            run() {
                const dialog = this.anchor.closest("dialog");
                const pencil = this.anchor.getBoundingClientRect();
                const close = dialog.querySelector("[data-sc-sheet-close]").getBoundingClientRect();
                const body = dialog.querySelector(".o_sc_sheet_body").getBoundingClientRect();
                const select = dialog
                    .querySelector(".o_sc_autosave[data-sc-field='allergy_level']")
                    .getBoundingClientRect();
                assert(pencil.width > 0 && pencil.height > 0, "the pencil is hidden while editing");
                assert(!this.anchor.textContent.trim(), "the pencil has text");
                assert(pencil.top >= close.bottom - 1, "the pencil overlaps the sheet head");
                assert(pencil.right > body.right - pencil.width * 1.5, "the pencil is not at the right");
                assert(pencil.bottom <= select.top + 1, "the pencil is not above the fields");
            },
        },
        {
            content: "Tick EpiPen (« Yes »)",
            trigger: "dialog[open] .o_sc_autosave[data-sc-field='allergy_epipen'] button[data-sc-value='1']",
            run: "click",
        },
        {
            content: "Saved",
            trigger: "dialog[open] .o_sc_autosave[data-sc-field='allergy_epipen'][data-sc-state='saved']",
        },
        {
            content: "« Done »",
            trigger: "dialog[open] [data-sc-edit-card='medical-allergy'] [data-sc-edit-view='edit'] button[data-sc-edit-done]",
            run: "click",
        },
        {
            content: "The popup's read view and the header pill follow (no reload)",
            trigger: "dialog[open] [data-sc-edit-card='medical-allergy'] [data-sc-edit-view='read']:not([hidden])",
            async run() {
                await waitFor(
                    () => document.querySelector("dialog[open] [data-sc-edit-view='read'] [data-sc-med-epipen]"),
                    "EpiPen in the popup"
                );
                await waitFor(() => {
                    const node = pill("allergy");
                    return node && node.classList.contains("o_sc_med_urgent") && node.querySelector("[data-sc-med-epipen]");
                }, "red pill with the EpiPen icon");
                assert(window.__sc1630NoReload, "the page reloaded");
            },
        },
        {
            content: "Close the popup",
            trigger: "dialog[open] [data-sc-sheet-close]",
            run: "click",
        },
        {
            content: "Closed",
            trigger: `${PILLS} button[data-sc-med-pill="allergy"].o_sc_med_urgent`,
            run() {
                assert(!document.querySelector("dialog[open]"), "the popup is still open");
            },
        },
    ],
});

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
            content: "Its popup: the details, no pencil, no editor",
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
