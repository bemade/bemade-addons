/*
 * Task 1723 — creating an event: a typed team is picked or refused clearly,
 * an organisation change says what it dropped, a server refusal shows its
 * message and keeps what was typed (tests/test_event_create_1723.py).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = "form[data-sc-event-form]";
const TEAMS = `${FORM} [data-sc-event-pick="teams"]`;
const SEARCH = `${TEAMS} input.o_sc_tags_search`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function setValue(selector, value) {
    const input = document.querySelector(selector);
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

function basics(name, start, end) {
    return {
        content: `Name and times of ${name}`,
        trigger: `${FORM} input[name="name"]`,
        run() {
            setValue(`${FORM} input[name="name"]`, name);
            setValue(`${FORM} input[name="date_start"]`, start);
            setValue(`${FORM} input[name="date_end"]`, end);
        },
    };
}

function typeTeam(text) {
    return [
        { content: `Focus the teams box`, trigger: SEARCH, run: "click" },
        { content: `Type « ${text} »`, trigger: SEARCH, run: `edit ${text}` },
    ];
}

const leaveBox = {
    content: "Leave the teams box (focus the description)",
    trigger: `${FORM} textarea[name="description"]`,
    run: "click",
};

const create = {
    content: "Create",
    trigger: `${FORM} button[data-sc-action="event.save"]:not([aria-disabled="true"])`,
    run: "click",
    expectUnloadPage: true,
};

const created = {
    content: "The new event's page",
    trigger: '[data-sc-section="event.hero"]',
};

// Typed then picked from the list.
tours.add("sc_1723_typed_then_picked", {
    steps: () => [
        basics("SC 1723 Picked", "2026-05-04T18:00", "2026-05-04T20:00"),
        ...typeTeam("team a"),
        { content: "Pick it", trigger: `${TEAMS} .o_sc_tags_option:contains("PC Team A")`, run: "click" },
        create,
        created,
    ],
});

// The exact name typed, never picked: picked when leaving the box.
tours.add("sc_1723_typed_exact", {
    steps: () => [
        basics("SC 1723 Exact", "2026-05-05T18:00", "2026-05-05T20:00"),
        ...typeTeam("pc TEAM a"),
        leaveBox,
        {
            content: "The typed name became a chip",
            trigger: `${TEAMS} .o_sc_tag:contains("PC Team A")`,
            run() {
                assert(document.querySelector(`${FORM} input[name="team_ids"]`).value, "team_ids empty");
                assert(!document.querySelector(`${TEAMS} [data-sc-tags-typed-error]`), "an error shows");
            },
        },
        create,
        created,
    ],
});

// Text matching nothing: an inline error, the submit refused with it.
tours.add("sc_1723_typed_nothing", {
    steps: () => [
        basics("SC 1723 Nothing", "2026-05-06T18:00", "2026-05-06T20:00"),
        ...typeTeam("No Such Synthetic Team"),
        leaveBox,
        {
            content: "The inline error; « Créer » says why",
            trigger: `${TEAMS} [data-sc-tags-typed-error]`,
            run() {
                assert(this.anchor.textContent.includes("No Such Synthetic Team"), this.anchor.textContent);
                const submit = document.querySelector(`${FORM} button[data-sc-action="event.save"]`);
                assert(submit.getAttribute("aria-disabled") === "true", "the submit is not refused");
            },
        },
        {
            content: "Clear the text: the error goes",
            trigger: SEARCH,
            run: "clear",
        },
        {
            content: "No error any more",
            trigger: `${TEAMS}:not(:has([data-sc-tags-typed-error]))`,
        },
    ],
});

// A server refusal (the client rule removed, as when the two disagree):
// the message shows, nothing typed is lost.
tours.add("sc_1723_server_refusal_kept", {
    steps: () => [
        basics("SC 1723 Refused", "2026-05-07T20:00", "2026-05-07T18:00"),
        ...typeTeam("team a"),
        { content: "Pick it", trigger: `${TEAMS} .o_sc_tags_option:contains("PC Team A")`, run: "click" },
        {
            content: "Submit past the client rule",
            trigger: `${FORM} button[data-sc-action="event.save"]`,
            run() {
                const form = document.querySelector(FORM);
                form.removeAttribute("data-sc-guard-rules");
                this.anchor.removeAttribute("aria-disabled");
                this.anchor.click();
            },
        },
        {
            content: "The refusal shows under the end time; the values stay",
            trigger: `${FORM} .o_sc_field_error[data-sc-guard-field-error="date_end"]`,
            run() {
                assert(document.querySelector(`${FORM} input[name="name"]`).value === "SC 1723 Refused", "name lost");
                assert(document.querySelector(`${FORM} input[name="team_ids"]`).value, "team lost");
                assert(document.querySelector(`${FORM} input[name="date_start"]`).value === "2026-05-07T20:00", "start lost");
            },
        },
    ],
});

// An organisation change drops the other organisation's teams — and says so.
tours.add("sc_1723_org_drop_notice", {
    steps: () => [
        ...typeTeam("team a"),
        { content: "Pick it", trigger: `${TEAMS} .o_sc_tags_option:contains("PC Team A")`, run: "click" },
        {
            content: "Choose the other organisation",
            trigger: `${FORM} select[name="organization_id"]:not(:visible)`,
            run() {
                const option = [...this.anchor.options].find((opt) => opt.textContent.includes("ZZ Org 1597"));
                this.anchor.value = option.value;
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "The team is dropped and the notice says so",
            trigger: `${TEAMS} [data-sc-tags-group-notice]`,
            run() {
                assert(!document.querySelector(`${FORM} input[name="team_ids"]`).value, "team kept");
            },
        },
    ],
});
