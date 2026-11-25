/*
 * Task 5345 (P3c2) — pk_theme_pref: the theme preference forms
 * (form[data-pk-pref]) post with fetch and switch the theme in place.
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, mockFetch, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";

import { applyTheme } from "@bemade_portal_kit/js/pk_theme_pref";

function mount(inner, theme = "light") {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1" data-pk-theme="${theme}"
        data-pk-theme-color-light="#fafafa" data-pk-theme-color-dark="#0a0a0a">${inner}</div>`;
    return getFixture().querySelector(".o_pk_app");
}

const TOGGLE = `<form method="post" action="/pk/t/pref" data-pk-pref="1">
    <input type="hidden" name="csrf_token" value="t"/>
    <button type="submit" name="pk_t_theme" value="dark" data-pk-theme-toggle="1">t</button>
</form>`;
const SWITCH = `<form method="post" action="/pk/t/pref" data-pk-pref="1">
    <label class="o_pk_switch"><input type="checkbox" role="switch" name="pk_t_theme" value="dark" data-pk-theme-switch="1"/></label>
</form>`;

describe("pk_theme_pref", () => {
    test("applyTheme: root, body classes, theme colour, toggles and switches", () => {
        const meta = document.createElement("meta");
        meta.name = "theme-color";
        meta.content = "#fafafa";
        document.head.appendChild(meta);
        try {
            const app = mount(TOGGLE + SWITCH);
            applyTheme(app, "dark");
            expect(app.dataset.pkTheme).toBe("dark");
            expect(document.body.classList.contains("o_pk_app_body_dark")).toBe(true);
            expect(document.body.classList.contains("o_pk_app_body_light")).toBe(false);
            expect(meta.content).toBe("#0a0a0a");
            expect(app.querySelector("[data-pk-theme-toggle]").value).toBe("light");
            const input = app.querySelector("[data-pk-theme-switch]");
            expect(input.checked).toBe(true);
            expect(input.getAttribute("aria-checked")).toBe("true");
            applyTheme(app, "light");
            expect(meta.content).toBe("#fafafa");
            expect(app.querySelector("[data-pk-theme-toggle]").value).toBe("dark");
            expect(input.checked).toBe(false);
        } finally {
            meta.remove();
            document.body.classList.remove("o_pk_app_body_dark", "o_pk_app_body_light");
        }
    });

    test("a pref form posts with fetch and applies the answer's pk_theme", async () => {
        const app = mount(TOGGLE);
        const posted = [];
        mockFetch((input, init) => {
            posted.push([String(input), init.body.get("pk_t_theme")]);
            return new Response(JSON.stringify({ pk_theme: "dark" }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            });
        });
        const button = app.querySelector("[data-pk-theme-toggle]");
        app.querySelector("form").requestSubmit(button);
        await animationFrame();
        await animationFrame();
        expect(posted.length).toBe(1);
        expect(posted[0][0]).toMatch(/\/pk\/t\/pref$/);
        expect(posted[0][1]).toBe("dark");
        expect(app.dataset.pkTheme).toBe("dark");
        document.body.classList.remove("o_pk_app_body_dark", "o_pk_app_body_light");
    });

    test("the consumer's old markers are not read", async () => {
        getFixture().innerHTML = `<div class="o_pk_app" data-pk-theme="light">
            <form method="post" action="/pk/t/pref" data-sc-pref="1">
                <input type="checkbox" role="switch" name="t" value="dark" data-sc-theme-switch="1"/>
                <button type="submit" name="t" value="dark">t</button>
            </form></div>`;
        const app = getFixture().querySelector(".o_pk_app");
        let fetched = false;
        mockFetch(() => {
            fetched = true;
            return new Response("{}", { status: 200 });
        });
        const form = app.querySelector("form");
        const stop = (ev) => ev.preventDefault(); // the plain post never leaves the test page
        form.addEventListener("submit", stop);
        form.requestSubmit(form.querySelector("button"));
        form.removeEventListener("submit", stop);
        await animationFrame();
        expect(fetched).toBe(false);
        applyTheme(app, "dark");
        expect(app.querySelector("[data-sc-theme-switch]").checked).toBe(false);
        document.body.classList.remove("o_pk_app_body_dark", "o_pk_app_body_light");
    });
});
