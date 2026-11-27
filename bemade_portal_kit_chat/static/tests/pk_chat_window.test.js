/*
 * Task 5516 — the portal chat's client: the ONE window swaps its thread,
 * follows the user from page to page (sessionStorage), a reader of a
 * managed channel only replies, Enter sends, and the backend palette's
 * portal partners. Task 5566: a closed conversation (no composer, no
 * « Reply », its chip) and the list's « Ended » section. Synthetic fixtures
 * only (a fake API).
 */
import { afterEach, beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";

import { ChatThread, renderConversations, renderMessage } from "@bemade_portal_kit_chat/js/pk_chat_client";
import { ChatWindow, PK_CHAT_MIN_KEY, PK_CHAT_OPEN_KEY } from "@bemade_portal_kit_chat/js/pk_chat_window";
import { pkPortalPartners } from "@bemade_portal_kit_chat/backend/pk_chat_portal_partners";

const TEXTS = {
    reply: "Reply",
    send: "Send",
    placeholder: "Write",
    replyingTo: "Replying to %s",
    cancel: "Cancel",
    readerHint: "Reply to a message to answer.",
    members: "Members",
    poster: "Poster",
    reader: "Reader",
    empty: "Nothing",
    error: "Error",
    older: "Older",
    closed: "Closed note",
};

function msg(id, author, extra = {}) {
    return {
        id,
        author_name: author,
        author_avatar_url: "",
        body_html: `<p>message ${id}</p>`,
        when: "10:00",
        own: false,
        parent: null,
        can_reply: true,
        ...extra,
    };
}

/** A fake API: two conversations, 11 (direct) and 22 (managed, reader). */
function fakeApi() {
    const calls = [];
    const threads = {
        11: { id: 11, kind: "direct", title: "Avery", managed: false, composer: "full", more: false,
              messages: [msg(1, "Avery")] },
        22: { id: 22, kind: "group", title: "Team news", managed: true, composer: "reply", more: false,
              messages: [msg(5, "Coach")] },
        33: { id: 33, kind: "group", title: "Ended team", managed: true, closed: true, closed_label: "Ended",
              composer: "none", more: false, messages: [msg(7, "Coach", { can_reply: false })] },
    };
    return {
        calls,
        threads,
        messages: async (id, opts = {}) => {
            calls.push(["messages", id, opts]);
            if (opts.after) {
                return { ...threads[id], messages: threads[id].messages.filter((m) => m.id > opts.after) };
            }
            return threads[id];
        },
        read: async (id) => {
            calls.push(["read", id]);
            return { count: 0 };
        },
        post: async (id, body, parentId) => {
            calls.push(["post", id, body, parentId || null]);
            return {
                message: msg(100 + calls.length, "Me", {
                    own: true,
                    parent: parentId ? { id: parentId, author_name: "Coach", excerpt: "message" } : null,
                }),
            };
        },
    };
}

function windowFixture() {
    getFixture().innerHTML = `
        <div class="o_pk_app">
            <section data-pk-chat-window="1" hidden="hidden">
                <header data-pk-chat-head="1">
                    <button data-pk-chat-back="1"></button>
                    <strong data-pk-chat-title="1"></strong>
                    <span data-pk-chat-closed-chip="1" hidden="hidden"></span>
                    <button data-pk-chat-min="1"></button>
                    <button data-pk-chat-close="1"></button>
                </header>
                <div data-pk-chat-thread-host="1"></div>
            </section>
        </div>`;
    return getFixture().querySelector("[data-pk-chat-window]");
}

beforeEach(() => {
    window.sessionStorage.removeItem(PK_CHAT_OPEN_KEY);
    window.sessionStorage.removeItem(PK_CHAT_MIN_KEY);
});
afterEach(() => {
    window.sessionStorage.removeItem(PK_CHAT_OPEN_KEY);
    window.sessionStorage.removeItem(PK_CHAT_MIN_KEY);
});

describe("pk_chat_window", () => {
    test("one window: picking another conversation swaps its thread", async () => {
        const api = fakeApi();
        const host = windowFixture();
        const win = new ChatWindow(host, { api, texts: TEXTS });
        await win.open(11);
        expect(host.hidden).toBe(false);
        expect(host.querySelectorAll("[data-pk-chat-thread]").length).toBe(1);
        expect(host.querySelector("[data-pk-chat-thread]").dataset.pkChatThread).toBe("11");
        expect(host.querySelector("[data-pk-chat-title]").textContent).toBe("Avery");
        await win.open(22);
        expect(host.querySelectorAll("[data-pk-chat-thread]").length).toBe(1);
        expect(host.querySelector("[data-pk-chat-thread]").dataset.pkChatThread).toBe("22");
        expect(host.querySelector("[data-pk-chat-title]").textContent).toBe("Team news");
        expect(api.calls.filter((c) => c[0] === "read").map((c) => c[1])).toEqual([11, 22]);
    });

    test("the open conversation and the minimised state survive a page load", async () => {
        const api = fakeApi();
        let win = new ChatWindow(windowFixture(), { api, texts: TEXTS });
        await win.open(22);
        win.setMinimised(true);
        expect(window.sessionStorage.getItem(PK_CHAT_OPEN_KEY)).toBe("22");
        expect(window.sessionStorage.getItem(PK_CHAT_MIN_KEY)).toBe("1");
        // « The next page »: a new window restores it.
        const host = windowFixture();
        win = new ChatWindow(host, { api, texts: TEXTS });
        await win.restore();
        expect(host.hidden).toBe(false);
        expect(host.dataset.pkChatOpen).toBe("22");
        expect(host.dataset.pkChatMinimised).toBe("1");
        // Closed: nothing to restore.
        win.close();
        expect(window.sessionStorage.getItem(PK_CHAT_OPEN_KEY)).toBe(null);
        const again = new ChatWindow(windowFixture(), { api, texts: TEXTS });
        expect(await again.restore()).toBe(null);
    });

    test("the back arrow closes the window and shows the list", async () => {
        let back = 0;
        const host = windowFixture();
        const win = new ChatWindow(host, { api: fakeApi(), texts: TEXTS, onBack: () => back++ });
        await win.open(11);
        host.querySelector("[data-pk-chat-back]").click();
        expect(host.hidden).toBe(true);
        expect(back).toBe(1);
    });
});

describe("pk_chat_client", () => {
    test("a reader has no composer: « Reply » opens it with the quoted parent", async () => {
        const api = fakeApi();
        const host = getFixture();
        host.innerHTML = "<div></div>";
        const thread = new ChatThread(host.firstChild, 22, { api, texts: TEXTS });
        await thread.load();
        const form = host.querySelector("[data-pk-chat-composer]");
        expect(form.hidden).toBe(true);
        expect(host.querySelector("[data-pk-chat-reader-hint]").hidden).toBe(false);
        expect(host.querySelector("[data-pk-chat-members]").hidden).toBe(true);
        host.querySelector('[data-pk-chat-reply="5"]').click();
        expect(form.hidden).toBe(false);
        expect(host.querySelector("[data-pk-chat-replying]").textContent).toInclude("Replying to Coach");
        form.querySelector("textarea").value = "Thanks";
        form.dispatchEvent(new Event("submit", { cancelable: true }));
        await animationFrame();
        expect(api.calls.find((c) => c[0] === "post")).toEqual(["post", 22, "Thanks", 5]);
        expect(form.hidden).toBe(true);
        const items = host.querySelectorAll("[data-pk-chat-msg]");
        expect(items.length).toBe(2);
        // A reply to the message just above carries no quote (it would repeat it).
        expect(items[1].querySelector(".o_pk_chat_quote")).toBe(null);
    });

    test("a reply quotes its parent unless the parent is just above", () => {
        const msg = {
            id: 9, own: false, author_name: "Avery", when: "10:00", body_html: "<p>Ok</p>",
            parent: { id: 5, author_name: "Coach", excerpt: "Practice moved" },
        };
        const quoted = renderMessage(msg, TEXTS, { canReply: true, prevId: 7 });
        expect(quoted.querySelector(".o_pk_chat_quote").textContent).toInclude("Coach Practice moved");
        const adjacent = renderMessage(msg, TEXTS, { canReply: true, prevId: 5 });
        expect(adjacent.querySelector(".o_pk_chat_quote")).toBe(null);
    });

    test("a direct chat has the composer; Enter sends, Shift+Enter does not", async () => {
        const api = fakeApi();
        const host = getFixture();
        host.innerHTML = "<div></div>";
        const thread = new ChatThread(host.firstChild, 11, { api, texts: TEXTS });
        await thread.load();
        const input = host.querySelector("textarea");
        expect(host.querySelector("[data-pk-chat-composer]").hidden).toBe(false);
        expect(host.querySelector("[data-pk-chat-reply]")).toBe(null);
        input.value = "Line one";
        input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", shiftKey: true, bubbles: true }));
        await animationFrame();
        expect(api.calls.filter((c) => c[0] === "post").length).toBe(0);
        input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
        await animationFrame();
        expect(api.calls.filter((c) => c[0] === "post").length).toBe(1);
        expect(input.value).toBe("");
    });

    test("refresh appends only the newer messages", async () => {
        const api = fakeApi();
        const host = getFixture();
        host.innerHTML = "<div></div>";
        const thread = new ChatThread(host.firstChild, 11, { api, texts: TEXTS });
        await thread.load();
        api.threads[11].messages = [msg(1, "Avery"), msg(2, "Avery")];
        await thread.refresh();
        expect(host.querySelectorAll("[data-pk-chat-msg]").length).toBe(2);
        expect(api.calls.find((c) => c[0] === "messages" && c[2].after)).toEqual(["messages", 11, { after: 1 }]);
    });
});

describe("pk_chat_closed", () => {
    test("a closed conversation: no composer, no « Reply », a note and its chip", async () => {
        const api = fakeApi();
        const host = getFixture();
        host.innerHTML = "<div></div>";
        const thread = new ChatThread(host.firstChild, 33, { api, texts: TEXTS });
        await thread.load();
        expect(host.querySelector("[data-pk-chat-composer]").hidden).toBe(true);
        expect(host.querySelector("[data-pk-chat-reader-hint]").hidden).toBe(true);
        expect(host.querySelector("[data-pk-chat-closed-note]").hidden).toBe(false);
        expect(host.querySelector("[data-pk-chat-closed-note]").textContent).toBe("Closed note");
        expect(host.querySelector("[data-pk-chat-reply]")).toBe(null);
        expect(host.querySelectorAll("[data-pk-chat-msg]").length).toBe(1);
        const chip = host.querySelector("[data-pk-chat-closed-chip]");
        expect(chip.hidden).toBe(false);
        expect(chip.textContent).toBe("Ended");
        // Even forced, nothing is sent.
        host.querySelector("textarea").value = "Hello?";
        await thread.submit();
        expect(api.calls.filter((c) => c[0] === "post").length).toBe(0);
    });

    test("an open managed conversation keeps « Reply » and has no chip", async () => {
        const host = getFixture();
        host.innerHTML = "<div></div>";
        const thread = new ChatThread(host.firstChild, 22, { api: fakeApi(), texts: TEXTS });
        await thread.load();
        expect(host.querySelector("[data-pk-chat-closed-note]").hidden).toBe(true);
        expect(host.querySelector("[data-pk-chat-closed-chip]").hidden).toBe(true);
        expect(host.querySelector('[data-pk-chat-reply="5"]')).not.toBe(null);
    });

    test("the window shows the chip in its header, and drops it for an open one", async () => {
        const host = windowFixture();
        const win = new ChatWindow(host, { api: fakeApi(), texts: TEXTS });
        await win.open(33);
        const headChip = host.querySelector("header [data-pk-chat-closed-chip]");
        expect(headChip.hidden).toBe(false);
        expect(headChip.textContent).toBe("Ended");
        expect(host.querySelector("[data-pk-chat-thread] [data-pk-chat-closed-chip]").hidden).toBe(true);
        await win.open(11);
        expect(headChip.hidden).toBe(true);
    });

    test("the list: the closed conversations under their heading, each with its chip", () => {
        const list = getFixture();
        const row = (id, closed) => ({
            id, kind: "group", title: `Group ${id}`, avatar_url: "", preview: "", when: "", unread: 0,
            closed, closed_label: closed ? "Ended" : "",
        });
        renderConversations(list, [row(1, false), row(2, false), row(3, true), row(4, true)], {
            closedSection: "Ended conversations",
        });
        const items = [...list.children].map((node) =>
            node.dataset.pkChatClosedSection ? "section" : node.dataset.pkChatOpen
        );
        expect(items).toEqual(["1", "2", "section", "3", "4"]);
        expect(list.querySelector("[data-pk-chat-closed-section]").textContent).toBe("Ended conversations");
        expect(list.querySelectorAll("[data-pk-chat-closed-chip]").length).toBe(2);
        expect(list.querySelector('[data-pk-chat-open="1"] [data-pk-chat-closed-chip]')).toBe(null);
        // Nothing closed: no heading.
        renderConversations(list, [row(1, false)], { closedSection: "Ended conversations" });
        expect(list.querySelector("[data-pk-chat-closed-section]")).toBe(null);
    });
});

describe("pk_chat_portal_partners", () => {
    test("only portal partners matching the term, not shown yet, within the limit", () => {
        const internal = { displayName: "Dana Staff", main_user_id: { share: false } };
        const portalA = { displayName: "Avery Parent", main_user_id: { share: true } };
        const portalB = { displayName: "Blake Parent", main_user_id: { share: true } };
        const noUser = { displayName: "Casey Parent" };
        const all = [internal, portalA, portalB, noUser];
        expect(pkPortalPartners(all, "parent", new Set(), 5)).toEqual([portalA, portalB]);
        expect(pkPortalPartners(all, "parent", new Set([portalA]), 5)).toEqual([portalB]);
        expect(pkPortalPartners(all, "parent", new Set(), 1)).toEqual([portalA]);
        expect(pkPortalPartners(all, "parent", new Set(), 0)).toEqual([]);
    });
});
