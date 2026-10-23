/*
 * Task 1606 — the user menu (tests/test_app_shell_user_menu_tours_1606.py).
 *
 * sc_1606_menu_laptop (1366 px, rail footer) and sc_1606_menu_phone (360 px,
 * app-bar avatar) share the keyboard / Escape / outside-tap steps, then open
 * « Paramètres » and switch the language (the user starts in French).
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

tours.add("sc_1606_menu_laptop", { steps: () => menuSteps("rail") });
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
                assert(!document.querySelector(".o_sc_rail_me").getClientRects().length,
                    "the rail footer shows on a phone");
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
