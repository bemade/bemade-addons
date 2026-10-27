/*
 * Task 1646 — opening an add panel never focuses a select / picker; on a
 * phone it focuses nothing (tests/test_add_panel_focus_tours_1646.py).
 *
 * sc_1646_notes_laptop: « + Ajouter » of the Notes list → the note's
 * textarea has the focus, not « Link to Injury » (a <select>).
 * sc_1646_notes_touch: matchMedia("(pointer: coarse)") stubbed true → no
 * element of the panel has the focus.
 *
 * The real iPhone (no picker, no keyboard) stays UNVERIFIED until
 * /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const ADD = 'button[data-sc-list-add-toggle][aria-controls="sc_note_add"]';
const PANEL = "details#sc_note_add";

tours.add("sc_1646_notes_laptop", {
    steps: () => [
        {
            content: "« + Ajouter » of the Notes list",
            trigger: ADD,
            run: "click",
        },
        {
            content: "The note text has the focus — never the injury select",
            trigger: `${PANEL}[open] textarea`,
            run() {
                const active = document.activeElement;
                const panel = document.querySelector(PANEL);
                assert(panel.contains(active), `focus outside the panel: ${active && active.tagName}`);
                assert(active.tagName === "TEXTAREA", `focused: ${active.tagName}#${active.id}`);
                assert(document.querySelector(`${PANEL} select`), "the fixture lost its select");
            },
        },
    ],
});

tours.add("sc_1646_notes_touch", {
    steps: () => [
        {
            content: "A touch screen (coarse pointer), then « + Ajouter »",
            trigger: ADD,
            run(helpers) {
                const real = window.matchMedia.bind(window);
                window.matchMedia = (query) =>
                    query.includes("pointer: coarse")
                        ? { matches: true, media: query, addEventListener() {}, removeEventListener() {} }
                        : real(query);
                document.activeElement && document.activeElement.blur();
                return helpers.click();
            },
        },
        {
            content: "Nothing in the panel has the focus (no keyboard, no picker)",
            trigger: `${PANEL}[open] textarea`,
            run() {
                const panel = document.querySelector(PANEL);
                const active = document.activeElement;
                assert(!panel.contains(active) || active === panel,
                    `focused in the panel: ${active && active.tagName}#${active && active.id}`);
            },
        },
    ],
});
