/*
 * Task 1668 — the type-to-filter picker (#1648) on the activity assignee and
 * the other long single-choice lists (tests/test_single_picker_1668.py).
 *
 * sc_1668_activity_form: the « Assigned To » picker of the new-activity form
 * — typing part of a name narrows, a pick sets the select and the « no
 * access » warning follows the pick; the activity is saved with that person.
 * sc_1668_activity_detail: the activity's autosave « Assigned To » is a
 * picker; a pick saves.
 * sc_1668_events_filter: the events « assigned professional » filter.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function pickerOf(select) {
    const next = select.nextElementSibling;
    assert(next && next.classList.contains("o_sc_picker"), "no picker after the select");
    return next;
}

function type(select, text) {
    const input = pickerOf(select).querySelector(".o_sc_picker_input");
    input.focus();
    input.value = text;
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

function pick(select, text) {
    const item = [...pickerOf(select).querySelectorAll(".o_sc_picker_option")].find((li) =>
        li.textContent.includes(text)
    );
    assert(item, `« ${text} » not listed`);
    item.click();
}

const USER = "select#sc_act_user";

tours.add("sc_1668_activity_form", {
    steps: () => [
        {
            content: "The assignee is a picker; nothing focused on open",
            trigger: `${USER} + .o_sc_picker .o_sc_picker_input`,
            run() {
                assert(!document.activeElement.classList.contains("o_sc_picker_input"), "auto-focused");
                const select = document.querySelector(USER);
                type(select, "zed synth");
                const listed = [...pickerOf(select).querySelectorAll(".o_sc_picker_option")].map((li) => li.textContent);
                assert(listed.length === 1 && listed[0].includes("Zed"), `listed: ${listed}`);
                pick(select, "Zed");
                assert(select.options[select.selectedIndex].textContent.includes("Zed"), "not set");
            },
        },
        {
            content: "The « no access » warning follows the pick",
            trigger: "[data-sc-assignee-warning]:not([hidden])",
            run() {
                const select = document.querySelector(USER);
                type(select, "pc tp");
                pick(select, "PC TP");
                assert(document.querySelector("[data-sc-assignee-warning]").hidden, "warning kept");
                type(select, "zed");
                pick(select, "Zed");
                assert(!document.querySelector("[data-sc-assignee-warning]").hidden, "warning not back");
                const summary = document.querySelector("#sc_act_summary");
                summary.value = "T1668 synthetic activity";
                summary.dispatchEvent(new Event("input", { bubbles: true }));
            },
        },
        {
            content: "Save",
            trigger: 'form[data-sc-form="activity.form"] button[type="submit"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Saved",
            trigger: ".o_sc_app",
        },
    ],
});

tours.add("sc_1668_activity_detail", {
    steps: () => [
        {
            content: "Edit the activity (pencil)",
            trigger: '[data-sc-edit-card="activity"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "« Assigned To » is a picker: pick by typing",
            trigger: '[data-sc-edit-card="activity"] .o_sc_autosave[data-sc-field="user_id"] .o_sc_picker_input',
            run() {
                const select = document.querySelector(
                    '[data-sc-edit-card="activity"] .o_sc_autosave[data-sc-field="user_id"] select'
                );
                type(select, "zed");
                pick(select, "Zed");
            },
        },
        {
            content: "Saved on pick",
            trigger: '[data-sc-edit-card="activity"] .o_sc_autosave[data-sc-field="user_id"][data-sc-state="saved"]',
        },
    ],
});

tours.add("sc_1668_events_filter", {
    steps: () => [
        {
            content: "The « assigned professional » filter is a picker",
            trigger: "select#sc_ev_staff + .o_sc_picker .o_sc_picker_input:not(:visible), select#sc_ev_staff + .o_sc_picker .o_sc_picker_input",
            run() {
                const select = document.querySelector("select#sc_ev_staff");
                const details = select.closest("details");
                if (details) {
                    details.open = true;
                }
                type(select, "pc tp");
                pick(select, "PC TP");
                assert(select.options[select.selectedIndex].textContent.includes("PC TP"), "not set");
            },
        },
    ],
});
