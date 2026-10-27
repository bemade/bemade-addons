/*
 * Task 1723 — creating an event: a typed team is picked or refused clearly,
 * an organisation change warns before dropping teams, a server refusal shows its
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

// Review round 1 (owner 2026-10-27): an organisation change that would drop
// the chosen teams WARNS FIRST (inline, never a browser confirm); « Cancel »
// keeps the organisation and the teams, « Change organization » drops them.
function chooseOrg(label) {
    return {
        content: `Choose the organisation « ${label} »`,
        trigger: `${FORM} select[name="organization_id"]:not(:visible)`,
        run() {
            const option = [...this.anchor.options].find((opt) => opt.textContent.includes(label));
            this.anchor.dataset.scTourBefore = this.anchor.value;
            this.anchor.value = option.value;
            this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
        },
    };
}

tours.add("sc_1723_org_drop_notice", {
    steps: () => [
        ...typeTeam("team a"),
        { content: "Pick it", trigger: `${TEAMS} .o_sc_tags_option:contains("PC Team A")`, run: "click" },
        chooseOrg("ZZ Org 1597"),
        {
            content: "A warning first: the team is still there, the submit waits",
            trigger: `${TEAMS} [data-sc-org-confirm-box] [data-sc-org-cancel]`,
            run() {
                assert(document.querySelector(`${FORM} input[name="team_ids"]`).value, "team dropped before confirming");
                assert(document.querySelector(`${TEAMS} [data-sc-org-confirm-box]`).textContent.includes("PC Team A"),
                    "the warning does not name the team");
                assert(!document.querySelector(`${TEAMS} [data-sc-tags-group-notice]`), "an after-the-fact notice");
            },
        },
        { content: "« Cancel »", trigger: `${TEAMS} [data-sc-org-cancel]`, run: "click" },
        {
            content: "The former organisation and the team are kept",
            trigger: `${TEAMS}:not(:has([data-sc-org-confirm-box]))`,
            run() {
                const select = document.querySelector(`${FORM} select[name="organization_id"]`);
                assert(select.value === select.dataset.scTourBefore, "the organisation was not restored");
                assert(document.querySelector(`${FORM} input[name="team_ids"]`).value, "team lost on cancel");
                assert(document.querySelector(`${TEAMS} .o_sc_tag`), "no team chip");
            },
        },
        chooseOrg("ZZ Org 1597"),
        { content: "« Change organization »", trigger: `${TEAMS} [data-sc-org-confirm]`, run: "click" },
        {
            content: "The team is dropped once confirmed",
            trigger: `${TEAMS}:not(:has([data-sc-org-confirm-box]))`,
            run() {
                assert(!document.querySelector(`${FORM} input[name="team_ids"]`).value, "team kept");
                const select = document.querySelector(`${FORM} select[name="organization_id"]`);
                assert(select.selectedOptions[0].textContent.includes("ZZ Org 1597"), "organisation not changed");
            },
        },
    ],
});
