/*
 * Task 5381 (P4c2) — pk_sheets: the sheets (open, lazy body once, fresh on
 * every open, a body URL from the opener, the refetch links inside, close,
 * backdrop, open on load), the lazy <details> and the row « Details »
 * expand, with the empty, failure and loading texts. Synthetic fixtures only.
 */
import { beforeEach, describe, expect, getFixture, mockFetch, test, tick } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";

import { bootSheets, openSheet } from "@bemade_portal_kit/js/pk_sheets";

function mount(inner) {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">${inner}</div>`;
    return getFixture().querySelector(".o_pk_app");
}

function sheet(id, attrs = "", body = '<p class="o_pk_empty o_pk_lazy_loading">Loading…</p>') {
    return `<dialog id="${id}" class="o_pk_sheet" ${attrs}>
        <div class="o_pk_sheet_head"><button type="button" class="pk_t_close" data-pk-sheet-close="1">x</button></div>
        <div class="o_pk_sheet_body">${body}</div>
    </dialog>`;
}

async function settle() {
    for (let i = 0; i < 6; i++) {
        await tick();
    }
}

function answer(map, calls) {
    mockFetch((input) => {
        const url = String(input);
        calls.push(url);
        for (const [key, value] of Object.entries(map)) {
            if (url.includes(key)) {
                if (value === 500) {
                    return new Response("no", { status: 500 });
                }
                return new Response(value, { status: 200, headers: { "Content-Type": "text/html" } });
            }
        }
        return new Response("", { status: 404 });
    });
}

describe("pk_sheets", () => {
    beforeEach(() => {
        patchTranslations();
    });

    test("an opener opens its sheet; the lazy body is fetched once", async () => {
        const calls = [];
        answer({ "/pk/t/body": "<ul><li>one</li></ul>" }, calls);
        const root = mount(`<button type="button" class="pk_t_open" data-pk-sheet-open="pk_t_sheet">open</button>
            ${sheet("pk_t_sheet", 'data-pk-lazy-url="/pk/t/body"')}`);
        const dialog = root.querySelector("dialog");
        root.querySelector(".pk_t_open").click();
        await settle();
        expect(dialog.open).toBe(true);
        expect(dialog.querySelector(".o_pk_sheet_body li").textContent).toBe("one");
        expect(dialog.dataset.pkLoaded).toBe("1");
        dialog.querySelector(".pk_t_close").click();
        expect(dialog.open).toBe(false);
        root.querySelector(".pk_t_open").click();
        await settle();
        expect(calls).toHaveLength(1);
        dialog.close();
    });

    test("data-pk-lazy-fresh: fetched again on every open", async () => {
        const calls = [];
        answer({ "/pk/t/history": "<ol><li>h</li></ol>" }, calls);
        const root = mount(sheet("pk_t_hist", 'data-pk-lazy-url="/pk/t/history" data-pk-lazy-fresh="1"'));
        const dialog = root.querySelector("dialog");
        openSheet("pk_t_hist");
        await settle();
        dialog.close();
        openSheet("pk_t_hist");
        expect(dialog.querySelector(".o_pk_lazy_loading").textContent).toBe("Loading…");
        await settle();
        expect(calls).toHaveLength(2);
        expect(dialog.querySelector("li").textContent).toBe("h");
        dialog.close();
    });

    test("an empty answer reads « Nothing to show. »; a failure says how to retry", async () => {
        const calls = [];
        answer({ "/pk/t/empty": "<div></div>", "/pk/t/fail": 500 }, calls);
        const root = mount(sheet("pk_t_e", 'data-pk-lazy-url="/pk/t/empty"') + sheet("pk_t_f", 'data-pk-lazy-url="/pk/t/fail"'));
        openSheet("pk_t_e");
        await settle();
        expect(root.querySelector("#pk_t_e .o_pk_sheet_body").textContent.trim()).toBe("Nothing to show.");
        root.querySelector("#pk_t_e").close();
        openSheet("pk_t_f");
        await settle();
        const failed = root.querySelector("#pk_t_f");
        expect(failed.querySelector(".o_pk_sheet_body").textContent.trim()).toBe(
            "Could not load. Close and open again to retry."
        );
        expect(failed.dataset.pkLoaded).toBe("0");
        failed.close();
    });

    test("a [data-pk-lazy-filled] answer is content", async () => {
        answer({ "/pk/t/filled": '<div data-pk-lazy-filled="1">day</div>' }, []);
        const root = mount(sheet("pk_t_fill", 'data-pk-lazy-url="/pk/t/filled"'));
        openSheet("pk_t_fill");
        await settle();
        expect(root.querySelector("[data-pk-lazy-filled]").textContent).toBe("day");
        root.querySelector("dialog").close();
    });

    test("an opener with data-pk-sheet-url loads that body into the shared sheet", async () => {
        const calls = [];
        answer({ "/pk/t/one": "<p><a href='#'>first</a></p>", "/pk/t/two": "<p><a href='#'>second</a></p>" }, calls);
        const root = mount(`
            <a href="/pk/t/one" class="pk_t_one" data-pk-sheet-open="pk_t_shared" data-pk-sheet-url="/pk/t/one">1</a>
            <a href="/pk/t/two" class="pk_t_two" data-pk-sheet-open="pk_t_shared" data-pk-sheet-url="/pk/t/two">2</a>
            ${sheet("pk_t_shared")}`);
        const dialog = root.querySelector("dialog");
        root.querySelector(".pk_t_one").click();
        await settle();
        expect(dialog.querySelector("a").textContent).toBe("first");
        dialog.close();
        root.querySelector(".pk_t_two").click();
        await settle();
        expect(dialog.querySelector("a").textContent).toBe("second");
        expect(dialog.dataset.pkLazyFresh).toBe("1");
        dialog.close();
    });

    test("a refetch link inside the sheet reloads its body; the sheet stays open", async () => {
        const calls = [];
        answer({ "scope=mine": "<ul><li>mine</li></ul>", "/pk/t/notes": '<ul><li>all</li></ul><a class="pk_t_chip" href="/pk/t/notes?scope=mine" data-pk-sheet-refetch="1">mine</a>' }, calls);
        const root = mount(sheet("pk_t_notes", 'data-pk-lazy-url="/pk/t/notes"'));
        const dialog = root.querySelector("dialog");
        openSheet("pk_t_notes");
        await settle();
        dialog.querySelector(".pk_t_chip").click();
        await settle();
        expect(dialog.open).toBe(true);
        expect(dialog.querySelector("li").textContent).toBe("mine");
        expect(calls.at(-1)).toInclude("scope=mine");
        dialog.close();
    });

    test("a click on the backdrop closes the sheet, inside it does not", () => {
        const root = mount(sheet("pk_t_bd", "", "<p>static</p>"));
        const dialog = root.querySelector("dialog");
        openSheet("pk_t_bd");
        const rect = dialog.getBoundingClientRect();
        dialog.dispatchEvent(new MouseEvent("click", {
            bubbles: true, clientX: rect.left + 2, clientY: rect.top + 2,
        }));
        expect(dialog.open).toBe(true);
        dialog.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: rect.left - 5, clientY: rect.top - 5 }));
        expect(dialog.open).toBe(false);
    });

    test("a sheet marked to open on load opens; the old markers do nothing", () => {
        const root = mount(sheet("pk_t_load", 'data-pk-sheet-open-on-load="1"', "<p>x</p>")
            + '<button type="button" class="pk_t_old" data-sc-sheet-open="pk_t_old">o</button>'
            + sheet("pk_t_old", "", "<p>y</p>"));
        bootSheets();
        expect(root.querySelector("#pk_t_load").open).toBe(true);
        root.querySelector("#pk_t_load").close();
        root.querySelector(".pk_t_old").click();
        expect(root.querySelector("#pk_t_old").open).toBe(false);
    });

    test("a lazy <details> fetches its body on first open", async () => {
        const calls = [];
        answer({ "/pk/t/row": "<ul><li>row</li></ul>" }, calls);
        const root = mount(`<details data-pk-lazy-url="/pk/t/row"><summary>s</summary>
            <div class="o_pk_lazy_body"></div></details>`);
        const details = root.querySelector("details");
        details.open = true;
        await settle();
        expect(details.querySelector("li").textContent).toBe("row");
        details.open = false;
        await settle();
        details.open = true;
        await settle();
        expect(calls).toHaveLength(1);
    });

    test("a row « Details » shows its region, fetched once; a refresh keeps aria-expanded", async () => {
        const calls = [];
        answer({ "/pk/t/detail": "<ul><li>detail</li></ul>" }, calls);
        const root = mount(`<div class="o_pk_row_group">
            <button type="button" class="pk_t_expand" data-pk-row-expand="pk_t_region" aria-expanded="false">Details</button>
            <div id="pk_t_region" hidden="" data-pk-lazy-url="/pk/t/detail"><div class="o_pk_lazy_body"></div></div>
        </div>`);
        const toggle = root.querySelector(".pk_t_expand");
        const region = root.querySelector("#pk_t_region");
        toggle.click();
        await settle();
        expect(region.hidden).toBe(false);
        expect(toggle.getAttribute("aria-expanded")).toBe("true");
        expect(root.querySelector(".o_pk_row_group")).toHaveClass("o_pk_row_open");
        expect(region.querySelector("li").textContent).toBe("detail");
        toggle.click();
        expect(region.hidden).toBe(true);
        toggle.click();
        await settle();
        expect(calls).toHaveLength(1);
        // A refreshed row face: its fresh control follows the open region.
        toggle.setAttribute("aria-expanded", "false");
        document.dispatchEvent(new CustomEvent("pk:fragments"));
        expect(toggle.getAttribute("aria-expanded")).toBe("true");
    });
});
