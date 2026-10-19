/*
 * Task 1611 — read fragments in a browser: what shows follows an in-place
 * save WITHOUT « Done » and without a reload; « back » reloads a page only
 * when something was saved after it was rendered.
 * Run by tests/test_app_shell_fragments_tours_1611.py (phone 390 px and
 * laptop 1366 px). Synthetic data; language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

/** Poll ``check`` (hidden nodes included) until true, or fail. */
async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function frag(suffix) {
    return document.querySelector(`[data-sc-fragment$=":${suffix}"]`);
}

function markNoReload() {
    window.__sc1611NoReload = "1";
}

function assertNoReload() {
    assert(window.__sc1611NoReload === "1", "the page reloaded");
}

/** Type a value into an input / textarea and leave it (headless CI blur). */
function typeAndLeave(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
}

// -------------------------------------------- player page (Info tab)
const IDENTITY = '[data-sc-edit-card="identity"]';
const HEADER = '[data-sc-edit-card="player-header"]';

tours.add("sc_1611_player_fragments", {
    steps: () => [
        {
            content: "Player page; open the identity card",
            trigger: `${IDENTITY} button[data-sc-edit-toggle]`,
            run(helpers) {
                markNoReload();
                return helpers.click();
            },
        },
        {
            content: "Rename the player and leave the field",
            trigger: `${IDENTITY} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="last_name"] input`,
            run() {
                typeAndLeave(this.anchor, "Zedsynth");
            },
        },
        {
            content: "Confirm the identity correction",
            trigger: '.o_sc_autosave[data-sc-field="last_name"] .o_sc_identity_banner .o_sc_identity_confirm',
            run: "click",
        },
        {
            content: "Saved",
            trigger: '.o_sc_autosave[data-sc-field="last_name"][data-sc-state="saved"]',
        },
        {
            content: "Title, document title, hero name + initials follow — no « Done », no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => frag("appbar") && frag("appbar").textContent.includes("Zedsynth"), "app bar title");
                await waitFor(() => document.title.includes("Zedsynth"), "document title");
                const hero = frag("hero-head");
                assert(hero.textContent.includes("Zedsynth"), "hero name");
                assert(hero.querySelector(".o_sc_avatar").textContent.trim() === "PZ", "hero initials");
                assert(document.querySelector(`${IDENTITY}[data-sc-edit-open]`), "the card closed");
                assertNoReload();
            },
        },
        {
            content: "Set the date of birth and leave it",
            trigger: `${IDENTITY} .o_sc_autosave[data-sc-field="date_of_birth"] input`,
            run() {
                const year = new Date().getFullYear() - 16;
                typeAndLeave(this.anchor, `${year}-01-02`);
            },
        },
        {
            content: "Saved",
            trigger: `${IDENTITY} .o_sc_autosave[data-sc-field="date_of_birth"][data-sc-state="saved"]`,
        },
        {
            content: "The identity read view (behind the open card) shows the age",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => {
                    const read = frag("identity");
                    return read && [...read.querySelectorAll("dd")].some((dd) => dd.textContent.trim() === "16");
                }, "age 16");
                assert(frag("identity").hidden, "the read view must stay hidden while editing");
                assertNoReload();
            },
        },
        {
            // Review fixes 2026-10-18 b: the allergies are edited in the
            // player header only (its pencil), no longer in the Medical card.
            content: "Open the header pencil",
            trigger: `${HEADER} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Fill the allergies and leave the field",
            trigger: `${HEADER} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="allergies"] textarea`,
            run() {
                typeAndLeave(this.anchor, "Synthetic pollen");
            },
        },
        {
            content: "The hero's allergies banner is refreshed (read view, behind the open edit view)",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => {
                    const banner = document.querySelector('[data-sc-section="player.allergies"] .o_sc_banner');
                    return banner && banner.textContent.includes("Synthetic pollen");
                }, "banner shown");
                assertNoReload();
            },
        },
        {
            content: "Clear the allergies",
            trigger: `${HEADER} .o_sc_autosave[data-sc-field="allergies"] .o_sc_clear_btn`,
            run: "click",
        },
        {
            content: "The banner goes",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector('[data-sc-section="player.allergies"] .o_sc_banner'), "banner gone");
                assertNoReload();
            },
        },
    ],
});

// ------------------------------------- injury card (player Injuries tab)
const CARD = ".o_sc_injury_item[open]";

const CARD_DETAILS = `${CARD} section[data-sc-edit-card="injury-details"]`;

tours.add("sc_1611_injury_stage", {
    steps: () => [
        {
            content: "Open card: the Details pencil (task 1616: one per group)",
            trigger: `${CARD_DETAILS} button[data-sc-edit-toggle]`,
            run(helpers) {
                markNoReload();
                return helpers.click();
            },
        },
        {
            content: "« Resolved »",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="stage"] button[data-sc-value="resolved"]`,
            run: "click",
        },
        {
            content: "Saved",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="stage"][data-sc-state="saved"]`,
        },
        {
            content: "The summary turns green at once, the card stays open in edit mode",
            trigger: `${CARD} > summary .o_sc_dot.o_sc_tone_green`,
            run() {
                assert(document.querySelector(`${CARD_DETAILS}[data-sc-edit-open]`), "the card closed");
                assertNoReload();
            },
        },
        {
            content: "Done",
            trigger: `${CARD_DETAILS} [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The read view shows the resolution date; resolved card moved last",
            trigger: `${CARD_DETAILS} [data-sc-edit-view="read"]:not([hidden])`,
            async run() {
                const card = document.querySelector(CARD);
                await waitFor(() => {
                    const items = [...document.querySelectorAll('[data-sc-section="player.injuries"] [data-sc-fragment-item]')];
                    return items[items.length - 1] === card;
                }, "resolved card last");
                assert(card.querySelectorAll('[data-sc-edit-card="injury-details"] [data-sc-edit-view="read"] dt').length >= 3, "read rows");
                assertNoReload();
            },
        },
    ],
});

// ------------------------------------------- event page + timesheet
const EVENT = '[data-sc-edit-card="event"]';

tours.add("sc_1611_event_when", {
    steps: () => [
        {
            content: "Event card: pencil",
            trigger: `${EVENT} button[data-sc-edit-toggle]`,
            run(helpers) {
                markNoReload();
                return helpers.click();
            },
        },
        {
            content: "New start time",
            trigger: `${EVENT} .o_sc_autosave[data-sc-field="date_start"] input`,
            run() {
                typeAndLeave(this.anchor, "2026-02-02T08:15");
            },
        },
        {
            content: "Saved",
            trigger: `${EVENT} .o_sc_autosave[data-sc-field="date_start"][data-sc-state="saved"]`,
        },
        {
            content: "« When » follows (read view behind the open card)",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => frag("read") && frag("read").textContent.includes("08:15"), "When 08:15");
                assertNoReload();
            },
        },
        {
            content: "Done",
            trigger: `${EVENT} [data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "Timesheet card: pencil",
            trigger: '[data-sc-edit-card^="timesheet-"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Coverage end two hours after the start",
            trigger: '[data-sc-edit-card^="timesheet-"] .o_sc_autosave[data-sc-field="coverage_end"] input',
            run() {
                typeAndLeave(this.anchor, "2026-02-02T12:00");
            },
        },
        {
            content: "Saved",
            trigger: '[data-sc-edit-card^="timesheet-"] .o_sc_autosave[data-sc-field="coverage_end"][data-sc-state="saved"]',
        },
        {
            content: "Done: the read lines show the new total",
            trigger: '[data-sc-edit-card^="timesheet-"] [data-sc-edit-done]',
            run: "click",
        },
        {
            content: "Coverage hours 2:00",
            trigger: '[data-sc-edit-card^="timesheet-"] [data-sc-edit-view="read"]:not([hidden]) dd:contains("2:00")',
            run: assertNoReload,
        },
    ],
});

// -------------------------------------- back after a change: roster row
// history.back() may restore a page from the back/forward cache with this
// tour's old step timers: like the 1579 tours, the team page reloads itself
// when restored (the « back » check would reload it too: a save happened).
function reloadIfRestored() {
    window.addEventListener("pageshow", (ev) => {
        if (ev.persisted) {
            window.location.reload();
        }
    });
}

const ROSTER_ROW = '[data-sc-section="team.roster"] .o_sc_player_row:has(a.o_sc_link_row_main:contains("Zedback"))';

tours.add("sc_1611_back_roster", {
    steps: () => [
        {
            content: "Team roster: the player is available",
            trigger: `${ROSTER_ROW} .o_sc_dot.o_sc_tone_green`,
            run() {
                reloadIfRestored();
                this.anchor.closest(".o_sc_player_row").querySelector("a.o_sc_link_row_main").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Player page: the header's pencil (review fixes 2026-10-18)",
            trigger: '[data-sc-section="player.hero"] > button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "Player page: « No play »",
            trigger: '.o_sc_autosave[data-sc-field="sc_status"] button[data-sc-value="no:no"]',
            run: "click",
        },
        {
            content: "Saved; back",
            trigger: '.o_sc_autosave[data-sc-field="sc_status"][data-sc-state="saved"]',
            run() {
                window.history.back();
            },
            expectUnloadPage: true,
        },
        {
            content: "The roster row shows the new status",
            trigger: `${ROSTER_ROW} .o_sc_dot.o_sc_tone_red`,
        },
    ],
});

// ----------------------------------- the « back » check, deterministic
function renderedAt() {
    return Number(document.querySelector(".o_sc_app").dataset.scRenderedAt);
}

tours.add("sc_1611_back_check", {
    steps: () => [
        {
            content: "Shown again from the cache, nothing saved since: no reload",
            trigger: ".o_sc_app[data-sc-rendered-at]",
            async run() {
                markNoReload();
                window.sessionStorage.setItem("sc_dirty_at:v1", String(renderedAt() - 60000));
                window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
                await new Promise((resolve) => setTimeout(resolve, 500));
                assertNoReload();
            },
        },
        {
            content: "Shown again after a save made elsewhere: it reloads",
            trigger: ".o_sc_app[data-sc-rendered-at]",
            run() {
                window.sessionStorage.setItem("sc_dirty_at:v1", String(renderedAt() + 60000));
                window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
            },
            expectUnloadPage: true,
        },
        {
            content: "Reloaded (a fresh render, no loop)",
            trigger: ".o_sc_app[data-sc-rendered-at]",
            run() {
                assert(window.__sc1611NoReload !== "1", "the page did not reload");
                window.sessionStorage.removeItem("sc_dirty_at:v1");
            },
        },
    ],
});
