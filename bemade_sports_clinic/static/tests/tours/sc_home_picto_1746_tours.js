/*
 * Task 1746 — phone: the Fit Crew picto after the back chevron goes home
 * (tests/test_home_picto_1746.py, phone 390 px and laptop 1366 px).
 * Language-independent triggers only (classes, URLs).
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

function rect(selector) {
    const el = document.querySelector(selector);
    return el ? el.getBoundingClientRect() : null;
}

tours.add("sc_1746_phone_home_picto", {
    steps: () => [
        {
            content: "Player page (sub-page): back chevron, then the home picto, then the title",
            trigger: '.o_sc_app[data-sc-top="0"] .o_sc_appbar a.o_sc_home_picto[href="/my/home"]',
            run() {
                assert(visible(".o_sc_appbar a.o_sc_back"), "phone: back chevron hidden");
                assert(visible(".o_sc_appbar a.o_sc_home_picto"), "phone: home picto hidden");
                assert(!document.querySelector(".o_sc_appbar a.o_sc_logo"), "phone: logo instead of back");
                const back = rect(".o_sc_appbar a.o_sc_back");
                const picto = rect(".o_sc_appbar a.o_sc_home_picto");
                const title = rect(".o_sc_appbar_title");
                assert(picto.left >= back.right - 0.5, "picto not after the chevron");
                assert(title.left >= picto.right - 0.5, "title not after the picto");
                assert(picto.width >= 44 && picto.height >= 44,
                    `picto tap target too small: ${picto.width}x${picto.height}`);
                // The title truncates inside the bar, the bar does not overflow.
                const text = document.querySelector(".o_sc_appbar_title_text");
                assert(getComputedStyle(text).textOverflow === "ellipsis", "title does not truncate");
                const bar = document.querySelector(".o_sc_appbar");
                assert(bar.scrollWidth <= bar.clientWidth + 1, "app bar overflows");
                assert(document.documentElement.scrollWidth <= window.innerWidth + 1, "page scrolls sideways");
                // The right-hand icons keep their place: the avatar is still the
                // last, flush with the bar's right padding.
                const me = rect(".o_sc_appbar .o_sc_appbar_me");
                assert(me && me.right > bar.getBoundingClientRect().right - 24, "avatar moved");
                window.sessionStorage.setItem("sc1746_me_right", String(me.right));
                document.querySelector(".o_sc_appbar a.o_sc_home_picto").click();
            },
            expectUnloadPage: true,
        },
        {
            content: "The picto opened the dashboard (top level: logo, no back, no picto)",
            trigger: '.o_sc_app[data-sc-top="1"] .o_sc_appbar a.o_sc_logo',
            run() {
                assert(window.location.pathname === "/my/home", window.location.href);
                assert(!document.querySelector(".o_sc_appbar a.o_sc_home_picto"), "top level: picto shows");
                assert(!document.querySelector(".o_sc_appbar a.o_sc_back"), "top level: back shows");
                const before = Number(window.sessionStorage.getItem("sc1746_me_right"));
                const me = rect(".o_sc_appbar .o_sc_appbar_me");
                assert(Math.abs(me.right - before) < 1, `right-hand icons moved: ${before} -> ${me.right}`);
            },
        },
    ],
});

tours.add("sc_1746_laptop_no_picto", {
    steps: () => [
        {
            content: "Laptop sub-page: back chevron + trail, the picto hidden (the rail's brand goes home)",
            trigger: '.o_sc_app[data-sc-top="0"] .o_sc_appbar a.o_sc_back',
            run() {
                assert(visible(".o_sc_appbar a.o_sc_back"), "laptop: back chevron hidden");
                assert(visible("nav.o_sc_crumbs"), "laptop: trail hidden");
                assert(document.querySelector(".o_sc_appbar a.o_sc_home_picto"), "picto not rendered");
                assert(!visible(".o_sc_appbar a.o_sc_home_picto"), "laptop: picto shows");
                assert(visible("a.o_sc_rail_brand[href='/my/home']"), "laptop: rail brand hidden");
            },
        },
    ],
});
