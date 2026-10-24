/*
 * Task 1669 — the injury card's Notes read view shows each note's
 * « Dernière note le … par … » stamp and refreshes it in place after a
 * save (tests/test_card_note_stamps_1669.py). Language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const CARD = 'details.o_sc_injury_item[open] [data-sc-edit-card="injury-notes-external"]';  // task 1675
const FIELD = `${CARD} .o_sc_autosave[data-sc-field="external_notes"]`;
const NEW = "T1669 tour new note";

tours.add("sc_1669_note_stamp", {
    steps: () => [
        {
            content: "No stamp yet (no note history)",
            trigger: `${CARD} [data-sc-edit-view="read"]`,
            run() {
                assert(!document.querySelector(`${CARD} [data-sc-note-stamp="external"]`), "a stamp before any note");
            },
        },
        {
            content: "Edit the notes (pencil)",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Write a new external note",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run: `edit ${NEW}`,
        },
        {
            content: "Leave the field so it saves",
            trigger: `${FIELD} textarea[data-sc-replace="new"]`,
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur"));
            },
        },
        {
            content: "Saved: the (hidden) read view already holds the stamp",
            trigger: `${CARD} [data-sc-edit-view="read"] [data-sc-note-stamp="external"]:not(:visible)`,
        },
        {
            content: "Close the card (pencil)",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "The read view shows the new text and its stamp, no reload",
            trigger: `${CARD} [data-sc-edit-view="read"] [data-sc-note-stamp="external"]`,
            run() {
                const read = document.querySelector(`${CARD} [data-sc-edit-view="read"]`);
                assert(read.textContent.includes(NEW), "read text not refreshed");
                const stamp = read.querySelector('[data-sc-note-stamp="external"]');
                assert(stamp.classList.contains("o_sc_meta"), "stamp not an o_sc_meta line");
                assert(stamp.textContent.includes("PC TP"), `stamp: ${stamp.textContent}`);
            },
        },
    ],
});
