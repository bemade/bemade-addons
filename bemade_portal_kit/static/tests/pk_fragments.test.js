/*
 * Task 5199 (P4a) — pk_fragments: the screen refresh moved to the kit.
 * Key patterns, matching, applying a fragment answer (swap, missing, keep,
 * lists), the consumer markers and the « back » dirty stamp (with its
 * one-time read of the old sc_dirty_at:v1 key). Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import {
    applyFragments,
    DIRTY_KEY,
    FRAGMENTS_HEADER,
    markDirty,
    matchFragmentKeys,
    pageIsStale,
    patternToRegExp,
    registerRefreshMarkers,
} from "@bemade_portal_kit/js/pk_fragments";

function mount(html, renderedAt = 1000) {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1" data-pk-rendered-at="${renderedAt}">${html}</div>`;
    return getFixture();
}

function clearDirty() {
    window.sessionStorage.removeItem(DIRTY_KEY);
    window.sessionStorage.removeItem("sc_dirty_at:v1");
}

describe("pk_fragments", () => {
    test("the wire names are the kit's", () => {
        expect(FRAGMENTS_HEADER).toBe("X-Pk-Fragments");
        expect(DIRTY_KEY).toBe("pk_dirty_at:v1");
    });

    test("a pattern's * matches within one segment only", () => {
        const re = patternToRegExp("res.partner:*:hero");
        expect(re.test("res.partner:12:hero")).toBe(true);
        expect(re.test("res.partner:12:x:hero")).toBe(false);
        expect(patternToRegExp("page:list:*").test("page:list:rows")).toBe(true);
        expect(patternToRegExp("a.b:1:x").test("aXb:1:x")).toBe(false);
    });

    test("matchFragmentKeys lists each matching key once", () => {
        mount(`<p data-pk-fragment="m:1:a"></p><p data-pk-fragment="m:1:a"></p>
               <p data-pk-fragment="m:2:a"></p><p data-pk-fragment="n:1:a"></p>
               <p data-sc-fragment="m:3:a"></p>`);
        expect(matchFragmentKeys(["m:*:a"])).toEqual(["m:1:a", "m:2:a"]);
        expect(matchFragmentKeys([])).toEqual([]);
    });

    test("applyFragments swaps, empties the missing and keeps the kept", () => {
        const root = mount(`<div data-pk-fragment="m:1:a">old</div>
               <div data-pk-fragment="m:1:b">gone</div>
               <div data-pk-fragment="m:1:c" data-pk-fragment-keep="1">kept</div>`);
        const events = [];
        const listener = (ev) => events.push(ev.detail.keys);
        document.addEventListener("pk:fragments", listener);
        const swapped = applyFragments({
            fragments: { "m:1:a": '<div data-pk-fragment="m:1:a">new</div>' },
            missing: ["m:1:b", "m:1:c"],
        });
        document.removeEventListener("pk:fragments", listener);
        expect(swapped).toEqual(["m:1:a"]);
        expect(events).toEqual([["m:1:a"]]);
        expect(root.querySelector('[data-pk-fragment="m:1:a"]').textContent).toBe("new");
        const gone = root.querySelector('[data-pk-fragment="m:1:b"]');
        expect(gone.hidden).toBe(true);
        expect(gone.textContent).toBe("");
        expect(root.querySelector('[data-pk-fragment="m:1:c"]').textContent).toBe("kept");
    });

    test("a node holding an OWL island is never swapped", () => {
        const root = mount('<div data-pk-fragment="m:1:a"><owl-component></owl-component></div>');
        expect(applyFragments({ fragments: { "m:1:a": '<div data-pk-fragment="m:1:a">x</div>' } })).toEqual([]);
        expect(root.querySelector("owl-component")).not.toBe(null);
    });

    test("a list keeps its live items, takes the fresh order and the fold state", () => {
        const root = mount(`<ul data-pk-fragment="page:l:rows" data-pk-fragment-mode="list">
                <li data-pk-fragment-item="i1">one</li><li data-pk-fragment-item="i2">two</li>
                <details data-pk-keep-open="f" open=""><summary>f</summary></details></ul>`);
        const liveOne = root.querySelector('[data-pk-fragment-item="i1"]');
        applyFragments({
            fragments: {
                "page:l:rows": `<ul data-pk-fragment="page:l:rows" data-pk-fragment-mode="list">
                    <li data-pk-fragment-item="i2">two</li><li data-pk-fragment-item="i1">fresh</li>
                    <details data-pk-keep-open="f"><summary>f</summary></details></ul>`,
            },
        });
        const items = [...root.querySelectorAll("[data-pk-fragment-item]")];
        expect(items.map((el) => el.dataset.pkFragmentItem)).toEqual(["i2", "i1"]);
        expect(items[1]).toBe(liveOne);
        expect(root.querySelector("details").open).toBe(true);
    });

    test("a list with data-pk-fragment-keep-empty stays shown without items", () => {
        const root = mount(`<ul data-pk-fragment="page:l:rows" data-pk-fragment-mode="list" data-pk-fragment-keep-empty="1">
                <li data-pk-fragment-item="i1">one</li></ul>`);
        applyFragments({
            fragments: {
                "page:l:rows": '<ul data-pk-fragment="page:l:rows" data-pk-fragment-mode="list" data-pk-fragment-keep-empty="1"><li>none</li></ul>',
            },
        });
        const list = root.querySelector('[data-pk-fragment="page:l:rows"]');
        expect(list.hidden).toBe(false);
        expect(list.textContent.trim()).toBe("none");
    });

    test("consumer markers: an item being edited holds its list; a read view keeps hidden", () => {
        registerRefreshMarkers({ editing: ["[data-test-editing]"], keepsHidden: ["[data-test-view]"] });
        const root = mount(`<ul data-pk-fragment="page:l:rows" data-pk-fragment-mode="list">
                <li data-pk-fragment-item="i1" data-test-editing="1">one</li><li data-pk-fragment-item="i2">two</li></ul>
                <div data-pk-fragment="m:1:read" data-test-view="read" hidden="">old</div>`);
        applyFragments({
            fragments: {
                "page:l:rows": `<ul data-pk-fragment="page:l:rows" data-pk-fragment-mode="list">
                    <li data-pk-fragment-item="i2">two</li></ul>`,
                "m:1:read": '<div data-pk-fragment="m:1:read" data-test-view="read">new</div>',
            },
        });
        expect([...root.querySelectorAll("[data-pk-fragment-item]")].length).toBe(2);
        const read = root.querySelector('[data-pk-fragment="m:1:read"]');
        expect(read.textContent).toBe("new");
        expect(read.hidden).toBe(true);
    });

    test("markDirty / pageIsStale compare the save with the render time", () => {
        clearDirty();
        mount("", 1000);
        expect(pageIsStale()).toBe(false);
        markDirty(900);
        expect(pageIsStale()).toBe(false);
        markDirty(1500);
        expect(window.sessionStorage.getItem(DIRTY_KEY)).toBe("1500");
        expect(pageIsStale()).toBe(true);
        markDirty(1200);
        expect(window.sessionStorage.getItem(DIRTY_KEY)).toBe("1500");
        clearDirty();
    });

    test("the old sc_dirty_at:v1 stamp is read once and moved", () => {
        clearDirty();
        window.sessionStorage.setItem("sc_dirty_at:v1", "2000");
        mount("", 1000);
        expect(pageIsStale()).toBe(true);
        expect(window.sessionStorage.getItem("sc_dirty_at:v1")).toBe(null);
        expect(window.sessionStorage.getItem(DIRTY_KEY)).toBe("2000");
        clearDirty();
    });

    test("the old data-sc-* markers are not read any more", () => {
        clearDirty();
        getFixture().innerHTML =
            '<div class="o_pk_app" data-pk-app-shell="1" data-sc-rendered-at="1000"><p data-sc-fragment="m:1:a"></p></div>';
        markDirty(5000);
        expect(pageIsStale()).toBe(false);
        expect(matchFragmentKeys(["m:*:a"])).toEqual([]);
        clearDirty();
    });
});
