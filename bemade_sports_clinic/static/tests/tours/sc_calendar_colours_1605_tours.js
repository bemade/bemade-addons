/*
 * Task 1605 — browser tour of the therapist colours on the events calendar
 * (run by tests/test_calendar_staff_colours_1605.py, phone and laptop, as a
 * treatment professional). Synthetic fixtures: « SC 1605 Solo » (PC TP),
 * « SC 1605 Duo » (PC TP + ZZ Second TP 1605), « SC 1605 Nobody »
 * (unassigned), all today. Language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const CAL = ".o_sc_calendar_box[data-sc-calendar-ready='1']";
const EVENT = ".fc-event"; // list rows carry it too
const LEGEND = '.o_sc_staff_legend[data-sc-section="calendar.legend"]';
const SECOND = `${LEGEND} button.o_sc_staff_legend_item:contains(ZZ Second TP 1605)`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function dotOf(title) {
    const row = [...document.querySelectorAll(`.o_sc_calendar ${EVENT}`)].find((el) =>
        el.textContent.includes(title)
    );
    return row && row.querySelector(".o_sc_staff_dot");
}

function calendarText() {
    return document.querySelector(".o_sc_calendar").textContent;
}

function noOverflow() {
    assert(
        document.documentElement.scrollWidth <= window.innerWidth + 1,
        `page overflows: ${document.documentElement.scrollWidth} > ${window.innerWidth}`
    );
}

tours.add("sc_1605_calendar_colours", {
    steps: () => [
        {
            content: "Each event has a dot: one colour, a split circle, grey",
            trigger: `${CAL} ${EVENT}:contains(SC 1605 Nobody) .o_sc_staff_dot`,
            run() {
                const solo = dotOf("SC 1605 Solo");
                assert(solo, "Solo has a dot");
                assert(!solo.dataset.scStaffDot.includes(","), `solo: ${solo.dataset.scStaffDot}`);
                assert(/^rgb|^#/.test(solo.style.background), `solo bg: ${solo.style.background}`);
                assert(solo.getAttribute("aria-label") === "PC TP", solo.getAttribute("aria-label"));
                const duo = dotOf("SC 1605 Duo");
                assert(duo.dataset.scStaffDot.split(",").length === 2, `duo: ${duo.dataset.scStaffDot}`);
                assert(duo.style.background.includes("conic-gradient"), `duo bg: ${duo.style.background}`);
                assert(duo.title.includes("ZZ Second TP 1605"), duo.title);
                const nobody = dotOf("SC 1605 Nobody");
                assert(nobody.classList.contains("o_sc_staff_dot_none"), "unassigned is grey");
                assert(nobody.dataset.scStaffDot === "none", nobody.dataset.scStaffDot);
            },
        },
        {
            content: "The legend lists the therapists of the visible range",
            trigger: SECOND,
            run() {
                const legend = document.querySelector(LEGEND).textContent;
                assert(legend.includes("PC TP"), "PC TP in the legend");
                assert(document.querySelector(`${LEGEND} [data-sc-staff-legend="none"]`), "unassigned key");
                assert(this.anchor.getAttribute("aria-pressed") === "false", "not filtered yet");
                noOverflow();
                this.anchor.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Filtered on the second therapist: only their event",
            trigger: `${SECOND}[aria-pressed="true"]`,
        },
        {
            content: "The calendar shows only the second therapist's event",
            trigger: `${CAL} ${EVENT}:contains(SC 1605 Duo)`,
            run() {
                const params = new URLSearchParams(window.location.search);
                assert(params.get("assigned_user_id"), `url: ${window.location.search}`);
                assert(window.location.hash.includes("sc_date="), `hash: ${window.location.hash}`);
                const text = calendarText();
                assert(!text.includes("SC 1605 Solo"), "Solo is filtered out");
                assert(!text.includes("SC 1605 Nobody"), "Nobody is filtered out");
                noOverflow();
            },
        },
        {
            content: "Tap again: back to everyone",
            trigger: `${SECOND}[aria-pressed="true"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Everything is back",
            trigger: `${CAL} ${EVENT}:contains(SC 1605 Solo)`,
            run() {
                assert(
                    !new URLSearchParams(window.location.search).get("assigned_user_id"),
                    `url: ${window.location.search}`
                );
                assert(calendarText().includes("SC 1605 Nobody"), "Nobody is back");
            },
        },
    ],
});
