/*
 * Task 1726 — the shared switch in each kind of form
 * (tests/test_switches_tours_1726.py, phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers. Each tour taps the switch
 * ROW (its label), the way a finger does.
 *
 * - sc_1726_switch_pref: « Paramètres › Afficher les boutons Terminé » — the
 *   switch posts the preference on its own (no button) and comes back on.
 * - sc_1726_switch_filter: the events filter « Afficher les événements
 *   annulés » — a GET filter form, applied on change (show_cancelled=1).
 * - sc_1726_switch_autosave: the new injury's date « N/A » (the OWL
 *   autosave field) — on: the date is disabled; off again: enabled.
 * - sc_1726_switch_fetch: the Medical alert popup's « Aucune condition
 *   connue » — a fetch save (no reload), aria-checked follows.
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

// The switch ROW (the visible label) of the input ``input`` within ``scope``.
function row(scope, input) {
    return `${scope} label.o_sc_switch:has(${input})`;
}

function assertSwitchLayout(label) {
    // One line: the label on the left, the switch on the right, 44 px tall.
    const text = label.querySelector(".o_sc_switch_label").getBoundingClientRect();
    const track = label.querySelector(".o_sc_switch_track").getBoundingClientRect();
    assert(track.left >= text.left, "the switch is not right of its label");
    assert(label.getBoundingClientRect().height >= 43, "the row is under 44 px");
}

const DONE_SCOPE = "#sc_done_buttons";
const DONE = 'input[role="switch"][name="sc_show_done_buttons"]';

tours.add("sc_1726_switch_pref", {
    steps: () => [
        {
            content: "« Terminé » buttons: a switch, off",
            trigger: row(DONE_SCOPE, `${DONE}[aria-checked="false"]`),
            run() {
                assertSwitchLayout(this.anchor);
            },
        },
        {
            content: "Tap it: the preference posts by itself",
            trigger: row(DONE_SCOPE, DONE),
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the settings, the switch on",
            trigger: row(DONE_SCOPE, `${DONE}[aria-checked="true"]:checked`),
        },
    ],
});

const FILTERS = 'form[data-sc-section="events.filters"]';
const CANCELLED = 'input[role="switch"][name="show_cancelled"]';

tours.add("sc_1726_switch_filter", {
    steps: () => [
        {
            content: "Open the filters",
            trigger: 'form[data-sc-section="events.filters"] details.o_sc_disclosure > summary',
            run() {
                this.anchor.closest("details").open = true;
            },
        },
        {
            content: "Show cancelled events: tap the switch",
            trigger: `${row(FILTERS, CANCELLED)}:visible`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Applied on change: the filter in the address, the switch on",
            trigger: row(FILTERS, `${CANCELLED}[aria-checked="true"]:checked`),
            run() {
                assert(window.location.search.includes("show_cancelled=1"), window.location.search);
            },
        },
    ],
});

const NA_SCOPE = ".o_sc_date_na";
const NA = 'input[role="switch"][name="injury_date_na"]';

tours.add("sc_1726_switch_autosave", {
    steps: () => [
        {
            content: "The date's « N/A » switch, off",
            trigger: row(NA_SCOPE, `${NA}[aria-checked="false"]`),
        },
        {
            content: "Tap it",
            trigger: row(NA_SCOPE, NA),
            run: "click",
        },
        {
            content: "On: the date is disabled",
            trigger: row(NA_SCOPE, `${NA}[aria-checked="true"]:checked`),
            run() {
                assert(document.querySelector('.o_sc_date_na input[type="date"]').disabled, "the date");
            },
        },
        {
            content: "Tap it again",
            trigger: row(NA_SCOPE, NA),
            run: "click",
        },
        {
            content: "Off: the date is back",
            trigger: row(NA_SCOPE, `${NA}[aria-checked="false"]:not(:checked)`),
            run() {
                assert(!document.querySelector('.o_sc_date_na input[type="date"]').disabled, "the date");
            },
        },
    ],
});

const CONDITION = 'dialog[open] [data-sc-section="medical.medical_alert"]';
const NONE = 'input[role="switch"][data-sc-med-set="medical_none_confirmed"]';

tours.add("sc_1726_switch_fetch", {
    steps: () => [
        {
            content: "The Medical alert pill",
            trigger: '[data-sc-section="player.medical"] button[data-sc-med-pill="medical_alert"]',
            run() {
                window.__sc1726NoReload = true;
                this.anchor.click();
            },
        },
        {
            content: "« No known condition »: a switch, off",
            trigger: row(CONDITION, `${NONE}[aria-checked="false"]`),
            run() {
                assertSwitchLayout(this.anchor);
            },
        },
        {
            content: "Tap it",
            trigger: row(CONDITION, NONE),
            run: "click",
        },
        {
            content: "Saved in place: on, no reload",
            trigger: row(CONDITION, `${NONE}:checked`),
            async run() {
                await waitFor(() => document.querySelector(`${CONDITION} ${NONE}`).getAttribute("aria-checked") === "true",
                    "aria-checked");
                await waitFor(() => document.querySelector(`${CONDITION} [data-sc-med-head]`).dataset.scMedLevel === "none",
                    "the grey « none » head pill");
                assert(window.__sc1726NoReload, "the page reloaded");
            },
        },
    ],
});
