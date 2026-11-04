/*
 * Task 1622 — the activities page opened from the app-bar clock has a back
 * arrow to the page the user was on (tests/test_clock_back_tours_1622.py,
 * phone 360 px and laptop 1366 px). Language-independent triggers only; app
 * links are matched by suffix (website multilang prefixes them on the CI).
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

function activitiesSteps() {
    return [
        {
            content: "Activities from the clock: the back arrow shows",
            trigger: ".o_sc_app.o_sc_back_useful a.o_sc_back[data-sc-back]",
            run() {
                assert(window.location.pathname.endsWith("/my/activities"), window.location.href);
                assert(visible(".o_sc_back"), "clock: back arrow hidden");
                assert(!document.querySelector(".o_sc_appbar a.o_sc_logo"), "clock: logo instead of back");
                const href = document.querySelector("a.o_sc_back").getAttribute("href");
                assert(href.includes("/my/player?player_id="), `back href is not the player: ${href}`);
            },
        },
        {
            content: "Switch to the All tab",
            trigger: '.o_sc_app a[data-sc-tab="all"]',
            run: "click",
        },
        {
            content: "All tab: the arrow is still there; go back",
            trigger: '.o_sc_app section[data-sc-tab-panel="all"]:not([hidden])',
            run() {
                assert(window.location.search.includes("sc_from="), window.location.href);
                assert(visible(".o_sc_back"), "tab switch: back arrow gone");
                document.querySelector("a.o_sc_back").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "Back on the player page",
            trigger: ".o_sc_app .o_sc_appbar_title",
            run() {
                assert(window.location.pathname.endsWith("/my/player"), window.location.href);
                assert(window.location.search.includes("player_id="), window.location.href);
            },
        },
    ];
}

// Player page → clock → activities → back (history.back()) → player page.
tours.add("sc_1622_clock_back", {
    steps: () => [
        {
            content: "Player page: tap the app-bar clock",
            trigger: ".o_sc_appbar a[data-sc-activity-clock-bar]",
            run(helpers) {
                assert(window.location.pathname.endsWith("/my/player"), window.location.href);
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        ...activitiesSteps(),
    ],
});

// Deep link (no in-app history in this tab): back = the clock's origin href.
tours.add("sc_1622_clock_back_deep_link", {
    steps: () => activitiesSteps(),
});
