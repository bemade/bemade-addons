/*
 * Task 1736 — the card top bars in a browser
 * (tests/test_card_top_bars_tours_1736.py, phone 390 px and laptop 1366 px).
 * Synthetic data; language-independent triggers.
 *
 * - sc_1736_injury: the injury card folds ONLY with its chevron (a tap on
 *   the header's title does nothing); the header pencil opens the Details
 *   group (unfolding a folded card), its red trash shows while editing and
 *   opens « Delete injury »'s confirmation; the ✓ hides it again.
 * - sc_1736_star: the player header's ★ follows / unfollows in place.
 * - sc_1736_contact: the emergency contact's trash shows only while editing.
 * - sc_1736_med_delete: a medical item's trash asks first; « Cancel » keeps
 *   it, « Delete » removes it.
 * - sc_1736_note_undo: a quick note's archive icon archives it; the toast's
 *   « Undo » brings it back.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function q(selector) {
    return document.querySelector(selector);
}

function shown(el) {
    if (!el || el.hidden) {
        return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

async function pause(ms = 300) {
    await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await pause(100);
    }
}

const CARD = "details.o_sc_injury_item";
const HEAD = `${CARD} > summary`;
const TRASH = `${HEAD} button.o_pk_card_trash`;
const PENCIL = `${HEAD} button[data-sc-edit-toggle]`;
const CHEVRON = `${HEAD} button[data-sc-injury-toggle]`;

tours.add("sc_1736_injury", {
    steps: () => [
        {
            content: "A folded card: the top bar's order, the trash hidden",
            trigger: `${CARD}:not([open]) ${"> summary"} button[data-sc-injury-toggle][aria-expanded="false"]`,
            run() {
                const icons = [...q(`${HEAD} [data-sc-card-icons]`).querySelectorAll("a, button")];
                const kinds = icons.map((el) => ["o_sc_card_clock", "o_pk_card_trash", "o_pk_card_edit"]
                    .find((cls) => el.classList.contains(cls))).filter(Boolean);
                // (the clock only when the viewer has an activity on it)
                assert(["o_sc_card_clock,o_pk_card_trash,o_pk_card_edit", "o_pk_card_trash,o_pk_card_edit"]
                    .includes(kinds.join()), `order: ${kinds}`);
                assert(!shown(q(TRASH)), "the trash shows in read mode");
                const pencil = q(PENCIL).getBoundingClientRect();
                const chevron = this.anchor.getBoundingClientRect();
                assert(pencil.right <= chevron.left + 1, "the chevron is not right of the pencil");
                assert(Math.abs((pencil.top + pencil.bottom) / 2 - (chevron.top + chevron.bottom) / 2) < 4,
                    "pencil and chevron not on one line");
            },
        },
        {
            content: "A tap on the header's title does not unfold the card",
            trigger: `${HEAD} .o_pk_row_title`,
            async run(helpers) {
                await helpers.click();
                await pause();
                assert(!q(CARD).open, "the header tap unfolded the card");
            },
        },
        {
            content: "The chevron unfolds it",
            trigger: CHEVRON,
            run: "click",
        },
        {
            content: "Open; the chevron says so",
            trigger: `${CARD}[open] > summary button[data-sc-injury-toggle][aria-expanded="true"]`,
        },
        {
            content: "A tap on the header's title does not fold it",
            trigger: `${CARD}[open] > summary .o_pk_row_title`,
            async run(helpers) {
                await helpers.click();
                await pause();
                assert(q(CARD).open, "the header tap folded the card");
            },
        },
        {
            content: "The header pencil edits the Details",
            trigger: PENCIL,
            run: "click",
        },
        {
            content: "Details in edit mode, the pencil a ✓, the red trash next to it",
            trigger: `${CARD} [data-pk-edit-card="injury-details"][data-sc-edit-open] [data-sc-edit-view="edit"]:not([hidden])`,
            run() {
                const trash = q(TRASH);
                assert(shown(trash), "no trash while editing");
                assert(trash.classList.contains("o_pk_icon_btn_danger")
                    && getComputedStyle(trash).color !== getComputedStyle(q(`${HEAD} [data-sc-card-icons] .o_sc_card_clock`) || q(PENCIL)).color,
                    "the trash is not red");
                assert(q(PENCIL).dataset.scEditToggleDone === "1", "the pencil is not a ✓");
                assert(trash.getBoundingClientRect().right <= q(PENCIL).getBoundingClientRect().left + 1,
                    "the trash is not left of the ✓");
            },
        },
        {
            content: "The ✓ closes the Details",
            trigger: `${PENCIL}[data-sc-edit-toggle-done]`,
            run: "click",
        },
        {
            content: "Read mode: the trash is hidden again",
            trigger: `${CARD} [data-pk-edit-card="injury-details"]:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
            run() {
                assert(!shown(q(TRASH)), "the trash still shows");
            },
        },
        {
            content: "The chevron folds the card",
            trigger: CHEVRON,
            run: "click",
        },
        {
            content: "Folded",
            trigger: `${CARD}:not([open]) > summary button[data-sc-injury-toggle][aria-expanded="false"]`,
        },
        {
            content: "The pencil of a folded card unfolds it in edit mode",
            trigger: PENCIL,
            run: "click",
        },
        {
            content: "Unfolded, Details editing; the trash opens « Delete injury »",
            trigger: `${CARD}[open] [data-pk-edit-card="injury-details"][data-sc-edit-open]`,
            run() {
                q(TRASH).click();
            },
        },
        {
            content: "The confirmation sheet",
            trigger: "dialog[id^='sc_delete_injury_sheet_'][open]",
        },
    ],
});

tours.add("sc_1736_star", {
    steps: () => [
        {
            content: "The ★ (not followed), left of the pencil",
            trigger: '[data-pk-section="player.hero"] button[data-sc-follow][aria-pressed="false"]',
            run(helpers) {
                const pencil = q('[data-pk-section="player.hero"] [data-sc-card-icons] button[data-sc-edit-toggle]');
                assert(pencil, "no pencil in the hero's icon group");
                assert(this.anchor.getBoundingClientRect().right <= pencil.getBoundingClientRect().left + 1,
                    "the ★ is not left of the pencil");
                window.__sc1736Star = getComputedStyle(this.anchor.querySelector("svg")).fill;
                return helpers.click();
            },
        },
        {
            content: "Followed: pressed, the star filled",
            trigger: '[data-pk-section="player.hero"] button[data-sc-follow][aria-pressed="true"][data-sc-followed="1"]:not([disabled])',
            run(helpers) {
                assert(getComputedStyle(this.anchor.querySelector("svg")).fill !== window.__sc1736Star, "the star is not filled");
                return helpers.click();
            },
        },
        {
            content: "Unfollowed again",
            trigger: '[data-pk-section="player.hero"] button[data-sc-follow][aria-pressed="false"][data-sc-followed="0"]:not([disabled])',
        },
    ],
});

const CONTACT = "section.o_sc_contact";

tours.add("sc_1736_contact", {
    steps: () => [
        {
            content: "Read mode: no trash; the pencil",
            trigger: `${CONTACT}:not([data-sc-edit-open]) button[data-sc-edit-toggle]`,
            run(helpers) {
                assert(!shown(q(`${CONTACT} button.o_pk_card_trash`)), "the trash shows in read mode");
                return helpers.click();
            },
        },
        {
            content: "Editing: the red trash left of the ✓",
            trigger: `${CONTACT}[data-sc-edit-open] button.o_pk_card_trash:visible`,
            run(helpers) {
                const done = q(`${CONTACT} button[data-sc-edit-toggle-done]`);
                assert(this.anchor.getBoundingClientRect().right <= done.getBoundingClientRect().left + 1, "order");
                return helpers.click();
            },
        },
        {
            content: "It asks first",
            trigger: "dialog[id^='sc_delete_contact_'][open]",
        },
    ],
});

const ALLERGY = 'dialog[open] [data-pk-section="medical.allergy"]';
const ITEM = `${ALLERGY} [data-sc-med-item]`;

tours.add("sc_1736_med_delete", {
    steps: () => [
        {
            content: "The Allergies pill",
            trigger: '[data-pk-section="player.medical"] button[data-sc-med-pill="allergy"]',
            run: "click",
        },
        {
            content: "An item's pencil",
            trigger: `${ITEM} button[data-sc-edit-toggle]`,
            run(helpers) {
                assert(!shown(q(`${ITEM} button[data-sc-med-item-delete]`)), "the trash shows in read mode");
                return helpers.click();
            },
        },
        {
            content: "Its trash, while editing",
            trigger: `${ITEM}[data-sc-edit-open] button[data-sc-med-item-delete]:visible`,
            run: "click",
        },
        {
            content: "It asks first — Cancel",
            trigger: "dialog[data-pk-confirm][open] [data-pk-confirm-cancel]",
            run: "click",
        },
        {
            content: "Still there; the trash again",
            trigger: `${ITEM}[data-sc-edit-open] button[data-sc-med-item-delete]:visible`,
            async run(helpers) {
                await pause();
                assert(document.querySelectorAll(ITEM).length === 1, "the item went without a confirmation");
                return helpers.click();
            },
        },
        {
            content: "Confirm",
            trigger: "dialog[data-pk-confirm][open] [data-pk-confirm-ok]",
            run: "click",
        },
        {
            content: "Gone",
            trigger: `${ALLERGY}`,
            async run() {
                await waitFor(() => !q(ITEM), "the item is removed");
            },
        },
    ],
});

tours.add("sc_1736_note_undo", {
    steps: () => [
        {
            content: "The note's archive icon (read mode), left of the pencil; no trash yet",
            trigger: "article.o_sc_quick_note button.o_pk_card_archive",
            expectUnloadPage: true,
            run(helpers) {
                const card = this.anchor.closest("article");
                assert(!shown(card.querySelector("button.o_pk_card_trash")), "the trash shows in read mode");
                const pencil = card.querySelector("button[data-sc-edit-toggle]");
                assert(this.anchor.getBoundingClientRect().right <= pencil.getBoundingClientRect().left + 1, "order");
                return helpers.click();
            },
        },
        {
            content: "Archived: the toast offers « Undo »",
            trigger: ".o_pk_toast:not([hidden]) button[data-pk-toast-action]",
            expectUnloadPage: true,
            run(helpers) {
                assert(!q("article.o_sc_quick_note"), "the note is still listed");
                return helpers.click();
            },
        },
        {
            content: "Back in the notes",
            trigger: "article.o_sc_quick_note button.o_pk_card_archive",
        },
    ],
});
