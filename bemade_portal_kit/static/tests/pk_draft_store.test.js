/*
 * Task 5197 (P2) — pk_draft_store: drafts scoped by database and user.
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import {
    clearAllDrafts,
    purgeForeignDrafts,
    readDraft,
    removeDraft,
    removeDraftsWithPrefix,
    writeDraft,
} from "@bemade_portal_kit/js/pk_draft_store";

function mountShell(db, uid) {
    getFixture().innerHTML = `<div class="o_sc_app" data-sc-db="${db}" data-sc-uid="${uid}"></div>`;
}

describe("pk_draft_store", () => {
    test("a draft is stored under its db + uid scope", () => {
        mountShell("db_a", "7");
        expect(writeDraft("note:new", { value: "hello" })).toBe(true);
        expect(Object.keys(window.localStorage)).toInclude("sc_draft:db_a:7:note:new");
        expect(readDraft("note:new").value).toBe("hello");
    });

    test("another user or database does not see the draft", () => {
        mountShell("db_a", "7");
        writeDraft("note:new", { value: "hello" });
        mountShell("db_a", "8");
        expect(readDraft("note:new")).toBe(null);
        mountShell("db_b", "7");
        expect(readDraft("note:new")).toBe(null);
    });

    test("without a shell root, drafts are off", () => {
        getFixture().innerHTML = "";
        expect(writeDraft("note:new", { value: "x" })).toBe(false);
        expect(readDraft("note:new")).toBe(null);
    });

    test("purgeForeignDrafts drops other users' drafts only", () => {
        window.localStorage.setItem("sc_draft:db_a:8:note:1", "{}");
        window.localStorage.setItem("sc_draft:db_b:7:note:1", "{}");
        window.localStorage.setItem("unrelated:key", "1");
        mountShell("db_a", "7");
        writeDraft("note:1", { value: "mine" });
        purgeForeignDrafts();
        const keys = Object.keys(window.localStorage);
        expect(keys).toInclude("sc_draft:db_a:7:note:1");
        expect(keys).toInclude("unrelated:key");
        expect(keys).not.toInclude("sc_draft:db_a:8:note:1");
        expect(keys).not.toInclude("sc_draft:db_b:7:note:1");
    });

    test("removeDraftsWithPrefix drops this user's matching drafts", () => {
        window.localStorage.setItem("sc_draft:db_a:8:injury:new:1", "{}");
        mountShell("db_a", "7");
        writeDraft("injury:new:1", { value: "a" });
        writeDraft("injury:new:2", { value: "b" });
        writeDraft("note:new", { value: "c" });
        removeDraftsWithPrefix("injury:new");
        expect(readDraft("injury:new:1")).toBe(null);
        expect(readDraft("injury:new:2")).toBe(null);
        expect(readDraft("note:new").value).toBe("c");
        expect(Object.keys(window.localStorage)).toInclude("sc_draft:db_a:8:injury:new:1");
    });

    test("removeDraft and clearAllDrafts", () => {
        mountShell("db_a", "7");
        writeDraft("a", { value: 1 });
        writeDraft("b", { value: 2 });
        removeDraft("a");
        expect(readDraft("a")).toBe(null);
        expect(readDraft("b").value).toBe(2);
        window.localStorage.setItem("sc_draft:db_a:8:c", "{}");
        clearAllDrafts();
        expect(Object.keys(window.localStorage).filter((k) => k.startsWith("sc_draft:"))).toEqual([]);
    });
});
