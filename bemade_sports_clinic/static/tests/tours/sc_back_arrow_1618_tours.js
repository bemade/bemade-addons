/*
 * Task 1618 — laptop: the back chevron shows next to the breadcrumb on EVERY
 * sub-page (owner review 2026-10-18; tests/test_back_arrow_tours_1618.py,
 * laptop 1366 px and phone 390 px). Language-independent triggers only.
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

// A page we come back to through history.back() reloads itself when it is
// restored from the back/forward cache (a fresh tour run, see 1579 tours).
function reloadIfRestored() {
    window.addEventListener("pageshow", (ev) => {
        if (ev.persisted) {
            window.location.reload();
        }
    });
}

// --------------------------------- laptop: drill-down = arrow AND trail too
tours.add("sc_1618_laptop_drill_down", {
    steps: () => [
        {
            content: "Team page (players tab): open a player of the roster",
            trigger: '.o_sc_app section[data-sc-tab-panel="players"] a.o_sc_link_row_main[href*="/my/player?player_id="]',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Player page after a drill-down: breadcrumb AND back arrow",
            trigger: 'nav.o_sc_crumbs ol li[aria-current="page"]',
            run() {
                assert(window.location.pathname === "/my/player", window.location.href);
                assert(visible("nav.o_sc_crumbs"), "laptop: no trail");
                assert(visible(".o_sc_back"), "drill-down: back arrow hidden on a laptop");
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back on the team's players tab",
            trigger: '.o_sc_app section[data-sc-tab-panel="players"]',
            run() {
                assert(window.location.pathname === "/my/team", window.location.href);
            },
        },
    ],
});

// ------------------------------- laptop: sideways arrival = arrow + trail
tours.add("sc_1618_laptop_sideways", {
    steps: () => [
        {
            content: "Activities list (with its filter): open the activity",
            trigger: '.o_sc_app [data-sc-activity-row] a.o_sc_link_row_main[href^="/my/activity/"]',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Activity page (parent = the player): arrow AND trail",
            trigger: ".o_sc_app.o_sc_back_useful a.o_sc_back[data-sc-back]",
            run() {
                assert(window.location.pathname.startsWith("/my/activity/"), window.location.href);
                assert(visible("nav.o_sc_crumbs"), "laptop: no trail");
                assert(visible(".o_sc_back"), "sideways: back arrow hidden on a laptop");
                const href = document.querySelector("a.o_sc_back").getAttribute("href");
                assert(href.startsWith("/my/player?"), `back href is not the player: ${href}`);
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back on the activities list we came from, its filter kept",
            trigger: ".o_sc_app [data-sc-activity-row]",
            run() {
                assert(window.location.pathname === "/my/activities", window.location.href);
                assert(window.location.search.includes("sc_clock=1"), window.location.href);
            },
        },
    ],
});

// ------------------------------------------ laptop: installed app = arrow
tours.add("sc_1618_laptop_standalone", {
    steps: () => [
        {
            content: "Deep link in a browser tab: arrow (to the parent) + trail",
            trigger: 'nav.o_sc_crumbs ol li[aria-current="page"]',
            run() {
                assert(visible(".o_sc_back"), "browser tab deep link: back arrow hidden");
                // Emulate the installed app (display-mode: standalone).
                const original = window.matchMedia.bind(window);
                window.matchMedia = (query) =>
                    query.includes("display-mode: standalone")
                        ? { matches: true, media: query, addEventListener() {}, removeEventListener() {} }
                        : original(query);
                document.dispatchEvent(new CustomEvent("sc:nav-sync"));
            },
        },
        {
            content: "Installed: the arrow shows next to the trail",
            trigger: ".o_sc_app.o_sc_back_useful a.o_sc_back",
            run() {
                assert(visible(".o_sc_back"), "standalone: back arrow hidden");
                assert(visible("nav.o_sc_crumbs"), "standalone: trail hidden");
            },
        },
    ],
});

// ---------------------------------------------- phone: unchanged (arrow)
tours.add("sc_1618_phone_unchanged", {
    steps: () => [
        {
            content: "Team page: open a player of the roster",
            trigger: '.o_sc_app section[data-sc-tab-panel="players"] a.o_sc_link_row_main[href*="/my/player?player_id="]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Phone: the back chevron after a drill-down, no trail",
            trigger: ".o_sc_app a.o_sc_back[data-sc-back]",
            run() {
                assert(visible(".o_sc_back"), "phone: back chevron hidden");
                assert(!visible("nav.o_sc_crumbs"), "phone: trail visible");
            },
        },
    ],
});
