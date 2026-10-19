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
            trigger: '[data-sc-section="players.list"] [data-sc-player-id] a.o_sc_link_row_main',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Player page: it opens on « Blessures » (owner review 2026-10-11)",
            trigger: 'section[data-sc-tab-panel="injuries"]:not([hidden]) [data-sc-injury-id]',
        },
        {
            content: "Switch to « Infos » in place",
            trigger: '[data-sc-tabs] a[data-sc-tab="info"]',
            run: "click",
        },
        {
            trigger: 'section[data-sc-tab-panel="info"]:not([hidden]) [data-sc-section="player.info.teams"]',
            run() {
                assert(window.location.search.includes("tab=info"), "?tab= kept in the URL");
                const injuries = document.querySelector('section[data-sc-tab-panel="injuries"]');
                assert(injuries.hidden, "injuries still shown");
            },
        },
        {
            content: "Back to « Blessures »",
            trigger: '[data-sc-tabs] a[data-sc-tab="injuries"]',
            run: "click",
        },
        {
            trigger: 'section[data-sc-tab-panel="injuries"]:not([hidden]) [data-sc-injury-id]',
        },
    ],
});

// ------------------------------------------ injury edit: autosave + undo
tours.add("sc_1539_injury_autosave", {
    steps: () => [
        {
            content: "Edit the notes card (pencil paradigm, owner review 2026-10-11)",
            trigger: '[data-sc-edit-card="injury-notes"] button[data-sc-edit-toggle]',
            run: "click",
        },
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
            content: "Edit the details card (pencil)",
            trigger: '[data-sc-edit-card="injury-details"] button[data-sc-edit-toggle]',
            run: "click",
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
            // Task 1579: no « created » POST-result page any more — the
            // player's Injuries tab (the canonical page) is the landing.
            content: "Landed on the player's injuries: the draft is gone",
            trigger: '.o_sc_app [data-sc-tab-panel="injuries"]:not([hidden])',
            run() {
                assert(window.location.pathname === "/my/player", window.location.href);
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
    // Owner review 2026-10-11: the status selector lives in the page header
    // (in place of the status pill) and saves in place. Review fixes
    // 2026-10-18: the header is a read view; its pencil opens the selector.
    steps: () => [
        {
            content: "Read view: the status label; mark the page to detect a reload, open the pencil",
            trigger: '[data-sc-section="player.hero"] [data-sc-edit-view="read"] [data-sc-stage-chip]',
            run() {
                window.__scPillNoReload = true;
                document.querySelector('[data-sc-section="player.hero"] > button[data-sc-edit-toggle]').click();
            },
        },
        {
            content: "Available: « Match + practice » pressed in the header's edit view",
            trigger: '[data-sc-section="player.hero"] .o_sc_autosave[data-sc-field="sc_status"] button[data-sc-value="yes:yes"][aria-pressed="true"]',
        },
        {
            content: "Pick « No play »",
            trigger: '[data-sc-section="player.hero"] .o_sc_autosave[data-sc-field="sc_status"] button[data-sc-value="no:no"]',
            run: "click",
        },
        {
            content: "Saved in place (no reload)",
            trigger:
                '[data-sc-section="player.hero"] .o_sc_autosave[data-sc-field="sc_status"][data-sc-state="saved"] button[data-sc-value="no:no"][aria-pressed="true"]',
            run() {
                if (!window.__scPillNoReload) {
                    throw new Error("the page reloaded");
                }
            },
        },
        {
            content: "« Done » closes the header's edit view",
            trigger: '[data-sc-section="player.hero"] [data-sc-edit-view="edit"] button[data-sc-edit-done]',
            run: "click",
        },
        {
            content: "The read view shows the new status (read fragment, no reload)",
            trigger: '[data-sc-section="player.hero"] [data-sc-edit-view="read"] [data-sc-stage-chip].o_sc_chip_red',
            run() {
                if (!window.__scPillNoReload) {
                    throw new Error("the page reloaded");
                }
            },
        },
    ],
});

// ------------- player page: inline « Add Injury », then « Undo »
tours.add("sc_injury_inline_create", {
    steps: () => [
        {
            content: "Open « Add Injury » from the list header's « + Ajouter »",
            trigger: '.o_sc_list_header button.o_sc_list_add[aria-controls="sc_new_injury"][aria-expanded="false"]',
            run: "click",
        },
        {
            content: "Only the visibility question first: no diagnosis yet",
            trigger: 'details#sc_new_injury[open] [data-sc-step="visibility"]',
            run() {
                const diag = document.querySelector('details#sc_new_injury [data-sc-step="diagnosis"]');
                if (diag.offsetParent !== null) {
                    throw new Error("the diagnosis shows before the visibility choice");
                }
            },
        },
        {
            content: "Answer « No, hide it »",
            trigger: 'details#sc_new_injury label.o_sc_choice_option:has(input[value="hidden"])',
            run: "click",
        },
        {
            content: "The diagnosis appears; type it",
            trigger: 'details#sc_new_injury [data-sc-step="diagnosis"] input[name="diagnosis"]:visible',
            run: "edit Synthetic tour ankle",
        },
        {
            content: "Create",
            trigger: 'details#sc_new_injury button[data-sc-action="injury.create"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The new injury is open in edit mode, with « Undo » offered",
            trigger: '.o_sc_injury_item[data-sc-created-injury][open] [data-sc-edit-view="edit"]:not([hidden])',
        },
        {
            content: "Undo",
            trigger: '.o_sc_toast:not([hidden]) [data-sc-toast-action]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the Injuries tab, the injury is gone",
            trigger: 'section[data-sc-tab-panel="injuries"]:not([hidden])',
            run() {
                if ([...document.querySelectorAll(".o_sc_injury_item")].some((el) => el.textContent.includes("Synthetic tour ankle"))) {
                    throw new Error("the undone injury is still listed");
                }
            },
        },
    ],
});

// ------------- player page: « Resolved » fills the resolution date in place
tours.add("sc_injury_resolve_date", {
    steps: () => [
        {
            content: "The injury is open; mark the page and edit it",
            trigger: ".o_sc_injury_item[open] [data-sc-edit-toggle]",
            run(helpers) {
                window.__scResolveNoReload = true;
                helpers.click();
            },
        },
        {
            // Review fixes 2026-10-18: the resolution date field is hidden
            // until the injury is resolved.
            content: "No resolution date yet (its field hidden while active)",
            trigger: '.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="predicted_resolution_date"] input',
            run() {
                const input = document.querySelector(
                    '.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="resolution_date"] input'
                );
                if (input.value) {
                    throw new Error(`resolution date already set: ${input.value}`);
                }
                if (input.offsetParent) {
                    throw new Error("the resolution date shows on an active injury");
                }
            },
        },
        {
            content: "Resolve",
            trigger: '.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="stage"] button[data-sc-value="resolved"]',
            run: "click",
        },
        {
            content: "The resolution date shows at once (no reload)",
            trigger: `.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="resolution_date"] input:value(${new Date().getFullYear()})`,
            run() {
                if (!window.__scResolveNoReload) {
                    throw new Error("the page reloaded");
                }
            },
        },
    ],
});

// ------------- event page: the pencil card (owner review 2026-10-11)
tours.add("sc_event_pencil", {
    steps: () => [
        {
            content: "Read view first; open the pencil",
            trigger: '[data-sc-edit-card="event"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Rename the event",
            trigger: '[data-sc-edit-card="event"] .o_sc_autosave[data-sc-field="name"] input',
            run: "edit Synthetic pencil event",
        },
        {
            content: "Leave the field so it saves",
            trigger: '[data-sc-edit-card="event"] .o_sc_autosave[data-sc-field="name"] input',
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Saved",
            trigger: '[data-sc-edit-card="event"] .o_sc_autosave[data-sc-field="name"][data-sc-state="saved"]',
        },
        {
            content: "Done: the card closes (task 1611: no reload, the title is a read fragment)",
            trigger: '[data-sc-edit-card="event"] [data-sc-edit-done]',
            run: "click",
        },
        {
            content: "The title shows the new name",
            trigger: '.o_sc_appbar_title:contains(Synthetic pencil event)',
        },
    ],
});

// ------------- player page: training history refreshes without a reload
tours.add("sc_training_history_refresh", {
    steps: () => [
        {
            content: "Open the (empty) training history; mark the page to detect a reload",
            trigger: '[data-sc-section="player.training"] .o_sc_field_label [data-sc-sheet-open="sc_training_history_sheet"]',
            run(helpers) {
                window.__scTrainingNoReload = true;
                helpers.click();
            },
        },
        {
            content: "Nothing yet",
            trigger: "dialog#sc_training_history_sheet[open] .o_sc_empty:not(.o_sc_lazy_loading)",
        },
        {
            content: "Close the sheet",
            trigger: "dialog#sc_training_history_sheet[open] [data-sc-sheet-close]",
            run: "click",
        },
        {
            content: "Review fixes 2026-10-18: the header's pencil opens its edit view",
            trigger: '[data-sc-section="player.hero"] > button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Type a recommendation",
            trigger: '.o_sc_autosave[data-sc-field="training_recommendation"] textarea',
            run: "edit Synthetic bike only",
        },
        {
            content: "Leave the field so it saves",
            trigger: '.o_sc_autosave[data-sc-field="training_recommendation"] textarea',
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Saved",
            trigger: '.o_sc_autosave[data-sc-field="training_recommendation"][data-sc-state="saved"]',
        },
        {
            // Task 1601: the « Updated on … by … » stamp appears in place.
            content: "The authorship stamp is updated without a reload",
            trigger: '.o_sc_autosave[data-sc-field="training_recommendation"] .o_sc_hint:contains(Updated on):contains(PC TP)',
        },
        {
            content: "Open the history again (the edit view's link)",
            trigger: '[data-sc-section="player.training.edit"] [data-sc-sheet-open="sc_training_history_sheet"]',
            run: "click",
        },
        {
            content: "The new recommendation is listed, without a reload",
            trigger: "dialog#sc_training_history_sheet[open] li:contains(Synthetic bike only)",
            run() {
                if (!window.__scTrainingNoReload) {
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
            // Task 1579: the context line is the PHONE's (hidden on a
            // laptop, where this tour runs): check its text, not visibility.
            // Task 1611: refreshed as a read fragment (a fetch after the save).
            content: "The app bar context follows",
            trigger: '[data-sc-edit-card="identity"] [data-sc-edit-view="read"]',
            async run() {
                const start = Date.now();
                const context = () => document.querySelector(".o_sc_appbar_context");
                while (!(context() && context().textContent.includes("Safety"))) {
                    if (Date.now() - start > 8000) {
                        throw new Error(`context line reads « ${context() && context().textContent} »`);
                    }
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
            },
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
