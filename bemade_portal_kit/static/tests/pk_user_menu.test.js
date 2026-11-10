/*
 * Task 5198 (P3a) — pk_user_menu: the data-pk-* menu attributes, and the
 * data-pk-keep-in-view hook (a popup kept inside the content area).
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { close, keepsInView, open } from "@bemade_portal_kit/js/pk_user_menu";

function mount(popupAttrs = "") {
    getFixture().innerHTML = `
        <div class="o_sc_app">
            <button type="button" data-pk-menu-toggle="1" aria-controls="pk_test_popup" aria-expanded="false">Menu</button>
            <div id="pk_test_popup" data-pk-menu-popup="1" ${popupAttrs} hidden="">
                <button type="button" role="menuitem">One</button>
                <button type="button" role="menuitem">Two</button>
            </div>
        </div>`;
    return getFixture().querySelector("[data-pk-menu-toggle]");
}

describe("pk_user_menu", () => {
    test("open / close follow the data-pk-menu-* pair", () => {
        const toggle = mount();
        const popup = getFixture().querySelector("#pk_test_popup");
        open(toggle);
        expect(popup.hidden).toBe(false);
        expect(toggle.getAttribute("aria-expanded")).toBe("true");
        close(toggle);
        expect(popup.hidden).toBe(true);
        expect(toggle.getAttribute("aria-expanded")).toBe("false");
    });

    test("data-pk-keep-in-view marks a popup kept inside the content area", () => {
        mount("data-pk-keep-in-view=\"1\"");
        expect(keepsInView(getFixture().querySelector("#pk_test_popup"))).toBe(true);
    });

    test("the hook is generic: no consumer class keeps a popup in view", () => {
        mount('class="o_sc_pill_popup"');
        expect(keepsInView(getFixture().querySelector("#pk_test_popup"))).toBe(false);
    });
});
