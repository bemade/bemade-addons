/*
 * Task 1590 — the clinic dossier's injuries in the new look
 * (tests/test_clinic_dossier_tours_1590.py): the inline « Add Injury » card
 * (visibility, then diagnosis, « Create »), the new injury open in edit mode
 * ON THE CLINIC PAGE, a quick note saved in place with its « last note »
 * stamp, « Done » reloading the same clinic / patient / file tab; and the
 * « Undo » of a create returning to the dossier. Language-independent
 * triggers only.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const ADD = "details#sc_clinic_injury_add";
const NEW_CARD = '[data-sc-section="clinic.dossier.injuries"] .o_sc_injury_item[data-sc-created-injury]';
const NOTE = '.o_sc_autosave[data-sc-field="external_notes"]';
const DIAG_EDIT = "Tour 1590 synthetic shoulder";
const DIAG_UNDO = "Tour 1590 synthetic undo";
const QUICK_NOTE = "Tour 1590 synthetic current state";

function onClinicDossier() {
    const url = new URL(window.location.href);
    assert(/^\/my\/clinic\/\d+$/.test(url.pathname), `left the clinic: ${url.pathname}`);
    assert(url.searchParams.get("patient"), "no patient selected");
    const pane = document.querySelector('section[data-sc-tab-panel="dossier"]');
    assert(pane && !pane.hidden, "the patient file is not shown");
}

function addSteps(diagnosis) {
    return [
        {
            content: "Open « Add Injury » on the patient file (the list header's « + Ajouter »)",
            trigger: '.o_sc_list_header button.o_sc_list_add[aria-controls="sc_clinic_injury_add"]',
            run: "click",
        },
        {
            content: "Answer « Yes » (coaches may see it)",
            trigger: `${ADD}[open] label.o_sc_choice_option:has(input[value="visible"])`,
            run: "click",
        },
        {
            content: "Type the diagnosis",
            trigger: `${ADD} [data-sc-step="diagnosis"] input[name="diagnosis"]:visible`,
            run: `edit ${diagnosis}`,
        },
        {
            content: "Create",
            trigger: `${ADD} button[data-sc-action="injury.create"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the clinic: the new injury is open in edit mode",
            trigger: `${NEW_CARD}[open] [data-sc-edit-view="edit"]:not([hidden])`,
            run() {
                onClinicDossier();
                assert(this.anchor.closest(".o_sc_injury_item").textContent.includes(diagnosis), "another card");
            },
        },
    ];
}

// --------------------------- add, then edit field by field on the dossier
tours.add("sc_1590_clinic_injury_edit", {
    steps: () => [
        ...addSteps(DIAG_EDIT),
        {
            // Task 1616: one pencil per group — the new injury opens its
            // Details; the notes are the Notes group's.
            content: "The Notes pencil",
            trigger: `${NEW_CARD} [data-sc-edit-card="injury-notes"] button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Write the quick note",
            trigger: `${NEW_CARD} ${NOTE} textarea[data-sc-replace="new"]`,
            run: `edit ${QUICK_NOTE}`,
        },
        {
            content: "Leave the field so it saves",
            trigger: `${NEW_CARD} ${NOTE} textarea[data-sc-replace="new"]`,
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Saved in place, with the « last note » stamp",
            trigger: `${NEW_CARD} ${NOTE}[data-sc-state="saved"] .o_sc_replace_current .o_sc_hint`,
            run() {
                assert(this.anchor.textContent.trim(), "empty stamp");
                const current = document.querySelector(`${NEW_CARD} ${NOTE} .o_sc_replace_current_text`);
                assert(current.textContent.includes(QUICK_NOTE), "the note is not the current text");
                onClinicDossier();
            },
        },
        {
            content: "« Done » of the Notes (task 1611: no reload)",
            trigger: `${NEW_CARD} [data-sc-edit-card="injury-notes"] [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "Same clinic, same patient, file tab; the card reads the note",
            trigger: `[data-sc-section="clinic.dossier.injuries"] .o_sc_injury_item[open] [data-sc-edit-card="injury-notes"] [data-sc-edit-view="read"]:not([hidden])`,
            run() {
                onClinicDossier();
                assert(this.anchor.textContent.includes(QUICK_NOTE), "the read view misses the note");
                assert(!document.querySelector("dialog.o_sc_sheet[open]"), "a sheet opened");
            },
        },
        {
            content: "« Done » of the Details (opened by the create)",
            trigger: `${NEW_CARD} [data-sc-edit-card="injury-details"][data-sc-edit-open] [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The Details pencil opens its edit view again",
            trigger: '[data-sc-section="clinic.dossier.injuries"] .o_sc_injury_item[open] [data-sc-edit-card="injury-details"]:not([data-sc-edit-open]) button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Edit view shown, no legacy form anywhere",
            trigger: '[data-sc-section="clinic.dossier.injuries"] .o_sc_injury_item[open] [data-sc-edit-card="injury-details"] [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="stage"]',
            run() {
                assert(!document.querySelector('form[action*="/my/injury/save"]'), "a legacy injury form");
            },
        },
    ],
});

// --------------------------------------------- add, then « Undo » it
tours.add("sc_1590_clinic_injury_undo", {
    steps: () => [
        ...addSteps(DIAG_UNDO),
        {
            content: "Undo",
            trigger: ".o_sc_toast:not([hidden]) [data-sc-toast-action]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the dossier, the injury is gone",
            trigger: '[data-sc-section="clinic.dossier.injuries"]',
            run() {
                onClinicDossier();
                assert(
                    ![...document.querySelectorAll(".o_sc_injury_item")].some((el) => el.textContent.includes(DIAG_UNDO)),
                    "the undone injury is still listed"
                );
            },
        },
    ],
});
