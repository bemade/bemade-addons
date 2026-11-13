/*
 * Task 5381 (P4c2) — pk_shell: the shell's boot (foreign drafts purged, the
 * drafts named by [data-pk-draft-clear] dropped), the logout that clears
 * every draft and the test-database ribbon's height. Synthetic fixtures only.
 */
import { afterEach, describe, expect, getFixture, test } from "@odoo/hoot";

import { DRAFT_PREFIX } from "@bemade_portal_kit/js/pk_draft_store";
import { bootShell } from "@bemade_portal_kit/js/pk_shell";

function mount(inner = "") {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1" data-pk-db="db_t" data-pk-uid="7">${inner}</div>`;
    return getFixture().querySelector(".o_pk_app");
}

function drafts() {
    return Object.keys(window.localStorage).filter((key) => key.startsWith(DRAFT_PREFIX)).sort();
}

function put(...keys) {
    for (const key of keys) {
        window.localStorage.setItem(DRAFT_PREFIX + key, JSON.stringify({ value: "x" }));
    }
}

describe("pk_shell", () => {
    afterEach(() => {
        for (const key of drafts()) {
            window.localStorage.removeItem(key);
        }
        document.documentElement.style.removeProperty("--pk-ribbon-h");
    });

    test("boot: another user's drafts go, the cleared prefix goes, the rest stays", () => {
        put("db_t:8:note:1", "db_t:7:injury:new:5", "db_t:7:injury:new:6", "db_t:7:note:1");
        mount('<span data-pk-draft-clear="injury:new:"></span><span data-sc-draft-clear="note:"></span>');
        bootShell();
        expect(drafts()).toEqual([`${DRAFT_PREFIX}db_t:7:note:1`]);
    });

    test("the logout link clears every draft on the device", () => {
        put("db_t:7:note:1", "db_t:8:note:2");
        const root = mount('<a class="pk_t_logout" href="/web/session/logout?redirect=/">Log out</a>');
        const spy = (ev) => ev.preventDefault(); // the test page never navigates
        document.addEventListener("click", spy);
        root.querySelector(".pk_t_logout").click();
        document.removeEventListener("click", spy);
        expect(drafts()).toEqual([]);
    });

    test("a fixed test-database ribbon lifts the tabs by its height", () => {
        mount('<div id="oe_neutralize_banner" style="position: fixed; bottom: 0; height: 24px">test db</div>');
        bootShell();
        expect(document.documentElement.style.getPropertyValue("--pk-ribbon-h")).toBe("24px");
    });
});
