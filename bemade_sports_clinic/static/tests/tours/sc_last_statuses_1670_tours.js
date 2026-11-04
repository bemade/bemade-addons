/*
 * Task 1670 — resolving the LAST active injury also proposes Match /
 * Practice « Yes » (tests/test_last_injury_statuses_1670.py, phone).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const SHEET = "dialog#sc_injury_resolve_sheet";
const PROPOSAL = "dialog#sc_proposal_sheet";
const HERO = '[data-sc-section="player.hero"]';

function card(diagnosis) {
    return [...document.querySelectorAll("details.o_sc_injury_item")].find((node) =>
        node.querySelector("summary").textContent.includes(diagnosis)
    );
}

tours.add("sc_1670_last_statuses", {
    steps: () => [
        {
            content: "« Résoudre » on the last active injury",
            trigger: "details.o_sc_injury_item:not([open]) summary button[data-sc-injury-quick=resolve]",
            run() {
                window.__sc1670NoReload = "1";
                card("Synthetic ankle").querySelector("summary button[data-sc-injury-quick=resolve]").click();
            },
        },
        {
            content: "Confirm the resolution",
            trigger: `${SHEET}[open] [data-sc-injury-resolve-confirm]`,
            run: "click",
        },
        {
            content: "The proposal shows the Match / Practice rows, « Yes » proposed",
            trigger: `${PROPOSAL}[open][data-sc-proposal-kind="last_resolved"] [data-sc-proposal-item$=":practice_status"] select[data-sc-proposal-value]`,
            run() {
                const match = document.querySelector(
                    `${PROPOSAL} [data-sc-proposal-item$=":match_status"] select[data-sc-proposal-value]`
                );
                assert(match && match.value === "yes", "match row");
                assert(this.anchor.value === "yes", "practice row");
                assert(this.anchor.options.length === 3, "practice choices");
            },
        },
        {
            content: "Apply",
            trigger: `${PROPOSAL}[open] [data-sc-proposal-apply]`,
            run: "click",
        },
        {
            content: "The header pills read Match: Yes / Practice: Yes, no reload",
            trigger: `${HERO} [data-sc-pill-key="match"] [data-sc-pill-value="yes"].o_sc_pill_select`,
            run() {
                assert(document.querySelector(
                    `${HERO} [data-sc-pill-key="practice"] [data-sc-pill-value="yes"].o_sc_pill_select`
                ), "practice pill");
                assert(!document.querySelector(`${PROPOSAL}[open]`), "the proposal stayed open");
                assert(window.__sc1670NoReload === "1", "the page reloaded");
            },
        },
    ],
});
