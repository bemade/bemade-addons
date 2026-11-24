/*
 * Task 5198 (P3a) — pk_focus: a field marked data-pk-focus-skip (a picker's
 * search box) never takes the focus. Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { firstTextField } from "@bemade_portal_kit/js/pk_focus";

describe("pk_focus", () => {
    test("the first visible text field is picked, never a select", () => {
        getFixture().innerHTML = `
            <form>
                <select name="kind"><option>a</option></select>
                <input type="text" name="title"/>
            </form>`;
        expect(firstTextField(getFixture()).name).toBe("title");
    });

    test("a field with data-pk-focus-skip is skipped", () => {
        getFixture().innerHTML = `
            <form>
                <input type="text" name="search" data-pk-focus-skip="1"/>
                <textarea name="body"></textarea>
            </form>`;
        expect(firstTextField(getFixture()).name).toBe("body");
    });

    test("the hook is generic: no consumer class is skipped by itself", () => {
        getFixture().innerHTML = `
            <form>
                <input type="text" name="search" class="o_pk_picker_input"/>
                <textarea name="body"></textarea>
            </form>`;
        expect(firstTextField(getFixture()).name).toBe("search");
    });

    test("only skipped fields: nothing", () => {
        getFixture().innerHTML = '<form><input type="text" data-pk-focus-skip="1"/></form>';
        expect(firstTextField(getFixture())).toBe(null);
    });
});
