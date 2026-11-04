/*
 * Task 1608 — browser tours of the event form's compact multi-selects
 * (browse-all list) and of the coverage-time snapping (create form and the
 * event page's pencil card). Run by tests/test_event_form_pickers_1608.py;
 * language-independent triggers, the test's synthetic fixtures.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = "form[data-sc-event-form]";
const TEAMS = `${FORM} [data-sc-event-pick="teams"]`;
const STAFF = `${FORM} [data-sc-event-pick="staff"]`;
const CARD = '[data-sc-edit-card="event"]';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function optionLabels(root) {
    return [...document.querySelectorAll(`${root} .o_sc_tags_option`)].map((el) => el.textContent.trim());
}

function value(selector) {
    return document.querySelector(selector).value;
}

/** A picked (not typed) datetime-local value: change, then leave the field. */
function pick(selector, val) {
    const input = document.querySelector(selector);
    input.value = val;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur"));
}

tours.add("sc_1608_event_form_pickers", {
    steps: () => [
        {
            content: "Focus the teams field without typing: the full list opens",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            run: "click",
        },
        {
            content: "Every team is listed, grouped by organization",
            trigger: `${TEAMS} [data-sc-tags-open="1"] ul.o_sc_tags_options .o_sc_tags_option`,
            run() {
                const labels = optionLabels(TEAMS);
                for (const name of ["AA Unstaffed 1577", "PC Team A", "PC Team B", "ZZ Team C 1597", "ZZ Free Team 1597"]) {
                    assert(labels.includes(name), `${name} listed (got ${labels.join(", ")})`);
                }
                const groups = [...document.querySelectorAll(`${TEAMS} .o_sc_tags_group`)].map((el) =>
                    el.textContent.trim()
                );
                assert(groups.includes("PC Org") && groups.includes("ZZ Org 1597"), `groups: ${groups.join(", ")}`);
                assert(groups.length === 3, `three groups (got ${groups.join(", ")})`);
            },
        },
        {
            content: "Pick PC Team A from the list",
            trigger: `${TEAMS} .o_sc_tags_option:contains("PC Team A")`,
            run: "click",
        },
        {
            content: "A chip, the hidden field holds it, the list CLOSED after the pick",
            trigger: `${TEAMS} .o_sc_tag:contains("PC Team A")`,
            async run() {
                await waitFor(() => value('input[name="team_ids"]') !== "", "team_ids filled");
                assert(value('input[name="team_ids"]').split(",").length === 1, "one team");
                await waitFor(() => document.querySelector(`${TEAMS} [data-sc-tags-open="0"]`), "the list closes");
                assert(!document.querySelector(`${TEAMS} ul.o_sc_tags_options`), "no option list after a pick");
            },
        },
        {
            content: "Clicking the box again reopens the list, without the picked team",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            run: "click",
        },
        {
            content: "Reopened: the picked team left the list",
            trigger: `${TEAMS} [data-sc-tags-open="1"] ul.o_sc_tags_options .o_sc_tags_option`,
            run() {
                assert(!optionLabels(TEAMS).includes("PC Team A"), "a picked team leaves the list");
                assert(optionLabels(TEAMS).includes("PC Team B"), "the others are still offered");
            },
        },
        {
            content: "Type to narrow the list",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            run: "edit team b",
        },
        {
            content: "Only the match is left",
            trigger: `${TEAMS} .o_sc_tags_option:contains("PC Team B")`,
            run() {
                const labels = optionLabels(TEAMS);
                assert(JSON.stringify(labels) === JSON.stringify(["PC Team B"]), `narrowed to ${labels.join(", ")}`);
            },
        },
        {
            content: "Pick it with the keyboard",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            run: "press ArrowDown",
        },
        {
            content: "Enter picks the highlighted option",
            trigger: `${TEAMS} .o_sc_tags_option_active:contains("PC Team B")`,
            run() {
                const input = document.querySelector(`${TEAMS} input.o_sc_tags_search`);
                input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
            },
        },
        {
            content: "Two teams in the hidden field; Enter closed the list too",
            trigger: `${TEAMS} .o_sc_tag:contains("PC Team B")`,
            async run() {
                await waitFor(() => value('input[name="team_ids"]').split(",").length === 2, "two teams");
                await waitFor(() => document.querySelector(`${TEAMS} [data-sc-tags-open="0"]`), "Enter closes the list");
                const input = document.querySelector(`${TEAMS} input.o_sc_tags_search`);
                assert(document.activeElement === input, "the keyboard keeps the focus in the box");
                // ArrowDown reopens it, Escape closes it again.
                input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true }));
                await waitFor(() => document.querySelector(`${TEAMS} [data-sc-tags-open="1"]`), "ArrowDown reopens");
                input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
                await waitFor(() => document.querySelector(`${TEAMS} [data-sc-tags-open="0"]`), "Escape closes");
            },
        },
        {
            content: "Focus the staff field: every therapist is listed",
            trigger: `${STAFF} input.o_sc_tags_search`,
            run: "click",
        },
        {
            content: "Pick the therapist",
            trigger: `${STAFF} .o_sc_tags_option:contains("PC TP")`,
            run: "click",
        },
        {
            content: "The staff hidden field holds them; that list closed too",
            trigger: `${STAFF} .o_sc_tag:contains("PC TP")`,
            async run() {
                await waitFor(() => value('input[name="assigned_staff_ids"]') !== "", "staff filled");
                await waitFor(() => document.querySelector(`${STAFF} [data-sc-tags-open="0"]`), "the staff list closes");
            },
        },
        {
            content: "A new start moves the end and both coverage times",
            trigger: `${FORM} input[name="date_start"]`,
            run() {
                pick(`${FORM} input[name="date_start"]`, "2026-05-04T18:00");
                assert(value(`${FORM} input[name="therapist_start"]`) === "2026-05-04T18:00", "coverage start = start");
                assert(value(`${FORM} input[name="date_end"]`) === "2026-05-04T20:00", "end = start + 2 h");
                assert(value(`${FORM} input[name="therapist_end"]`) === "2026-05-04T20:00", "coverage end = end");
            },
        },
        {
            content: "A later end moves the coverage end; an earlier one does not",
            trigger: `${FORM} input[name="date_end"]`,
            run() {
                pick(`${FORM} input[name="date_end"]`, "2026-05-04T21:00");
                assert(value(`${FORM} input[name="therapist_end"]`) === "2026-05-04T21:00", "coverage end follows");
                pick(`${FORM} input[name="date_end"]`, "2026-05-04T20:30");
                assert(value(`${FORM} input[name="therapist_end"]`) === "2026-05-04T21:00", "coverage end kept");
                pick(`${FORM} input[name="date_end"]`, "2026-05-04T21:00");
            },
        },
        {
            content: "Name it and create it",
            trigger: `${FORM} input[name="name"]`,
            expectUnloadPage: true,
            run() {
                const name = document.querySelector(`${FORM} input[name="name"]`);
                name.value = "SC 1608 Tour";
                name.dispatchEvent(new Event("input", { bubbles: true }));
                document.querySelector(`${FORM} button[data-sc-action="event.save"]`).click();
            },
        },
        {
            content: "The event page opens",
            trigger: ".o_sc_app [data-sc-section='event.hero']",
        },
    ],
});

tours.add("sc_1608_event_page_snap", {
    steps: () => [
        {
            content: "Open the event card",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Pick a new start and leave it",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="date_start"] input`,
            run() {
                pick(`${CARD} .o_sc_autosave[data-sc-field="date_start"] input`, "2026-03-05T17:30");
            },
        },
        {
            content: "The end and both coverage times follow in the card",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="date_start"][data-sc-state="saved"]`,
            async run() {
                const field = (name) => document.querySelector(`${CARD} .o_sc_autosave[data-sc-field="${name}"] input`);
                await waitFor(() => field("date_end").value === "2026-03-05T19:30", "end follows");
                await waitFor(() => field("therapist_start").value === "2026-03-05T17:30", "coverage start follows");
                await waitFor(() => field("therapist_end").value === "2026-03-05T19:30", "coverage end follows");
            },
        },
    ],
});
