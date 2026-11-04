/*
 * Task 1624 — « Configurer » the dashboard in a browser
 * (tests/test_dashboard_tours_1624.py, phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers.
 *
 * Open « Configurer » from the dashboard, switch « Aujourd'hui » off (saved
 * as you go, no reload), move « Couvertures à venir » up, add a second
 * « Joueurs à surveiller », give it a title and limit it to DB Team C (the
 * tag picker), back on the dashboard check the order / title / content,
 * then « Rétablir par défaut » (confirm sheet).
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

function noHorizontalScroll() {
    const doc = document.documentElement;
    assert(doc.scrollWidth <= doc.clientWidth + 1, `horizontal scroll (${doc.scrollWidth} > ${doc.clientWidth})`);
}

const ITEM = (id) => `li[data-sc-dash-item="${id}"]`;
const FORM = (id) => `form[data-sc-dash-instance="${id}"]`;
const SECTION_IDS = () =>
    [...document.querySelectorAll("section[data-sc-instance]")].map((el) => el.dataset.scInstance);

tours.add("sc_1624_dashboard_configure", {
    steps: () => [
        {
            content: "The dashboard: the default sections, « Today » first",
            trigger: 'section[data-sc-instance="today"]',
            run() {
                const ids = SECTION_IDS();
                assert(ids[0] === "today" && ids.includes("watch") && ids.includes("coverage"), `sections: ${ids}`);
                noHorizontalScroll();
            },
        },
        {
            content: "Open « Configure »",
            trigger: 'a[data-sc-action="dashboard.configure"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "One row per section; switch « Today » off (tap the row)",
            trigger: `${ITEM("today")} label.o_sc_switch`,
            run() {
                noHorizontalScroll();
                assert(!document.querySelector("[data-sc-dash-save]:not([hidden])"), "no-JS save button hidden");
                this.anchor.click();
            },
        },
        {
            content: "Saved in place, the row greyed (no reload)",
            trigger: `${ITEM("today")}.o_sc_dash_cfg_off ${FORM("today")}:not([data-sc-dash-saving]) [data-sc-dash-status]:not(:empty)`,
            async run() {
                await waitFor(() => !document.querySelector(`${FORM("today")} [data-sc-guard-error]:not([hidden])`), "no error");
            },
        },
        {
            content: "Move « Upcoming coverage » up",
            trigger: `${ITEM("coverage")} button[data-sc-dash-move="up"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Coverage is now above « To do » (round 2: within its zone)",
            trigger: `${ITEM("coverage")}`,
            run() {
                const ids = [...document.querySelectorAll("li[data-sc-dash-item]")].map((el) => el.dataset.scDashItem);
                assert(ids.indexOf("coverage") < ids.indexOf("todo"), `order: ${ids}`);
            },
        },
        {
            content: "Pick « Players to watch » to add",
            trigger: "select#sc_dash_add_widget",
            run: "select watch",
        },
        {
            content: "« + Add a section »",
            trigger: "button[data-sc-dash-add]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The new instance: open its settings",
            trigger: `${ITEM("watch-2")} summary[data-sc-dash-settings]`,
            run: "click",
        },
        {
            content: "Give it a title",
            trigger: `${FORM("watch-2")} input[name="title"]`,
            run: "edit Watch C only",
        },
        {
            content: "Title saved",
            trigger: `${FORM("watch-2")}:not([data-sc-dash-saving]) [data-sc-dash-status]:not(:empty)`,
            async run() {
                await waitFor(
                    () => document.querySelector(`${ITEM("watch-2")} .o_sc_switch_label`).textContent.trim() === "Watch C only",
                    "the row shows the title"
                );
            },
        },
        {
            content: "Limit it to DB Team C: type in the teams picker",
            trigger: `${FORM("watch-2")} [data-sc-dash-scope] input.o_sc_tags_search:last`,
            run: "edit Team C",
        },
        {
            content: "Pick DB Team C",
            trigger: `${FORM("watch-2")} .o_sc_tags_option:contains("DB Team C")`,
            run: "click",
        },
        {
            content: "The scope is saved",
            trigger: `${FORM("watch-2")} .o_sc_tag:contains("DB Team C")`,
            async run() {
                const hidden = document.querySelector(`${FORM("watch-2")} input[name="scope_team_ids"]`);
                await waitFor(() => hidden.value !== "", "scope filled");
                await waitFor(
                    () => document.querySelector(`${FORM("watch-2")}:not([data-sc-dash-saving])`) &&
                        !document.querySelector(`${FORM("watch-2")} [data-sc-guard-error]:not([hidden])`),
                    "saved"
                );
                noHorizontalScroll();
            },
        },
        {
            content: "Back to the dashboard",
            trigger: 'a[data-sc-action="dashboard.back"]',
            async run() {
                // Let the last autosave land before leaving.
                await new Promise((resolve) => setTimeout(resolve, 400));
                this.anchor.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Today is gone, coverage before « To do », the new section titled and scoped",
            trigger: 'section[data-sc-instance="watch-2"]',
            run() {
                const ids = SECTION_IDS();
                assert(!ids.includes("today"), `today switched off: ${ids}`);
                assert(ids.indexOf("coverage") < ids.indexOf("todo"), `order: ${ids}`);
                // Round 2: added to the shorter column (a tie: the left one).
                assert(this.anchor.closest("[data-sc-zone]").dataset.scZone === "left", "watch-2 in the left zone");
                const section = this.anchor;
                assert(section.querySelector(".o_sc_dw_title_text").textContent.trim() === "Watch C only", "title");
                assert(section.querySelector("[data-sc-dw-scope]").textContent.includes("DB Team C"), "scope line");
                const players = [...section.querySelectorAll("[data-sc-player-id]")].map((el) => el.textContent);
                assert(players.some((t) => t.includes("Yellow")), "Team C's yellow player listed");
                assert(!players.some((t) => t.includes("Red, ") || t.includes("Synth, Red")), "Team A's red player not listed");
                noHorizontalScroll();
            },
        },
        {
            content: "Configure again",
            trigger: 'a[data-sc-action="dashboard.configure"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "« Restore the default »",
            trigger: "button[data-sc-dash-reset]",
            run: "click",
        },
        {
            content: "Confirm",
            trigger: "dialog[open] button[data-sc-confirm-ok]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back to the defaults: no second instance, « Today » on",
            trigger: `${ITEM("today")}:not(.o_sc_dash_cfg_off)`,
            run() {
                assert(!document.querySelector(ITEM("watch-2")), "the added instance is gone");
            },
        },
    ],
});
