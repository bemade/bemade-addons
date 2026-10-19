/*
 * Task 1612 — « Nouveau lieu » from the event page's pencil card: after a
 * sibling field's autosave (the event's write date moved), the new venue is
 * created AND set on the event in one request, no « HTTP 400 », and the card
 * shows it (task 1611: in place, no reload). Synthetic data only.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const CARD = '[data-sc-edit-card="event"]';
const NAME = `${CARD} .o_sc_autosave[data-sc-field="name"]`;
const SHEET_FORM = "form[data-sc-venue-form]";

tours.add("sc_1612_event_new_venue", {
    steps: () => [
        {
            content: "Open the event card",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Rename the event (a sibling autosave moves the write date)",
            trigger: `${NAME} input`,
            run() {
                const input = this.anchor;
                input.focus();
                input.value = "Tour 1612 Game renamed";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.blur(); input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Saved",
            trigger: `${NAME}[data-sc-state="saved"]`,
        },
        {
            content: "« New venue »",
            trigger: `${CARD} button[data-sc-action="venue.new"]`,
            run: "click",
        },
        {
            content: "Name the venue",
            trigger: `${SHEET_FORM} input[name="name"]`,
            run: "edit Tour 1612 Arena",
        },
        {
            content: "Save the venue (task 1611: shown in place, no reload)",
            trigger: `${SHEET_FORM} button[type="submit"]`,
            run() {
                window.__sc1612NoReload = "1";
                this.anchor.click();
            },
        },
        {
            content: "The card's venue field holds the new venue",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="venue_id"] select`,
            async run() {
                const start = Date.now();
                const shown = () => {
                    const option = this.anchor.options[this.anchor.selectedIndex];
                    return option && option.textContent.includes("Tour 1612 Arena");
                };
                while (!shown()) {
                    if (Date.now() - start > 8000) {
                        throw new Error("the venue select does not show the new venue");
                    }
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
            },
        },
        {
            content: "Done",
            trigger: `${CARD} [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The read view shows the venue, no error, no reload",
            trigger: '[data-sc-section="event.hero"] [data-sc-edit-view="read"] dd:contains("Tour 1612 Arena")',
            run() {
                const error = document.querySelector("[data-sc-venue-error]");
                if (error && !error.hidden) {
                    throw new Error(`venue error shown: ${error.textContent}`);
                }
                if (window.__sc1612NoReload !== "1") {
                    throw new Error("the page reloaded");
                }
            },
        },
    ],
});
