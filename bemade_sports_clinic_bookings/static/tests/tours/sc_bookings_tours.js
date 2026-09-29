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
    ],
});
