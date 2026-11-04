/*
 * Task 1593 — a player row's « Details » expands the legacy card's detail
 * under the row (lazy-loaded), without leaving the page, and closes again.
 * Run by tests/test_app_shell_roster_rows_1593.py (phone width, coach);
 * language-independent triggers only (data attributes).
 */
import { registry } from "@web/core/registry";

const ROW = '[data-sc-section="team.roster"] .o_sc_player_row';

registry.category("web_tour.tours").add("sc_1593_row_expand", {
    steps: () => [
        {
            content: "Roster row with its training recommendation line",
            trigger: `${ROW} [data-sc-row-training]`,
            run() {
                window.__sc1593NoReload = "1";
            },
        },
        {
            content: "Expand the injured player's row",
            trigger: `${ROW}:has([data-sc-row-return]) button[data-sc-row-expand][aria-expanded="false"]`,
            run: "click",
        },
        {
            content: "The injury detail is loaded under the row, same page",
            trigger: `${ROW} [data-sc-row-detail]:not([hidden]) .o_sc_injury_detail`,
            run() {
                if (window.__sc1593NoReload !== "1") {
                    throw new Error("the page reloaded");
                }
                const region = document.querySelector(`${ROW} [data-sc-row-detail]:not([hidden])`);
                if (region.textContent.includes("Synthetic hidden diagnosis")) {
                    throw new Error("a coach sees an injury hidden from coaches");
                }
            },
        },
        {
            content: "Collapse it",
            trigger: `${ROW} button[data-sc-row-expand][aria-expanded="true"]`,
            run: "click",
        },
        {
            content: "The detail is hidden again",
            trigger: `${ROW}:has(button[data-sc-row-expand][aria-expanded="false"]) [data-sc-row-detail][hidden]:not(:visible)`,
        },
    ],
});
