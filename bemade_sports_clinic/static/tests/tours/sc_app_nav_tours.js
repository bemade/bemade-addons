/*
 * Task 1579 — the app shell's back / breadcrumb engine in a browser
 * (tests/test_app_shell_tours_1579.py, phone 390 px and laptop 1366 px).
 * Language-independent triggers only (data attributes, URLs).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(selector) {
    const el = document.querySelector(selector);
    return Boolean(el && el.offsetParent);
}

// history.back() may restore a page from the back/forward cache: its old JS
// context (and this tour's step timers) would resume instead of a fresh tour
// run. A page we will come back to reloads itself when restored that way.
function reloadIfRestored() {
    window.addEventListener("pageshow", (ev) => {
        if (ev.persisted) {
            window.location.reload();
        }
    });
}

// Phone: back chevron + context line, no trail.
function phoneChrome() {
    assert(visible(".o_sc_back"), "phone: no back chevron");
    assert(!visible("nav.o_sc_crumbs"), "phone: the crumb trail shows");
}

// ------------------------------------------- back = where you came from
tours.add("sc_1579_back_came_from", {
    steps: () => [
        {
            content: "Filtered players list (top level: logo, no back)",
            trigger: '.o_sc_app[data-sc-top="1"] [data-sc-section="players.list"] [data-sc-player-id] a.o_sc_link_row_main:contains("One")',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Player page: back's href is the declared parent (the players list)",
            trigger: '.o_sc_app[data-sc-top="0"] a.o_sc_back[href$="/my/players"]',
            run() {
                phoneChrome();
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back returned to the FILTERED list we came from (history), not the href",
            trigger: '.o_sc_app[data-sc-top="1"] [data-sc-section="players.list"]',
            run() {
                assert(window.location.pathname === "/my/players", window.location.href);
                assert(
                    window.location.search.includes("first_name=Pat"),
                    `back did not return to the filtered list: ${window.location.href}`
                );
            },
        },
    ],
});

// ------------------------------------- deep link: back = declared parent
tours.add("sc_1579_deep_link_fallback", {
    steps: () => [
        {
            content: "Deep link to a player opened from a team: back goes to the team's players",
            trigger: '.o_sc_app a.o_sc_back[href*="/my/team?team_id="]',
            run() {
                phoneChrome();
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Landed on the team page, players tab",
            trigger: '.o_sc_app section[data-sc-tab-panel="players"]:not([hidden])',
            run() {
                assert(window.location.pathname === "/my/team", window.location.href);
                assert(window.location.search.includes("tab=players"), window.location.href);
            },
        },
    ],
});

// ------------------------------- team → digest list → snapshot, and back
tours.add("sc_1579_digest_chain", {
    steps: () => [
        {
            content: "Team page: « History » goes straight to the digest list",
            trigger: 'a[data-sc-action="team.digest_history"]',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            // Task 1614: a date expands in place; its « Open this day » link
            // leads to the day's page.
            content: "Digest list: expand a date",
            trigger: '[data-sc-section="digest.history"] details[data-sc-digest-row] > summary',
            run: "click",
        },
        {
            content: "Digest list: open the day's page",
            trigger: '[data-sc-section="digest.history"] details[open] a[data-sc-digest-id]',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Snapshot: back",
            trigger: '[data-sc-section="digest.body"]',
            run() {
                phoneChrome();
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back on the digest list; back again",
            trigger: '[data-sc-section="digest.history"]',
            run() {
                assert(window.location.pathname.endsWith("/digest-history"), window.location.href);
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back on the team page",
            trigger: 'a[data-sc-action="team.digest_history"]',
            run() {
                assert(window.location.pathname === "/my/team", window.location.href);
            },
        },
    ],
});

// A deep link to a snapshot: back steps up the declared chain (snapshot →
// list → team page), never down again.
tours.add("sc_1579_digest_deep_link", {
    steps: () => [
        {
            content: "Snapshot opened directly: back",
            trigger: '[data-sc-section="digest.body"]',
            run() {
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "The digest list (the declared parent); back again",
            trigger: '[data-sc-section="digest.history"]',
            run() {
                assert(window.location.pathname.endsWith("/digest-history"), window.location.href);
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "The team page, not the snapshot again",
            trigger: 'a[data-sc-action="team.digest_history"]',
            run() {
                assert(window.location.pathname === "/my/team", window.location.href);
            },
        },
    ],
});

// ------------------------------------------------------ laptop: the trail
tours.add("sc_1579_laptop_trail", {
    steps: () => [
        {
            content: "Laptop: the full trail, the current page last",
            trigger: 'nav.o_sc_crumbs[aria-label] ol li[aria-current="page"]',
            run() {
                // Task 1618 (owner review 2026-10-18): the chevron always
                // shows next to the trail on a laptop sub-page.
                assert(visible(".o_sc_back"), "laptop: back chevron hidden");
                assert(!visible(".o_sc_appbar_context"), "laptop: context line visible");
                const links = [...document.querySelectorAll("nav.o_sc_crumbs ol li a")].map(
                    (a) => a.getAttribute("href")
                );
                assert(links[0] === "/my/teams", `trail starts with ${links[0]}`);
                assert(links.length === 2, `trail: ${links.join(" › ")}`);
            },
        },
        {
            content: "A crumb goes up to the team",
            trigger: 'nav.o_sc_crumbs ol li a[href*="/my/team?team_id="]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Team page: its trail is « Teams »",
            trigger: 'nav.o_sc_crumbs ol li a[href$="/my/teams"]',
            run() {
                assert(window.location.pathname === "/my/team", window.location.href);
            },
        },
    ],
});
