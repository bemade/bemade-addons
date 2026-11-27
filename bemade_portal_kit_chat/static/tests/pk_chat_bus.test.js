/*
 * Task 5520 — the chat's bus listeners: a reader of a managed group gets
 * only the content-free « pk_chat.ping » for it; like Discuss's own
 * « new_message » (posters, direct chats) it means « refetch channel X ».
 * A fake bus; synthetic payloads only.
 */
import { describe, expect, test } from "@odoo/hoot";

import {
    PK_CHAT_JOINED,
    PK_CHAT_NEW_MESSAGE,
    PK_CHAT_PING,
    subscribeChatBus,
} from "@bemade_portal_kit_chat/js/pk_chat_client";

function fakeBus() {
    const handlers = {};
    return {
        handlers,
        subscribe(type, fn) {
            (handlers[type] ||= []).push(fn);
        },
        unsubscribe(type, fn) {
            handlers[type] = (handlers[type] || []).filter((h) => h !== fn);
        },
        emit(type, payload) {
            for (const fn of handlers[type] || []) {
                fn(payload);
            }
        },
    };
}

describe("pk_chat bus", () => {
    test("a ping refetches its channel", () => {
        const bus = fakeBus();
        const changed = [];
        subscribeChatBus(bus, { onChanged: (id) => changed.push(id), onJoined: () => changed.push("joined") });
        bus.emit(PK_CHAT_PING, { channel_id: 22, message_id: 501 });
        expect(changed).toEqual([22]);
    });

    test("Discuss's new_message and joined still work", () => {
        const bus = fakeBus();
        const changed = [];
        subscribeChatBus(bus, { onChanged: (id) => changed.push(id), onJoined: () => changed.push("joined") });
        bus.emit(PK_CHAT_NEW_MESSAGE, { id: 11, data: {} });
        bus.emit(PK_CHAT_JOINED, { channel_id: 33 });
        expect(changed).toEqual([11, "joined"]);
    });

    test("unsubscribe removes every listener", () => {
        const bus = fakeBus();
        const changed = [];
        const off = subscribeChatBus(bus, { onChanged: (id) => changed.push(id), onJoined: () => {} });
        off();
        bus.emit(PK_CHAT_PING, { channel_id: 22 });
        bus.emit(PK_CHAT_NEW_MESSAGE, { id: 11 });
        expect(changed).toEqual([]);
        expect(Object.values(bus.handlers).flat()).toHaveLength(0);
    });
});
