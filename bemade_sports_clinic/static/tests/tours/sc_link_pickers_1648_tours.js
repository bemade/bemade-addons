/*
 * Task 1648 — the link pickers in a browser (tests/test_link_pickers_1648.py).
 *
 * sc_1648_notepad: on the new note, the team « PC Team B » narrows the
 * players (Pat One, team A, is out) and the events; clearing it widens them;
 * typing « zo pick » finds « Pickerline, Zoé »; picking her narrows the
 * injuries to hers; « wrist » picks it; « Add » posts the note linked.
 * sc_1648_note_injury: the add-note « Link to Injury » picker.
 *
 * Phone keyboard behaviour stays UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const FORM = "form#quick-add";

function picker(name) {
    return document.querySelector(`${FORM} select[name="${name}"]`).nextElementSibling;
}

function optionFor(name, text) {
    return [...document.querySelector(`${FORM} select[name="${name}"]`).options].find((o) =>
        o.textContent.includes(text)
    );
}

function type(name, text) {
    const input = picker(name).querySelector(".o_sc_picker_input");
    input.focus();
    input.value = text;
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

function pick(name, text) {
    const item = [...picker(name).querySelectorAll(".o_sc_picker_option")].find((li) =>
        li.textContent.includes(text)
    );
    assert(item, `« ${text} » not listed in the ${name} picker`);
    item.click();
}

tours.add("sc_1648_notepad", {
    steps: () => [
        {
            content: "Open « Link this note »",
            trigger: `${FORM} details.o_sc_disclosure > summary`,
            run: "click",
        },
        {
            content: "Team B narrows the players and events",
            trigger: `${FORM} details.o_sc_disclosure[open] .o_sc_picker .o_sc_picker_input`,
            run() {
                assert(!document.activeElement.classList.contains("o_sc_picker_input"), "a picker was auto-focused");
                type("team_id", "team b");
                pick("team_id", "PC Team B");
                assert(document.querySelector(`${FORM} select[name="team_id"]`).value, "team not set");
                assert(optionFor("patient_id", "One").dataset.scPickerOut, "Pat One (team A) still offered");
                assert(!optionFor("patient_id", "Zoé").dataset.scPickerOut, "Zoé (team B) narrowed out");
                type("patient_id", "");
                const listed = [...picker("patient_id").querySelectorAll(".o_sc_picker_option")].map((li) => li.textContent);
                assert(!listed.some((t) => t.includes("One")), `team A player listed: ${listed}`);
            },
        },
        {
            content: "Clearing the team widens the lists",
            trigger: `${FORM} .o_sc_picker_clear:not([hidden])`,
            run(helpers) {
                return helpers.click();
            },
        },
        {
            content: "Type part of the name, pick Zoé: the injuries narrow to hers",
            trigger: `${FORM} select[name="team_id"] + .o_sc_picker .o_sc_picker_input`,
            run() {
                assert(!document.querySelector(`${FORM} select[name="team_id"]`).value, "team not cleared");
                assert(!optionFor("patient_id", "One").dataset.scPickerOut, "the players did not widen");
                type("patient_id", "zo pick");
                pick("patient_id", "Zoé");
                assert(optionFor("injury_id", "wrist") && !optionFor("injury_id", "wrist").dataset.scPickerOut,
                    "Zoé's injury narrowed out");
                const other = [...document.querySelector(`${FORM} select[name="injury_id"]`).options].find(
                    (o) => o.value && !o.textContent.includes("wrist"));
                assert(!other || other.dataset.scPickerOut, "another player's injury still offered");
                type("injury_id", "wrist");
                pick("injury_id", "wrist");
            },
        },
        {
            content: "The note text",
            trigger: `${FORM} textarea`,
            run: "edit Tour 1648 synthetic note",
        },
        {
            content: "Add",
            trigger: `${FORM} button[data-sc-action="note.add"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Added",
            trigger: '.o_sc_quick_note:contains("Tour 1648 synthetic note")',
        },
    ],
});

tours.add("sc_1648_note_injury", {
    steps: () => [
        {
            content: "« + Ajouter » of the Notes list",
            trigger: 'button[data-sc-list-add-toggle][aria-controls="sc_note_add"]',
            run: "click",
        },
        {
            content: "« Link to Injury » is a picker: type, pick",
            trigger: "details#sc_note_add[open] select#sc_note_injury + .o_sc_picker .o_sc_picker_input",
            run() {
                const select = document.querySelector("select#sc_note_injury");
                const input = this.anchor;
                input.focus();
                input.value = "spr";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                const item = [...select.nextElementSibling.querySelectorAll(".o_sc_picker_option")]
                    .find((li) => li.textContent.includes("Sprain"));
                assert(item, "« Sprain » not listed");
                item.click();
                assert(select.value && select.selectedOptions[0].textContent.includes("Sprain"), "not picked");
                assert(input.value.includes("Sprain"), "the box does not show the pick");
            },
        },
    ],
});

// The note card's link fields (OWL autosave selects): pick → saved.
tours.add("sc_1648_card", {
    steps: () => [
        {
            content: "The note card's pencil",
            trigger: 'article.o_sc_quick_note:contains("Synthetic card 1648") button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Player picker: type, pick Zoé",
            trigger: 'article.o_sc_quick_note [data-sc-edit-view="edit"] select[data-sc-picker-key="player"] + .o_sc_picker .o_sc_picker_input',
            run() {
                const input = this.anchor;
                input.focus();
                input.value = "zoe";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                const item = [...input.closest(".o_sc_picker").querySelectorAll(".o_sc_picker_option")]
                    .find((li) => li.textContent.includes("Zoé"));
                assert(item, "Zoé not listed");
                item.click();
            },
        },
        {
            content: "Saved by the autosave",
            trigger: 'article.o_sc_quick_note .o_sc_autosave[data-sc-state="saved"] select[data-sc-picker-key="player"]:not(:visible)',
        },
    ],
});
