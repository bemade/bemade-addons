/*
 * Task 5344 (P3b1) — pk_live_count: a live chip's tone classes are the kit's
 * o_pk_chip_<tone>, and the tone formerly named « mauve » is « secondary ».
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { applyCount } from "@bemade_portal_kit/js/pk_live_count";

function chip(attrs) {
    getFixture().innerHTML = `<div class="o_pk_app"><span class="o_pk_chip" ${attrs}>0</span></div>`;
    return getFixture().querySelector(".o_pk_chip");
}

describe("pk_live_count", () => {
    test("the tone follows the count with o_pk_chip_<tone>", () => {
        const el = chip('data-pk-live-tone-on="secondary" data-pk-live-tone-off="ghost"');
        applyCount(el, 3);
        expect(el.textContent).toBe("3");
        expect(el.classList.contains("o_pk_chip_secondary")).toBe(true);
        expect(el.classList.contains("o_pk_chip_ghost")).toBe(false);
        applyCount(el, 0);
        expect(el.classList.contains("o_pk_chip_secondary")).toBe(false);
        expect(el.classList.contains("o_pk_chip_ghost")).toBe(true);
        expect(el.className).not.toMatch(/o_sc_/);
    });

    test("data-pk-live-hide-zero hides the chip at 0", () => {
        const el = chip('data-pk-live-hide-zero="1"');
        applyCount(el, 0);
        expect(el.hidden).toBe(true);
        applyCount(el, 2);
        expect(el.hidden).toBe(false);
        expect(el.textContent).toBe("2");
    });
});
