/*
 * Task 1672 — « + Ajouter » panels: a title tap never toggles them; a
 * successful create resets them (tests/test_add_panels_1672.py, phone +
 * laptop).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function type(selector, value) {
    const el = document.querySelector(selector);
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

const ADD = 'button[data-sc-list-add-toggle][aria-controls="sc_add_player"]';
const PANEL = "details#sc_add_player";
const FORM = `${PANEL}[open] form[data-sc-player-add]`;

function tapTitle(panel) {
    const summary = document.querySelector(`${panel} > summary`);
    assert(summary, "no title");
    summary.click();
}

tours.add("sc_1672_team_add_player", {
    steps: () => [
        {
            content: "« + Ajouter » opens the add-player panel",
            trigger: ADD,
            run: "click",
        },
        {
            content: "Tap the panel's title: it stays open",
            trigger: `${FORM} [data-sc-player-add-field="first"]`,
            run() {
                window.__sc1672Team = document.querySelector(`${FORM} [data-sc-player-add-teams]`).value;
                assert(window.__sc1672Team, "the page's team is not pre-filled");
                tapTitle(PANEL);
                assert(document.querySelector(PANEL).open, "the title tap closed the panel");
                assert(document.querySelector(ADD).getAttribute("aria-expanded") === "true", "aria-expanded");
            },
        },
        {
            content: "Name, date of birth, emergency contact",
            trigger: `${FORM} [data-sc-player-add-field="first"]`,
            run() {
                type(`${FORM} [data-sc-player-add-field="first"]`, "Tourone");
                type(`${FORM} [data-sc-player-add-field="last"]`, "Synthfirst");
                type(`${FORM} [data-sc-player-add-field="dob"]`, "2012-03-04");
                document.querySelector(`${FORM} details[data-sc-player-add-ec-box]`).open = true;
                type(`${FORM} [data-sc-player-add-ec="name"]`, "Synthetic Parent");
                type(`${FORM} [data-sc-player-add-ec="mobile"]`, "514-555-0199");
            },
        },
        {
            content: "No match: « Créer »",
            trigger: `${FORM} [data-sc-check-none]`,
        },
        {
            content: "Create",
            trigger: `${FORM} [data-sc-player-add-submit][aria-disabled="false"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The new player's page; back to the team page",
            trigger: '[data-sc-edit-card="identity"][data-sc-edit-open] [data-sc-edit-view="edit"]:not([hidden])',
            run() {
                window.history.back();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back on the team page: reopen the panel",
            trigger: ADD,
            run() {
                const panel = document.querySelector(PANEL);
                if (!panel.open) {
                    document.querySelector(ADD).click();
                }
            },
        },
        {
            content: "An empty form, the team pre-filled again, no check rows",
            trigger: `${FORM} [data-sc-player-add-field="first"]`,
            run() {
                for (const key of ["first", "last", "dob"]) {
                    const value = document.querySelector(`${FORM} [data-sc-player-add-field="${key}"]`).value;
                    assert(value === "", `${key} kept: ${value}`);
                }
                for (const key of ["name", "mobile"]) {
                    const value = document.querySelector(`${FORM} [data-sc-player-add-ec="${key}"]`).value;
                    assert(value === "", `contact ${key} kept: ${value}`);
                }
                const teams = document.querySelector(`${FORM} [data-sc-player-add-teams]`).value;
                assert(teams === window.__sc1672Team || (teams && !window.__sc1672Team), `team: ${teams}`);
                assert(!document.querySelector(`${FORM} li[data-sc-check-player]`), "check rows kept");
            },
        },
        {
            content: "The « + Ajouter » toggle still closes…",
            trigger: ADD,
            run: "click",
        },
        {
            content: "…and reopens it",
            trigger: `${PANEL}:not([open]):not(:visible)`,
            run() {
                document.querySelector(ADD).click();
                assert(document.querySelector(PANEL).open, "not reopened");
            },
        },
    ],
});

const IADD = 'button[data-sc-list-add-toggle][aria-controls="sc_new_injury"]';
const IPANEL = "details#sc_new_injury";

tours.add("sc_1672_injury_add_panel", {
    steps: () => [
        {
            content: "« + Ajouter » of the injuries",
            trigger: IADD,
            run: "click",
        },
        {
            content: "A title tap keeps it open; choose the visibility, type a diagnosis",
            trigger: `${IPANEL}[open] form`,
            run() {
                tapTitle(IPANEL);
                assert(document.querySelector(IPANEL).open, "the title tap closed the panel");
                const radio = document.querySelector(`${IPANEL} input[name="coach_visibility"]`);
                if (radio) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event("change", { bubbles: true }));
                }
                type(`${IPANEL} input[name="diagnosis"]`, "Synthetic typed diagnosis");
                // The shared reset a successful create runs (the guard's fetch post).
                document.querySelector(`${IPANEL} form`).dispatchEvent(
                    new CustomEvent("sc:create-success", { bubbles: true })
                );
            },
        },
        {
            content: "Reset: the panel closed; reopened, it is empty",
            trigger: `${IPANEL}:not([open]):not(:visible)`,
            run() {
                document.querySelector(IADD).click();
                assert(document.querySelector(`${IPANEL} input[name="diagnosis"]`).value === "", "diagnosis kept");
                assert(!document.querySelector(`${IPANEL} input[name="coach_visibility"]:checked`), "visibility kept");
            },
        },
    ],
});
