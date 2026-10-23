/*
 * Task 1626 — the team dashboard's « Recent changes » card works like the
 * other player cards: « Details » loads the change detail under the row
 * (same page), and while it is open the face's training and « Retour
 * prévu » lines are hidden (the detail has them); collapsing shows them
 * again. Checked on a recent-changes card and on a roster card.
 * Run by tests/test_dashboard_card_1626.py (phone width, coach);
 * language-independent triggers only (data attributes).
 */
import { registry } from "@web/core/registry";

const DASH = '[data-sc-section="team.recent_changes"] .o_sc_player_row';
const ROSTER = '[data-sc-section="team.roster"] .o_sc_player_row';
const FACE = ".o_sc_link_row";

function assertFace(row, visible) {
    for (const sel of ["[data-sc-row-training]", "[data-sc-row-return]"]) {
        const el = document.querySelector(`${row} ${FACE} ${sel}`);
        if (!el) {
            throw new Error(`no face line ${sel}`);
        }
        const shown = el.getClientRects().length > 0;
        if (shown !== visible) {
            throw new Error(`face line ${sel} should be ${visible ? "visible" : "hidden"}`);
        }
    }
}

registry.category("web_tour.tours").add("sc_1626_card_details", {
    steps: () => [
        {
            content: "Recent-changes card: face lines + arrow to the player page",
            trigger: `${DASH} ${FACE} [data-sc-row-training]:visible`,
            run() {
                window.__sc1626NoReload = "1";
                if (!document.querySelector(`${DASH} a.o_sc_link_row_main[href*="/my/player"]`)) {
                    throw new Error("no link to the player page on the card face");
                }
                assertFace(DASH, true);
            },
        },
        {
            content: "Open its Details",
            trigger: `${DASH} button[data-sc-row-expand][aria-expanded="false"]`,
            run: "click",
        },
        {
            content: "The change detail loads under the card; face lines hidden",
            trigger: `${DASH} [data-sc-row-detail]:not([hidden]) .o_sc_change_detail a.o_sc_section_more:visible`,
            run() {
                if (window.__sc1626NoReload !== "1") {
                    throw new Error("the page reloaded");
                }
                assertFace(DASH, false);
                const detail = document.querySelector(`${DASH} [data-sc-row-detail] .o_sc_change_detail`);
                if (!detail.textContent.includes("Second line of advice")) {
                    throw new Error("the detail lacks the whole training recommendation");
                }
            },
        },
        {
            content: "Collapse it",
            trigger: `${DASH} button[data-sc-row-expand][aria-expanded="true"]`,
            run: "click",
        },
        {
            content: "Face lines are back",
            trigger: `${DASH}:has(button[data-sc-row-expand][aria-expanded="false"]) [data-sc-row-detail][hidden]:not(:visible)`,
            run() {
                assertFace(DASH, true);
            },
        },
        {
            content: "Players tab",
            trigger: '[data-sc-tabs] a[data-sc-tab="players"]',
            run: "click",
        },
        {
            content: "Open a roster card's Details",
            trigger: `${ROSTER}:has([data-sc-row-return]) button[data-sc-row-expand][aria-expanded="false"]`,
            run: "click",
        },
        {
            content: "Roster card: detail open, face lines hidden",
            trigger: `${ROSTER} [data-sc-row-detail]:not([hidden]) .o_sc_row_detail_body:visible`,
            run() {
                assertFace(`${ROSTER}.o_sc_row_open`, false);
            },
        },
        {
            content: "Collapse the roster card",
            trigger: `${ROSTER} button[data-sc-row-expand][aria-expanded="true"]`,
            run: "click",
        },
        {
            content: "Roster card face lines are back",
            trigger: `${ROSTER}:not(.o_sc_row_open):has([data-sc-row-return]) [data-sc-row-detail][hidden]:not(:visible)`,
            run() {
                assertFace(`${ROSTER}:has([data-sc-row-return])`, true);
            },
        },
    ],
});
