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
            trigger: '[data-sc-section="clinic.dossier.note_list"] .o_sc_note_card textarea',
            run() {
                // The author's own note is an autosave field (a textarea).
                const texts = [...document.querySelectorAll(".o_sc_note_card textarea, .o_sc_note_card .o_sc_note_text")]
                    .map((el) => el.value || el.textContent);
                assert(texts.some((text) => text.includes(NOTE)), `notes: ${texts}`);
            },
        },
        {
            content: "Open the injury sheet",
            trigger: '[data-sc-section="clinic.dossier.injuries"] a[data-sc-injury-id]',
            run: "click",
        },
        {
            content: "The unchanged injury form fragment is loaded in the sheet",
            trigger: "dialog.o_sc_sheet[open] .o_sc_sheet_body form",
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
            content: "« Ajouter ma feuille de temps » (app bar)",
            trigger: 'header button[data-sc-sheet-open="sc_ts_add_sheet"]',
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
