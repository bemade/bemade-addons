/*
 * Task 5583 — the bubble's « New conversation » shows only when the list
 * says the user has someone to write to (``can_start``); otherwise it stays
 * hidden and an open picker closes. Synthetic fixtures only (a fake API).
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { PkChatBubble } from "@bemade_portal_kit_chat/js/pk_chat_bubble";

/** The bubble's menu parts, as the template renders them (button hidden). */
function fakeBubble(canStart) {
    const fixture = getFixture();
    fixture.innerHTML = `
        <div data-pk-chat-bubble="1">
            <button type="button" data-pk-chat-new="1" hidden="hidden">New conversation</button>
            <div data-pk-chat-picker="1" hidden="hidden"></div>
            <div data-pk-chat-list="1"></div>
        </div>`;
    const bubble = Object.create(PkChatBubble.prototype);
    Object.assign(bubble, {
        el: fixture.querySelector("[data-pk-chat-bubble]"),
        newBtn: fixture.querySelector("[data-pk-chat-new]"),
        pickerHost: fixture.querySelector("[data-pk-chat-picker]"),
        list: fixture.querySelector("[data-pk-chat-list]"),
        texts: { noConversations: "Nothing", closedSection: "Ended" },
        api: { conversations: async () => ({ conversations: [], can_start: canStart }) },
    });
    return bubble;
}

describe("pk_chat_bubble", () => {
    test("« New conversation » stays hidden without anybody to write to", async () => {
        const bubble = fakeBubble(false);
        await bubble.loadConversations();
        expect(bubble.newBtn.hidden).toBe(true);
    });

    test("« New conversation » shows when the user has a contact", async () => {
        const bubble = fakeBubble(true);
        await bubble.loadConversations();
        expect(bubble.newBtn.hidden).toBe(false);
    });

    test("an open picker closes when the user no longer may start", async () => {
        const bubble = fakeBubble(false);
        bubble.newBtn.hidden = false;
        bubble.pickerHost.hidden = false;
        bubble.pickerHost.innerHTML = "<select></select>";
        await bubble.loadConversations();
        expect(bubble.newBtn.hidden).toBe(true);
        expect(bubble.pickerHost.hidden).toBe(true);
        expect(bubble.pickerHost.innerHTML).toBe("");
    });
});
