/*
 * Task 5370 (P4b) — pk_lazy_edit: an edit view's fields kept in an inert
 * <template data-pk-lazy-edit> are mounted on « pk:edit-view-open », once.
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";
import { setupInteractionWhiteList, startInteractions } from "@web/../tests/public/helpers";
import { registry } from "@web/core/registry";

import { PkLazyEdit } from "@bemade_portal_kit/js/pk_lazy_edit";

const KEY = "bemade_portal_kit.pk_lazy_edit";

const HTML = `<div class="o_pk_app" data-pk-app-shell="1">
    <div class="pk_t_card" data-pk-lazy-edit-host="1">
        <template data-pk-lazy-edit="1"><div class="pk_t_fields"><input name="summary"/></div></template>
        <div class="pk_t_edit">edit</div>
    </div></div>`;

describe("pk_lazy_edit", () => {
    test("registered once, under the kit's key", () => {
        const interactions = registry.category("public.interactions");
        expect(interactions.get(KEY)).toBe(PkLazyEdit);
        expect(interactions.contains("bemade_sports_clinic.sc_lazy_edit")).toBe(false);
    });

    test("pk:edit-view-open mounts the fields once", async () => {
        setupInteractionWhiteList(KEY);
        await startInteractions(HTML);
        const host = getFixture().querySelector("[data-pk-lazy-edit-host]");
        const edit = host.querySelector(".pk_t_edit");
        expect(host.querySelector(".pk_t_fields")).toBe(null);
        edit.dispatchEvent(new CustomEvent("pk:edit-view-open", { bubbles: true }));
        expect(host.querySelectorAll(".pk_t_fields")).toHaveLength(1);
        expect(host.querySelector("template")).toBe(null);
        expect(host.dataset.pkLazyMounted).toBe("1");
        edit.dispatchEvent(new CustomEvent("pk:edit-view-open", { bubbles: true }));
        expect(host.querySelectorAll(".pk_t_fields")).toHaveLength(1);
    });

    test("the old sc:edit-view-open does nothing", async () => {
        setupInteractionWhiteList(KEY);
        await startInteractions(HTML);
        const host = getFixture().querySelector("[data-pk-lazy-edit-host]");
        host.querySelector(".pk_t_edit").dispatchEvent(new CustomEvent("sc:edit-view-open", { bubbles: true }));
        expect(host.querySelector(".pk_t_fields")).toBe(null);
        expect(host.querySelector("template")).not.toBe(null);
    });
});
