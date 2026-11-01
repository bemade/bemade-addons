/*
 * Task 1727 — « Retour prévu » cannot be set in the past; a past one reads
 * « · Dépassé ». Run by tests/test_retour_prevu_past_tours_1727.py (phone
 * 390 px and laptop 1366 px). Synthetic data; language-independent
 * triggers; « today » is the server's (the inputs' min).
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

/** ``iso`` (YYYY-MM-DD) shifted by ``days``. */
function shift(iso, days) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

function typeAndLeave(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
}

const FIELD = '[data-sc-section="player.predicted_return"] .o_sc_autosave[data-sc-field="predicted_return_date"]';
const READ = '[data-sc-section="player.return"]';
const SHEET = "dialog#sc_proposal_sheet";
const CARD = ".o_sc_injury_item[open]";

tours.add("sc_1727_header_past", {
    steps: () => [
        {
            content: "The read view flags the past date « Dépassé »",
            trigger: `${READ} .o_sc_overdue [data-sc-overdue]`,
        },
        {
            content: "Open the header's pencil",
            trigger: '[data-sc-section="player.hero"] > button[data-sc-edit-toggle][aria-expanded="false"]',
            run: "click",
        },
        {
            content: "The date input starts at today; type a past date",
            trigger: `${FIELD} input[type="date"]`,
            run() {
                const min = this.anchor.min;
                assert(/^\d{4}-\d{2}-\d{2}$/.test(min) && min > "2000-01-01", `min ${min}`);
                window.__sc1727Min = min;
                typeAndLeave(this.anchor, shift(min, -3));
            },
        },
        {
            content: "Refused inline; the typed value is kept",
            trigger: `${FIELD} .o_sc_field_error`,
            run() {
                const input = document.querySelector(`${FIELD} input[type="date"]`);
                assert(input.value === shift(window.__sc1727Min, -3), `kept ${input.value}`);
                assert(this.anchor.textContent.trim(), "a message");
            },
        },
        {
            content: "A future date saves",
            trigger: `${FIELD} input[type="date"]`,
            run() {
                typeAndLeave(this.anchor, shift(window.__sc1727Min, 20));
            },
        },
        {
            content: "Saved; the read view drops the flag",
            trigger: `${FIELD}[data-sc-state="saved"]`,
            async run() {
                await waitFor(() => !document.querySelector(`${READ} [data-sc-overdue]`), "flag gone");
                assert(!document.querySelector(`${FIELD} .o_sc_field_error`), "no error left");
            },
        },
    ],
});

tours.add("sc_1727_proposal_past", {
    steps: () => [
        {
            content: "Open card: pencil",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "A predicted resolution date already past",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="predicted_resolution_date"] input`,
            run() {
                // The header's « Retour prévu » input carries today.
                const min = document.querySelector(`${FIELD} input[type="date"]`).min;
                window.__sc1727Min = min;
                typeAndLeave(this.anchor, shift(min, -2));
            },
        },
        {
            content: "The proposal asks for a new date: empty, min = today, the reason",
            trigger: `${SHEET}[open][data-sc-proposal-kind="retour_prevu"] [data-sc-proposal-needs-date] input[data-sc-proposal-value]`,
            run() {
                assert(this.anchor.value === "", `prefilled ${this.anchor.value}`);
                assert(this.anchor.min === window.__sc1727Min, `min ${this.anchor.min}`);
                assert(document.querySelector(`${SHEET} .o_sc_proposal_hint`), "the reason");
            },
        },
        {
            content: "Apply without a date",
            trigger: `${SHEET}[open] [data-sc-proposal-apply]`,
            run: "click",
        },
        {
            content: "Asked for a date; the sheet stays open",
            trigger: `${SHEET}[open] [data-sc-proposal-error]:not([hidden])`,
            run() {
                const input = document.querySelector(`${SHEET} input[data-sc-proposal-value]`);
                assert(input.getAttribute("aria-invalid") === "true", "the row is flagged");
                input.value = shift(window.__sc1727Min, 9);
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Apply the new date",
            trigger: `${SHEET}[open] [data-sc-proposal-apply]`,
            run: "click",
        },
        {
            content: "Applied: the sheet closes",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector(`${SHEET}[open]`), "sheet closed");
                await waitFor(
                    () => document.querySelector(`${FIELD} input`).value === shift(window.__sc1727Min, 9),
                    "header Retour prévu"
                );
            },
        },
    ],
});
