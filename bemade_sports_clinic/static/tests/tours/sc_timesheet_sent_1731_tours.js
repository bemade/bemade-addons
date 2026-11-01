/*
 * Task 1731 — « Add My Timesheet » with an existing timesheet opens its card
 * in edit: the « already sent » hint is visible, and an edit saves as
 * « Sent · hh:mm » (tests/test_timesheet_sent_state_1731.py, phone width).
 * Language-independent triggers (data attributes).
 *
 * Real phone taps stay UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const CARD = "[data-sc-timesheet-id][data-sc-edit-card]";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

registry.category("web_tour.tours").add("sc_1731_timesheet_sent", {
    steps: () => [
        {
            content: "The card says « Submitted ✓ »",
            trigger: `${CARD} [data-sc-ts-state="submitted"].o_sc_chip_green`,
        },
        {
            content: "« Add My Timesheet »",
            trigger: 'button[data-sc-action="timesheet.add"][data-sc-sheet-open]',
            run: "click",
        },
        {
            content: "The existing card opens in edit, the « already sent » hint visible",
            trigger: `${CARD}[data-sc-edit-open] [data-sc-ts-sent-hint]:visible`,
        },
        {
            content: "Leave 30 min earlier (travel start before the coverage start)",
            trigger: `${CARD}[data-sc-edit-open] .o_sc_autosave[data-sc-field="travel_start"] input`,
            run() {
                const input = this.anchor;
                const card = input.closest("[data-sc-edit-card]");
                const start = card.querySelector('.o_sc_autosave[data-sc-field="coverage_start"] input').value;
                assert(start, "the coverage start is filled");
                const at = new Date(new Date(start).getTime() - 30 * 60 * 1000);
                const pad = (n) => String(n).padStart(2, "0");
                input.focus();
                input.value = `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.blur();
                input.dispatchEvent(new FocusEvent("blur")); // headless: blur() fires no event
            },
        },
        {
            content: "Saved: the field reads « Sent · hh:mm »",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="travel_start"][data-sc-state="saved"] .o_sc_save_state`,
            run() {
                const text = this.anchor.textContent.trim();
                assert(/^Sent · \d{1,2}:\d{2}$/.test(text), `save state reads « ${text} »`);
            },
        },
    ],
});
