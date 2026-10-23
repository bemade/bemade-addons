/*
 * Task 1606 — the user menu (tests/test_app_shell_user_menu_tours_1606.py).
 *
 * sc_1606_menu_laptop (1366 px) and sc_1606_menu_phone (360 px) share the
 * keyboard / Escape / outside-tap steps, then open « Paramètres » and switch
 * the language (the user starts in French). Task 1638: both use the ONE
 * app-bar avatar (top right, at every width; no rail footer menu any more);
 * sc_1638_menu_placement checks its place and the popup's at 1024 / 1366 /
 * 1920 px.
 * sc_1606_sign_out: « Se déconnecter » logs out. Language-independent
 * triggers (ids, hrefs, html[lang]).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function menuSteps(where) {
    const toggle = `button[data-sc-user-menu-toggle][aria-controls="sc_user_menu_${where}"]`;
    const popup = `#sc_user_menu_${where}`;
    const settings = `${popup}:not([hidden]) a[role="menuitem"][href$="/my/app/settings"]`;
    const signOut = `${popup}:not([hidden]) a[role="menuitem"][href^="/web/session/logout"]`;
    return [
        {
            content: "The menu is closed",
            trigger: `${toggle}[aria-expanded="false"]`,
            run() {
                assert(document.querySelector(popup).hidden, "popup shown before a tap");
            },
        },
        {
            content: "Tap the trigger: the menu opens on « Paramètres »",
            trigger: toggle,
            run: "click",
        },
        {
            content: "Open, focus on the first item, name shown",
            trigger: `${toggle}[aria-expanded="true"]`,
            run() {
                const first = document.querySelector(settings);
                assert(first, "« Paramètres » not shown");
                assert(document.activeElement === first, "focus is not on « Paramètres »");
                assert(document.querySelector(`${popup} [data-sc-user-menu-head]`).textContent
                    .includes("PC TP"), "the user's name is missing");
                const rect = document.querySelector(popup).getBoundingClientRect();
                assert(rect.left >= 0 && rect.right <= window.innerWidth + 0.5,
                    `the menu overflows the screen: ${rect.left}-${rect.right} / ${window.innerWidth}`);
                assert(rect.top >= 0 && rect.bottom <= window.innerHeight + 0.5,
                    `the menu leaves the screen: ${rect.top}-${rect.bottom} / ${window.innerHeight}`);
            },
        },
        {
            content: "ArrowDown → « Se déconnecter »",
            trigger: settings,
            run: "press ArrowDown",
        },
        {
            trigger: signOut,
            run() {
                assert(document.activeElement === document.querySelector(signOut),
                    "ArrowDown did not reach « Se déconnecter »");
            },
        },
        {
            content: "ArrowDown wraps to « Paramètres »",
            trigger: signOut,
            run: "press ArrowDown",
        },
        {
            trigger: settings,
            run() {
                assert(document.activeElement === document.querySelector(settings),
                    "ArrowDown did not wrap");
            },
        },
        {
            content: "Escape closes and gives the focus back",
            trigger: settings,
            run: "press Escape",
        },
        {
            trigger: `${toggle}[aria-expanded="false"]`,
            run() {
                assert(document.querySelector(popup).hidden, "Escape left the menu open");
                assert(document.activeElement === document.querySelector(toggle),
                    "focus not back on the trigger");
            },
        },
        {
            content: "Reopen",
            trigger: toggle,
            run: "click",
        },
        {
            content: "A tap outside closes it",
            trigger: settings,
            run() {
                document.querySelector("main#sc_content").click();
            },
        },
        {
            trigger: `${toggle}[aria-expanded="false"]`,
            run() {
                assert(document.querySelector(popup).hidden, "an outside tap left it open");
            },
        },
        {
            content: "ArrowUp on the (focused) trigger opens on the last item",
            trigger: toggle,
            run() {
                const button = document.querySelector(toggle);
                button.focus();
                button.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
            },
        },
        {
            trigger: signOut,
            run() {
                assert(document.activeElement === document.querySelector(signOut),
                    "ArrowUp did not open on « Se déconnecter »");
            },
        },
        {
            content: "« Paramètres »",
            trigger: settings,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The settings page, in French, its menu item current",
            trigger: `html[lang="fr-CA"] main #sc_language button[value="fr_CA"][aria-pressed="true"]`,
            run() {
                assert(document.querySelector(`${popup} a[href$="/my/app/settings"][aria-current="page"]`),
                    "« Paramètres » not marked current");
                assert(document.querySelector('main a[href$="/my/account"]'), "« Mon compte » missing");
                assert(document.querySelector('main a[href$="/my/security"]'), "« Sécurité » missing");
                assert(!document.querySelector('main a[href$="/my/home?classic=1"]'), "classic portal link still shown");
            },
        },
        {
            content: "Switch to English",
            trigger: 'main #sc_language button[name="lang"][value="en_US"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on « Paramètres », now in English",
            trigger: 'html[lang="en-US"] main #sc_language button[value="en_US"][aria-pressed="true"]',
        },
    ];
}

/**
 * Task 1638: at laptop width the avatar is at the top right of the app bar
 * (last, after the clock and search), the rail holds no user menu, there is
 * one user menu in the DOM, and the popup drops down right-aligned under the
 * bubble, fully in view.
 */
function placementSteps() {
    const toggle = 'header.o_sc_appbar button[data-sc-user-menu-toggle][aria-controls="sc_user_menu_bar"]';
    return [
        {
            content: "1638: one user menu, at the top right of the app bar",
            trigger: toggle,
            run() {
                assert(document.querySelectorAll("[data-sc-user-menu-popup]").length === 1,
                    "more than one user menu in the DOM");
                assert(document.querySelectorAll("button[data-sc-user-menu-toggle]").length === 1,
                    "more than one user-menu trigger");
                assert(!document.querySelector(".o_sc_rail [data-sc-user-menu-toggle]"),
                    "the rail still holds a user menu");
                const rail = document.querySelector(".o_sc_rail");
                assert(rail && rail.getClientRects().length, "the rail should show at laptop width");
                const bar = document.querySelector("header.o_sc_appbar");
                const barRect = bar.getBoundingClientRect();
                const button = document.querySelector(toggle);
                const rect = button.getBoundingClientRect();
                assert(rect.width > 0 && rect.height >= 44, `the avatar is hidden or too small: ${rect.width}x${rect.height}`);
                assert(rect.top >= barRect.top && rect.bottom <= barRect.bottom + 0.5,
                    "the avatar is not inside the app bar");
                assert(rect.top < 100, `the avatar is not at the top: ${rect.top}`);
                assert(window.innerWidth - rect.right <= 48,
                    `the avatar is not at the right edge: ${rect.right} / ${window.innerWidth}`);
                const visible = [...bar.children].filter((el) => el.getClientRects().length);
                assert(visible[visible.length - 1].contains(button), "the avatar is not last in the bar");
                assert(bar.scrollWidth <= bar.clientWidth + 0.5,
                    `the app bar overflows: ${bar.scrollWidth} > ${bar.clientWidth}`);
                const title = document.querySelector(".o_sc_appbar_title").getBoundingClientRect();
                assert(title.width >= 120, `the title is squeezed to ${title.width}px`);
            },
        },
        {
            content: "Open it",
            trigger: toggle,
            run: "click",
        },
        {
            content: "1638: the popup drops down, right-aligned under the bubble, in view",
            trigger: `${toggle}[aria-expanded="true"]`,
            run() {
                const popup = document.querySelector("#sc_user_menu_bar");
                assert(!popup.hidden, "the popup did not open");
                const rect = popup.getBoundingClientRect();
                const button = document.querySelector(toggle).getBoundingClientRect();
                assert(rect.top >= button.bottom - 0.5, "the popup does not open downwards");
                assert(Math.abs(rect.right - button.right) <= 1,
                    `the popup is not right-aligned: ${rect.right} vs ${button.right}`);
                assert(rect.left >= 0 && rect.right <= window.innerWidth + 0.5,
                    `the menu overflows the screen: ${rect.left}-${rect.right} / ${window.innerWidth}`);
                assert(rect.bottom <= window.innerHeight + 0.5, "the menu leaves the screen");
                const head = popup.querySelector("[data-sc-user-menu-head]").textContent;
                assert(head.includes("PC TP"), "the name is missing from the menu head");
            },
        },
        {
            content: "Escape closes it",
            trigger: `#sc_user_menu_bar:not([hidden]) a[role="menuitem"]`,
            run: "press Escape",
        },
        {
            trigger: `${toggle}[aria-expanded="false"]`,
        },
    ];
}

tours.add("sc_1606_menu_laptop", { steps: () => [...placementSteps(), ...menuSteps("bar")] });
tours.add("sc_1638_menu_placement", { steps: () => placementSteps() });
tours.add("sc_1606_menu_phone", {
    steps: () => [
        {
            content: "360 px: the avatar fits next to the clock and search, the title keeps room",
            trigger: 'header.o_sc_appbar button[aria-controls="sc_user_menu_bar"]',
            run() {
                const bar = document.querySelector("header.o_sc_appbar");
                assert(bar.scrollWidth <= bar.clientWidth + 0.5,
                    `the app bar overflows: ${bar.scrollWidth} > ${bar.clientWidth}`);
                assert(document.documentElement.scrollWidth <= window.innerWidth + 0.5,
                    "the page scrolls sideways");
                const title = document.querySelector(".o_sc_appbar_title").getBoundingClientRect();
                assert(title.width >= 80, `the title is squeezed to ${title.width}px`);
                const avatar = document.querySelector('button[aria-controls="sc_user_menu_bar"]')
                    .getBoundingClientRect();
                assert(avatar.right <= window.innerWidth, "the avatar is off screen");
                assert(avatar.height >= 44, `tap target ${avatar.height}px tall`);
                assert(document.querySelectorAll("[data-sc-user-menu-popup]").length === 1,
                    "more than one user menu in the DOM");
            },
        },
        ...menuSteps("bar"),
    ],
});

tours.add("sc_1606_sign_out", {
    steps: () => [
        {
            trigger: "button[data-sc-user-menu-toggle]",
            run: "click",
        },
        {
            content: "« Se déconnecter »",
            trigger: '[data-sc-user-menu-popup]:not([hidden]) a[role="menuitem"][href^="/web/session/logout"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Signed out: the login page",
            trigger: 'form.oe_login_form, form[action="/web/login"], .oe_website_login_container, body:not(:has(.o_sc_app))',
        },
    ],
});
