/*
 * Task 5197 (P2) — pk_fetch: the CSRF token and the error path.
 * Synthetic fixtures only.
 */
import { afterEach, beforeEach, describe, expect, getFixture, mockFetch, test } from "@odoo/hoot";

import { csrfToken, PkFetchError, pkFetch } from "@bemade_portal_kit/js/pk_fetch";

describe("pk_fetch", () => {
    let savedToken;

    beforeEach(() => {
        window.odoo = window.odoo || {};
        savedToken = window.odoo.csrf_token;
    });

    afterEach(() => {
        window.odoo.csrf_token = savedToken;
    });

    test("the CSRF token comes from odoo.csrf_token first", () => {
        window.odoo.csrf_token = "token-from-odoo";
        getFixture().innerHTML = '<input name="csrf_token" value="token-from-form"/>';
        expect(csrfToken()).toBe("token-from-odoo");
    });

    test("the CSRF token falls back to the form input", () => {
        window.odoo.csrf_token = "";
        getFixture().innerHTML = '<input name="csrf_token" value="token-from-form"/>';
        expect(csrfToken()).toBe("token-from-form");
    });

    test("a POST carries the CSRF token, form-encoded", async () => {
        window.odoo.csrf_token = "token-from-odoo";
        let body = null;
        mockFetch((input, init) => {
            body = init.body;
            return new Response(JSON.stringify({ ok: true }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            });
        });
        const result = await pkFetch("/pk/test/save", { method: "POST", data: { name: "Alpha" } });
        expect(result).toEqual({ ok: true });
        expect(body.get("csrf_token")).toBe("token-from-odoo");
        expect(body.get("name")).toBe("Alpha");
    });

    test("a failure dispatches sc:fetch-error and throws PkFetchError", async () => {
        mockFetch(() => new Response(JSON.stringify({ error: "nope" }), { status: 500 }));
        const seen = [];
        const onError = (ev) => seen.push(ev.detail);
        document.addEventListener("sc:fetch-error", onError);
        let thrown = null;
        try {
            await pkFetch("/pk/test/fail");
        } catch (err) {
            thrown = err;
        } finally {
            document.removeEventListener("sc:fetch-error", onError);
        }
        expect(thrown).toBeInstanceOf(PkFetchError);
        expect(thrown.status).toBe(500);
        expect(thrown.reason).toBe("http");
        expect(seen).toHaveLength(1);
        expect(seen[0]).toBe(thrown);
    });

    test("toast: false throws without dispatching", async () => {
        mockFetch(() => new Response("", { status: 404 }));
        const seen = [];
        const onError = (ev) => seen.push(ev.detail);
        document.addEventListener("sc:fetch-error", onError);
        let thrown = null;
        try {
            await pkFetch("/pk/test/missing", { toast: false });
        } catch (err) {
            thrown = err;
        } finally {
            document.removeEventListener("sc:fetch-error", onError);
        }
        expect(thrown).toBeInstanceOf(PkFetchError);
        expect(seen).toHaveLength(0);
    });
});
