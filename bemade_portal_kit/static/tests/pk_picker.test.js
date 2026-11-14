/*
 * Task 5200 (P5) — pk_picker: the type-to-filter picker moved to the kit,
 * with DECLARATIVE narrowing (data-pk-picker-narrow="<parent key>:<meta
 * key>", data-pk-picker-hint), the kept empty option (data-pk-picker-empty)
 * and the narrowing scope (data-pk-picker-scope). Synthetic fixtures only.
 */
import { beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";

import { applyNarrowing, enhanceAll } from "@bemade_portal_kit/js/pk_picker";
import { pkFold, pkNameMatches, pkWords } from "@bemade_portal_kit/js/pk_match";

const HINT = "Cleared: not in the chosen group.";

function scope(id) {
    return `<div data-pk-picker-scope="1" class="pk_t_scope_${id}">
        <select data-pk-picker="1" data-pk-picker-key="group" class="pk_t_group">
            <option value="">—</option>
            <option value="1">Group one</option>
            <option value="2">Group two</option>
        </select>
        <select data-pk-picker="1" data-pk-picker-key="member" class="pk_t_member"
                data-pk-picker-narrow="group:groups" data-pk-picker-hint="${HINT}">
            <option value="">—</option>
            <option value="10" data-pk-meta-groups="1">Anne Leclerc</option>
            <option value="11" data-pk-meta-groups="2">Bob Dubois</option>
            <option value="12" data-pk-meta-groups="1,2">Élodie Roy</option>
        </select>
    </div>`;
}

function mount(inner) {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">${inner}</div>`;
    enhanceAll(getFixture());
    return getFixture();
}

function offered(select) {
    return [...select.options].filter((o) => o.value && !o.dataset.pkPickerOut).map((o) => o.value);
}

function pick(select, value) {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("pk_picker", () => {
    beforeEach(() => patchTranslations());

    test("pk_match: folded words, every typed word starts a word", () => {
        expect(pkFold("Élodie")).toBe("elodie");
        expect(pkWords("Roy, Élodie-Anne")).toEqual(["roy", "elodie", "anne"]);
        expect(pkNameMatches(["el", "ro"], "Roy, Élodie")).toBe(true);
        expect(pkNameMatches(["lod"], "Roy, Élodie")).toBe(false);
    });

    test("a select gets its picker box; its own markers are pk names", () => {
        const root = mount(scope("a"));
        const select = root.querySelector(".pk_t_member");
        expect(select.dataset.pkPickerReady).toBe("1");
        const picker = select.nextElementSibling;
        expect(picker.classList.contains("o_pk_picker")).toBe(true);
        expect(picker.id.startsWith("pk_picker_")).toBe(true);
    });

    test("the parent narrows the child it declares; a value that no longer fits is cleared with the hint", () => {
        const root = mount(scope("a"));
        const group = root.querySelector(".pk_t_group");
        const member = root.querySelector(".pk_t_member");
        pick(member, "11");
        pick(group, "1");
        expect(offered(member)).toEqual(["10", "12"]);
        expect(member.value).toBe("");
        const note = member.nextElementSibling.querySelector(".o_pk_picker_cleared");
        expect(note.hidden).toBe(false);
        expect(note.textContent).toBe(HINT);
        // A value that fits stays, without a hint.
        pick(member, "12");
        pick(group, "2");
        expect(member.value).toBe("12");
        expect(note.hidden).toBe(true);
        // Clearing the parent widens again.
        pick(group, "");
        expect(offered(member)).toEqual(["10", "11", "12"]);
    });

    test("narrowing stays inside its scope", () => {
        const root = mount(scope("a") + scope("b"));
        pick(root.querySelector(".pk_t_scope_a .pk_t_group"), "2");
        expect(offered(root.querySelector(".pk_t_scope_a .pk_t_member"))).toEqual(["11", "12"]);
        expect(offered(root.querySelector(".pk_t_scope_b .pk_t_member"))).toEqual(["10", "11", "12"]);
    });

    test("a select without a narrow declaration is never narrowed", () => {
        const root = mount(scope("a").replace(' data-pk-picker-narrow="group:groups"', ""));
        const group = root.querySelector(".pk_t_group");
        group.value = "1";
        applyNarrowing(group);
        expect(offered(root.querySelector(".pk_t_member"))).toEqual(["10", "11", "12"]);
    });

    test("data-pk-picker-empty keeps the empty option as a real choice", () => {
        const root = mount(`<select data-pk-picker="1" data-pk-picker-key="place" data-pk-picker-empty="1" class="pk_t_place">
            <option value="">To be decided</option>
            <option value="1">Hall</option>
        </select>`);
        const select = root.querySelector(".pk_t_place");
        const picker = select.nextElementSibling;
        const input = picker.querySelector(".o_pk_picker_input");
        expect(input.value).toBe("To be decided");
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        const first = picker.querySelector(".o_pk_picker_option");
        expect(first.dataset.pkPickerValue).toBe("");
        expect(first.textContent).toBe("To be decided");
    });
});
