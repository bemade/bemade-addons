/*
 * Task 5202 (kit P7) — pk_dashboard_anchor: a dashboard fold-out keeps its
 * header in place. Synthetic fixtures only.
 */
import { afterEach, describe, expect, getFixture, test } from "@odoo/hoot";

import {
    pkDashAnchorOf,
    pkDashHeld,
    pkDashHoldAnchor,
    pkDashRelease,
} from "@bemade_portal_kit_dashboard/js/pk_dashboard_anchor";

afterEach(() => pkDashRelease());

function page() {
    getFixture().innerHTML = `
        <div class="o_pk_app">
            <div data-pk-dashboard="1">
                <details><summary class="s1"><span class="in">Open</span></summary><p>Body</p></details>
                <div class="row"><button type="button" data-pk-row-expand="1" class="x">Details</button></div>
                <p class="plain">Text</p>
            </div>
            <details class="outside"><summary class="s2">Elsewhere</summary></details>
        </div>`;
    return getFixture();
}

describe("pk_dashboard_anchor", () => {
    test("the anchor of a click: its <details> summary or row expander, nothing else", () => {
        const root = page();
        expect(pkDashAnchorOf(root.querySelector(".in"))).toBe(root.querySelector(".s1"));
        expect(pkDashAnchorOf(root.querySelector(".x"))).toBe(root.querySelector(".x"));
        expect(pkDashAnchorOf(root.querySelector(".plain"))).toBe(null);
        expect(pkDashAnchorOf(null)).toBe(null);
    });

    test("only a dashboard anchor is held", () => {
        const root = page();
        expect(pkDashHoldAnchor(root.querySelector(".s2"))).toBe(false);
        expect(pkDashHeld()).toBe(null);
        expect(pkDashHoldAnchor(root.querySelector(".s1"))).toBe(true);
        expect(pkDashHeld()).toBe(root.querySelector(".s1"));
        pkDashRelease();
        expect(pkDashHeld()).toBe(null);
    });

    test("a click on a dashboard toggle holds it; outside the dashboard it does not", () => {
        const root = page();
        root.querySelector(".s2").click();
        expect(pkDashHeld()).toBe(null);
        root.querySelector(".in").click();
        expect(pkDashHeld()).toBe(root.querySelector(".s1"));
    });

    test("a user scroll (wheel) ends the hold", () => {
        const root = page();
        pkDashHoldAnchor(root.querySelector(".x"));
        window.dispatchEvent(new Event("wheel"));
        expect(pkDashHeld()).toBe(null);
    });
});
