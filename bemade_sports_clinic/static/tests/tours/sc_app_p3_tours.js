/*
 * Task 1540 (epic #1535) — browser tours of the P3 shell pages (clinic and
 * its live waiting list, events + calendar, timesheets, notepad). Run by
 * tests/test_app_shell_tours_1540.py through HttpCase.start_tour;
 * language-independent triggers only (data attributes).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

// --------------------------------- clinic list -> clinic -> live waiting list
const NOTE = "Tour 1540 synthetic clinic note";

tours.add("sc_1540_clinic", {
    steps: () => [
        {
            content: "Clinic list: open the clinic",
            trigger: '[data-sc-section="clinics.list"] a[data-sc-clinic-id]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The live waiting list is mounted",
            trigger: '.o_sc_wl_live[data-sc-worklist-live] li[data-sc-state="expected"][data-sc-patient-id]',
            run() {
                window.__sc1540NoReload = "1";
            },
        },
        {
            content: "« Arrivé » on a row (instant, no reload)",
            trigger: '.o_sc_wl_live li[data-sc-state="expected"][data-sc-patient-id] button[data-sc-wl-state="arrived"]',
            run: "click",
        },
        {
            content: "The row is Arrived, confirmed by the server, same page",
            trigger: '.o_sc_wl_live[data-sc-status="live"] li[data-sc-state="arrived"] button[data-sc-wl-state="arrived"][aria-pressed="true"]',
            run() {
                assert(window.__sc1540NoReload === "1", "the page reloaded");
            },
        },
        {
            content: "The action round-trip is over (server answer applied)",
            trigger: '.o_sc_wl_live[data-sc-busy="0"] li[data-sc-state="arrived"]',
        },
        {
            content: "Open the patient's file",
            trigger: '.o_sc_wl_live li[data-sc-state="arrived"] a.o_sc_row_title',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "File shown, note form docked open",
            trigger: 'section[data-sc-tab-panel="dossier"]:not([hidden]) details[data-sc-section="notes.add"][open] textarea',
            run: `edit ${NOTE}`,
        },
        {
            content: "« Ajouter la note »",
            trigger: 'button[data-sc-action="notes.submit"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The note is on the file",
            trigger: '[data-sc-section="clinic.dossier.note_list"] .o_sc_note_card .o_sc_note_text',
            run() {
                // The author's own note reads as text with a pencil (owner
                // review 2026-10-11); its autosave field is in the edit view.
                const texts = [...document.querySelectorAll(".o_sc_note_card textarea, .o_sc_note_card .o_sc_note_text")]
                    .map((el) => el.value || el.textContent);
                assert(texts.some((text) => text.includes(NOTE)), `notes: ${texts}`);
            },
        },
        {
            content: "Open the injury card (task 1590: inline, no sheet)",
            trigger: '[data-sc-section="clinic.dossier.injuries"] details[data-sc-edit-card="injury"] > summary',
            run: "click",
        },
        {
            content: "The card's read view is shown, with its pencil",
            trigger: '[data-sc-section="clinic.dossier.injuries"] details[data-sc-edit-card="injury"][open] button[data-sc-edit-toggle]',
        },
    ],
});

// -------------------------------- events list -> event -> timesheet add
tours.add("sc_1540_event_timesheet", {
    steps: () => [
        {
            content: "Events list: open the event",
            trigger: '[data-sc-section="events.list"] a[data-sc-event-id]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "« + Ajouter » (Add My Timesheet) in the timesheets list header",
            trigger: '[data-sc-section="event.timesheets"] .o_sc_list_header button.o_sc_list_add[data-sc-sheet-open="sc_ts_add_sheet"]',
            run: "click",
        },
        {
            content: "Submit the prefilled timesheet (today's route, CSRF)",
            trigger: 'dialog#sc_ts_add_sheet[open] button[data-sc-action="timesheet.add.submit"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the event: the saved timesheet is listed",
            trigger: '[data-sc-section="event.timesheets"] [data-sc-timesheet-id]',
            run() {
                assert(window.location.search.includes("ts_saved=1"), window.location.search);
            },
        },
    ],
});

// ------------------------------------------------------ shared calendar
tours.add("sc_1540_calendar", {
    steps: () => [
        {
            content: "FullCalendar rendered from the lazy bundle",
            trigger: '.o_sc_calendar_box[data-sc-calendar-ready="1"] .fc',
            run() {
                assert(!document.querySelector('script[src*="/web/static/lib/fullcalendar"]'), "raw FullCalendar <script src>");
            },
        },
        {
            content: "The feed's event is shown; open it",
            trigger: ".o_sc_calendar a.fc-event, .o_sc_calendar .fc-list-event a",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The event page",
            trigger: '[data-sc-section="event.hero"]',
        },
    ],
});

// ------------------------------------------------------ notepad add
const QUICK = "Tour 1540 synthetic quick note";

tours.add("sc_1540_notepad", {
    steps: () => [
        {
            content: "Type a quick note (kept as a device draft)",
            trigger: 'form[data-sc-form="note.add"] .o_sc_autosave textarea',
            run: `edit ${QUICK}`,
        },
        {
            content: "« Ajouter »",
            trigger: 'form[data-sc-form="note.add"] button[data-sc-action="note.add"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The note is listed and the draft is gone",
            trigger: `[data-sc-section="notepad.list"] .o_sc_quick_note:contains("${QUICK}")`,
            run() {
                const drafts = [];
                for (let i = 0; i < window.localStorage.length; i++) {
                    const key = window.localStorage.key(i);
                    if (key && key.startsWith("sc_draft:") && key.includes("sports.quick.note.new.")) {
                        drafts.push(key);
                    }
                }
                assert(drafts.length === 0, `drafts left: ${drafts}`);
            },
        },
    ],
});

// ------------- task 1587: a note's pencil edit changes its date and injury
const NOTE_CARD = '[data-sc-edit-card^="note-"]';

tours.add("sc_1587_note_date_injury", {
    steps: () => [
        {
            content: "Open the note's pencil",
            trigger: `${NOTE_CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Change the note's date",
            trigger: `${NOTE_CARD} .o_sc_autosave[data-sc-field="date"] input[type="date"]`,
            run() {
                this.anchor.value = "2026-02-14";
                this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "The date is saved",
            trigger: `${NOTE_CARD} .o_sc_autosave[data-sc-field="date"][data-sc-state="saved"]`,
        },
        {
            content: "Link the note to another injury of the player",
            trigger: `${NOTE_CARD} .o_sc_autosave[data-sc-field="injury_id"] select`,
            run() {
                const option = [...this.anchor.options].find((opt) => opt.text === "Synthetic strain");
                assert(option, "the player's open injury is offered");
                assert(this.anchor.options[0].value === "", "« General note » comes first");
                this.anchor.value = option.value;
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "The injury is saved",
            trigger: `${NOTE_CARD} .o_sc_autosave[data-sc-field="injury_id"][data-sc-state="saved"]`,
        },
        {
            content: "Done: the card closes (task 1611: no reload, the meta line is a read fragment)",
            trigger: `${NOTE_CARD} [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The meta line shows the new injury",
            trigger: `${NOTE_CARD} .o_sc_note_meta:contains("Synthetic strain")`,
            run() {
                assert(!this.anchor.textContent.includes("Synthetic old bruise"), "old injury still shown");
            },
        },
    ],
});
