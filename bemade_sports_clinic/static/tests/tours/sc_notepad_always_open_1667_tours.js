/*
 * Task 1667 — the Notepad's quick-note form is always shown
 * (tests/test_notepad_always_open_1667.py, phone + laptop).
 *
 * sc_1667_notepad_always_open: the textarea and « Ajouter » are visible
 * with no tap, there is no « + Ajouter » header toggle, nothing is
 * auto-focused (#1646), « Lier cette note » still opens, and a note is
 * added.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(el) {
    if (!el) {
        return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== "hidden";
}

const FORM = 'section#sc_notepad_add form[data-sc-form="note.add"]';
const NOTE = "Tour 1667 synthetic quick note";

tours.add("sc_1667_notepad_always_open", {
    steps: () => [
        {
            content: "The form is there with no tap: textarea + « Ajouter »",
            trigger: `${FORM} .o_sc_autosave textarea`,
            run() {
                const textarea = document.querySelector(`${FORM} .o_sc_autosave textarea`);
                const add = document.querySelector(`${FORM} button[data-sc-action="note.add"]`);
                assert(visible(textarea), "the quick-note textarea is not visible");
                assert(visible(add), "« Ajouter » is not visible");
                assert(!document.querySelector("details#sc_notepad_add"), "the form is still collapsible");
                assert(!document.querySelector('[data-sc-list-add-toggle][aria-controls="sc_notepad_add"]'),
                    "the « + Ajouter » header toggle is still there");
                assert(document.activeElement !== textarea, "the textarea was auto-focused");
            },
        },
        {
            content: "« Lier cette note » still opens",
            trigger: `${FORM} details.o_sc_disclosure > summary`,
            run: "click",
        },
        {
            content: "The link fields show",
            trigger: `${FORM} details.o_sc_disclosure[open] .o_sc_picker`,
        },
        {
            content: "Type a note",
            trigger: `${FORM} .o_sc_autosave textarea`,
            run: `edit ${NOTE}`,
        },
        {
            content: "« Ajouter »",
            trigger: `${FORM} button[data-sc-action="note.add"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The note is listed and the form is still open",
            trigger: `[data-sc-section="notepad.list"] .o_sc_quick_note:contains("${NOTE}")`,
            run() {
                assert(visible(document.querySelector(`${FORM} .o_sc_autosave textarea`)),
                    "the form is gone after the add");
            },
        },
    ],
});
