/*
 * Task 1631 — the injury card's pills (tests/test_injury_card_1631.py).
 * Language-independent triggers, synthetic fixtures, no reloads.
 *
 * - sc_1631_injury_card (therapist, player Injuries tab, the only ACTIVE
 *   injury open, with a predicted date and an external note):
 *   status pill Actif -> Résolu (the date sheet, then the #1603 popup,
 *   dismissed); Résolu -> Actif (the backward popup proposes the predicted
 *   date back: applied, the card follows in place); consent pill -> Oui
 *   (green), visibility pill -> Masquée (yellow); ONE notes Historique;
 *   « Effacer » the external note, then write a new one -> one history
 *   entry (checked server side).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const CARD = "details.o_sc_injury_item[open]";
const DETAILS = `${CARD} [data-sc-edit-card="injury-details"]`;
const NOTES = `${CARD} [data-sc-edit-card="injury-notes"]`;
const FIELD = `${NOTES} .o_sc_autosave[data-sc-field="external_notes"]`;
const PROPOSAL = "#sc_proposal_sheet";
const NEW_NOTE = "Synthetic rewritten 1631";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function noReload() {
    assert(window.__sc1631NoReload, "the page reloaded");
}

async function waitFor(check, what, timeout = 5000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timed out waiting for ${what}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 50));
    }
}

function toggle(scope, key, tone = "") {
    return `${scope} [data-sc-pill-select][data-sc-pill-key="${key}"]:not([aria-busy]) button.o_sc_pill_select${
        tone ? `.o_sc_chip_${tone}` : ""
    }`;
}

function item(scope, key, value) {
    return `${scope} [data-sc-pill-key="${key}"] [role="menuitemradio"][data-sc-pill-value="${value}"]`;
}

function pick(scope, key, value, fromTone) {
    return [
        { content: `Open the ${key} pill`, trigger: toggle(scope, key, fromTone), run: "click" },
        { content: `Pick ${value || "blank"}`, trigger: item(scope, key, value), run: "click" },
    ];
}

tours.add("sc_1631_injury_card", {
    steps: () => [
        {
            content: "The card is open; the status pill is red (active)",
            trigger: toggle(`${CARD} > summary`, "stage", "red"),
            run() {
                window.__sc1631NoReload = true;
                assert(!document.querySelector(`${CARD} .o_sc_autosave[data-sc-field="stage"]`), "a status selector in the body");
                assert(document.querySelector(`${CARD} > summary button[data-sc-injury-quick="resolve"]`), "no quick Resolve");
            },
        },
        // -- forward: Actif -> Résolu (the date sheet, then the popup)
        {
            content: "Open the status pill (the card must not toggle)",
            trigger: toggle(`${CARD} > summary`, "stage", "red"),
            run: "click",
        },
        {
            content: "« Résolu »",
            trigger: item(`${CARD} > summary`, "stage", "resolved"),
            run() {
                assert(document.querySelector(CARD), "the pill toggled the card");
                this.anchor.click();
            },
        },
        {
            content: "The resolution-date sheet: confirm",
            trigger: "#sc_injury_resolve_sheet[open] [data-sc-injury-resolve-confirm]",
            run: "click",
        },
        {
            content: "The #1603 popup (last active injury resolved): dismiss",
            trigger: `${PROPOSAL}[open][data-sc-proposal-kind="last_resolved"] [data-sc-proposal-dismiss]`,
            run: "click",
        },
        // -- backward: Résolu -> Actif (the backward popup)
        ...pick(`${CARD} > summary`, "stage", "active", "green"),
        {
            content: "The backward popup proposes the predicted date back",
            trigger: `${PROPOSAL}[open][data-sc-proposal-kind="moved_back"] [data-sc-proposal-item$=":predicted_resolution_date"] input[data-sc-proposal-value]`,
            run() {
                assert(this.anchor.value, "no predicted date restored");
                window.__sc1631Predicted = this.anchor.value;
                assert(
                    document.querySelector(`${PROPOSAL} [data-sc-proposal-item$=":resolution_date"]`),
                    "no resolution-date row"
                );
            },
        },
        {
            content: "Apply",
            trigger: `${PROPOSAL}[open] [data-sc-proposal-apply]`,
            run: "click",
        },
        {
            content: "Active again (red), the predicted date back in the Details — in place",
            trigger: toggle(`${CARD} > summary`, "stage", "red"),
            async run() {
                await waitFor(() => !document.querySelector(`${PROPOSAL}[open]`), "popup closed");
                await waitFor(() => {
                    const read = document.querySelector(
                        `${DETAILS} [data-sc-edit-view="read"] [data-sc-display$=":predicted_resolution_date"]`
                    );
                    return read && read.textContent.trim() && read.textContent.trim() !== "—";
                }, "the predicted date in the read view");
                noReload();
            },
        },
        // -- consent + visibility pills
        {
            content: "Consent and visibility pills share one row",
            trigger: `${DETAILS} .o_sc_injury_flags`,
            run() {
                const pills = this.anchor.querySelectorAll("[data-sc-pill-key]");
                assert(pills.length === 2, `${pills.length} pills`);
            },
        },
        ...pick(DETAILS, "consent", "yes", "yellow"),
        {
            content: "Consent: green, in place",
            trigger: toggle(DETAILS, "consent", "green"),
            run: () => noReload(),
        },
        ...pick(DETAILS, "visibility", "1", "ghost"),
        {
            content: "Visibility: hidden (yellow), in place",
            trigger: toggle(DETAILS, "visibility", "yellow"),
            run: () => noReload(),
        },
        // -- one Historique
        {
            content: "One notes « History », in the head",
            trigger: `${NOTES} .o_sc_edit_card_head [data-sc-sheet-open^="sc_note_history_sheet_"]`,
            run() {
                const links = document.querySelectorAll(`${NOTES} [data-sc-sheet-open^="sc_note_history_sheet_"]`);
                assert(links.length === 1, `${links.length} History links`);
            },
        },
        {
            content: "Edit the notes (pencil)",
            trigger: `${NOTES} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Still one « History » in edit mode",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run() {
                const links = [...document.querySelectorAll(`${NOTES} [data-sc-sheet-open^="sc_note_history_sheet_"]`)].filter(
                    (el) => el.offsetParent
                );
                assert(links.length === 1, `${links.length} visible History links`);
            },
        },
        // -- « Effacer », then a new note: one history entry
        {
            content: "« Effacer » the external note",
            trigger: `${FIELD} .o_sc_clear_btn`,
            run: "click",
        },
        {
            content: "Cleared and saved",
            trigger: `${FIELD}[data-sc-state="saved"]`,
        },
        {
            content: "Write a new note",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run: `edit ${NEW_NOTE}`,
        },
        {
            content: "Leave the field so it saves",
            trigger: `${FIELD}[data-sc-state="dirty"] textarea[data-sc-replace="new"]`,
            run() {
                this.anchor.blur();
                this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI
            },
        },
        {
            content: "Saved: the new text is the current one",
            trigger: `${FIELD}[data-sc-state="saved"] .o_sc_replace_current_text:contains(${NEW_NOTE})`,
            run: () => noReload(),
        },
    ],
});
