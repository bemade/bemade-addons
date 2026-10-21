/*
 * Task 1634 — quick-change Match / Practice pills on the player cards
 * (tests/test_card_status_pills_1634.py). Language-independent triggers,
 * synthetic fixtures; the team page opens on its « players » tab (the
 * dashboard panel shares the DOM).
 *
 * - sc_1634_card_pills (therapist; the player « Pat One » is on the roster
 *   AND on the dashboard's « Recent changes », starts « yes:yes »): Match ->
 *   no on the ROSTER card: the card recolours in place (pill red, dot no
 *   longer green), the page did not navigate, the same player's dashboard
 *   card updated too, ONE fragment fetch for the pick, the roster order is
 *   unchanged (it re-sorts on the next visit only).
 * - sc_1634_card_pills_coach: coloured read-only pills, no button.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const ROSTER = '[data-sc-section="team.roster"]';
const DASH = '[data-sc-section="team.recent_changes"]';
const TARGET = `${ROSTER} .o_sc_player_row[data-sc-tour-1634]`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function rosterOrder() {
    return [...document.querySelectorAll(`${ROSTER} .o_sc_player_row`)]
        .map((row) => row.dataset.scPlayerId)
        .join(",");
}

function headerOf(init) {
    const headers = (init && init.headers) || {};
    return headers instanceof Headers ? headers.get("X-Sc-Fragments") : headers["X-Sc-Fragments"];
}

tours.add("sc_1634_card_pills", {
    steps: () => [
        {
            content: "Roster cards carry the compact dropdown pills",
            trigger: `${ROSTER} .o_sc_pill_select_compact button.o_sc_pill_select`,
            run() {
                const dash = document.querySelector(`${DASH} .o_sc_player_row`);
                assert(dash, "the player is not on the dashboard");
                const id = dash.dataset.scPlayerId;
                const row = document.querySelector(`${ROSTER} .o_sc_player_row[data-sc-player-id="${id}"]`);
                assert(row, "the dashboard player is not on the roster");
                row.setAttribute("data-sc-tour-1634", "1");
                window.__sc1634 = {
                    id,
                    url: window.location.href,
                    order: rosterOrder(),
                    fragmentFetches: 0,
                };
                assert(
                    dash.querySelector('[data-sc-pill-key="match"] button.o_sc_chip_green'),
                    "the dashboard card's Match pill is not green"
                );
                const fetchOrig = window.fetch;
                window.fetch = function (url, init) {
                    if (headerOf(init)) {
                        window.__sc1634.fragmentFetches += 1;
                    }
                    return fetchOrig.apply(this, arguments);
                };
            },
        },
        {
            content: "Open the roster card's Match pill (not the player page)",
            trigger: `${TARGET} [data-sc-pill-key="match"]:not([aria-busy]) button.o_sc_pill_select.o_sc_chip_green`,
            run: "click",
        },
        {
            content: "The menu is open; « Practice » choices untouched",
            trigger: `${TARGET} [data-sc-pill-key="match"] button.o_sc_pill_select[aria-expanded="true"]`,
            run() {
                assert(window.location.href === window.__sc1634.url, "the tap navigated");
            },
        },
        {
            content: "Pick « No »",
            trigger: `${TARGET} [data-sc-pill-key="match"] [role="menuitemradio"][data-sc-pill-value="no"]:not([aria-disabled])`,
            run: "click",
        },
        {
            content: "The roster card recoloured in place",
            trigger: `${TARGET} [data-sc-pill-key="match"]:not([aria-busy]) button.o_sc_pill_select.o_sc_chip_red`,
            run() {
                const state = window.__sc1634;
                assert(state, "the page reloaded");
                assert(window.location.href === state.url, "the page navigated");
                assert(
                    document.querySelector(`${TARGET} [data-sc-pill-key="practice"] button.o_sc_chip_green`),
                    "the Practice pill changed"
                );
                const dot = document.querySelector(`${TARGET} .o_sc_link_row .o_sc_dot`);
                assert(dot && !dot.classList.contains("o_sc_tone_green"), "the card's dot did not recolour");
                const dash = document.querySelector(
                    `${DASH} .o_sc_player_row[data-sc-player-id="${state.id}"]`
                );
                assert(
                    dash && dash.querySelector('[data-sc-pill-key="match"] button.o_sc_chip_red'),
                    "the same player's dashboard card did not update"
                );
                assert(rosterOrder() === state.order, "the roster re-sorted");
            },
        },
        {
            content: "One fragment fetch for the pick",
            trigger: `${TARGET} [data-sc-pill-key="match"] button.o_sc_chip_red`,
            async run() {
                // Anything still queued would fire within the debounce window.
                await new Promise((resolve) => setTimeout(resolve, 700));
                const count = window.__sc1634.fragmentFetches;
                assert(count === 1, `${count} fragment fetches for one pick`);
                assert(rosterOrder() === window.__sc1634.order, "the roster re-sorted");
            },
        },
    ],
});

tours.add("sc_1634_card_pills_coach", {
    steps: () => [
        {
            content: "Coach: coloured read-only pills, no button, no menu",
            trigger: `${ROSTER} .o_sc_row_status .o_sc_status_pill`,
            run() {
                assert(!document.querySelector(".o_sc_row_status button"), "a button on a coach's card");
                assert(!document.querySelector("[data-sc-pill-select]"), "a dropdown for a coach");
                assert(document.querySelector(`${DASH} .o_sc_row_status .o_sc_status_pill`), "no dashboard pills");
            },
        },
    ],
});
