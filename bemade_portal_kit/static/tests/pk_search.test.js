/*
 * Task 5200 (P5) — pk_search: the header search moved to the kit. « / »
 * opens the sheet (never while typing in a field), typing fetches
 * /my/app/search after a debounce, the arrows move among the results and
 * Enter opens the highlighted one. Synthetic fixtures only.
 */
import { advanceTime, describe, expect, getFixture, mockFetch, test, tick } from "@odoo/hoot";

import { openSearch, PK_SEARCH_DEBOUNCE_MS } from "@bemade_portal_kit/js/pk_search";

const RESULTS = `<div class="o_pk_search_results">
    <ul><li><a href="#pk_t_one" class="pk_t_one" data-pk-search-result="1">One</a></li>
        <li><a href="#pk_t_two" class="pk_t_two" data-pk-search-result="1">Two</a></li></ul></div>`;

function mount() {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">
        <header><a href="/pk/t/list" data-pk-search-open="1">search</a><input class="pk_t_other" type="text"/></header>
        <dialog id="pk_search_sheet" data-pk-search-sheet="1">
            <input type="search" data-pk-search-input="1"/>
            <div data-pk-search-body="1"><p>Type at least 2 letters</p></div>
        </dialog>
    </div>`;
    return getFixture().querySelector("#pk_search_sheet");
}

function key(target, keyName, init = {}) {
    target.dispatchEvent(new KeyboardEvent("keydown", { key: keyName, bubbles: true, cancelable: true, ...init }));
}

describe("pk_search", () => {
    test("« / » opens the sheet, not while typing in a field", () => {
        const dialog = mount();
        key(getFixture().querySelector(".pk_t_other"), "/");
        expect(dialog.open).toBe(false);
        key(document.body, "/");
        expect(dialog.open).toBe(true);
        expect(document.activeElement).toBe(dialog.querySelector("[data-pk-search-input]"));
        dialog.close();
    });

    test("typing fetches the results once, after the debounce", async () => {
        const dialog = mount();
        const asked = [];
        mockFetch((input) => {
            asked.push(String(input));
            return new Response(RESULTS, { status: 200, headers: { "Content-Type": "text/html" } });
        });
        expect(openSearch()).toBe(true);
        const input = dialog.querySelector("[data-pk-search-input]");
        for (const value of ["o", "on", "one"]) {
            input.value = value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            await advanceTime(50);
        }
        expect(asked).toEqual([]);
        await advanceTime(PK_SEARCH_DEBOUNCE_MS);
        for (let i = 0; i < 5; i++) {
            await tick();
        }
        expect(asked.length).toBe(1);
        expect(asked[0]).toInclude("/my/app/search?q=one");
        expect(dialog.querySelectorAll("[data-pk-search-result]").length).toBe(2);
        expect(dialog.dataset.pkSearchQuery).toBe("one");
        dialog.close();
    });

    test("the arrows move the highlight, Enter opens the highlighted result", async () => {
        const dialog = mount();
        dialog.querySelector("[data-pk-search-body]").innerHTML = RESULTS;
        openSearch();
        const input = dialog.querySelector("[data-pk-search-input]");
        const clicked = [];
        for (const link of dialog.querySelectorAll("[data-pk-search-result]")) {
            link.addEventListener("click", (ev) => {
                ev.preventDefault();
                clicked.push(link.className);
            });
        }
        key(input, "ArrowDown");
        key(input, "ArrowDown");
        expect(dialog.querySelector(".pk_t_two").classList.contains("o_pk_search_active")).toBe(true);
        key(input, "ArrowUp");
        expect(dialog.querySelector(".pk_t_one").classList.contains("o_pk_search_active")).toBe(true);
        key(input, "Enter");
        expect(clicked).toEqual(["pk_t_one o_pk_search_active"]);
        dialog.close();
    });
});
