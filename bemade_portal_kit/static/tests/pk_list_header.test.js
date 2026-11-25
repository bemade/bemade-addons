/*
 * Task 5198 (P3a) — pk_list_header: an add card marked data-pk-list-reset
 * is reset like an add panel after « pk:create-success ». Synthetic fixtures
 * only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { readDraft, writeDraft } from "@bemade_portal_kit/js/pk_draft_store";
import { resetAddPanel } from "@bemade_portal_kit/js/pk_list_header";

function mount(wrapper) {
    getFixture().innerHTML = `
        <div class="o_pk_app" data-pk-db="db_a" data-pk-uid="7">
            ${wrapper.replace(
                "FORM",
                `<form data-pk-draft-prefix="thing:new">
                    <input type="text" name="title"/>
                </form>`
            )}
        </div>`;
    return getFixture().querySelector("form");
}

describe("pk_list_header", () => {
    test("a form in a [data-pk-list-reset] card is reset and its drafts dropped", () => {
        const form = mount('<div class="o_any_card" data-pk-list-reset="1">FORM</div>');
        writeDraft("thing:new:title", { value: "typed" });
        form.querySelector("input").value = "typed";
        const resets = [];
        form.addEventListener("pk:form-reset", () => resets.push(true));
        expect(resetAddPanel(form)).toBe(true);
        expect(form.querySelector("input").value).toBe("");
        expect(readDraft("thing:new:title")).toBe(null);
        expect(resets).toHaveLength(1);
    });

    test("pk:create-success on such a form resets it", () => {
        const form = mount('<div data-pk-list-reset="1">FORM</div>');
        form.dataset.pkSubmitted = "1";
        form.querySelector("input").value = "typed";
        form.dispatchEvent(new CustomEvent("pk:create-success", { bubbles: true }));
        expect(form.querySelector("input").value).toBe("");
        expect(form.dataset.pkSubmitted).toBe(undefined);
    });

    test("a form outside an add panel or a reset card is left alone", () => {
        const form = mount('<div class="o_sc_notepad_add">FORM</div>');
        form.querySelector("input").value = "typed";
        expect(resetAddPanel(form)).toBe(false);
        expect(form.querySelector("input").value).toBe("typed");
    });
});
