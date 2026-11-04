/*
 * Task 1724 — « Annuler » in the inline add panels: closes the panel,
 * clears its fields (and device drafts), the focus goes back to the
 * header's « + Ajouter » (tests/test_add_cancel_1724.py, phone + laptop).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function type(el, value) {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function cancelSteps(panelId, fieldSelector, name) {
    const ADD = `button[data-sc-list-add-toggle][aria-controls="${panelId}"]`;
    const PANEL = `details#${panelId}`;
    return [
        {
            content: `${name}: « + Ajouter » opens the panel`,
            trigger: ADD,
            run: "click",
        },
        {
            content: `${name}: type something`,
            trigger: `${PANEL}[open] ${fieldSelector}`,
            run() {
                type(document.querySelector(`${PANEL} ${fieldSelector}`), "Synthetic typed text");
            },
        },
        {
            content: `${name}: « Annuler »`,
            trigger: `${PANEL}[open] button[data-sc-list-add-cancel]`,
            run: "click",
        },
        {
            content: `${name}: closed, the focus on « + Ajouter »`,
            trigger: `${PANEL}:not([open]):not(:visible)`,
            run() {
                const add = document.querySelector(ADD);
                assert(add.getAttribute("aria-expanded") === "false", "aria-expanded");
                assert(document.activeElement === add, "focus not on « + Ajouter »");
                add.click();
            },
        },
        {
            content: `${name}: reopened, the field is empty`,
            trigger: `${PANEL}[open] ${fieldSelector}`,
            run() {
                const value = document.querySelector(`${PANEL} ${fieldSelector}`).value;
                assert(value === "", `kept: ${value}`);
            },
        },
    ];
}

tours.add("sc_1724_activity_cancel", {
    steps: () => cancelSteps("sc_activity_add", 'input[name="summary"]', "Activity"),
});

tours.add("sc_1724_note_cancel", {
    steps: () => cancelSteps("sc_note_add", "textarea", "Note"),
});
