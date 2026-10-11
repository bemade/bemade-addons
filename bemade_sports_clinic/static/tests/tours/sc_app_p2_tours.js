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

// ------------------- player status: the hero pill follows the save (2026-10-10)
tours.add("sc_status_pill_refresh", {
    steps: () => [
        {
            content: "Available: the hero pill is green; mark the page to detect a reload",
            trigger: "[data-sc-stage-chip].o_sc_chip_green",
            run() {
                window.__scPillNoReload = true;
            },
        },
        {
            content: "Pick « No play »",
            trigger: '.o_sc_autosave[data-sc-field="sc_status"] button[data-sc-value="no:no"]',
            run: "click",
        },
        {
            content: "Saved",
            trigger:
                '.o_sc_autosave[data-sc-field="sc_status"][data-sc-state="saved"] button[data-sc-value="no:no"][aria-pressed="true"]',
        },
        {
            content: "The hero pill turned red in place (no reload)",
            trigger: "[data-sc-stage-chip].o_sc_chip_red",
            run() {
                if (!window.__scPillNoReload) {
                    throw new Error("the page reloaded");
                }
            },
        },
    ],
});

// ------------- player page: one pencil per card, read view updates in place
tours.add("sc_player_inline_edit", {
    steps: () => [
        {
            content: "Identity card in read mode; mark the page to detect a reload",
            trigger: '[data-sc-edit-card="identity"] [data-sc-edit-view="read"]',
            run() {
                const edit = document.querySelector('[data-sc-edit-card="identity"] [data-sc-edit-view="edit"]');
                if (!edit || !edit.hidden) {
                    throw new Error("the edit view is not hidden by default");
                }
                window.__scInlineNoReload = true;
            },
        },
        {
            content: "Pencil: the card's fields appear",
            trigger: '[data-sc-edit-card="identity"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Edit the position",
            trigger: '[data-sc-edit-card="identity"] [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="position"] input',
            run: "edit Safety",
        },
        {
            content: "Leave the field (saves)",
            trigger: ".o_sc_appbar_title",
            run: "click",
        },
        {
            content: "Saved",
            trigger: '[data-sc-edit-card="identity"] .o_sc_autosave[data-sc-field="position"][data-sc-state="saved"]',
        },
        {
            content: "Done: back to read mode",
            trigger: '[data-sc-edit-card="identity"] button[data-sc-edit-done]',
            run: "click",
        },
        {
            content: "The read view shows the new position, without a reload",
            trigger: '[data-sc-edit-card="identity"] [data-sc-edit-view="read"]',
            run() {
                if (!document.querySelector('[data-sc-edit-card="identity"] [data-sc-edit-view="edit"]').hidden) {
                    throw new Error("« Done » left the edit view open");
                }
                const shown = document.querySelector('[data-sc-edit-card="identity"] [data-sc-display$=":position"]');
                if (!window.__scInlineNoReload) {
                    throw new Error("the page reloaded");
                }
                if (!shown || shown.textContent.trim() !== "Safety") {
                    throw new Error(`read view shows « ${shown && shown.textContent} »`);
                }
            },
        },
        {
            content: "The app bar context follows",
            trigger: '.o_sc_appbar_context:contains("Safety")',
        },
    ],
});

// ---------------- player page Teams card: chips + search to add (2026-10-10)
tours.add("sc_player_teams_tags", {
    steps: () => [
        {
            content: "Open the Teams card",
            trigger: '[data-sc-edit-card="teams"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "The current team is a chip",
            trigger: '[data-sc-edit-card="teams"] .o_sc_tags .o_sc_tag:contains("PC Team A")',
        },
        {
            content: "Search a team to add",
            trigger: '[data-sc-edit-card="teams"] .o_sc_tags_search',
            run: "edit Team C",
        },
        {
            content: "Pick it in the suggestions",
            trigger: '[data-sc-edit-card="teams"] .o_sc_tags_option:contains("PC Team C")',
            run: "click",
        },
        {
            content: "Added and saved",
            trigger:
                '[data-sc-edit-card="teams"] .o_sc_autosave[data-sc-state="saved"] .o_sc_tag:contains("PC Team C")',
        },
        {
            content: "Remove Team A",
            trigger: '[data-sc-edit-card="teams"] .o_sc_tag:contains("PC Team A") button.o_sc_tag_remove',
            run: "click",
        },
        {
            content: "Only Team C left, saved",
            trigger:
                '[data-sc-edit-card="teams"] .o_sc_autosave[data-sc-state="saved"] .o_sc_tags:not(:has(.o_sc_tag:contains("PC Team A")))',
        },
    ],
});
