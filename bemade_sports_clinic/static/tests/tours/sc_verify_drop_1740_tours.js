/*
 * Task 1740 — « Vérifier » on the dashboard drops the injury card at once
 * (tests/test_dashboard_verify_drop_1740.py, phone 390 px). Synthetic data;
 * language-independent triggers. No reload: a marker on window survives.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 10000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

const LINE = 'section[data-sc-instance="todo"] details[data-sc-todo="verify"]';
const cards = () => [...document.querySelectorAll(`${LINE} details[data-sc-edit-card="injury"]`)];
const count = () => (document.querySelector(`${LINE} [data-sc-todo-count]`) || {}).textContent;
const line = () => document.querySelector(LINE);

tours.add("sc_1740_verify_drop", {
    steps: () => [
        {
            content: "Open « Injuries to verify » (2 cards)",
            trigger: `${LINE} > summary`,
            run() {
                window.__sc1740 = true;
                this.anchor.click();
                assert(cards().length === 2, `2 cards expected, got ${cards().length}`);
                assert(count().trim() === "2", `count 2 expected, got ${count()}`);
            },
        },
        {
            content: "Verify the first: the card leaves, the count follows",
            trigger: `${LINE} button[data-sc-injury-quick="verify"]`,
            async run() {
                const card = this.anchor.closest('details[data-sc-edit-card="injury"]');
                const id = card.dataset.scInjuryId;
                this.anchor.click();
                await waitFor(() => !cards().some((c) => c.dataset.scInjuryId === id), "the card leaves");
                await waitFor(() => (count() || "").trim() === "1", "the count reads 1");
                assert(cards().length === 1, `1 card expected, got ${cards().length}`);
                assert(!cards()[0].querySelector(".o_sc_injury_head, summary") ||
                       cards()[0].textContent.trim(), "the remaining card is not an empty shell");
                assert(window.__sc1740, "no reload");
            },
        },
        {
            content: "Verify the last: the line hides",
            trigger: `${LINE} button[data-sc-injury-quick="verify"]`,
            async run() {
                this.anchor.click();
                await waitFor(() => !line() || line().hidden, "the line hides");
                assert(window.__sc1740, "no reload");
            },
        },
    ],
});
