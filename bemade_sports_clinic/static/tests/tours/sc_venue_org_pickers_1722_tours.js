/*
 * Task 1722 — the event form's Venue and Organisation pickers
 * (tests/test_venue_org_pickers_1722.py): type, pick, the organisation
 * narrows the teams, the event is created with the typed-then-picked venue.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = "form[data-sc-event-form]";
const VENUE = `${FORM} select[name="venue_id"] + .o_sc_picker`;
const ORG = `${FORM} select[name="organization_id"] + .o_sc_picker`;
const TEAMS = `${FORM} [data-sc-event-pick="teams"]`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function typeIn(selector, value) {
    const input = document.querySelector(selector);
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

tours.add("sc_1722_venue_org_pickers", {
    steps: () => [
        {
            content: "Name the event",
            trigger: `${FORM} input[name="name"]`,
            run: "edit SC 1722 Tour",
        },
        {
            content: "The venue box shows « To be determined »; opening lists it first",
            trigger: `${VENUE} input.o_sc_picker_input`,
            run() {
                assert(this.anchor.value.length > 0, "the empty choice has no label in the box");
                this.anchor.click();
                const first = document.querySelector(`${VENUE} .o_sc_picker_option`);
                assert(first && first.dataset.scPickerValue === "", "« To be determined » is not first");
            },
        },
        {
            content: "Type part of the venue name without accents",
            trigger: `${VENUE} input.o_sc_picker_input`,
            run() {
                typeIn(`${VENUE} input.o_sc_picker_input`, "arena synthetique");
            },
        },
        {
            content: "Pick it",
            trigger: `${VENUE} .o_sc_picker_option:contains("Aréna Synthétique-Côté")`,
            run: "click",
        },
        {
            content: "The select holds it",
            trigger: `${VENUE} input.o_sc_picker_input`,
            run() {
                const select = document.querySelector(`${FORM} select[name="venue_id"]`);
                assert(select.value && select.selectedOptions[0].textContent.includes("Aréna"), "venue not set");
            },
        },
        {
            content: "Type the organisation",
            trigger: `${ORG} input.o_sc_picker_input`,
            run() {
                document.querySelector(`${ORG} input.o_sc_picker_input`).click();
                typeIn(`${ORG} input.o_sc_picker_input`, "zz org");
            },
        },
        {
            content: "Pick it",
            trigger: `${ORG} .o_sc_picker_option:contains("ZZ Org 1597")`,
            run: "click",
        },
        {
            content: "The teams list is narrowed to that organisation",
            trigger: `${TEAMS} input.o_sc_tags_search`,
            run: "click",
        },
        {
            content: "Only its team is offered; pick it",
            trigger: `${TEAMS} .o_sc_tags_option:contains("ZZ Team C 1597")`,
            run() {
                const labels = [...document.querySelectorAll(`${TEAMS} .o_sc_tags_option`)].map((el) =>
                    el.textContent.trim()
                );
                assert(!labels.includes("PC Team A"), `not narrowed: ${labels.join(", ")}`);
                this.anchor.click();
            },
        },
        {
            content: "Set the times",
            trigger: `${FORM} input[name="date_start"]`,
            run() {
                for (const [name, value] of [["date_start", "2026-05-04T18:00"], ["date_end", "2026-05-04T20:00"]]) {
                    const input = document.querySelector(`${FORM} input[name="${name}"]`);
                    input.value = value;
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                }
            },
        },
        {
            content: "Create",
            trigger: `${FORM} button[data-sc-action="event.save"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The event page",
            trigger: '[data-sc-section="event.hero"]',
        },
    ],
});
