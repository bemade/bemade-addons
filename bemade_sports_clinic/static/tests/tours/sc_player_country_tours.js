/*
 * Task 1594 — browser tours of the player page's country / province and
 * actual return date (run by tests/test_app_shell_player_country_1594.py).
 * Language-independent triggers (data attributes); option labels are the
 * English country / province names of the test database.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function pick(select, label) {
    const option = [...select.options].find((opt) => opt.text === label);
    assert(option, `« ${label} » is offered`);
    select.value = option.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
}

const CONTACT = '[data-sc-edit-card="contact"]';

// ------------- a country change: the province choices follow it, in place
tours.add("sc_1594_country_province", {
    steps: () => [
        {
            content: "Mark the page to detect a reload",
            trigger: `${CONTACT} [data-sc-edit-view="read"]`,
            run() {
                window.__sc1594NoReload = true;
            },
        },
        {
            content: "Open the Contact card",
            trigger: `${CONTACT} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Choose another country",
            trigger: `${CONTACT} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="country_id"] select`,
            run() {
                pick(this.anchor, "United States");
            },
        },
        {
            content: "The country is saved",
            trigger: `${CONTACT} .o_sc_autosave[data-sc-field="country_id"][data-sc-state="saved"]`,
        },
        {
            content: "The province choices are the new country's; the old province is gone",
            trigger: `${CONTACT} .o_sc_autosave[data-sc-field="state_id"] select`,
            run() {
                const labels = [...this.anchor.options].map((opt) => opt.text);
                assert(labels.includes("New York"), "the new country's provinces are offered");
                assert(!labels.includes("Quebec"), "the old country's provinces are gone");
                assert(this.anchor.value === "", "the foreign province was dropped");
                pick(this.anchor, "New York");
            },
        },
        {
            content: "The province is saved",
            trigger: `${CONTACT} .o_sc_autosave[data-sc-field="state_id"][data-sc-state="saved"]`,
        },
        {
            content: "Done: back to read mode",
            trigger: `${CONTACT} button[data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The read view shows the new country and province, without a reload",
            trigger: `${CONTACT} [data-sc-edit-view="read"]:not([hidden])`,
            run() {
                assert(window.__sc1594NoReload, "the page reloaded");
                const country = document.querySelector(`${CONTACT} [data-sc-display$=":country_id"]`);
                const state = document.querySelector(`${CONTACT} [data-sc-display$=":state_id"]`);
                assert(country && country.textContent.trim() === "United States",
                    `country reads « ${country && country.textContent} »`);
                assert(state && state.textContent.trim() === "New York",
                    `province reads « ${state && state.textContent} »`);
            },
        },
    ],
});

// ------------- the actual return date: Medical card pencil -> hero chip
tours.add("sc_1594_return_date", {
    steps: () => [
        {
            content: "Review fixes 2026-10-18: no return date shown in the header while empty",
            trigger: '[data-sc-section="player.hero"] [data-sc-edit-view="read"]',
            run() {
                const holder = this.anchor.querySelector('[data-sc-section="player.return"][data-sc-return-kind="actual"]');
                assert(holder && !holder.querySelector(".o_sc_field_static"), "an empty « Retour réel » is shown");
                window.__sc1594NoReload = true;
            },
        },
        {
            content: "Open the Medical Information card",
            trigger: '[data-sc-edit-card="medical"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Set the actual return date",
            trigger: '[data-sc-edit-card="medical"] .o_sc_autosave[data-sc-field="return_date"] input[type="date"]',
            run() {
                this.anchor.value = "2026-11-02";
                this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Saved",
            trigger: '[data-sc-edit-card="medical"] .o_sc_autosave[data-sc-field="return_date"][data-sc-state="saved"]',
        },
        {
            content: "The header's read view shows it (read fragment, no reload)",
            trigger: '[data-sc-section="player.hero"] [data-sc-section="player.return"][data-sc-return-kind="actual"] .o_sc_field_value',
            run() {
                assert(window.__sc1594NoReload, "the page reloaded");
                const shown = this.anchor.textContent.trim();
                assert(shown && shown !== "—" && !shown.includes("2026-11-02"), `the header reads « ${shown} »`);
            },
        },
    ],
});
