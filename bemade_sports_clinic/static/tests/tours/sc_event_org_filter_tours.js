/*
 * Task 1597 — browser tour of the event form's organization filter (run by
 * tests/test_event_org_team_filter_1597.py as a clinic administrator, who
 * is offered every team). Language-independent triggers; the organization
 * and team names are the test's synthetic fixtures. Task 1608: the teams
 * are the tags field's browse list (chips) instead of checkboxes.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = "form[data-sc-event-form]";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const TEAMS = `${FORM} [data-sc-event-pick="teams"]`;

// Task 1608 (deliberate update): the teams are a tags field (chips + the
// browse list) instead of checkboxes; the organization select narrows it.
function offered() {
    return [...document.querySelectorAll(`${TEAMS} .o_sc_tags_option`)].map((el) => el.textContent.trim());
}

function chosen() {
    return [...document.querySelectorAll(`${TEAMS} .o_sc_tag > span`)].map((el) => el.textContent.trim());
}

async function openList() {
    const input = document.querySelector(`${TEAMS} input.o_sc_tags_search`);
    input.focus();
    input.click();
    await waitFor(() => document.querySelector(`${TEAMS} [data-sc-tags-open="1"]`), "the list opens");
}

async function pickTeam(label) {
    await openList();
    const button = [...document.querySelectorAll(`${TEAMS} .o_sc_tags_option`)].find(
        (el) => el.textContent.trim() === label
    );
    assert(button, `team « ${label} » is offered`);
    button.click();
    await waitFor(() => chosen().includes(label), `${label} chosen`);
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

function setValue(selector, value) {
    const input = document.querySelector(selector);
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

function selectOrg(select, text) {
    const option = [...select.options].find((opt) => opt.text === text);
    assert(option, `the organization ${text} is offered`);
    select.value = option.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
}

tours.add("sc_1597_event_org_filter", {
    steps: () => [
        {
            content: "All organizations: teams of both organizations are offered",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            async run() {
                assert(document.querySelector(`${FORM} select[data-sc-org-select]`).value === "", "no organization is preselected");
                await openList();
                const labels = offered();
                assert(labels.includes("PC Team A"), "PC Team A shown");
                assert(labels.includes("ZZ Team C 1597"), "ZZ Team C shown");
                assert(labels.includes("ZZ Free Team 1597"), "the team without organization is shown");
            },
        },
        {
            content: "Pick a team of each organization",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            async run() {
                await pickTeam("PC Team A");
                await pickTeam("ZZ Team C 1597");
            },
        },
        {
            content: "Pick the second organization",
            trigger: `${FORM} select[data-sc-org-select]`,
            run() {
                selectOrg(this.anchor, "ZZ Org 1597");
            },
        },
        {
            content: "Only its teams remain; the other organization's team is dropped",
            trigger: `${TEAMS} .o_sc_tag:contains("ZZ Team C 1597")`,
            async run() {
                await waitFor(() => !chosen().includes("PC Team A"), "PC Team A dropped");
                assert(JSON.stringify(chosen()) === JSON.stringify(["ZZ Team C 1597"]), `chosen: ${chosen().join(", ")}`);
                const hidden = document.querySelector(`${FORM} input[name="team_ids"]`).value;
                assert(hidden.split(",").length === 1, `team_ids: ${hidden}`);
                await openList();
                await waitFor(() => !offered().includes("PC Team A") && !offered().includes("ZZ Free Team 1597"),
                    `only the organization's teams offered (got ${offered().join(", ")})`);
            },
        },
        {
            content: "Back to all organizations: every team is offered again, picks kept",
            trigger: `${FORM} select[data-sc-org-select]`,
            async run() {
                this.anchor.value = "";
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
                await openList();
                await waitFor(() => offered().includes("PC Team A"), "PC Team A offered again");
                assert(!chosen().includes("PC Team A"), "PC Team A stays dropped");
                assert(chosen().includes("ZZ Team C 1597"), "ZZ Team C stays chosen");
                selectOrg(this.anchor, "ZZ Org 1597");
            },
        },
        {
            content: "Fill the event and create it",
            trigger: `${FORM} input[name="name"]`,
            expectUnloadPage: true,
            run() {
                setValue(`${FORM} input[name="name"]`, "SC 1597 Tour");
                setValue(`${FORM} input[name="date_start"]`, "2026-05-04T18:00");
                setValue(`${FORM} input[name="date_end"]`, "2026-05-04T20:00");
                document.querySelector(`${FORM} button[data-sc-action="event.save"]`).click();
            },
        },
        {
            content: "The event page opens",
            trigger: ".o_sc_app [data-sc-section='event.hero']",
        },
    ],
});
