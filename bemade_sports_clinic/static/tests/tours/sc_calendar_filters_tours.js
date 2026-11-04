/*
 * Task 1591 — browser tour of the events filters carried between the list
 * and the calendar (run by tests/test_app_shell_calendar_filters_1591.py,
 * phone and laptop, as a treatment professional). The tour starts on the
 * list filtered on « game » + PC Team A. Language-independent triggers; the
 * event and team names are the test's synthetic fixtures.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = 'form[data-sc-section="events.filters"]';
const CAL = ".o_sc_calendar_box[data-sc-calendar-ready='1']";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function selectedTeam() {
    const select = document.querySelector(`${FORM} select[name="team_id"]`);
    return select.options[select.selectedIndex].text.trim();
}

function activeType() {
    const chip = document.querySelector('[data-sc-section="events.types"] a[aria-pressed="true"]');
    return chip && chip.dataset.scEventType;
}

function calendarText() {
    return document.querySelector(".o_sc_calendar").textContent;
}

tours.add("sc_1591_calendar_filters", {
    steps: () => [
        {
            content: "The list is filtered on « game » and PC Team A; open the calendar",
            trigger: 'nav[data-sc-tabs] a[data-sc-tab="calendar"]',
            run() {
                assert(selectedTeam() === "PC Team A", `list team: ${selectedTeam()}`);
                assert(activeType() === "game", `list type: ${activeType()}`);
                this.anchor.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "The calendar has the same filters, in its URL and its filter bar",
            trigger: `${FORM}[action="/my/events/calendar"]`,
            run() {
                const params = new URLSearchParams(window.location.search);
                assert(window.location.pathname === "/my/events/calendar", window.location.pathname);
                assert(params.get("event_type") === "game", `url: ${window.location.search}`);
                assert(params.get("team_id"), `url: ${window.location.search}`);
                assert(!params.has("date_from"), "the list's default date is not forwarded");
                assert(selectedTeam() === "PC Team A", `calendar team: ${selectedTeam()}`);
                assert(activeType() === "game", `calendar type: ${activeType()}`);
            },
        },
        {
            content: "Only the matching event is on the calendar",
            trigger: `${CAL} .fc .fc-event:contains(SC 1591 Game A)`,
            run() {
                const text = calendarText();
                assert(!text.includes("SC 1591 Game C"), "another team's game is filtered out");
                assert(!text.includes("SC 1591 Practice A"), "a practice is filtered out");
            },
        },
        {
            content: "Filter the calendar on its own: the « practice » type",
            trigger: '[data-sc-section="events.types"] a[data-sc-event-type="practice"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The practice is shown, the team filter kept",
            trigger: `${CAL} .fc .fc-event:contains(SC 1591 Practice A)`,
            run() {
                assert(window.location.pathname === "/my/events/calendar", window.location.pathname);
                assert(activeType() === "practice", `calendar type: ${activeType()}`);
                assert(selectedTeam() === "PC Team A", `calendar team: ${selectedTeam()}`);
                assert(!calendarText().includes("SC 1591 Game A"), "the game is filtered out");
            },
        },
        {
            content: "Back to the list",
            trigger: 'nav[data-sc-tabs] a[data-sc-tab="upcoming"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The list keeps the calendar's filters",
            trigger: '[data-sc-section="events.list"] [data-sc-event-id]',
            run() {
                assert(window.location.pathname === "/my/events", window.location.pathname);
                assert(activeType() === "practice", `list type: ${activeType()}`);
                assert(selectedTeam() === "PC Team A", `list team: ${selectedTeam()}`);
                const titles = document.querySelector('[data-sc-section="events.list"]').textContent;
                assert(titles.includes("SC 1591 Practice A"), "the practice is listed");
                assert(!titles.includes("SC 1591 Game A"), "the game is filtered out");
            },
        },
    ],
});
