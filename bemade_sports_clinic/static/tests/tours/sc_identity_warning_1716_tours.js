/*
 * Task 1716 — adding a player: a name + date-of-birth twin is a warning
 * (« Create anyway »), an unlikely date of birth asks for confirmation
 * (tests/test_identity_warning_1716.py, phone + laptop).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = "details#sc_player_add[open] form[data-sc-player-add]";
const SUBMIT = `${FORM} [data-sc-player-add-submit]`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function type(key, value) {
    const el = document.querySelector(`${FORM} [data-sc-player-add-field="${key}"]`);
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function today(years = 0) {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear() + years}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Review round 2: the team of the form (the hidden input the picker writes).
let savedTeams = "";
function setTeams(value) {
    const el = document.querySelector(`${FORM} [data-sc-player-add-teams]`);
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

tours.add("sc_1716_twin_create_anyway", {
    steps: () => [
        {
            content: "The panel is open",
            trigger: `${FORM} [data-sc-player-add-field="first"]`,
            run() {
                type("first", "Élodie");
                type("last", "Synthé-Côté");
                type("dob", "2010-02-03");
            },
        },
        {
            content: "The twin warning with its team; « Create » greyed with the reason",
            trigger: `${FORM} [data-sc-check-exact] [data-sc-player-add-force-btn]`,
            run() {
                const box = document.querySelector(`${FORM} [data-sc-check-exact]`);
                assert(box.textContent.includes("PC Team B"), box.textContent);
                assert(document.querySelector(SUBMIT).getAttribute("aria-disabled") === "true", "Create not greyed");
            },
        },
        {
            content: "« Create anyway »",
            trigger: `${FORM} [data-sc-check-exact] [data-sc-player-add-force-btn]:not([disabled])`,
            run: "click",
        },
        {
            content: "Review round 1: the button gave way to « ✓ Accepted by the user »",
            trigger: `${FORM} [data-sc-check-exact] [data-sc-check-accepted="force"]:not([hidden])`,
            run() {
                const button = document.querySelector(`${FORM} [data-sc-player-add-force-btn]`);
                assert(button.hidden && !button.getClientRects().length, "« Create anyway » still shows");
            },
        },
        {
            content: "Review round 2: the team removed — « Create » waits for a team",
            trigger: `${SUBMIT}[aria-disabled="false"]`,
            run() {
                savedTeams = document.querySelector(`${FORM} [data-sc-player-add-teams]`).value;
                assert(savedTeams, "no team in the form");
                setTeams("");
            },
        },
        {
            content: "Greyed for the team only; the acceptance stays",
            trigger: `${SUBMIT}[aria-disabled="true"]`,
            run() {
                setTeams(savedTeams);
            },
        },
        {
            content: "The team back (re-checked): still « ✓ Accepted by the user », no second « Create anyway »",
            trigger: `${FORM} [data-sc-check-exact] [data-sc-check-accepted="force"]:not([hidden])`,
            run() {
                const button = document.querySelector(`${FORM} [data-sc-player-add-force-btn]`);
                assert(button.hidden, "« Create anyway » asked again after a team change");
            },
        },
        {
            content: "« Create » is enabled; create",
            trigger: `${SUBMIT}[aria-disabled="false"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The new player's page",
            trigger: '[data-sc-edit-card="identity"]',
        },
    ],
});

tours.add("sc_1716_dob_today", {
    steps: () => [
        {
            content: "Type a new player born today",
            trigger: `${FORM} [data-sc-player-add-field="first"]`,
            run() {
                type("first", "Todaysyn");
                type("last", "Dobtour");
                type("dob", today());
            },
        },
        {
            content: "The date warning; « Create » greyed",
            trigger: `${FORM} [data-sc-check-dob-warning] [data-sc-player-add-dob-confirm]`,
            run() {
                assert(document.querySelector(SUBMIT).getAttribute("aria-disabled") === "true", "Create not greyed");
            },
        },
        {
            content: "« The date is correct »",
            trigger: `${FORM} [data-sc-player-add-dob-confirm]:not([disabled])`,
            run: "click",
        },
        {
            content: "Review round 1: the button gave way to « ✓ Accepted by the user »",
            trigger: `${FORM} [data-sc-check-dob-warning] [data-sc-check-accepted="dob"]:not([hidden])`,
            run() {
                const button = document.querySelector(`${FORM} [data-sc-player-add-dob-confirm]`);
                assert(button.hidden && !button.getClientRects().length, "« The date is correct » still shows");
            },
        },
        {
            content: "Review round 2: another date of birth (age 1, still unlikely) asks again",
            trigger: `${SUBMIT}[aria-disabled="false"]`,
            run() {
                type("dob", today(-1)); // age 1: unlikely too
            },
        },
        {
            content: "« The date is correct » is back for the new date",
            trigger: `${FORM} [data-sc-check-dob-warning] [data-sc-player-add-dob-confirm]:not([hidden])`,
            run: "click",
        },
        {
            content: "Accepted again",
            trigger: `${FORM} [data-sc-check-dob-warning] [data-sc-check-accepted="dob"]:not([hidden])`,
        },
        {
            content: "Create",
            trigger: `${SUBMIT}[aria-disabled="false"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The new player's page",
            trigger: '[data-sc-edit-card="identity"]',
        },
    ],
});
