/*
 * Task 5546 (pwa 1.2) — pkPush: status / enable / disable / resync with a
 * stubbed PushManager, Notification and fetch. No real push service.
 * Synthetic endpoints and keys only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import {
    PK_PUSH_STORE_KEY,
    createPkPush,
    pkIsIos,
    pkPushKeyBytes,
    pkPushShowState,
    pkPushShowing,
} from "@bemade_portal_kit_pwa/js/pk_push";

const KEY = "BFakeVapidKey_-A";
const OWNER = "owner-ana";

function memoryStorage(initial = {}) {
    const data = { ...initial };
    return {
        getItem: (k) => (k in data ? data[k] : null),
        setItem: (k, v) => {
            data[k] = String(v);
        },
        removeItem: (k) => {
            delete data[k];
        },
        data,
    };
}

function fakeSub(endpoint, key = KEY) {
    const sub = {
        endpoint,
        expirationTime: null,
        options: { applicationServerKey: pkPushKeyBytes(key).buffer },
        unsubscribed: false,
        toJSON: () => ({ endpoint, keys: { p256dh: "p", auth: "a" } }),
        unsubscribe: async () => {
            sub.unsubscribed = true;
            return true;
        },
    };
    return sub;
}

function setup({ permission = "default", grant = "granted", sub = null, stored = null, ua = "Android",
                 standalone = false, registered = "none", owner = OWNER, noPush = false } = {}) {
    const calls = [];
    const state = { sub, subscribeCalls: [] };
    const pushManager = {
        getSubscription: async () => state.sub,
        subscribe: async (options) => {
            state.subscribeCalls.push(options);
            state.sub = fakeSub("https://push.example.com/new");
            return state.sub;
        },
    };
    const Notification = {
        permission,
        requestPermission: async () => {
            calls.push(["requestPermission"]);
            Notification.permission = grant;
            return grant;
        },
    };
    const win = {
        navigator: { userAgent: ua, maxTouchPoints: 0, serviceWorker: {}, standalone },
        matchMedia: () => ({ matches: standalone }),
        Notification,
    };
    if (!noPush) {
        win.PushManager = function () {};
    }
    const doc = document.createElement("div");
    doc.innerHTML = owner ? `<meta name="pk-push-owner" content="${owner}">` : "";
    const fetchFn = async (url, options = {}) => {
        calls.push([url, options.method || "GET", options.body ? Object.fromEntries(options.body) : null]);
        let json = {};
        if (url.startsWith("/my/app/push/key")) {
            json = { key: KEY, csrf_token: "tok", owner: OWNER, registered };
        } else if (url === "/my/app/push/register") {
            json = { registered: true, owner: OWNER, kinds_on: ["chat.direct"] };
        }
        return { ok: true, status: 200, json: async () => json };
    };
    const storage = memoryStorage(stored ? { [PK_PUSH_STORE_KEY]: JSON.stringify(stored) } : {});
    const push = createPkPush({ win, doc, fetchFn, storage, registration: async () => ({ pushManager }) });
    return { push, calls, state, storage, Notification };
}

describe("pk_push", () => {
    test("iOS detection, an iPad reporting a Mac included", () => {
        expect(pkIsIos({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)" })).toBe(true);
        expect(pkIsIos({ userAgent: "Mozilla/5.0 (Macintosh)", maxTouchPoints: 5 })).toBe(true);
        expect(pkIsIos({ userAgent: "Mozilla/5.0 (Macintosh)", maxTouchPoints: 0 })).toBe(false);
        expect(pkIsIos({ userAgent: "Mozilla/5.0 (Linux; Android 14)" })).toBe(false);
    });

    test("status: ios outside the app, unsupported, denied, off, on", async () => {
        expect((await setup({ ua: "iPhone", noPush: true }).push.status()).state).toBe("ios-install");
        expect((await setup({ ua: "iPhone", standalone: true }).push.status()).state).toBe("off");
        expect((await setup({ noPush: true }).push.status()).state).toBe("unsupported");
        expect((await setup({ permission: "denied" }).push.status()).state).toBe("denied");
        expect(await setup().push.status()).toEqual({ state: "off", permission: "default" });
        const sub = fakeSub("https://push.example.com/ep1");
        const mine = { endpoint: sub.endpoint, owner: OWNER };
        expect((await setup({ permission: "granted", sub, stored: mine }).push.status()).state).toBe("on");
        const theirs = { endpoint: sub.endpoint, owner: "owner-ben" };
        expect((await setup({ permission: "granted", sub, stored: theirs }).push.status()).state).toBe("off");
    });

    test("enable: the permission first, then subscribe and register (enable=1)", async () => {
        const { push, calls, state, storage } = setup();
        const result = await push.enable();
        expect(result).toEqual({ state: "on", kinds_on: ["chat.direct"] });
        expect(calls[0]).toEqual(["requestPermission"]);
        expect(state.subscribeCalls.length).toBe(1);
        expect(state.subscribeCalls[0].userVisibleOnly).toBe(true);
        const register = calls.find((c) => c[0] === "/my/app/push/register");
        expect(register[1]).toBe("POST");
        expect(register[2].endpoint).toBe("https://push.example.com/new");
        expect(register[2].enable).toBe("1");
        expect(register[2].vapid_public_key).toBe(KEY);
        expect(register[2].csrf_token).toBe("tok");
        expect(JSON.parse(register[2].keys)).toEqual({ p256dh: "p", auth: "a" });
        expect(JSON.parse(storage.data[PK_PUSH_STORE_KEY])).toEqual({
            endpoint: "https://push.example.com/new",
            owner: OWNER,
        });
    });

    test("enable: refused stays refused, nothing registered", async () => {
        const { push, calls } = setup({ grant: "denied" });
        expect((await push.enable()).state).toBe("denied");
        expect(calls.some((c) => c[0] === "/my/app/push/register")).toBe(false);
    });

    test("enable: another user's leftover subscription is replaced", async () => {
        const old = fakeSub("https://push.example.com/theirs");
        const { push, state } = setup({ permission: "granted", sub: old,
                                         stored: { endpoint: old.endpoint, owner: "owner-ben" } });
        await push.enable();
        expect(old.unsubscribed).toBe(true);
        expect(state.sub.endpoint).toBe("https://push.example.com/new");
    });

    test("disable: unregister on the server, then unsubscribe", async () => {
        const sub = fakeSub("https://push.example.com/ep1");
        const { push, calls, storage } = setup({ permission: "granted", sub,
                                                 stored: { endpoint: sub.endpoint, owner: OWNER } });
        expect((await push.disable()).state).toBe("off");
        const unregister = calls.find((c) => c[0] === "/my/app/push/unregister");
        expect(unregister[2]).toEqual({ csrf_token: "tok", endpoint: sub.endpoint });
        expect(sub.unsubscribed).toBe(true);
        expect(storage.data[PK_PUSH_STORE_KEY]).toBe(undefined);
    });

    test("resync: the viewer's own, lost on the server: registered again silently", async () => {
        const sub = fakeSub("https://push.example.com/ep1");
        const { push, calls } = setup({ permission: "granted", sub, registered: "none",
                                        stored: { endpoint: sub.endpoint, owner: OWNER } });
        expect(await push.resync()).toBe("registered");
        const register = calls.find((c) => c[0] === "/my/app/push/register");
        expect(register[2].enable).toBe("0");
        expect(calls.some((c) => c[0] === "requestPermission")).toBe(false);
    });

    test("resync: known on the server: nothing; someone else's: dropped", async () => {
        const sub = fakeSub("https://push.example.com/ep1");
        const ok = setup({ permission: "granted", sub, registered: "mine",
                           stored: { endpoint: sub.endpoint, owner: OWNER } });
        expect(await ok.push.resync()).toBe("ok");
        expect(ok.calls.some((c) => c[0] === "/my/app/push/register")).toBe(false);
        const other = setup({ permission: "granted", sub, stored: { endpoint: sub.endpoint, owner: "owner-ben" } });
        expect(await other.push.resync()).toBe("dropped");
        expect(sub.unsubscribed).toBe(true);
        expect(other.calls.some((c) => c[0] === "/my/app/push/register")).toBe(false);
        expect(await setup({ permission: "default" }).push.resync()).toBe("skip");
    });

    test("resync: a changed server key subscribes again", async () => {
        const sub = fakeSub("https://push.example.com/ep1", "BOtherKey_-AAAAA");
        const { push, state } = setup({ permission: "granted", sub, registered: "mine",
                                        stored: { endpoint: sub.endpoint, owner: OWNER } });
        expect(await push.resync()).toBe("resubscribed");
        expect(sub.unsubscribed).toBe(true);
        expect(state.subscribeCalls.length).toBe(1);
    });

    test("the settings card shows one state; the showing marker", () => {
        const fixture = getFixture();
        fixture.innerHTML = `<div data-pk-push-state="1">
            <p data-pk-push-show="on" hidden="hidden"></p>
            <p data-pk-push-show="off" hidden="hidden"></p>
            <p data-pk-push-show="denied" hidden="hidden"></p></div>
            <div data-pk-push-showing="/my/app/conversations/7">x</div>`;
        const card = fixture.querySelector("[data-pk-push-state]");
        expect(pkPushShowState(card, "denied")).toBe(true);
        const shown = [...card.querySelectorAll("[data-pk-push-show]")].filter((el) => !el.hidden);
        expect(shown.map((el) => el.dataset.pkPushShow)).toEqual(["denied"]);
        expect(pkPushShowState(null, "on")).toBe(false);
        expect(pkPushShowing("/my/app/conversations/7", fixture)).toBe(true);
        expect(pkPushShowing("/my/app/conversations/8", fixture)).toBe(false);
    });
});
