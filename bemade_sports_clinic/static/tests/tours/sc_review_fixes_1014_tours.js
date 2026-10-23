/*
 * Owner review 2026-10-14 — browser tours (run by
 * tests/test_review_fixes_1014.py, as a treatment professional, on synthetic
 * fixtures):
 *
 * - sc_1014_date_complete: a date typed into an autosave field is saved ONCE,
 *   when the user leaves it — not on each « change » while typing (the day
 *   « 15 » used to save « 01 » first);
 * - sc_1014_serialized_saves: a second save asked while the first is in
 *   flight waits for it and goes out with the fresh write_date — no
 *   « changed elsewhere » banner attributing the change to the user;
 * - sc_1014_filters_autosubmit: the events filters apply on change (a date
 *   once complete), the « Apply filters » button is hidden, the panel stays
 *   open across the reload.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

/** Count the autosave POSTs from now on (sc_fetch calls the global fetch). */
function countSaves() {
    window.__scSaves = 0;
    const original = window.fetch;
    window.fetch = function (url, ...rest) {
        if (String(url).includes("/my/app/save/")) {
            window.__scSaves++;
        }
        return original.call(this, url, ...rest);
    };
}

/** What a keyboard user typing into a date input makes the browser fire. */
function typeDate(input, key, value) {
    input.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

const RETURN = '[data-sc-edit-card="medical"] .o_sc_autosave[data-sc-field="return_date"]';

tours.add("sc_1014_date_complete", {
    steps: () => [
        {
            content: "Open the Medical Information card",
            trigger: '[data-sc-edit-card="medical"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Type the date: « 01 » on the way to « 15 » is not saved",
            trigger: `${RETURN} input[type="date"]`,
            run() {
                countSaves();
                this.anchor.focus();
                typeDate(this.anchor, "0", "2026-11-01");
                typeDate(this.anchor, "1", "2026-11-01");
            },
        },
        {
            content: "Still being typed: nothing sent",
            trigger: `${RETURN}[data-sc-state="dirty"]`,
            run() {
                assert(window.__scSaves === 0, `saves while typing: ${window.__scSaves}`);
                const input = document.querySelector(`${RETURN} input[type="date"]`);
                typeDate(input, "1", "2026-11-01");
                typeDate(input, "5", "2026-11-15");
                assert(window.__scSaves === 0, `saves while typing: ${window.__scSaves}`);
                input.blur(); input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Leaving the field saves the complete date, once",
            trigger: `${RETURN}[data-sc-state="saved"]`,
            run() {
                assert(window.__scSaves === 1, `saves: ${window.__scSaves}`);
                assert(!document.querySelector(`${RETURN} .o_sc_conflict_banner`), "no conflict");
            },
        },
    ],
});

// Review fixes 2026-10-18: the island is in the header's edit view.
const TRAINING = '[data-sc-section="player.training.edit"] .o_sc_autosave[data-sc-field="training_recommendation"]';

tours.add("sc_1014_serialized_saves", {
    steps: () => [
        {
            content: "Open the header's pencil",
            trigger: '[data-sc-section="player.hero"] > button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Save twice in a row: the second while the first is in flight",
            trigger: `${TRAINING} textarea`,
            run() {
                countSaves();
                const area = this.anchor;
                area.focus();
                area.value = "Synthetic first";
                area.dispatchEvent(new Event("input", { bubbles: true }));
                area.blur(); area.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
                area.focus();
                area.value = "Synthetic second";
                area.dispatchEvent(new Event("input", { bubbles: true }));
                area.blur(); area.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
        },
        {
            content: "Both saved, one after the other, no conflict",
            trigger: `${TRAINING}[data-sc-state="saved"]`,
            run() {
                assert(window.__scSaves === 2, `saves: ${window.__scSaves}`);
                assert(!document.querySelector(`${TRAINING} .o_sc_conflict_banner`),
                    "no « changed elsewhere » banner");
                const area = document.querySelector(`${TRAINING} textarea`);
                assert(area.value === "Synthetic second", `value: ${area.value}`);
            },
        },
    ],
});

const FORM = 'form[data-sc-section="events.filters"][data-sc-autosubmit]';

tours.add("sc_1014_filters_autosubmit", {
    steps: () => [
        {
            content: "No « Apply filters » button to press; open the filters",
            trigger: `${FORM} details summary`,
            run(helpers) {
                const fallback = document.querySelector(`${FORM} [data-sc-autosubmit-fallback]`);
                assert(fallback && fallback.classList.contains("visually-hidden"),
                    "the apply button is hidden (kept for Enter / no-JS)");
                window.__sc1014NoReload = true;
                if (!this.anchor.closest("details").open) {
                    helpers.click();
                }
            },
        },
        {
            content: "Typing a date applies nothing yet",
            trigger: `${FORM} details[open] input[name="date_from"]`,
            run() {
                this.anchor.focus();
                typeDate(this.anchor, "2", "2026-01-02");
                typeDate(this.anchor, "0", "2026-01-20");
            },
        },
        {
            content: "Still on the same page; leaving the date applies it",
            trigger: `${FORM} details[open] input[name="date_from"]`,
            run() {
                assert(window.__sc1014NoReload, "the page reloaded while typing");
                assert(!new URLSearchParams(window.location.search).has("date_from"), "applied too early");
                this.anchor.blur(); this.anchor.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
            },
            expectUnloadPage: true,
        },
        {
            content: "The date is applied and the panel is still open; pick a team",
            trigger: `${FORM} details[open] select[name="team_id"]`,
            run() {
                const params = new URLSearchParams(window.location.search);
                assert(params.get("date_from") === "2026-01-20", `url: ${window.location.search}`);
                const option = [...this.anchor.options].find((opt) => opt.value);
                this.anchor.value = option.value;
                this.anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
            expectUnloadPage: true,
        },
        {
            content: "The team filter is applied at once",
            trigger: `${FORM} details[open] select[name="team_id"]`,
            run() {
                const params = new URLSearchParams(window.location.search);
                assert(params.get("team_id") === this.anchor.value && this.anchor.value,
                    `url: ${window.location.search}`);
                assert(params.get("date_from") === "2026-01-20", "the date is kept");
            },
        },
    ],
});
