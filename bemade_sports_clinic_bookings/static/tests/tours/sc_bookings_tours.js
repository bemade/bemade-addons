/*
 * Task 1540 (epic #1535) — tour of the bookings pages on the app shell
 * (bemade_sports_clinic_bookings). Language-independent triggers only.
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("sc_1540_bookings", {
    steps: () => [
        {
            content: "The booking is listed on the shell",
            trigger: '.o_pk_app [data-pk-section="bookings.list"] [data-sc-booking-id]',
        },
        {
            // Task 1585: the client's email is a tap-to-email link.
            content: "The client's email is a mailto: link",
            trigger: '[data-sc-booking-id] a[data-sc-booking-link="email"][href="mailto:quinn@bk.example.com"]',
        },
        {
            content: "Open the calendar segment",
            trigger: '[data-pk-tabs] a[data-pk-tab="calendar"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The booking is on the calendar; open its details",
            trigger: '.o_pk_calendar_box[data-pk-calendar-ready="1"] :is(.fc-event, .fc-list-event)',
            run: "click",
        },
        {
            content: "Details shown under the calendar",
            trigger: '[data-pk-calendar-detail] .o_pk_kv',
        },
        {
            // Task 1585: tap to call / write from the details.
            content: "The client's phone and email are tap links",
            trigger: '[data-pk-calendar-detail] a[data-pk-calendar-detail-link="email"][href="mailto:quinn@bk.example.com"]',
            run() {
                const phone = document.querySelector('[data-pk-calendar-detail] a[data-pk-calendar-detail-link="phone"]');
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
            content: "Open the calendar segment (carrying the booking's date)",
            trigger: '[data-pk-tabs] a[data-pk-tab="calendar"]',
            async run(helpers) {
                // Task 1760: the test starts the tour on /my/bookings#pk_date=<booking's date>.
                const url = new URL(this.anchor.href);
                url.hash = window.location.hash;
                this.anchor.setAttribute("href", url.toString());
                await helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            // Task 1760: the phone calendar opens on the CURRENT week (listWeek,
            // Monday first) — from Sunday 22:00 UTC « now + 2 h » is next week's
            // Monday. Go to the booking's week with the calendar's own buttons:
            // back to today, then one « next » / « prev » per week of offset.
            content: "Show the booking's week",
            trigger: '.o_pk_calendar_box[data-pk-calendar-ready="1"] .fc-next-button',
            run() {
                const date = new URLSearchParams(window.location.hash.slice(1)).get("pk_date");
                if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) {
                    throw new Error(`no #pk_date on the calendar page (« ${window.location.hash} »)`);
                }
                const monday = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));
                const [y, m, d] = date.split("-").map(Number);
                const weeks = Math.round((monday(new Date(y, m - 1, d)) - monday(new Date())) / (7 * 864e5));
                const box = this.anchor.closest(".o_pk_calendar_box");
                const today = box.querySelector(".fc-today-button");
                if (!today.disabled) {
                    today.click(); // (disabled = already on the current week)
                }
                const button = box.querySelector(weeks < 0 ? ".fc-prev-button" : ".fc-next-button");
                for (let i = 0; i < Math.abs(weeks); i++) {
                    button.click();
                }
            },
        },
        {
            content: "Open the booking's details",
            trigger: '.o_pk_calendar_box[data-pk-calendar-ready="1"] :is(.fc-event, .fc-list-event)',
            run: "click",
        },
        {
            content: "The answers are in the details; a multi-line one keeps its breaks",
            trigger: '[data-pk-calendar-detail] .o_pk_kv dd:contains("Worse on stairs")',
            run() {
                const dd = [...document.querySelectorAll("[data-pk-calendar-detail] .o_pk_kv dd")].find((el) =>
                    el.textContent.includes("Worse on stairs")
                );
                const ws = getComputedStyle(dd).whiteSpace;
                if (!["pre-line", "pre-wrap"].includes(ws)) {
                    throw new Error(`white-space is « ${ws} »`);
                }
                if (!document.querySelector('[data-pk-calendar-detail] .o_pk_kv dd')) {
                    throw new Error("no details");
                }
            },
        },
    ],
});
