/*
 * Task 5197 (P2) — pk_draft_store: drafts scoped by database and user.
 * Task 5198 (P3a) — the pk_draft: prefix, data-pk-db / data-pk-uid, and the
 * read-old fallback for the drafts stored before P3a (sc_draft:).
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import {
    clearAllDrafts,
    DRAFT_PREFIX,
    purgeForeignDrafts,
    readDraft,
    removeDraft,
    removeDraftsWithPrefix,
    writeDraft,
} from "@bemade_portal_kit/js/pk_draft_store";

function mountShell(db, uid) {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-db="${db}" data-pk-uid="${uid}"></div>`;
}

function storedKeys() {
    return Object.keys(window.localStorage);
}

describe("pk_draft_store", () => {
    test("the prefix is pk_draft:", () => {
        expect(DRAFT_PREFIX).toBe("pk_draft:");
    });

    test("a draft is stored under its db + uid scope", () => {
        mountShell("db_a", "7");
        expect(writeDraft("note:new", { value: "hello" })).toBe(true);
        expect(storedKeys()).toInclude("pk_draft:db_a:7:note:new");
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

    test("the old data-sc-* root attributes are not read any more", () => {
        getFixture().innerHTML = '<div class="o_pk_app" data-sc-db="db_a" data-sc-uid="7"></div>';
        expect(writeDraft("note:new", { value: "x" })).toBe(false);
    });

    test("task 5344 (P3b1): an o_sc_app root is not read any more", () => {
        getFixture().innerHTML = '<div class="o_sc_app" data-pk-db="db_a" data-pk-uid="7"></div>';
        expect(writeDraft("note:new", { value: "x" })).toBe(false);
    });

    test("purgeForeignDrafts drops other users' drafts only", () => {
        window.localStorage.setItem("pk_draft:db_a:8:note:1", "{}");
        window.localStorage.setItem("pk_draft:db_b:7:note:1", "{}");
        window.localStorage.setItem("unrelated:key", "1");
        mountShell("db_a", "7");
        writeDraft("note:1", { value: "mine" });
        purgeForeignDrafts();
        const keys = storedKeys();
        expect(keys).toInclude("pk_draft:db_a:7:note:1");
        expect(keys).toInclude("unrelated:key");
        expect(keys).not.toInclude("pk_draft:db_a:8:note:1");
        expect(keys).not.toInclude("pk_draft:db_b:7:note:1");
    });

    test("removeDraftsWithPrefix drops this user's matching drafts", () => {
        window.localStorage.setItem("pk_draft:db_a:8:injury:new:1", "{}");
        mountShell("db_a", "7");
        writeDraft("injury:new:1", { value: "a" });
        writeDraft("injury:new:2", { value: "b" });
        writeDraft("note:new", { value: "c" });
        removeDraftsWithPrefix("injury:new");
        expect(readDraft("injury:new:1")).toBe(null);
        expect(readDraft("injury:new:2")).toBe(null);
        expect(readDraft("note:new").value).toBe("c");
        expect(storedKeys()).toInclude("pk_draft:db_a:8:injury:new:1");
    });

    test("removeDraft and clearAllDrafts", () => {
        mountShell("db_a", "7");
        writeDraft("a", { value: 1 });
        writeDraft("b", { value: 2 });
        removeDraft("a");
        expect(readDraft("a")).toBe(null);
        expect(readDraft("b").value).toBe(2);
        window.localStorage.setItem("pk_draft:db_a:8:c", "{}");
        clearAllDrafts();
        expect(storedKeys().filter((k) => k.startsWith("pk_draft:"))).toEqual([]);
    });
});

describe("pk_draft_store: the old-prefix fallback (task 5198)", () => {
    test("an old sc_draft: draft is read once, moved under pk_draft: and removed", () => {
        window.localStorage.setItem(
            "sc_draft:db_a:7:note:new",
            JSON.stringify({ value: "typed before the upgrade", at: 1 })
        );
        mountShell("db_a", "7");
        expect(readDraft("note:new").value).toBe("typed before the upgrade");
        const keys = storedKeys();
        expect(keys).toInclude("pk_draft:db_a:7:note:new");
        expect(keys).not.toInclude("sc_draft:db_a:7:note:new");
        expect(JSON.parse(window.localStorage.getItem("pk_draft:db_a:7:note:new")).value).toBe(
            "typed before the upgrade"
        );
        // Read again: from the new key.
        expect(readDraft("note:new").value).toBe("typed before the upgrade");
    });

    test("a new-key draft wins over an old one, and the old one is dropped", () => {
        window.localStorage.setItem("sc_draft:db_a:7:note:new", JSON.stringify({ value: "old" }));
        mountShell("db_a", "7");
        writeDraft("note:new", { value: "new" });
        expect(readDraft("note:new").value).toBe("new");
        expect(storedKeys()).not.toInclude("sc_draft:db_a:7:note:new");
    });

    test("another user's old draft is not read", () => {
        window.localStorage.setItem("sc_draft:db_a:8:note:new", JSON.stringify({ value: "theirs" }));
        mountShell("db_a", "7");
        expect(readDraft("note:new")).toBe(null);
        expect(storedKeys()).toInclude("sc_draft:db_a:8:note:new");
    });

    test("purgeForeignDrafts moves this user's old drafts and drops the others", () => {
        window.localStorage.setItem("sc_draft:db_a:7:note:1", JSON.stringify({ value: "mine" }));
        window.localStorage.setItem("sc_draft:db_a:8:note:1", "{}");
        window.localStorage.setItem("sc_draft:db_b:7:note:1", "{}");
        mountShell("db_a", "7");
        purgeForeignDrafts();
        const keys = storedKeys();
        expect(keys.filter((k) => k.startsWith("sc_draft:"))).toEqual([]);
        expect(keys).toInclude("pk_draft:db_a:7:note:1");
        expect(readDraft("note:1").value).toBe("mine");
    });

    test("removeDraft, removeDraftsWithPrefix and clearAllDrafts drop the old keys too", () => {
        window.localStorage.setItem("sc_draft:db_a:7:a", "{}");
        window.localStorage.setItem("sc_draft:db_a:7:injury:new:1", "{}");
        window.localStorage.setItem("sc_draft:db_a:7:note:new", "{}");
        window.localStorage.setItem("sc_draft:db_a:8:other", "{}");
        mountShell("db_a", "7");
        removeDraft("a");
        expect(storedKeys()).not.toInclude("sc_draft:db_a:7:a");
        removeDraftsWithPrefix("injury:new");
        expect(storedKeys()).not.toInclude("sc_draft:db_a:7:injury:new:1");
        expect(storedKeys()).toInclude("sc_draft:db_a:7:note:new");
        clearAllDrafts();
        expect(storedKeys().filter((k) => k.startsWith("sc_draft:"))).toEqual([]);
    });
});
