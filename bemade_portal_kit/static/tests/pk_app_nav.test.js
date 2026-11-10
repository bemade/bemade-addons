/*
 * Task 5197 (P2) — pk_app_nav: page keys and the tab's in-app stack.
 * Synthetic fixtures only (a stack written straight into sessionStorage).
 */
import { beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";

import {
    backDistance,
    backIsUseful,
    NAV_BF_RELOAD_KEY,
    NAV_STACK_KEY,
    pageKey,
    syncStack,
} from "@bemade_portal_kit/js/pk_app_nav";

const STORE_KEY = "pk_nav_stack:v1";

function here() {
    return pageKey(window.location.pathname + window.location.search);
}

function setStack(stack) {
    window.sessionStorage.setItem(STORE_KEY, JSON.stringify(stack));
}

function getStack() {
    return JSON.parse(window.sessionStorage.getItem(STORE_KEY) || "[]");
}

describe("pk_app_nav", () => {
    beforeEach(() => {
        window.sessionStorage.removeItem(STORE_KEY);
    });

    test("pageKey keeps the path and the sorted « …id » args only", () => {
        expect(pageKey("/my/thing?tab=notes&thing_id=4&other_id=2&q=x")).toBe(
            "/my/thing?other_id=2&thing_id=4"
        );
        expect(pageKey("/my/things")).toBe("/my/things");
        expect(pageKey("/my/things?filter=all")).toBe("/my/things");
    });

    test("pageKey ignores other origins", () => {
        expect(pageKey("https://elsewhere.example/my/things")).toBe("");
    });

    test("a reload starts a fresh stack on the current page", () => {
        setStack([{ u: "/my/a", k: "/my/a", n: 1 }, { u: "/my/b", k: "/my/b", n: 1 }]);
        const stack = syncStack("reload");
        expect(stack).toHaveLength(1);
        expect(stack[0].k).toBe(here());
        expect(getStack()).toEqual(stack);
    });

    test("back/forward to an earlier page cuts the stack there", () => {
        setStack([
            { u: "/my/a", k: "/my/a", n: 1 },
            { u: "/x", k: here(), n: 1 },
            { u: "/my/c", k: "/my/c", n: 1 },
        ]);
        const stack = syncStack("back_forward");
        expect(stack.map((entry) => entry.k)).toEqual(["/my/a", here()]);
    });

    test("back/forward to an unknown page starts over", () => {
        setStack([{ u: "/my/a", k: "/my/a", n: 1 }]);
        const stack = syncStack("back_forward");
        expect(stack.map((entry) => entry.k)).toEqual([here()]);
    });

    test("backDistance counts the current page's own entries", () => {
        expect(backDistance()).toBe(0);
        setStack([{ u: "/my/a", k: "/my/a", n: 1 }]);
        expect(backDistance()).toBe(0);
        setStack([{ u: "/my/a", k: "/my/a", n: 1 }, { u: "/x", k: here(), n: 2 }]);
        expect(backDistance()).toBe(2);
        setStack([{ u: "/my/a", k: "/my/a", n: 1 }, { u: "/my/b", k: "/my/b", n: 1 }]);
        expect(backDistance()).toBe(0);
    });

    test("backIsUseful follows the back chevron in the shell", () => {
        getFixture().innerHTML = '<div class="o_sc_app"></div>';
        expect(backIsUseful()).toBe(false);
        getFixture().innerHTML = '<div class="o_sc_app"><a href="/my" data-pk-back="1">Back</a></div>';
        expect(backIsUseful()).toBe(true);
    });

    test("task 5198 (P3a): the tab's storage keys take the pk_ prefix", () => {
        expect(NAV_STACK_KEY).toBe("pk_nav_stack:v1");
        expect(NAV_BF_RELOAD_KEY).toBe("pk_nav_bf_reload:v1");
    });
});
