/*
 * Task 5546 — the one-time phone prompt after a message sent: shown once,
 * only when due and possible; either answer is remembered. A stubbed
 * pkPush; synthetic texts only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { pkChatPushPrompt } from "@bemade_portal_kit_chat/js/pk_chat_push_prompt";

function setup({ due = true, state = "off", permission = "default" } = {}) {
    const fixture = getFixture();
    fixture.innerHTML = `${due ? `<span hidden="hidden" data-pk-chat-push-prompt="1"
            data-pk-chat-push-ask="Notify?" data-pk-chat-push-on="On" data-pk-chat-push-later="Later"
            data-pk-chat-push-ios="Add to home screen" data-pk-chat-push-ok="OK"></span>` : ""}
        <div class="thread"><form data-pk-chat-composer="1"></form></div>`;
    const root = fixture.querySelector(".thread");
    const thread = { root, form: root.querySelector("form") };
    const calls = [];
    const push = {
        status: async () => ({ state, permission }),
        enable: () => {
            calls.push("enable");
            return Promise.resolve({ state: "on" });
        },
        markPrompted: () => {
            calls.push("prompted");
            return Promise.resolve({});
        },
    };
    return { fixture, thread, push, calls };
}

describe("pk_chat_push_prompt", () => {
    test("due and never asked: Turn on / Later, before the composer", async () => {
        const { fixture, thread, push, calls } = setup();
        expect(await pkChatPushPrompt(thread, { push, root: fixture })).toBe("enable");
        const banner = thread.root.querySelector("[data-pk-chat-push-banner]");
        expect(banner.nextElementSibling).toBe(thread.form);
        expect(banner.querySelector("p").textContent).toBe("Notify?");
        banner.querySelector("[data-pk-chat-push-on]").click();
        expect(calls).toEqual(["enable", "prompted"]);
        expect(thread.root.querySelector("[data-pk-chat-push-banner]")).toBe(null);
        expect(await pkChatPushPrompt(thread, { push, root: fixture })).toBe(null);
    });

    test("Later is remembered: once only", async () => {
        const { fixture, thread, push, calls } = setup();
        await pkChatPushPrompt(thread, { push, root: fixture });
        thread.root.querySelector("[data-pk-chat-push-later]").click();
        expect(calls).toEqual(["prompted"]);
        expect(await pkChatPushPrompt(thread, { push, root: fixture })).toBe(null);
    });

    test("iPhone outside the app: the home-screen hint", async () => {
        const { fixture, thread, push } = setup({ state: "ios-install" });
        expect(await pkChatPushPrompt(thread, { push, root: fixture })).toBe("ios");
        expect(thread.root.querySelector("[data-pk-chat-push-banner] p").textContent).toBe("Add to home screen");
        expect(thread.root.querySelector("[data-pk-chat-push-on]")).toBe(null);
    });

    test("not due, no pkPush, already on, denied or unsupported: nothing", async () => {
        let ctx = setup({ due: false });
        expect(await pkChatPushPrompt(ctx.thread, { push: ctx.push, root: ctx.fixture })).toBe(null);
        ctx = setup();
        expect(await pkChatPushPrompt(ctx.thread, { push: null, root: ctx.fixture })).toBe(null);
        for (const [state, permission] of [["on", "granted"], ["denied", "denied"], ["unsupported", "default"],
                                           ["off", "granted"]]) {
            ctx = setup({ state, permission });
            expect(await pkChatPushPrompt(ctx.thread, { push: ctx.push, root: ctx.fixture })).toBe(null);
            expect(ctx.thread.root.querySelector("[data-pk-chat-push-banner]")).toBe(null);
        }
    });
});
