/*
 * Review fixes 2026-10-18 — browser tours (tests/test_review_fixes_tours_1018.py).
 * Language-independent triggers, synthetic fixtures.
 *
 * - sc_1018_header_pencil: the player header is a read view; its ONE pencil
 *   opens the edit view (status selector, recommendation, both return
 *   dates, allergies, « Remove player » only there); the allergies saved
 *   there show in the read view's banner after « Done » (no reload).
 * - sc_1018_injury_dates: on an injury card, « Resolved » hides the
 *   predicted resolution date and shows the resolution date in place.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const HERO = '[data-sc-section="player.hero"]';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(selector) {
    const el = document.querySelector(selector);
    return Boolean(el && el.offsetParent);
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

tours.add("sc_1018_header_pencil", {
    steps: () => [
        {
            content: "Read view: status chips, no selector, no « Remove player »; open the pencil",
            trigger: `${HERO} [data-sc-edit-view="read"] [data-sc-stage-chip]`,
            run() {
                window.__sc1018NoReload = true;
                assert(!visible(`${HERO} .o_sc_autosave[data-sc-field="sc_status"]`), "selector shown in read mode");
                assert(!visible(`${HERO} [data-sc-action="player.remove"]`), "« Remove player » shown in read mode");
                document.querySelector(`${HERO} > button[data-sc-edit-toggle]`).click();
            },
        },
        {
            content: "Edit view: every header field and « Remove player »",
            trigger: `${HERO} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="allergies"] textarea`,
            run() {
                for (const field of ["sc_status", "training_recommendation", "predicted_return_date", "return_date"]) {
                    assert(visible(`${HERO} .o_sc_autosave[data-sc-field="${field}"]`), `${field} missing`);
                }
                assert(visible(`${HERO} [data-sc-action="player.remove"]`), "« Remove player » hidden in edit mode");
                assert(!visible(`${HERO} [data-sc-edit-view="read"]`), "read view still shown");
            },
        },
        {
            content: "Type the allergies",
            trigger: `${HERO} .o_sc_autosave[data-sc-field="allergies"] textarea`,
            run: "edit Synthetic latex",
        },
        {
            content: "Leave the field so it saves",
            trigger: `${HERO} .o_sc_autosave[data-sc-field="allergies"] textarea`,
            run() {
                this.anchor.blur();
                this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI
            },
        },
        {
            content: "Saved",
            trigger: `${HERO} .o_sc_autosave[data-sc-field="allergies"][data-sc-state="saved"]`,
        },
        {
            content: "« Done »",
            trigger: `${HERO} [data-sc-edit-view="edit"] button[data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The read view's banner shows the allergies (read fragment, no reload)",
            trigger: `${HERO} [data-sc-edit-view="read"]`,
            async run() {
                await waitFor(
                    () => (document.querySelector(`${HERO} [data-sc-section="player.allergies"]`) || {})
                        .textContent?.includes("Synthetic latex"),
                    "allergies banner"
                );
                assert(window.__sc1018NoReload, "the page reloaded");
                assert(!visible(`${HERO} [data-sc-action="player.remove"]`), "« Remove player » shown after Done");
            },
        },
    ],
});

const CARD = "details.o_sc_injury_item[open]";
const DETAILS = `${CARD} [data-sc-edit-card="injury-details"]`;

tours.add("sc_1018_injury_dates", {
    steps: () => [
        {
            content: "Open the card's details pencil",
            trigger: `${DETAILS} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Active: the predicted date, not the resolution date",
            trigger: `${DETAILS} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="predicted_resolution_date"]`,
            run() {
                assert(!visible(`${DETAILS} .o_sc_autosave[data-sc-field="resolution_date"]`), "resolution date shown");
            },
        },
        {
            content: "Mark it resolved",
            trigger: `${DETAILS} .o_sc_autosave[data-sc-field="stage"] button[data-sc-value="resolved"]`,
            run: "click",
        },
        {
            content: "Resolved: the resolution date shows, the predicted one goes (in place)",
            trigger: `${DETAILS} .o_sc_autosave[data-sc-field="stage"][data-sc-state="saved"]`,
            async run() {
                await waitFor(
                    () => visible(`${DETAILS} .o_sc_autosave[data-sc-field="resolution_date"]`)
                        && !visible(`${DETAILS} .o_sc_autosave[data-sc-field="predicted_resolution_date"]`),
                    "the date fields flip"
                );
                const dismiss = document.querySelector("dialog#sc_proposal_sheet[open] [data-sc-proposal-dismiss]");
                if (dismiss) {
                    dismiss.click();
                }
            },
        },
    ],
});
