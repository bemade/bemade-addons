/*
 * Owner review 2026-10-25 (#1675) — a coach reads the injury's external note
 * on the open injury card, without a pencil or an editor
 * (tests/test_note_replace_tours_1582.py). Language-independent triggers.
 */
import { registry } from "@web/core/registry";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const CARD = 'details.o_sc_injury_item[open] [data-sc-edit-card="injury-notes-external"]';

registry.category("web_tour.tours").add("sc_1675_coach_external_readonly", {
    steps: () => [
        {
            content: "The coach reads the external note on the open injury card",
            trigger: `${CARD} [data-sc-display$=":external_notes"]:contains(T1582 tour current text)`,
            run() {
                const card = document.querySelector(CARD);
                assert(!card.querySelector("button[data-sc-edit-toggle]"), "a pencil on the external note");
                assert(!card.querySelector('[data-sc-edit-view="edit"]'), "an external-note editor");
                assert(
                    !document.querySelector('.o_sc_autosave[data-sc-field="external_notes"]'),
                    "an external-note autosave field"
                );
            },
        },
    ],
});
