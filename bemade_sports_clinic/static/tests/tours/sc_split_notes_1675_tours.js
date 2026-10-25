/*
 * Task 1675 — the external and internal injury notes are edited
 * independently, one pencil each (tests/test_split_injury_notes_1675.py,
 * phone + laptop). Language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

/** The block's visible text, whitespace-normalised. */
function readText(el) {
    return (el ? el.textContent : '').replace(/\s+/g, ' ').trim();
}


function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const NOTES = 'details.o_sc_injury_item[open] section[data-sc-section="injury.notes"]';
const EXT = `${NOTES} [data-sc-edit-card="injury-notes-external"]`;
const INT = `${NOTES} [data-sc-edit-card="injury-notes-internal"]`;

function editing(card) {
    return !document.querySelector(`${card} [data-sc-edit-view="edit"]`).hidden;
}

function noteSteps(card, scope, text, other) {
    return [
        {
            content: `The ${scope} pencil`,
            trigger: `${card} button[data-sc-edit-toggle]`,
            run(helpers) {
                // CI 2026-10-25: compare the visible text, not the markup (a fragment
                // refresh may redraw the other block with identical content).
                window[`__sc1675Other_${scope}`] = readText(document.querySelector(`${other} [data-sc-edit-view="read"]`));
                return helpers.click();
            },
        },
        {
            content: `Only the ${scope} editor opens`,
            trigger: `${card}[data-sc-edit-open] .o_sc_autosave[data-sc-field="${scope}_notes"] textarea[data-sc-replace="new"]`,
            run() {
                assert(!editing(other), "the other note opened too");
                assert(!document.querySelector(`${other}[data-sc-edit-open]`), "the other card is in edit mode");
            },
        },
        {
            content: `Write a new ${scope} note`,
            trigger: `${card} .o_sc_autosave[data-sc-field="${scope}_notes"] textarea[data-sc-replace="new"]`,
            run: `edit ${text}`,
        },
        {
            content: "Leave the field so it saves",
            trigger: `${card} .o_sc_autosave[data-sc-field="${scope}_notes"] textarea[data-sc-replace="new"]`,
            run() {
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur"));
            },
        },
        {
            content: "Saved: the card's read view holds the new text and its stamp",
            trigger: `${card} [data-sc-edit-view="read"]:not(:visible):contains(${text})`,
            run() {
                assert(this.anchor.querySelector(`[data-sc-note-stamp="${scope}"]`), "no stamp");
            },
        },
        {
            content: `Close the ${scope} note (pencil)`,
            trigger: `${card} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Closed; the other note's read view is unchanged",
            trigger: `${card}:not([data-sc-edit-open]) [data-sc-edit-view="read"] [data-sc-note-stamp="${scope}"]`,
            run() {
                const before = window[`__sc1675Other_${scope}`];
                const after = readText(document.querySelector(`${other} [data-sc-edit-view="read"]`));
                assert(before === after, "the other note's block changed");
                assert(!editing(other), "the other note is in edit mode");
            },
        },
    ];
}

tours.add("sc_1675_split_notes", {
    steps: () => [
        ...noteSteps(EXT, "external", "T1675 new external", INT),
        ...noteSteps(INT, "internal", "T1675 new internal", EXT),
    ],
});
