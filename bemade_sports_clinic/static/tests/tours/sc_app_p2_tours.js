/*
 * Task 1539 (epic #1535) — browser tours of the P2 shell pages (players,
 * injuries, activities). Run by tests/test_app_shell_tours_1539.py through
 * HttpCase.start_tour; language-independent triggers only (data attributes).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function draftKeys(fragment = "") {
    const keys = [];
    for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith("sc_draft:") && key.includes(fragment)) {
            keys.push(key);
        }
    }
    return keys;
}

// ------------------------------------------- players list -> player -> tabs
tours.add("sc_1539_players_to_player", {
    steps: () => [
        {
            content: "Players list: the « Joueurs » tab is active",
            trigger: '.o_sc_app a[data-sc-nav-key="players"][aria-current="page"]',
        },
        {
            content: "Open the first player",
            trigger: '[data-sc-section="players.list"] a.o_sc_entity_row[data-sc-player-id]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Player page: « Aperçu » panel shown",
            trigger: 'section[data-sc-tab-panel="overview"]:not([hidden])',
        },
        {
            content: "Switch to « Blessures » in place",
            trigger: '[data-sc-tabs] a[data-sc-tab="injuries"]',
            run: "click",
        },
        {
            trigger: 'section[data-sc-tab-panel="injuries"]:not([hidden]) [data-sc-injury-id]',
            run() {
                assert(window.location.search.includes("tab=injuries"), "?tab= kept in the URL");
                const overview = document.querySelector('section[data-sc-tab-panel="overview"]');
                assert(overview.hidden, "overview still shown");
            },
        },
        {
            content: "Switch to « Infos »",
            trigger: '[data-sc-tabs] a[data-sc-tab="info"]',
            run: "click",
        },
        {
            trigger: 'section[data-sc-tab-panel="info"]:not([hidden]) [data-sc-section="player.info.teams"]',
        },
    ],
});

// ------------------------------------------ injury edit: autosave + undo
tours.add("sc_1539_injury_autosave", {
    steps: () => [
        {
            content: "Type an external note",
            trigger: '.o_sc_autosave[data-sc-field="external_notes"] textarea',
            run: "edit Tour 1539 synthetic external note",
        },
        {
            content: "Leave the field (blur)",
            trigger: ".o_sc_appbar_title",
            run: "click",
        },
        {
            content: "Saved on blur",
            trigger: '.o_sc_autosave[data-sc-field="external_notes"][data-sc-state="saved"]',
        },
        {
            content: "Resolve: instant save",
            trigger: '.o_sc_autosave[data-sc-field="stage"] button[data-sc-value="resolved"]',
            run: "click",
        },
        {
            content: "Saved, « Résolue » pressed",
            trigger:
                '.o_sc_autosave[data-sc-field="stage"][data-sc-state="saved"] button[data-sc-value="resolved"][aria-pressed="true"]',
        },
        {
            content: "Undo from the toast",
            trigger: ".o_sc_toast:not([hidden]) [data-sc-toast-action]",
            run: "click",
        },
        {
            content: "Back to « Active », saved again",
            trigger:
                '.o_sc_autosave[data-sc-field="stage"][data-sc-state="saved"] button[data-sc-value="active"][aria-pressed="true"]',
        },
    ],
});

// ------------------------------------------- new injury: draft + « Créer »
const DIAGNOSIS = "Tour 1539 synthetic diagnosis";

tours.add("sc_1539_new_injury_draft", {
    steps: () => [
        {
            content: "Type the diagnosis",
            trigger: '.o_sc_autosave[data-sc-field="diagnosis"] input',
            run(helpers) {
                window.sessionStorage.setItem("sc1539NewUrl", window.location.href);
                return helpers.edit(DIAGNOSIS);
            },
        },
        {
            content: "Kept as a device draft",
            trigger: '.o_sc_autosave[data-sc-field="diagnosis"][data-sc-state="draft"]',
            run() {
                assert(draftKeys("new_injury.").length === 1, "expected one new-injury draft");
            },
        },
        {
            content: "Leave the page",
            trigger: ".o_sc_app",
            run() {
                window.location.assign("/my/players");
            },
            expectUnloadPage: true,
        },
        {
            trigger: '.o_sc_app a[data-sc-nav-key="players"][aria-current="page"]',
            run() {
                window.location.assign(window.sessionStorage.getItem("sc1539NewUrl"));
            },
            expectUnloadPage: true,
        },
        {
            content: "« Brouillon restauré » with the text",
            trigger: '.o_sc_autosave[data-sc-field="diagnosis"][data-sc-restored="1"]',
            run() {
                const value = document.querySelector('.o_sc_autosave[data-sc-field="diagnosis"] input').value;
                assert(value === DIAGNOSIS, `restored value: ${value}`);
            },
        },
        {
            content: "« Créer »",
            trigger: 'button[data-sc-action="injury.create"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Created landing: the draft is gone",
            trigger: '[data-sc-action="injury.back"]',
            run() {
                assert(draftKeys("new_injury.").length === 0, `drafts left: ${draftKeys()}`);
            },
        },
    ],
});

// ------------------------------------------------ activity complete
tours.add("sc_1539_activity_complete", {
    steps: () => [
        {
            content: "« Fait » on the activity row",
            trigger: 'section[data-sc-tab-panel="activities"]:not([hidden]) button[data-sc-action="activity.complete"]',
            run: "click",
        },
        {
            content: "The sheet received the activity id",
            trigger: 'dialog#sc_activity_complete_sheet[open] textarea[name="feedback"]',
            run(helpers) {
                const id = document.querySelector('#sc_activity_complete_sheet input[name="activity_id"]').value;
                assert(id, "activity_id not filled");
                return helpers.edit("Tour 1539 done");
            },
        },
        {
            content: "Submit (today's route, CSRF)",
            trigger: "dialog#sc_activity_complete_sheet[open] button[type=submit]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the player's Activities tab, confirmation shown",
            trigger: 'section[data-sc-tab-panel="activities"]:not([hidden])',
            run() {
                assert(window.location.search.includes("success=activity_done"), window.location.search);
            },
        },
    ],
});
