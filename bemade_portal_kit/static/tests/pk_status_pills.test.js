/*
 * Task 5370 (P4b) — pk_status_pills: the status pill dropdowns moved to the
 * kit. A pick posts the save, a conflict says so, the « Undo » re-posts the
 * previous value, a pick with an action is handed off (« pk:pill-action »),
 * and the toasts go out as « pk:toast ». Synthetic fixtures only.
 */
import { afterEach, beforeEach, describe, expect, getFixture, mockFetch, test, tick } from "@odoo/hoot";

import { patchTranslations } from "@web/../tests/web_test_helpers";

import { PILL_SELECTOR } from "@bemade_portal_kit/js/pk_status_pills";

function mount(prefix = "pk") {
    getFixture().innerHTML = `<div class="o_pk_app">
        <span class="o_pk_pill_select_wrap" data-${prefix}-pill-select="1" data-${prefix}-pill-key="state"
              data-${prefix}-model="x.thing" data-${prefix}-record-id="7" data-${prefix}-field="state"
              data-${prefix}-write-date="2026-01-01 10:00:00" data-${prefix}-old-value="a"
              data-${prefix}-undo-message="State changed">
            <button type="button" class="o_pk_pill_select" data-pk-menu-toggle="1" aria-haspopup="menu"
                    aria-expanded="false" aria-controls="pk-pill-x-thing-7-state">A</button>
            <span id="pk-pill-x-thing-7-state" class="o_pk_menu_popup" role="menu" data-pk-menu-popup="1" hidden="">
                <button type="button" role="menuitemradio" class="pk_t_a" aria-checked="true"
                        data-${prefix}-pill-value="a" data-${prefix}-pill-post="a">A</button>
                <button type="button" role="menuitemradio" class="pk_t_b" aria-checked="false"
                        data-${prefix}-pill-value="b" data-${prefix}-pill-post="b">B</button>
                <button type="button" role="menuitemradio" class="pk_t_c" aria-checked="false"
                        data-${prefix}-pill-value="c" data-${prefix}-pill-action="thing.verify"
                        data-${prefix}-pill-from="a">C</button>
            </span>
        </span></div>`;
    return getFixture().querySelector(".o_pk_pill_select_wrap");
}

function listen(type) {
    const seen = [];
    const handler = (ev) => seen.push(ev.detail);
    document.addEventListener(type, handler);
    seen.stop = () => document.removeEventListener(type, handler);
    return seen;
}

async function until(check) {
    for (let i = 0; i < 50 && !check(); i++) {
        await tick();
    }
}

describe("pk_status_pills", () => {
    let listeners = [];

    beforeEach(() => {
        patchTranslations();
        window.odoo = window.odoo || {};
        window.odoo.csrf_token = "pk-test-token";
    });

    afterEach(() => {
        for (const seen of listeners) {
            seen.stop();
        }
        listeners = [];
    });

    function watch(type) {
        const seen = listen(type);
        listeners.push(seen);
        return seen;
    }

    test("the pill marker is the kit's", () => {
        expect(PILL_SELECTOR).toBe("[data-pk-pill-select]");
    });

    test("a pick posts the save, announces pk:saved and offers an undo (pk:toast)", async () => {
        const pill = mount();
        const posts = [];
        mockFetch((input, init) => {
            if ((init.method || "GET").toUpperCase() !== "POST") {
                return new Response(JSON.stringify({ fragments: {}, missing: [] }), { status: 200 });
            }
            posts.push({ url: String(input), body: init.body });
            const value = init.body.get("value");
            return new Response(
                JSON.stringify({ value, write_date: `2026-01-02 10:00:0${posts.length}` }),
                { status: 200, headers: { "Content-Type": "application/json" } }
            );
        });
        const saved = watch("pk:saved");
        const toasts = watch("pk:toast");
        const oldToasts = watch("sc:toast");
        pill.querySelector(".pk_t_b").click();
        await until(() => toasts.length);
        expect(posts).toHaveLength(1);
        expect(posts[0].url).toInclude("/my/app/save/x.thing/7");
        expect(posts[0].body.get("field")).toBe("state");
        expect(posts[0].body.get("value")).toBe("b");
        expect(posts[0].body.get("write_date")).toBe("2026-01-01 10:00:00");
        expect(posts[0].body.get("old_value")).toBe("a");
        expect(saved).toHaveLength(1);
        expect(saved[0].model).toBe("x.thing");
        expect(saved[0].recordId).toBe(7);
        expect(pill.dataset.pkWriteDate).toBe("2026-01-02 10:00:01");
        expect(pill.dataset.pkOldValue).toBe("b");
        expect(toasts[0].message).toBe("State changed");
        expect(toasts[0].actionLabel).toBe("Undo");
        expect(oldToasts).toHaveLength(0);
        // « Undo »: the previous value, with the fresh write date.
        toasts[0].action();
        await until(() => posts.length > 1);
        expect(posts[1].body.get("value")).toBe("a");
        expect(posts[1].body.get("write_date")).toBe("2026-01-02 10:00:01");
        expect(posts[1].body.get("old_value")).toBe("b");
    });

    test("a conflict (409): « Changed elsewhere », no undo", async () => {
        const pill = mount();
        mockFetch((input, init) => {
            if ((init.method || "GET").toUpperCase() !== "POST") {
                return new Response(JSON.stringify({ fragments: {}, missing: [] }), { status: 200 });
            }
            return new Response(JSON.stringify({ message: "x" }), {
                status: 409,
                headers: { "Content-Type": "application/json" },
            });
        });
        const toasts = watch("pk:toast");
        pill.querySelector(".pk_t_b").click();
        await until(() => toasts.length);
        expect(toasts).toHaveLength(1);
        expect(toasts[0].message).toBe("Changed elsewhere");
        expect(toasts[0].action).toBe(undefined);
        expect(pill.getAttribute("aria-busy")).toBe(null);
    });

    test("a pick with an action is handed off as pk:pill-action, nothing posted", async () => {
        const pill = mount();
        let fetched = 0;
        mockFetch(() => {
            fetched++;
            return new Response("{}", { status: 200 });
        });
        const actions = watch("pk:pill-action");
        const oldActions = watch("sc:pill-action");
        pill.querySelector(".pk_t_c").click();
        await tick();
        expect(fetched).toBe(0);
        expect(oldActions).toHaveLength(0);
        expect(actions).toHaveLength(1);
        expect(actions[0].action).toBe("thing.verify");
        expect(actions[0].value).toBe("c");
        expect(actions[0].from).toBe("a");
        expect(actions[0].model).toBe("x.thing");
        expect(actions[0].recordId).toBe(7);
        expect(actions[0].pill).toBe(pill);
    });

    test("the checked item posts nothing", async () => {
        const pill = mount();
        let fetched = 0;
        mockFetch(() => {
            fetched++;
            return new Response("{}", { status: 200 });
        });
        pill.querySelector(".pk_t_a").click();
        await tick();
        expect(fetched).toBe(0);
    });

    test("the old data-sc-pill-* markers are not read", async () => {
        const pill = mount("sc");
        let fetched = 0;
        mockFetch(() => {
            fetched++;
            return new Response("{}", { status: 200 });
        });
        pill.querySelector(".pk_t_b").click();
        await tick();
        expect(fetched).toBe(0);
    });
});
