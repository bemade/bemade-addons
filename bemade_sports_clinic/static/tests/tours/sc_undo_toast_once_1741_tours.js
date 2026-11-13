/*
 * Task 1741 — the « restored » message shows once: not again when the page
 * comes back (tests/test_undo_toast_once_1741.py, phone 390 px). Synthetic
 * data; language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const toastShown = () => {
    const toast = document.querySelector(".o_pk_toast");
    return Boolean(toast && !toast.hidden && toast.textContent.trim());
};

tours.add("sc_1741_undo_toast_once", {
    steps: () => [
        {
            content: "Archive the note (its archive icon)",
            trigger: "article.o_sc_quick_note button.o_pk_card_archive",
            expectUnloadPage: true,
            run: "click",
        },
        {
            content: "« Undo » in the toast",
            trigger: ".o_pk_toast:not([hidden]) button[data-pk-toast-action]",
            expectUnloadPage: true,
            run: "click",
        },
        {
            content: "« restored » shows once, remembered by its id",
            trigger: ".o_pk_toast:not([hidden]) .o_pk_toast_text",
            run() {
                const shown = JSON.parse(window.sessionStorage.getItem("pk_notify_shown:v1") || "[]");
                assert(shown.length >= 1, "the notification id is not remembered");
            },
        },
        {
            content: "Another tab",
            trigger: ".o_pk_tabs a[href^='/my/activities']",
            expectUnloadPage: true,
            run: "click",
        },
        {
            content: "Back",
            trigger: ".o_pk_app[data-pk-app-shell]",
            expectUnloadPage: true,
            run() {
                window.history.back();
            },
        },
        {
            content: "Back on the notes: no message",
            trigger: "article.o_sc_quick_note button.o_pk_card_archive",
            async run() {
                await pause(1500);
                assert(!toastShown(), "the message shows again");
            },
        },
    ],
});
