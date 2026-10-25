/*
 * Security review 2026-10-23 — the inline « create a player » panel greys
 * « Create » with the generic « ask a manager » line when the typed name is
 * held by a player the user can't open, whatever the date of birth
 * (tests/test_identity_oracle_1023.py).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const PANEL = "details#sc_player_add[open] form[data-sc-player-add]";
const GENERIC = "A player with this identity already exists — ask a manager.";
// Task 1672 (addendum 3): the generic line sits in the suggestions only; the
// reason under « Create » points at it.
const REASON = "Check the existing player above";

function type(selector, value) {
    const el = document.querySelector(selector);
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function greyed(dob) {
    return {
        content: `Create greyed with the generic line (${dob})`,
        trigger: `${PANEL} [data-sc-check-results][data-sc-twin-elsewhere="1"]`,
        run() {
            const submit = document.querySelector(`${PANEL} [data-sc-player-add-submit]`);
            const line = document.querySelector(`${PANEL} [data-sc-player-add-reason]`);
            if (submit.getAttribute("aria-disabled") !== "true") {
                throw new Error(`Create enabled for a hidden namesake (${dob})`);
            }
            if (line.hidden || line.textContent.trim() !== REASON) {
                throw new Error(`Unexpected reason line: ${line.textContent}`);
            }
            const shown = document.querySelector(`${PANEL} [data-sc-check-twin-elsewhere]`);
            if (!shown || shown.textContent.trim() !== GENERIC) {
                throw new Error("the generic line is not in the suggestions");
            }
        },
    };
}

tours.add("sc_1023_twin_elsewhere", {
    steps: () => [
        {
            content: "A name held by another team's player, a wrong date of birth",
            trigger: `${PANEL} [data-sc-player-add-field="first"]`,
            run() {
                type(`${PANEL} [data-sc-player-add-field="first"]`, "Élodie");
                type(`${PANEL} [data-sc-player-add-field="last"]`, "Synthé-Côté");
                type(`${PANEL} [data-sc-player-add-field="dob"]`, "2001-01-01");
            },
        },
        greyed("2001-01-01"),
        {
            content: "The right date of birth",
            trigger: `${PANEL} [data-sc-player-add-field="dob"]`,
            run() {
                type(`${PANEL} [data-sc-player-add-field="dob"]`, "2010-02-03");
            },
        },
        {
            content: "The check ran again for the new date",
            trigger: `${PANEL} [data-sc-player-add-reason]:not(:contains("Checking"))`,
        },
        greyed("2010-02-03"),
        {
            content: "A click does nothing (no create)",
            trigger: `${PANEL} [data-sc-player-add-submit][aria-disabled="true"]`,
            run: "click",
        },
        {
            content: "Still greyed",
            trigger: `${PANEL} [data-sc-player-add-submit][aria-disabled="true"]`,
        },
    ],
});
