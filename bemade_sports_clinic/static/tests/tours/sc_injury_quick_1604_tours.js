/*
 * Task 1604 — quick « Vérifier » / « Résoudre » in a browser. Run by
 * tests/test_injury_quick_tours_1604.py (phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers; no reloads.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

/** Poll ``check`` until true, or fail. */
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
    window.__sc1604NoReload = "1";
}

function assertNoReload() {
    assert(window.__sc1604NoReload === "1", "the page reloaded");
}

/** The injury card whose row names ``diagnosis`` (re-queried after swaps). */
function card(diagnosis) {
    return [...document.querySelectorAll("details.o_sc_injury_item")].find((node) =>
        node.querySelector("summary").textContent.includes(diagnosis)
    );
}

function quick(diagnosis) {
    const node = card(diagnosis);
    return node ? node.querySelector("summary button[data-sc-injury-quick]") : null;
}

const SHEET = "dialog#sc_injury_resolve_sheet";
const PROPOSAL = "dialog#sc_proposal_sheet";

// --------------------------------------- « Vérifier » on a collapsed row
tours.add("sc_1604_verify_row", {
    steps: () => [
        {
            content: "Tap « Verify » on the strain's collapsed row",
            trigger: "details.o_sc_injury_item:not([open]) summary button[data-sc-injury-quick=verify]",
            run() {
                markNoReload();
                const button = quick("Synthetic strain");
                assert(button && button.dataset.scInjuryQuick === "verify", "verify button");
                button.click();
            },
        },
        {
            content: "The row turns into « Resolve » in place — the card stays closed, no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => {
                    const button = quick("Synthetic strain");
                    return button && button.dataset.scInjuryQuick === "resolve";
                }, "row refreshed to resolve");
                assert(!card("Synthetic strain").open, "the row button opened the card");
                assertNoReload();
            },
        },
    ],
});

// -------------------------------- « Résoudre » -> sheet -> date -> confirm
tours.add("sc_1604_resolve_row", {
    steps: () => [
        {
            content: "Tap « Resolve » on the ankle's collapsed row",
            trigger: "details.o_sc_injury_item:not([open]) summary button[data-sc-injury-quick=resolve]",
            run() {
                markNoReload();
                quick("Synthetic ankle").click();
            },
        },
        {
            content: "The sheet asks for the resolution date (today by default); the card stays closed",
            trigger: `${SHEET}[open] input[name=resolution_date]`,
            run() {
                assert(!card("Synthetic ankle").open, "the row button opened the card");
                assert(this.anchor.value && this.anchor.value === this.anchor.max, `default ${this.anchor.value}`);
                this.anchor.value = "2025-01-15";
                this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Confirm",
            trigger: `${SHEET}[open] [data-sc-injury-resolve-confirm]`,
            run: "click",
        },
        {
            content: "The last active injury: the #1603 proposal, actual return = the chosen date",
            trigger: `${PROPOSAL}[open][data-sc-proposal-kind="last_resolved"] [data-sc-proposal-item$=":return_date"] input[data-sc-proposal-value]`,
            run() {
                assert(!document.querySelector(`${SHEET}[open]`), "resolve sheet still open");
                assert(this.anchor.value === "2025-01-15", `proposed ${this.anchor.value}`);
            },
        },
        {
            content: "Dismiss",
            trigger: `${PROPOSAL}[open] [data-sc-proposal-dismiss]`,
            run: "click",
        },
        {
            content: "The ankle's row has no quick action any more — no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !quick("Synthetic ankle"), "ankle row refreshed");
                assertNoReload();
            },
        },
    ],
});

// ------------- an OPEN card (task 1616: the former injury page): « Verify »
tours.add("sc_1604_page_verify", {
    steps: () => [
        {
            content: "Tap « Verify » on the open card's row",
            trigger: "details.o_sc_injury_item[open] summary button[data-sc-injury-quick=verify]",
            run(helpers) {
                markNoReload();
                return helpers.click();
            },
        },
        {
            content: "The row now offers « Resolve » — the card stays open, no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => {
                    const button = quick("Synthetic strain");
                    return button && button.dataset.scInjuryQuick === "resolve";
                }, "row refreshed");
                assert(card("Synthetic strain").open, "the row button closed the card");
                assertNoReload();
            },
        },
    ],
});
