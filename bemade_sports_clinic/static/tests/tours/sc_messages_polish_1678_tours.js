/*
 * Task 1678 — toasts: the title above the text, the action button beside
 * them (under them on a phone, review round 1) (tests/test_messages_polish_1678.py, 360 / 390 / 1366 px).
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

function overlaps(a, b) {
    return a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
}

// Review round 1 (2026-10-26): the text block takes the toast's width (it
// collapsed to one word per line with the action drawn over it); the action
// sits under the text, right-aligned, on a phone (≤ 480 px), beside it on a
// wider screen.
function check(withTitle, withAction) {
    return {
        content: "The toast is laid out as a column (+ the action beside / under it)",
        trigger: ".o_sc_app .o_sc_toast:not([hidden]) .o_sc_toast_text",
        run() {
            const el = document.querySelector(".o_sc_app .o_sc_toast:not([hidden])");
            const body = el.querySelector(":scope > .o_sc_toast_body");
            assert(body, "no toast body column");
            const textEl = body.querySelector(".o_sc_toast_text");
            const text = textEl.getBoundingClientRect();
            const title = body.querySelector(".o_sc_toast_title");
            if (withTitle) {
                assert(title && title === body.firstElementChild, "the title must come first");
                assert(title.getBoundingClientRect().bottom <= text.top + 1, "the title must sit above the text");
            } else {
                assert(!title, "no title expected");
            }
            const rect = el.getBoundingClientRect();
            const box = body.getBoundingClientRect();
            const style = getComputedStyle(el);
            const inner = rect.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
                - parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth);
            console.log(`sc_1678: toast ${Math.round(rect.left)}-${Math.round(rect.right)}, ` +
                `text ${Math.round(text.width)}x${Math.round(text.height)}`);
            // One word per line = a text far narrower than its toast.
            assert(text.width >= Math.min(inner, textEl.scrollWidth) - 2,
                `the text (${text.width}px) is squeezed in its toast (${inner}px)`);
            assert(textEl.scrollWidth <= textEl.clientWidth + 1, "the text overflows its block");
            const action = el.querySelector(":scope > .o_sc_toast_action");
            if (withAction) {
                assert(action, "no action button");
                const act = action.getBoundingClientRect();
                assert(!overlaps(act, box), "the action overlaps the text");
                if (window.innerWidth <= 480) {
                    assert(act.top >= box.bottom - 1, "on a phone the action sits under the text");
                    const contentRight = rect.right - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth);
                    assert(act.right >= contentRight - 2, "the action is right-aligned");
                } else {
                    assert(act.left >= box.right - 1, "the action must sit beside the text");
                }
            } else {
                assert(!action, "no action expected");
            }
            assert(rect.left >= 0 && rect.right <= window.innerWidth, "the toast overflows the screen");
            if (window.innerWidth <= 480) {
                assert(rect.left >= 15 && rect.right <= window.innerWidth - 15, "the toast keeps its margins");
            }
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
        // The owner's case: a sentence and a long action label.
        toast({ message: "You already have a timesheet for this synthetic event.",
            actionLabel: "Add another timesheet", action: noop }),
        check(false, true),
        toast({ message: "Only a message." }),
        check(false, false),
    ],
});
