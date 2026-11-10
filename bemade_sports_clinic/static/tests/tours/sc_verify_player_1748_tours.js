/*
 * Task 1748 — the dashboard's « Injuries to verify » cards name their player
 * and link to the player's file (tests/test_dashboard_verify_player_1748.py,
 * phone 390 px and laptop 1440 px). Synthetic data; language-independent
 * triggers (data attributes, synthetic names).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const LINE = 'section[data-sc-instance="todo"] details[data-sc-todo="verify"]';
const YELLOW = `${LINE} details[data-pk-edit-card="injury"]:has([data-sc-injury-player-link]:contains("Synth, Yellow"))`;

function visible(el) {
    const box = el && el.getBoundingClientRect();
    return Boolean(box && box.width > 0 && box.height > 0);
}

tours.add("sc_1748_verify_card_player", {
    steps: () => [
        {
            content: "Open « Injuries to verify »",
            trigger: `${LINE} > summary`,
            run: "click",
        },
        {
            content: "Each card names its player and team(s), the header inside the card",
            trigger: `${YELLOW} > summary [data-sc-injury-player] .o_sc_injury_player_teams:contains("DB Team C")`,
            run() {
                const cards = [...document.querySelectorAll(`${LINE} details[data-pk-edit-card="injury"]`)];
                assert(cards.length === 2, `2 cards expected, got ${cards.length}`);
                for (const card of cards) {
                    const link = card.querySelector(":scope > summary [data-sc-injury-player-link]");
                    assert(link && visible(link), "every card shows its player link");
                    assert(link.textContent.trim(), "the link names the player");
                    // The name line sits above the card's title (not beside it).
                    const title = card.querySelector(":scope > summary .o_sc_row_title");
                    assert(link.getBoundingClientRect().bottom <= title.getBoundingClientRect().top + 1,
                           "the player line is above the injury title");
                }
                const shared = cards.find((c) => c.textContent.includes("Synth, Shared"));
                const teams = shared.querySelector(".o_sc_injury_player_teams").textContent;
                assert(teams.includes("PC Team A") && teams.includes("DB Team C"), `both teams: ${teams}`);
                assert(document.documentElement.scrollWidth <= window.innerWidth, "no horizontal scroll");
                // The card stays folded: a tap on the header line opens nothing.
                assert(!cards.some((c) => c.open), "the cards are folded");
            },
        },
        {
            content: "The name opens the player's file",
            trigger: `${YELLOW} [data-sc-injury-player-link]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The player page, Injuries tab, THAT injury unfolded",
            trigger: "details.o_sc_injury_item[open]",
            run() {
                const params = new URLSearchParams(window.location.search);
                assert(window.location.pathname === "/my/player", window.location.pathname);
                assert(params.get("tab") === "injuries", `tab=${params.get("tab")}`);
                const open = [...document.querySelectorAll("details.o_sc_injury_item[open]")];
                assert(open.length === 1, `one open card, got ${open.length}`);
                assert(open[0].id === `injury-${params.get("injury")}`, `${open[0].id} vs ${params.get("injury")}`);
                assert(open[0].textContent.includes("Synthetic sprain 1748"), "the yellow injury");
                assert(!document.querySelector("[data-sc-injury-player]"), "no player header on the player page");
            },
        },
        {
            content: "Back to the dashboard",
            trigger: "body",
            run() {
                window.location.href = "/my/home";
            },
            expectUnloadPage: true,
        },
        {
            content: "Open « Injuries to verify » again",
            trigger: `${LINE} > summary`,
            run() {
                window.__sc1748 = true;
                this.anchor.click();
            },
        },
        {
            content: "« Verify » on the yellow card",
            trigger: `${YELLOW} button[data-sc-injury-quick="verify"]`,
            run: "click",
        },
        {
            content: "The card leaves (header included), the count reads 1, no reload",
            trigger: `${LINE} [data-sc-todo-count]:contains("1")`,
            run() {
                const left = document.querySelectorAll(`${LINE} [data-sc-injury-player-link]`);
                assert(left.length === 1 && left[0].textContent.includes("Synth, Shared"), "the shared card stays");
                assert(window.__sc1748, "no reload");
            },
        },
    ],
});
