/*
 * Task 1624, owner UAT round 2 (2026-10-29) — the dashboard in a browser
 * (tests/test_dashboard_tours_1624.py, phone 390 px and laptop 1440 px).
 * Synthetic data; language-independent triggers. Each measured toggle is
 * clicked from inside its own step (a tour click may scroll first).
 *
 * - « Cliniques aujourd'hui » and the first event card do not touch;
 * - expanding / collapsing « Activités en retard » (10 cards), its « Voir
 *   les N autres » and an event's « Détails » keeps the toggle's top
 *   within 2 px;
 * - the quick « Retour prévu » of « Retours dépassés »: a future date drops
 *   « Dépassé » in place and the line count follows (2 → 1);
 * - « Suivre » from « Joueurs à surveiller » adds the card to « Joueurs que
 *   je suis » with its count, « Ne plus suivre » removes it (empty state
 *   back), without a reload.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 10000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function noHorizontalScroll() {
    const doc = document.documentElement;
    assert(doc.scrollWidth <= doc.clientWidth + 1, `horizontal scroll (${doc.scrollWidth} > ${doc.clientWidth})`);
}

/** Bring ``el`` to ~120 px from the top (as far as the page allows), click
 * it, and check its top moved by less than 2 px once things settle. */
async function clickKeepsTop(el, label) {
    window.scrollTo(0, Math.max(0, window.scrollY + el.getBoundingClientRect().top - 120));
    await pause(150);
    const before = el.getBoundingClientRect().top;
    el.click();
    await pause(1200);
    const after = el.getBoundingClientRect().top;
    assert(Math.abs(after - before) < 2, `${label}: the header moved ${before} -> ${after}`);
}

function shift(iso, days) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

function typeAndLeave(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur")); // headless: blur() fires no event without window focus
}

const TODAY = 'section[data-sc-instance="today"]';
const TODO = 'section[data-sc-instance="todo"]';
const WATCH = 'section[data-sc-instance="watch"]';
const FOLLOWED = 'section[data-sc-instance="followed"]';
const OVERDUE = `${TODO} details[data-sc-todo="activities_overdue"]`;
const RETURNS = `${TODO} details[data-sc-todo="returns"]`;

tours.add("sc_1624_dashboard_round2", {
    steps: () => [
        {
            content: "The clinics row and the first event card do not touch",
            trigger: `${TODAY} [data-sc-section="home.clinic_teaser"] + .o_sc_dw_events .o_sc_event_row`,
            run() {
                window.__sc1624r2NoReload = true;
                const clinics = document.querySelector(`${TODAY} [data-sc-section="home.clinic_teaser"]`);
                const gap = this.anchor.getBoundingClientRect().top - clinics.getBoundingClientRect().bottom;
                assert(gap >= 4, `gap ${gap}`);
                noHorizontalScroll();
            },
        },
        {
            content: "Expand and collapse « Overdue activities »: its header stays put",
            trigger: `${OVERDUE}:not([open]) > summary`,
            async run() {
                const summary = this.anchor;
                await clickKeepsTop(summary, "expand");
                const line = summary.parentElement;
                assert(line.open, "open");
                assert(line.querySelectorAll("[data-sc-activity-row]").length >= 8, "8+ cards");
                const more = line.querySelector("details[data-sc-dw-more] > summary");
                assert(more, "« See the N others »");
                await clickKeepsTop(more, "see the others");
                assert(more.parentElement.open, "others open");
                await clickKeepsTop(more, "see the others (fold)");
                await clickKeepsTop(summary, "collapse");
                assert(!line.open, "closed");
                noHorizontalScroll();
            },
        },
        {
            content: "An event card's « Details »: the card stays put",
            trigger: 'section[data-sc-instance="coverage"] .o_sc_event_row button[data-sc-row-expand][aria-expanded="false"]',
            async run() {
                const toggle = this.anchor;
                await clickKeepsTop(toggle, "event details");
                assert(toggle.getAttribute("aria-expanded") === "true", "expanded (⌃)");
                const region = document.getElementById(toggle.dataset.scRowExpand);
                assert(region && !region.hidden && region.querySelector('[data-sc-ev-field="staff"]'), "details shown");
                await clickKeepsTop(toggle, "event details (fold)");
                assert(region.hidden && toggle.getAttribute("aria-expanded") === "false", "folded (⌄)");
            },
        },
        {
            content: "Quick « Retour prévu » on an overdue return",
            trigger: `${RETURNS}:not([open]) > summary`,
            async run() {
                const line = this.anchor.parentElement;
                const count = line.querySelector("[data-sc-todo-count]");
                assert(count.textContent.trim() === "2", `count ${count.textContent}`);
                this.anchor.click();
                const card = line.querySelector(".o_sc_player_row");
                const id = card.dataset.scPlayerId;
                const field = '.o_sc_row_quick[data-sc-row-quick="predicted_return_date"] input[type="date"]';
                await waitFor(() => card.querySelector(field), "the quick field");
                const input = card.querySelector(field);
                assert(input.min, "min = today");
                assert(card.querySelector(".o_sc_overdue_flag"), "« Passed » before");
                typeAndLeave(input, shift(input.min, 7));
                await waitFor(
                    () => !line.querySelector(`[data-sc-player-id="${id}"] .o_sc_link_row .o_sc_overdue_flag`),
                    "« Passed » gone"
                );
                await waitFor(
                    () => line.querySelector("[data-sc-todo-count]").textContent.trim() === "1",
                    "the count follows"
                );
                assert(window.__sc1624r2NoReload, "the page reloaded");
            },
        },
        {
            content: "Follow from « Players to watch »: the card joins « Players I follow »",
            trigger: `${WATCH} .o_sc_player_row button[data-sc-row-expand]`,
            async run() {
                const followed = document.querySelector(FOLLOWED);
                assert(followed.querySelector(":scope > .o_sc_dw_body > .o_sc_empty"), "empty at first");
                const row = this.anchor.closest(".o_sc_player_row");
                const id = row.dataset.scPlayerId;
                this.anchor.click();
                const toggle = `button[data-sc-follow="${id}"]`;
                await waitFor(() => row.querySelector(`${toggle}[data-sc-followed="0"]`), "the follow toggle");
                row.querySelector(toggle).click();
                await waitFor(
                    () => document.querySelector(`${FOLLOWED} [data-sc-fragment-item="p${id}"]`),
                    "the card in « Players I follow »"
                );
                const count = document.querySelector(`${FOLLOWED} [data-sc-dw-count]`);
                assert(count && count.textContent.includes("1"), "the count");
                assert(!document.querySelector(`${FOLLOWED} > .o_sc_dw_body > .o_sc_empty`), "no empty state");
                // Unfollow (from the same card).
                await waitFor(() => row.querySelector(`${toggle}[data-sc-followed="1"]`), "followed");
                row.querySelector(toggle).click();
                await waitFor(
                    () => !document.querySelector(`${FOLLOWED} [data-sc-fragment-item]`),
                    "the card leaves « Players I follow »"
                );
                await waitFor(() => document.querySelector(`${FOLLOWED} > .o_sc_dw_body > .o_sc_empty`), "the empty state");
                assert(!document.querySelector(`${FOLLOWED} [data-sc-dw-count]`), "no count");
                assert(window.__sc1624r2NoReload, "the page reloaded");
                noHorizontalScroll();
            },
        },
    ],
});
