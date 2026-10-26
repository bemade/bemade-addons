/*
 * Task 1678 — toasts: the title above the text, the action button beside
 * them (tests/test_messages_polish_1678.py, 360 / 390 / 1366 px).
 * Real phone taps stay UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function toast(detail) {
    return {
        content: `Show a toast (${detail.title ? "title" : "no title"}, ${detail.actionLabel ? "action" : "no action"})`,
        trigger: ".o_sc_app",
        run() {
            document.dispatchEvent(new CustomEvent("sc:toast", { detail }));
        },
    };
}

function check(withTitle, withAction) {
    return {
        content: "The toast is laid out as a column (+ the action beside it)",
        trigger: ".o_sc_app .o_sc_toast:not([hidden]) .o_sc_toast_text",
        run() {
            const el = document.querySelector(".o_sc_app .o_sc_toast:not([hidden])");
            const body = el.querySelector(":scope > .o_sc_toast_body");
            assert(body, "no toast body column");
            const text = body.querySelector(".o_sc_toast_text").getBoundingClientRect();
            const title = body.querySelector(".o_sc_toast_title");
            if (withTitle) {
                assert(title && title === body.firstElementChild, "the title must come first");
                assert(title.getBoundingClientRect().bottom <= text.top + 1, "the title must sit above the text");
            } else {
                assert(!title, "no title expected");
            }
            const action = el.querySelector(":scope > .o_sc_toast_action");
            if (withAction) {
                assert(action, "no action button");
                const box = body.getBoundingClientRect();
                assert(action.getBoundingClientRect().left >= box.right - 1, "the action must sit beside the text");
            } else {
                assert(!action, "no action expected");
            }
            const rect = el.getBoundingClientRect();
            assert(rect.left >= 0 && rect.right <= window.innerWidth, "the toast overflows the screen");
        },
    };
}

const noop = () => {};

registry.category("web_tour.tours").add("sc_1678_toast_stacked", {
    steps: () => [
        toast({ title: "Synthetic title", message: "A synthetic message long enough to wrap on a phone screen.",
            actionLabel: "Undo", action: noop }),
        check(true, true),
        toast({ title: "Synthetic title", message: "A synthetic message." }),
        check(true, false),
        toast({ message: "Only a message.", actionLabel: "Undo", action: noop }),
        check(false, true),
        toast({ message: "Only a message." }),
        check(false, false),
    ],
});
