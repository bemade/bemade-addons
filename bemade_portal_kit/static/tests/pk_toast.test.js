/*
 * Task 5371 (P4c1) — pk_toast: the shell's toast, its session notification
 * (shown once), the « Undo » of an archive, the pending toast, the fetch-error
 * and offline toasts, and the undo offers (declarative forms + the
 * « pk_undo_offers » registry). Synthetic fixtures only.
 */
import { advanceTime, afterEach, beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

import { PENDING_TOAST_KEY } from "@bemade_portal_kit/js/pk_confirm";
import { DIRTY_KEY } from "@bemade_portal_kit/js/pk_fragments";
import {
    NOTIFY_SHOWN_KEY,
    UNDO_MS,
    UNDO_OFFERS,
    bootToasts,
    keepClearOfToast,
    offerUndos,
    showToast,
} from "@bemade_portal_kit/js/pk_toast";

const OLD_SHOWN_KEY = "sc_notify_shown:v1";

function mount(inner = "", toastAttrs = "") {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">
        <main class="pk_t_main">${inner}</main>
        <div class="o_pk_toast" role="status" aria-live="polite" hidden="" ${toastAttrs}></div>
    </div>`;
    return getFixture().querySelector(".o_pk_toast");
}

function text(toast) {
    const node = toast.querySelector(".o_pk_toast_text");
    return node ? node.textContent : "";
}

/** A form whose submit is recorded instead of navigating. */
function stubSubmit(form) {
    const calls = [];
    form.submit = () => calls.push(1);
    return calls;
}

function clearStorage() {
    for (const key of [NOTIFY_SHOWN_KEY, OLD_SHOWN_KEY, PENDING_TOAST_KEY, DIRTY_KEY]) {
        window.sessionStorage.removeItem(key);
    }
}

describe("pk_toast", () => {
    beforeEach(() => {
        patchTranslations();
        clearStorage();
    });

    afterEach(() => {
        clearStorage();
        for (const key of ["pk_t_hooked", "pk_t_rewrite"]) {
            if (registry.category(UNDO_OFFERS).contains(key)) {
                registry.category(UNDO_OFFERS).remove(key);
            }
        }
    });

    test("the names are the kit's", () => {
        expect(NOTIFY_SHOWN_KEY).toBe("pk_notify_shown:v1");
        expect(UNDO_OFFERS).toBe("pk_undo_offers");
        expect(UNDO_MS).toBe(8000);
    });

    test("showToast: message, title, tone, one action, then hides", async () => {
        const toast = mount();
        const done = [];
        showToast("Saved", "Undo", () => done.push(1), 5000, { title: "Note", tone: "success" });
        expect(toast.hidden).toBe(false);
        expect(text(toast)).toBe("Saved");
        expect(toast.querySelector(".o_pk_toast_title").textContent).toBe("Note");
        expect(toast.dataset.pkToastTone).toBe("success");
        const button = toast.querySelector("button.o_pk_toast_action[data-pk-toast-action]");
        expect(button.textContent).toBe("Undo");
        button.click();
        expect(done).toEqual([1]);
        expect(toast.hidden).toBe(true);
        // A plain toast: no tone, no action, gone after 4 s.
        showToast("Plain");
        expect(toast.hasAttribute("data-pk-toast-tone")).toBe(false);
        expect(toast.querySelector("[data-pk-toast-action]")).toBe(null);
        await advanceTime(3900);
        expect(toast.hidden).toBe(false);
        await advanceTime(200);
        expect(toast.hidden).toBe(true);
    });

    test("pk:toast shows the toast; the old sc:toast is not listened to", () => {
        const toast = mount();
        document.dispatchEvent(new CustomEvent("sc:toast", { detail: { message: "Old" } }));
        expect(toast.hidden).toBe(true);
        document.dispatchEvent(
            new CustomEvent("pk:toast", { detail: { message: "New", tone: "error", title: "T" } })
        );
        expect(toast.hidden).toBe(false);
        expect(text(toast)).toBe("New");
        expect(toast.dataset.pkToastTone).toBe("error");
    });

    test("keepClearOfToast: nothing to do while the toast is hidden", () => {
        mount('<section class="pk_t_card">card</section>');
        const card = getFixture().querySelector(".pk_t_card");
        expect(() => keepClearOfToast(card)).not.toThrow();
        expect(document.body.dataset.pkToastRoom).toBe(undefined);
        expect(() => keepClearOfToast(null, { fitOnly: true })).not.toThrow();
    });

    test("the session notification shows once, its markers cleared", () => {
        let toast = mount("", 'data-pk-notify="Added" data-pk-notify-title="Team" data-pk-notify-tone="error" data-pk-notify-id="n1"');
        bootToasts();
        expect(toast.hidden).toBe(false);
        expect(text(toast)).toBe("Added");
        expect(toast.dataset.pkToastTone).toBe("error");
        for (const name of ["pkNotify", "pkNotifyTitle", "pkNotifyTone", "pkNotifyId"]) {
            expect(toast.dataset[name]).toBe(undefined);
        }
        expect(JSON.parse(window.sessionStorage.getItem(NOTIFY_SHOWN_KEY))).toEqual(["n1"]);
        // The same page again (a cached copy): not shown a second time.
        toast = mount("", 'data-pk-notify="Added" data-pk-notify-id="n1"');
        bootToasts();
        expect(toast.hidden).toBe(true);
    });

    test("a notification already shown under the old key is not shown again", () => {
        window.sessionStorage.setItem(OLD_SHOWN_KEY, JSON.stringify(["old1"]));
        const toast = mount("", 'data-pk-notify="Archived" data-pk-notify-id="old1"');
        bootToasts();
        expect(toast.hidden).toBe(true);
        // The old list moved under the kit's key, read once.
        expect(window.sessionStorage.getItem(OLD_SHOWN_KEY)).toBe(null);
        expect(JSON.parse(window.sessionStorage.getItem(NOTIFY_SHOWN_KEY))).toEqual(["old1"]);
    });

    test("the old sc notify markers are not read", () => {
        const toast = mount("", 'data-sc-notify="Old" data-sc-notify-id="x"');
        bootToasts();
        expect(toast.hidden).toBe(true);
    });

    test("an archive's « Undo » posts the restore form and marks the session dirty", () => {
        const toast = mount(
            '<form action="/pk/t/restore" method="post" hidden="" data-pk-undo="1" data-pk-toast-action="Undo"></form>',
            'data-pk-notify="Note archived." data-pk-notify-id="u1"'
        );
        const form = getFixture().querySelector("form[data-pk-undo]");
        const submitted = stubSubmit(form);
        bootToasts();
        const button = toast.querySelector("[data-pk-toast-action]");
        expect(button.textContent).toBe("Undo");
        expect(window.sessionStorage.getItem(DIRTY_KEY)).toBe(null);
        button.click();
        expect(submitted).toEqual([1]);
        expect(Number(window.sessionStorage.getItem(DIRTY_KEY))).toBeGreaterThan(0);
    });

    test("an old sc.undo form is not an undo", () => {
        const toast = mount(
            '<form action="/pk/t/restore" method="post" hidden="" data-sc-form="sc.undo" data-sc-toast-action="Undo"></form>',
            'data-pk-notify="Archived" data-pk-notify-id="u2"'
        );
        bootToasts();
        expect(toast.hidden).toBe(false);
        expect(toast.querySelector("[data-pk-toast-action]")).toBe(null);
    });

    test("the pending toast of the previous page shows once", () => {
        window.sessionStorage.setItem(PENDING_TOAST_KEY, "You no longer have access.");
        const toast = mount();
        bootToasts();
        expect(text(toast)).toBe("You no longer have access.");
        expect(window.sessionStorage.getItem(PENDING_TOAST_KEY)).toBe(null);
    });

    test("fetch errors and the connection state are toasts", () => {
        const toast = mount();
        document.dispatchEvent(new CustomEvent("pk:fetch-error", { detail: { status: 0 } }));
        expect(text(toast)).toBe("No connection. Try again when you are back online.");
        document.dispatchEvent(new CustomEvent("pk:fetch-error", { detail: { status: 500 } }));
        expect(text(toast)).toBe("Something went wrong. Please try again.");
        window.dispatchEvent(new Event("offline"));
        expect(text(toast)).toBe("You are offline.");
        window.dispatchEvent(new Event("online"));
        expect(text(toast)).toBe("Back online.");
    });

    test("a declarative undo offer: toast, submit, parameter dropped, offered once", async () => {
        browser.history.replaceState(null, "", "/pk/t/page?made=7&keep=1");
        const toast = mount(`<form action="/pk/t/undo" method="post" hidden="" data-pk-undo-offer="pk_t_plain"
            data-pk-toast-message="Thing created" data-pk-toast-action="Undo" data-pk-undo-param="made"
            data-pk-undo-ms="20000"></form>`);
        const form = getFixture().querySelector("form[data-pk-undo-offer]");
        const submitted = stubSubmit(form);
        offerUndos();
        expect(text(toast)).toBe("Thing created");
        const url = new URL(browser.location.href);
        expect(url.searchParams.has("made")).toBe(false);
        expect(url.searchParams.get("keep")).toBe("1");
        // Its own time (data-pk-undo-ms), not the default.
        await advanceTime(UNDO_MS + 100);
        expect(toast.hidden).toBe(false);
        toast.querySelector("[data-pk-toast-action]").click();
        expect(submitted).toEqual([1]);
        // Offered once.
        offerUndos();
        expect(toast.hidden).toBe(true);
    });

    test("an offer's default time is the kit's undo time", async () => {
        const toast = mount(`<form action="/pk/t/undo" method="post" hidden="" data-pk-undo-offer="pk_t_plain"
            data-pk-toast-message="Archived" data-pk-toast-action="Undo"></form>`);
        offerUndos();
        await advanceTime(UNDO_MS - 100);
        expect(toast.hidden).toBe(false);
        await advanceTime(200);
        expect(toast.hidden).toBe(true);
    });

    test("a registered hook is called with the form, after the toast", () => {
        const calls = [];
        registry.category(UNDO_OFFERS).add("pk_t_hooked", {
            after: ({ form, root }) => calls.push([form.dataset.pkUndoOffer, root.classList.contains("o_pk_app"),
                Boolean(root.querySelector(".o_pk_toast:not([hidden])"))]),
        });
        mount(`<form action="/pk/t/undo" method="post" hidden="" data-pk-undo-offer="pk_t_hooked"
            data-pk-toast-message="Hooked" data-pk-toast-action="Undo"></form>`);
        offerUndos();
        expect(calls).toEqual([["pk_t_hooked", true, true]]);
    });

    test("a hook may rewrite the address before the parameter is dropped", () => {
        browser.history.replaceState(null, "", "/pk/t/page?created=12");
        registry.category(UNDO_OFFERS).add("pk_t_rewrite", {
            rewriteUrl(url, form) {
                url.searchParams.set("thing", url.searchParams.get("created"));
                url.searchParams.set("kind", form.dataset.pkUndoOffer);
            },
        });
        mount(`<form action="/pk/t/undo" method="post" hidden="" data-pk-undo-offer="pk_t_rewrite"
            data-pk-toast-message="Made" data-pk-toast-action="Undo" data-pk-undo-param="created"></form>`);
        offerUndos();
        const url = new URL(browser.location.href);
        expect(url.searchParams.has("created")).toBe(false);
        expect(url.searchParams.get("thing")).toBe("12");
        expect(url.searchParams.get("kind")).toBe("pk_t_rewrite");
    });

    test("an unknown kind (no registry entry) is still offered", () => {
        const toast = mount(`<form action="/pk/t/undo" method="post" hidden="" data-pk-undo-offer="pk_t_nobody"
            data-pk-toast-message="Done" data-pk-toast-action="Undo"></form>`);
        const submitted = stubSubmit(getFixture().querySelector("form"));
        bootToasts();
        expect(text(toast)).toBe("Done");
        toast.querySelector("[data-pk-toast-action]").click();
        expect(submitted).toEqual([1]);
    });

    test("an old sc undo form is not an offer", () => {
        const toast = mount(`<form action="/pk/t/undo" method="post" hidden="" data-sc-form="injury.undo"
            data-sc-toast-message="Old" data-sc-toast-action="Undo"></form>`);
        offerUndos();
        expect(toast.hidden).toBe(true);
    });
});
