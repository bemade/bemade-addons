/*
 * Task 1674 — the add-player check lists similar players; « Create » stays
 * enabled with the « check the similar players » reason
 * (tests/test_near_match_1674.py).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const PANEL = "details#sc_player_add[open] form[data-sc-player-add]";

function type(selector, value) {
    const el = document.querySelector(selector);
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

tours.add("sc_1674_near_check", {
    steps: () => [
        {
            content: "A typo'd name, the same date of birth",
            trigger: `${PANEL} [data-sc-player-add-field="first"]`,
            run() {
                type(`${PANEL} [data-sc-player-add-field="first"]`, "Jonathn");
                type(`${PANEL} [data-sc-player-add-field="last"]`, "Synthwel");
                type(`${PANEL} [data-sc-player-add-field="dob"]`, "2011-02-03");
            },
        },
        {
            content: "« Similar players » listed; « Create » enabled with the reason",
            trigger: `${PANEL} ul[data-sc-check-group="near"] li[data-sc-check-player]`,
            run() {
                const submit = document.querySelector(`${PANEL} [data-sc-player-add-submit]`);
                const line = document.querySelector(`${PANEL} [data-sc-player-add-reason]`);
                assert(submit.getAttribute("aria-disabled") === "false", "Create disabled");
                assert(!line.hidden && line.textContent.trim() === "Check the similar players above before creating",
                    `reason: ${line.textContent}`);
            },
        },
    ],
});
