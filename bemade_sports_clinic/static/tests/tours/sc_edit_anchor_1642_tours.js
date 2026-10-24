/*
 * Task 1642 — after an edit, the screen comes back to the top of the block
 * just edited (tests/test_edit_anchor_tours_1642.py, phone 390 px).
 *
 * Each tour pads the page (room to scroll), edits a block, scrolls the
 * window away (standing in for the keyboard / swap jump), then leaves the
 * field or presses « Done » / « Terminé »: the block's top must come back
 * just below the sticky app bar. A user gesture after the edit (touch)
 * cancels the anchor.
 *
 * The real keyboard closing on a phone cannot be reproduced headless —
 * UNVERIFIED until the /dev-review tap-through.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 5000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function barBottom() {
    return document.querySelector(".o_sc_appbar").getBoundingClientRect().bottom;
}

function anchored(selector) {
    const block = document.querySelector(selector);
    if (!block) {
        return false;
    }
    const top = block.getBoundingClientRect().top;
    return Math.abs(top - (barBottom() + 8)) <= 2;
}

function where(selector) {
    const block = document.querySelector(selector);
    return block ? `${Math.round(block.getBoundingClientRect().top)} vs bar ${Math.round(barBottom())}` : "missing";
}

function pad() {
    document.body.style.paddingBottom = "3000px";
}

const NOTES = 'details.o_sc_injury_item[open] [data-sc-edit-card="injury-notes-external"]';  // task 1675
const CARD = "details.o_sc_injury_item";

tours.add("sc_1642_injury_notes_blur", {
    steps: () => [
        {
            content: "Open the Notes group (pencil)",
            trigger: `${NOTES} button[data-sc-edit-toggle]`,
            run(helpers) {
                pad();
                return helpers.click();
            },
        },
        {
            content: "Type a note",
            trigger: `${NOTES} [data-sc-edit-view="edit"] textarea`,
            run: "edit Tour 1642 synthetic note",
        },
        {
            content: "The page jumps away, then the user leaves the field",
            trigger: `${NOTES} [data-sc-edit-view="edit"] textarea`,
            async run() {
                this.anchor.focus();
                window.scrollTo(0, 0);
                await sleep(50);
                this.anchor.blur();
                await waitFor(() => anchored(NOTES), `notes block not anchored: ${where(NOTES)}`);
            },
        },
    ],
});

tours.add("sc_1642_injury_done", {
    steps: () => [
        {
            content: "Open the Notes group, focus its field",
            trigger: `${NOTES} button[data-sc-edit-toggle]`,
            run(helpers) {
                pad();
                return helpers.click();
            },
        },
        {
            content: "Jump away, then « Terminé »: back to the top of the (collapsed) card",
            trigger: `${CARD}[open] [data-sc-injury-done]`,
            async run() {
                const card = this.anchor.closest(CARD);
                card.id = card.id || "t1642_card";
                const selector = `#${card.id}`;
                window.scrollTo(0, 0);
                await sleep(50);
                this.anchor.click();
                await waitFor(() => !document.querySelector(selector).open, "the card stayed open");
                await waitFor(() => anchored(selector), `card not anchored: ${where(selector)}`);
            },
        },
    ],
});

const MEDICAL = 'section[data-sc-edit-card="medical"]';

tours.add("sc_1642_player_group_done", {
    steps: () => [
        {
            content: "Open the medical card (pencil)",
            trigger: `${MEDICAL} button[data-sc-edit-toggle]`,
            run(helpers) {
                pad();
                return helpers.click();
            },
        },
        {
            content: "Jump away, then its « Done »: back to the top of the card",
            trigger: `${MEDICAL} [data-sc-edit-view="edit"] [data-sc-edit-done]`,
            async run() {
                window.scrollTo(0, 0);
                await sleep(50);
                this.anchor.click();
                await waitFor(() => anchored(MEDICAL), `medical card not anchored: ${where(MEDICAL)}`);
            },
        },
        {
            content: "A touch after the edit wins: no anchor",
            trigger: `${MEDICAL} button[data-sc-edit-toggle]`,
            async run() {
                this.anchor.click(); // re-open (focuses its first field)
                await sleep(100);
                // Leave the field first and let that anchor expire: only
                // « Done » then the touch are under test here.
                if (document.activeElement && document.activeElement !== document.body) {
                    document.activeElement.blur();
                }
                await sleep(1700);
                const done = document.querySelector(`${MEDICAL} [data-sc-edit-view="edit"] [data-sc-edit-done]`);
                window.scrollTo(0, 0);
                done.click();
                window.dispatchEvent(new Event("touchstart"));
                await sleep(800);
                assert(window.scrollY === 0, `the anchor fought the user: scrollY=${window.scrollY}`);
            },
        },
    ],
});
