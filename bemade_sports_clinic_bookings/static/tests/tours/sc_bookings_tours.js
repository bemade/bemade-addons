/*
 * Task 1540 (epic #1535) — tour of the bookings pages on the app shell
 * (bemade_sports_clinic_bookings). Language-independent triggers only.
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("sc_1540_bookings", {
    steps: () => [
        {
            content: "The booking is listed on the shell",
            trigger: '.o_sc_app [data-sc-section="bookings.list"] [data-sc-booking-id]',
        },
        {
            // Task 1585: the client's email is a tap-to-email link.
            content: "The client's email is a mailto: link",
            trigger: '[data-sc-booking-id] a[data-sc-booking-link="email"][href="mailto:quinn@bk.example.com"]',
        },
        {
            content: "Open the calendar segment",
            trigger: '[data-sc-tabs] a[data-sc-tab="calendar"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The booking is on the calendar; open its details",
            trigger: '.o_sc_calendar_box[data-sc-calendar-ready="1"] :is(.fc-event, .fc-list-event)',
            run: "click",
        },
        {
            content: "Details shown under the calendar",
            trigger: '[data-sc-calendar-detail] .o_sc_kv',
        },
        {
            // Task 1585: tap to call / write from the details.
            content: "The client's phone and email are tap links",
            trigger: '[data-sc-calendar-detail] a[data-sc-detail-link="email"][href="mailto:quinn@bk.example.com"]',
            run() {
                const phone = document.querySelector('[data-sc-calendar-detail] a[data-sc-detail-link="phone"]');
                if (!phone || phone.getAttribute("href") !== "tel:+15550100321") {
                    throw new Error(`phone link is « ${phone && phone.getAttribute("href")} »`);
                }
            },
        },
    ],
});

/*
 * Task 1732 — the booking form's answers in the list row and in the
 * calendar details (multi-line answer kept on several lines).
 */
registry.category("web_tour.tours").add("sc_1732_booking_answers", {
    steps: () => [
        {
            content: "The answers are under the booking row",
            trigger: '[data-sc-booking-id] [data-sc-booking-answers] dd:contains("Soccer")',
        },
        {
            content: "Open the calendar segment",
            trigger: '[data-sc-tabs] a[data-sc-tab="calendar"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Open the booking's details",
            trigger: '.o_sc_calendar_box[data-sc-calendar-ready="1"] :is(.fc-event, .fc-list-event)',
            run: "click",
        },
        {
            content: "The answers are in the details; a multi-line one keeps its breaks",
            trigger: '[data-sc-calendar-detail] .o_sc_kv dd:contains("Worse on stairs")',
            run() {
                const dd = [...document.querySelectorAll("[data-sc-calendar-detail] .o_sc_kv dd")].find((el) =>
                    el.textContent.includes("Worse on stairs")
                );
                const ws = getComputedStyle(dd).whiteSpace;
                if (!["pre-line", "pre-wrap"].includes(ws)) {
                    throw new Error(`white-space is « ${ws} »`);
                }
                if (!document.querySelector('[data-sc-calendar-detail] .o_sc_kv dd')) {
                    throw new Error("no details");
                }
            },
        },
    ],
});
