/*
 * Task 5381 (P4c2) — pk_tabs: the segmented page tabs switch their panels
 * in place and keep ?tab= in the address; a #hash (or one of a tab's
 * aliases) opens its tab on load. Synthetic fixtures only.
 */
import { afterEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { browser } from "@web/core/browser/browser";

import { activateTab, bootTabs } from "@bemade_portal_kit/js/pk_tabs";

function mount() {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">
        <nav data-pk-tabs="1">
            <a href="/pk/t/page?tab=overview" class="pk_t_overview" data-pk-tab="overview" aria-selected="true">Overview</a>
            <a href="/pk/t/page?tab=notes" class="pk_t_notes" data-pk-tab="notes" data-pk-tab-aliases="injury-notes patient-notes"
               aria-selected="false">Notes</a>
            <a href="/pk/t/page?tab=away" class="pk_t_away" data-pk-tab="away">Away</a>
        </nav>
        <section data-pk-tab-panel="overview">o</section>
        <section data-pk-tab-panel="notes" hidden="">n</section>
    </div>`;
    return getFixture().querySelector(".o_pk_app");
}

function shown(root) {
    return [...root.querySelectorAll("[data-pk-tab-panel]")].filter((p) => !p.hidden).map((p) => p.dataset.pkTabPanel);
}

describe("pk_tabs", () => {
    afterEach(() => {
        browser.history.replaceState(null, "", "/pk/t/page");
    });

    test("a tab switches its panel in place and keeps ?tab= in the address", () => {
        const root = mount();
        root.querySelector(".pk_t_notes").click();
        expect(shown(root)).toEqual(["notes"]);
        expect(root.querySelector(".pk_t_notes").getAttribute("aria-selected")).toBe("true");
        expect(root.querySelector(".pk_t_notes").getAttribute("aria-pressed")).toBe("true");
        expect(root.querySelector(".pk_t_overview").getAttribute("aria-selected")).toBe("false");
        expect(new URL(browser.location.href).searchParams.get("tab")).toBe("notes");
    });

    test("a tab without a panel on the page stays a link", () => {
        const root = mount();
        const away = root.querySelector(".pk_t_away");
        let prevented = null;
        const spy = (ev) => {
            prevented = ev.defaultPrevented;
            ev.preventDefault(); // the test page never navigates
        };
        document.addEventListener("click", spy);
        away.click();
        document.removeEventListener("click", spy);
        expect(prevented).toBe(false);
        expect(shown(root)).toEqual(["overview"]);
    });

    test("activateTab by key or alias", () => {
        const root = mount();
        activateTab(root, "patient-notes");
        expect(shown(root)).toEqual(["notes"]);
        activateTab(root, "overview");
        expect(shown(root)).toEqual(["overview"]);
        activateTab(root, "nothing");
        expect(shown(root)).toEqual(["overview"]);
    });

    test("a #hash opens its tab on load", () => {
        const root = mount();
        browser.history.replaceState(null, "", "/pk/t/page#injury-notes");
        bootTabs();
        expect(shown(root)).toEqual(["notes"]);
    });

    test("the old markers are not read", () => {
        getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">
            <nav data-sc-tabs="1"><a href="/pk/t/page?tab=b" class="pk_t_b" data-sc-tab="b">B</a></nav>
            <section data-sc-tab-panel="a">a</section><section data-sc-tab-panel="b" hidden="">b</section></div>`;
        const spy = (ev) => ev.preventDefault();
        document.addEventListener("click", spy);
        getFixture().querySelector(".pk_t_b").click();
        document.removeEventListener("click", spy);
        expect(getFixture().querySelector('[data-sc-tab-panel="b"]').hidden).toBe(true);
    });
});
