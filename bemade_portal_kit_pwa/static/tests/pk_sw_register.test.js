/*
 * Task 5201 (kit P6) — pk_sw_register: the kill switch and the install
 * page. Synthetic fixtures only (fake registrations and fetch).
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import {
    PK_SW_SCOPE,
    PK_SW_URL,
    pkInitInstallPage,
    pkSwIsMine,
    pkSwKillSwitch,
} from "@bemade_portal_kit_pwa/js/pk_sw_register";

function reg(scriptPath, slot = "active") {
    const registration = { active: null, waiting: null, installing: null, unregistered: false };
    registration[slot] = { scriptURL: new URL(scriptPath, window.location.origin).href };
    registration.unregister = async () => {
        registration.unregistered = true;
        return true;
    };
    return registration;
}

function container(regs) {
    return { getRegistrations: async () => regs };
}

function fetchStatus(status, calls) {
    return async (url, options) => {
        calls.push([url, options]);
        return { status };
    };
}

describe("pk_sw_register", () => {
    test("constants: the stable URL and the whole-origin scope", () => {
        expect(PK_SW_URL).toBe("/my/service-worker.js");
        expect(PK_SW_SCOPE).toBe("/");
    });

    test("pkSwIsMine: our script in any slot and scope, never another", () => {
        expect(pkSwIsMine(reg("/my/service-worker.js"))).toBe(true);
        expect(pkSwIsMine(reg("/my/service-worker.js", "waiting"))).toBe(true);
        expect(pkSwIsMine(reg("/my/service-worker.js", "installing"))).toBe(true);
        expect(pkSwIsMine(reg("/other-worker.js"))).toBe(false);
        expect(pkSwIsMine({ active: null, waiting: null, installing: null })).toBe(false);
        expect(pkSwIsMine({ active: { scriptURL: "not a url" } })).toBe(false);
    });

    test("kill switch: a 404 unregisters every registration of our worker", async () => {
        const mine = [reg("/my/service-worker.js"), reg("/my/service-worker.js", "waiting")];
        const other = reg("/other-worker.js");
        const calls = [];
        const state = await pkSwKillSwitch(container([...mine, other]), fetchStatus(404, calls));
        expect(state).toBe("unregistered");
        expect(mine.map((r) => r.unregistered)).toEqual([true, true]);
        expect(other.unregistered).toBe(false);
        expect(calls[0][0]).toBe("/my/service-worker.js");
        expect(calls[0][1].cache).toBe("no-store");
        expect(document.documentElement.getAttribute("data-pk-sw")).toBe("unregistered");
    });

    test("kill switch: the worker served (200) or offline leaves them", async () => {
        const mine = [reg("/my/service-worker.js")];
        expect(await pkSwKillSwitch(container(mine), fetchStatus(200, []))).toBe(undefined);
        const offline = async () => {
            throw new TypeError("offline");
        };
        expect(await pkSwKillSwitch(container(mine), offline)).toBe(undefined);
        expect(mine[0].unregistered).toBe(false);
    });

    test("kill switch: nothing registered, nothing fetched", async () => {
        const calls = [];
        expect(await pkSwKillSwitch(container([reg("/other.js")]), fetchStatus(404, calls))).toBe("none");
        expect(calls.length).toBe(0);
    });

    test("install page: standalone shows « installed » and hides the steps", () => {
        const fixture = getFixture();
        fixture.innerHTML = `<div data-pk-install="1"></div>
            <div data-pk-install-state="installed" hidden="hidden"></div>
            <section data-pk-install-steps="ios"></section>
            <section data-pk-install-steps="android"></section>`;
        expect(pkInitInstallPage(fixture, false)).toBe(true);
        expect(fixture.querySelector('[data-pk-install-state="installed"]').hidden).toBe(true);
        expect(pkInitInstallPage(fixture, true)).toBe(true);
        expect(fixture.querySelector('[data-pk-install-state="installed"]').hidden).toBe(false);
        expect([...fixture.querySelectorAll("[data-pk-install-steps]")].every((el) => el.hidden)).toBe(true);
        fixture.innerHTML = "<p>elsewhere</p>";
        expect(pkInitInstallPage(fixture, true)).toBe(false);
    });
});
