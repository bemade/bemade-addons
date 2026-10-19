/*
 * Task 1603 — « Retour prévu » and the follow-up proposals in a browser.
 * Run by tests/test_retour_prevu_tours_1603.py (phone 390 px and laptop
 * 1366 px). Synthetic data; language-independent triggers; no reloads.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

/** Poll ``check`` (hidden nodes included) until true, or fail. */
async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function markNoReload() {
    window.__sc1603NoReload = "1";
}

function assertNoReload() {
    assert(window.__sc1603NoReload === "1", "the page reloaded");
}

/** Type a value into an input and leave it (headless CI blur). */
function typeAndLeave(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
}

const CARD = ".o_sc_injury_item[open]";
const SHEET = "dialog#sc_proposal_sheet";
const HEADER_FIELD = '[data-sc-section="player.predicted_return"] .o_sc_autosave[data-sc-field="predicted_return_date"]';

// Review fixes 2026-10-18: the header's fields are behind its one pencil.
const HEADER_PENCIL = {
    content: "Open the header's pencil",
    trigger: '[data-sc-section="player.hero"] > button[data-sc-edit-toggle][aria-expanded="false"]',
    run: "click",
};

function sheetOpen(kind) {
    return `${SHEET}[open][data-sc-proposal-kind="${kind}"]`;
}

// ----------------------------- injury date -> the player's Retour prévu
tours.add("sc_1603_injury_to_player", {
    steps: () => [
        {
            content: "Open card: pencil",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run(helpers) {
                markNoReload();
                return helpers.click();
            },
        },
        {
            content: "Change the predicted resolution date and leave it",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="predicted_resolution_date"] input`,
            run() {
                typeAndLeave(this.anchor, "2030-05-01");
            },
        },
        {
            content: "The proposal: Retour prévu = the latest active date, editable",
            trigger: `${sheetOpen("retour_prevu")} input[data-sc-proposal-value]`,
            run() {
                assert(this.anchor.value === "2030-05-01", `proposed ${this.anchor.value}`);
                this.anchor.value = "2030-05-03";
                this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Apply",
            trigger: `${SHEET}[open] [data-sc-proposal-apply]`,
            run: "click",
        },
        {
            content: "The header field shows the edited date — no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector(`${SHEET}[open]`), "sheet closed");
                await waitFor(
                    () => document.querySelector(`${HEADER_FIELD} input`).value === "2030-05-03",
                    "header Retour prévu"
                );
                assertNoReload();
            },
        },
        {
            content: "The team roster shows the new Retour prévu",
            trigger: ".o_sc_hero_team_link",
            run() {
                const url = new URL(this.anchor.href, window.location.origin);
                url.searchParams.set("tab", "players");
                window.location.href = url.toString();
            },
            expectUnloadPage: true,
        },
        {
            content: "Roster row « Retour prévu »",
            trigger: "[data-sc-row-return]",
            run() {
                assert(/2030/.test(this.anchor.textContent), this.anchor.textContent);
            },
        },
    ],
});

// -------------------------- player's Retour prévu -> injuries' dates
/** The knee card's read view (a read fragment, re-queried after swaps). */
function kneeRead() {
    const card = [...document.querySelectorAll(".o_sc_injury_item")].find((node) =>
        node.querySelector("summary").textContent.includes("Synthetic knee")
    );
    return card.querySelector('[data-sc-fragment$=":read"]');
}

tours.add("sc_1603_player_to_injuries", {
    steps: () => [
        HEADER_PENCIL,
        {
            content: "Change Retour prévu in the header and leave it",
            trigger: `${HEADER_FIELD} input`,
            run() {
                markNoReload();
                typeAndLeave(this.anchor, "2030-06-01");
            },
        },
        {
            content: "The proposal lists the two active injuries, both ticked",
            trigger: `${sheetOpen("align_injuries")} [data-sc-proposal-item]`,
            run() {
                const rows = document.querySelectorAll(`${SHEET} [data-sc-proposal-item]`);
                assert(rows.length === 2, `${rows.length} rows`);
                for (const row of rows) {
                    assert(row.querySelector("[data-sc-proposal-tick]").checked, "ticked by default");
                }
            },
        },
        {
            content: "Untick the ankle",
            trigger: `${SHEET}[open] [data-sc-proposal-item]:contains("Synthetic ankle") [data-sc-proposal-tick]`,
            run: "click",
        },
        {
            content: "Apply",
            trigger: `${SHEET}[open] [data-sc-proposal-apply]`,
            run(helpers) {
                window.__sc1603Knee = kneeRead().textContent;
                return helpers.click();
            },
        },
        {
            content: "The knee's card follows in place — no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector(`${SHEET}[open]`), "sheet closed");
                await waitFor(() => kneeRead().textContent !== window.__sc1603Knee, "knee read view");
                assertNoReload();
            },
        },
    ],
});

// ------------------------------- last active injury resolved -> return
tours.add("sc_1603_last_resolved", {
    steps: () => [
        {
            content: "Open card: pencil",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run(helpers) {
                markNoReload();
                return helpers.click();
            },
        },
        {
            content: "« Resolved »",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="stage"] button[data-sc-value="resolved"]`,
            run: "click",
        },
        {
            content: "The proposal: clear Retour prévu + actual return date",
            trigger: `${sheetOpen("last_resolved")} [data-sc-proposal-item$=":return_date"] input[data-sc-proposal-value]`,
            run() {
                const rows = document.querySelectorAll(`${SHEET} [data-sc-proposal-item]`);
                assert(rows.length === 2, `${rows.length} rows`);
                this.anchor.value = "2030-01-31";
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Apply",
            trigger: `${SHEET}[open] [data-sc-proposal-apply]`,
            run: "click",
        },
        {
            content: "Header: Retour prévu cleared, the actual return date set — no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector(`${SHEET}[open]`), "sheet closed");
                await waitFor(() => document.querySelector(`${HEADER_FIELD} input`).value === "", "cleared");
                // Review fixes 2026-10-18: the header's edit view holds the
                // actual return date (its read view shows ONE date).
                await waitFor(
                    () => document.querySelector(
                        '[data-sc-section="player.return_date.edit"] .o_sc_autosave[data-sc-field="return_date"] input'
                    ).value === "2030-01-31",
                    "actual return date in the header"
                );
                assertNoReload();
            },
        },
    ],
});

// ------------------------------------------------ dismiss changes nothing
tours.add("sc_1603_dismiss", {
    steps: () => [
        HEADER_PENCIL,
        {
            content: "Change Retour prévu in the header and leave it",
            trigger: `${HEADER_FIELD} input`,
            run() {
                typeAndLeave(this.anchor, "2030-06-01");
            },
        },
        {
            content: "Dismiss",
            trigger: `${sheetOpen("align_injuries")} [data-sc-proposal-dismiss]`,
            run: "click",
        },
        {
            content: "Closed",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector(`${SHEET}[open]`), "sheet closed");
                await waitFor(() => document.querySelector(`${HEADER_FIELD}[data-sc-state="saved"]`), "saved");
            },
        },
    ],
});
