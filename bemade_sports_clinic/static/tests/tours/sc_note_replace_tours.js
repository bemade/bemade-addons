/*
 * Task 1582 — the injury notes' « replace » editor
 * (tests/test_note_replace_tours_1582.py): an EMPTY « New note » under the
 * read-only current text, « Reuse current text » prefills, an empty editor
 * never saves, a save replaces the text (a history row is added, the Notes
 * head's « History » sheet shows it — task 1631: the only one). Language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const CURRENT = "T1582 tour current text";
const NEW = "T1582 tour replaced text";
const FIELD = '.o_sc_autosave[data-sc-field="external_notes"]';

tours.add("sc_1582_note_replace", {
    steps: () => [
        {
            content: "Edit the notes card (pencil)",
            // Task 1616: the open injury card's Notes group.
            trigger: 'details.o_sc_injury_item[open] [data-sc-edit-card="injury-notes"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "The current text is shown read-only above an EMPTY editor",
            trigger: `${FIELD} [data-sc-replace="current"] .o_sc_replace_current_text:contains(${CURRENT})`,
            run() {
                const area = document.querySelector(`${FIELD} textarea[data-sc-replace="new"]`);
                assert(area, "no « New note » editor");
                assert(area.value === "", `editor not empty: ${area.value}`);
                assert(area.placeholder, "no placeholder");
                assert(document.querySelector(`${FIELD} .o_sc_replace_reuse`), "no « Reuse » button");
                assert(document.querySelector(`${FIELD} .o_sc_replace_hint`), "no replace hint");
            },
        },
        {
            content: "Type something…",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run: "edit T1582 tour scratch",
        },
        {
            content: "…empty the editor again and leave it",
            trigger: `${FIELD}[data-sc-state="dirty"] textarea[data-sc-replace="new"]`,
            run() {
                this.anchor.value = "";
                this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "An empty editor never saves: idle, the current text untouched",
            trigger: `${FIELD}[data-sc-state="idle"] .o_sc_replace_current_text:contains(${CURRENT})`,
        },
        {
            content: "« Reuse current text » prefills the editor",
            trigger: `${FIELD} .o_sc_replace_reuse`,
            run: "click",
        },
        {
            content: "The editor holds the current text, cursor at the start",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run() {
                assert(this.anchor.value === CURRENT, `prefill: ${this.anchor.value}`);
                assert(this.anchor.selectionStart === 0, `cursor: ${this.anchor.selectionStart}`);
                // The button goes away while the editor holds text.
                assert(!document.querySelector(`${FIELD} .o_sc_replace_reuse`), "reuse still offered");
            },
        },
        {
            content: "Write the new state of the injury",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run: `edit ${NEW}`,
        },
        {
            content: "Leave the field so it saves",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Saved: the new text is the current one, the editor is empty again",
            trigger: `${FIELD}[data-sc-state="saved"] .o_sc_replace_current_text:contains(${NEW})`,
            run() {
                const area = document.querySelector(`${FIELD} textarea[data-sc-replace="new"]`);
                assert(area.value === "", `editor not emptied: ${area.value}`);
                const read = document.querySelector('[data-sc-display$=":external_notes"]');
                assert(read && read.textContent.includes(NEW), "read view not refreshed");
            },
        },
        // Task 1631: no per-field « History » — the Notes head's one (both
        // scopes, each entry labelled), in edit mode too.
        {
            content: "No « History » next to the replace hint; the head's one opens the history",
            trigger: `[data-sc-edit-card="injury-notes"] .o_sc_edit_card_head [data-sc-sheet-open^="sc_note_history_sheet_"]`,
            run(helpers) {
                assert(
                    !document.querySelector(`${FIELD} [data-sc-sheet-open^="sc_note_history_sheet_"]`),
                    "a per-field History link"
                );
                return helpers.click();
            },
        },
        {
            content: "The history lists the new text and keeps the previous one",
            trigger: `dialog[id^="sc_note_history_sheet_"][open] li.o_sc_history_entry:contains(${NEW})`,
            run() {
                const rows = [...document.querySelectorAll('dialog[id^="sc_note_history_sheet_"][open] li.o_sc_history_entry')];
                assert(
                    rows.some((li) => li.textContent.includes(CURRENT)),
                    "the previous text is not kept in the history"
                );
            },
        },
    ],
});
