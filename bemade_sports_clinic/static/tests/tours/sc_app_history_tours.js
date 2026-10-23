/*
 * Task 1581 — one history pattern: the sheet is re-fetched on EVERY open, so
 * a change made on the page shows without a reload
 * (tests/test_app_shell_tours_1581.py). Language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const ANN = "Tour 1581 synthetic announcement";
const NOTE = "Tour 1581 synthetic external note";

function entries(sheet) {
    return [...document.querySelectorAll(`${sheetSel(sheet)}[open] li.o_sc_history_entry`)];
}

// Task 1616: the injury notes live in the open injury card — its combined
// notes-history sheet is « sc_note_history_sheet_<injury id> ».
const NOTES_CARD = 'details.o_sc_injury_item[open] [data-sc-edit-card="injury-notes"]';
const NOTES_SHEET = 'dialog[id^="sc_note_history_sheet_"]:not([id$="_external"]):not([id$="_internal"])';

function sheetSel(sheet) {
    return sheet === "sc_note_history_sheet" ? NOTES_SHEET : `dialog#${sheet}`;
}

// ------------------------------------------------------ team announcement
tours.add("sc_1581_announcement_fresh", {
    steps: () => [
        {
            content: "« History » in the announcement header; mark the page to detect a reload",
            trigger:
                '[data-sc-section="team.announcement.area"] .o_sc_section_header .o_sc_link_btn[data-sc-sheet-open="sc_announcement_history_sheet"]',
            run(helpers) {
                window.__sc1581NoReload = true;
                return helpers.click();
            },
        },
        {
            content: "The sheet lists the existing entries",
            trigger: "dialog#sc_announcement_history_sheet[open] li.o_sc_history_entry",
            run() {
                window.__sc1581Count = entries("sc_announcement_history_sheet").length;
                assert(window.__sc1581Count === 2, `entries: ${window.__sc1581Count}`);
            },
        },
        {
            content: "Close the sheet",
            trigger: "dialog#sc_announcement_history_sheet[open] [data-sc-sheet-close]",
            run: "click",
        },
        {
            content: "Publish an announcement from this page without reloading it",
            trigger: "dialog#sc_announcement_history_sheet:not([open]):not(:visible)",
            async run() {
                const teamId = new URL(window.location.href).searchParams.get("team_id");
                const body = new FormData();
                body.append("csrf_token", odoo.csrf_token);
                body.append("announcement", ANN);
                const resp = await fetch(`/my/team/${teamId}/announcement`, {
                    method: "POST",
                    body,
                    credentials: "same-origin",
                });
                assert(resp.ok, `publish answered ${resp.status}`);
            },
        },
        {
            content: "Open the history again",
            trigger: '.o_sc_link_btn[data-sc-sheet-open="sc_announcement_history_sheet"]',
            run: "click",
        },
        {
            content: "The new entry is there, fetched again (no reload)",
            trigger: `dialog#sc_announcement_history_sheet[open] li.o_sc_history_entry:contains(${ANN})`,
            run() {
                assert(window.__sc1581NoReload, "the page reloaded");
                const count = entries("sc_announcement_history_sheet").length;
                assert(count === window.__sc1581Count + 1, `entries: ${count}`);
            },
        },
    ],
});

// ------------------------------------------------------------ injury notes
tours.add("sc_1581_notes_fresh", {
    steps: () => [
        {
            content: "« History » next to the External Notes label",
            trigger:
                `${NOTES_CARD} .o_sc_edit_card_head .o_sc_link_btn[data-sc-sheet-open^="sc_note_history_sheet_"]`,
            run(helpers) {
                window.__sc1581NoReload = true;
                return helpers.click();
            },
        },
        {
            content: "The notes history, all scopes",
            trigger: `${NOTES_SHEET}[open] nav[data-sc-section="history.scope"] a[href$="scope=all"][aria-pressed="true"]`,
            run() {
                window.__sc1581Count = entries("sc_note_history_sheet").length;
                assert(window.__sc1581Count === 3, `entries: ${window.__sc1581Count}`);
            },
        },
        {
            content: "Filter: internal only (re-fetched inside the sheet)",
            trigger: `${NOTES_SHEET}[open] nav[data-sc-section="history.scope"] a[href$="scope=internal"]`,
            run: "click",
        },
        {
            content: "Only internal entries",
            trigger: `${NOTES_SHEET}[open] a[href$="scope=internal"][aria-pressed="true"]`,
            run() {
                const scopes = entries("sc_note_history_sheet").map((li) => li.dataset.scScope);
                assert(scopes.length === 1 && scopes[0] === "internal", `scopes: ${scopes}`);
            },
        },
        {
            content: "Close the sheet",
            trigger: `${NOTES_SHEET}[open] [data-sc-sheet-close]`,
            run: "click",
        },
        {
            content: "Edit the notes card (pencil)",
            trigger: `${NOTES_CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Type an external note",
            trigger: '.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="external_notes"] textarea',
            run: `edit ${NOTE}`,
        },
        {
            content: "Leave the field so it saves",
            trigger: '.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="external_notes"] textarea',
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Saved",
            trigger: '.o_sc_injury_item[open] .o_sc_autosave[data-sc-field="external_notes"][data-sc-state="saved"]',
        },
        {
            content: "Open the history again",
            trigger:
                `${NOTES_CARD} .o_sc_edit_card_head .o_sc_link_btn[data-sc-sheet-open^="sc_note_history_sheet_"]`,
            run: "click",
        },
        {
            content: "All scopes again, with the new note — no reload",
            trigger: `${NOTES_SHEET}[open] li.o_sc_history_entry:contains(${NOTE})`,
            run() {
                assert(window.__sc1581NoReload, "the page reloaded");
                const count = entries("sc_note_history_sheet").length;
                assert(count === window.__sc1581Count + 1, `entries: ${count}`);
            },
        },
    ],
});
