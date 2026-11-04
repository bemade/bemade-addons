/*
 * Task 1585 — tap-to-call / tap-to-email: an emergency contact's mobile is a
 * tel: link; a pencil save of a new number moves the href in place, without
 * a reload (tests/test_app_shell_tap_links_1585.py). Language-independent
 * triggers.
 */
import { registry } from "@web/core/registry";

const CARD = '[data-sc-edit-card^="contact-"]';
const MOBILE = `${CARD} [data-sc-edit-view="read"] a[data-sc-display-href="tel"][data-sc-display$=":mobile"]`;

registry.category("web_tour.tours").add("sc_1585_tap_links", {
    steps: () => [
        {
            content: "The contact's mobile is a tel: link; mark the page to detect a reload",
            trigger: `${MOBILE}[href="tel:5550100456"]`,
            run() {
                const email = document.querySelector(
                    `${CARD} [data-sc-edit-view="read"] a[data-sc-display-href="mailto"][data-sc-display$=":email"]`
                );
                if (!email || email.getAttribute("href") !== "mailto:parent.one@example.com") {
                    throw new Error(`email link is « ${email && email.getAttribute("href")} »`);
                }
                window.__scTapNoReload = true;
            },
        },
        {
            content: "Pencil: the contact's fields appear",
            trigger: `${CARD} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "Edit the mobile",
            trigger: `${CARD} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="mobile"] input`,
            run: "edit 514 555 0177", // task 1645: a valid number, saved formatted
        },
        {
            content: "Leave the field (saves)",
            trigger: ".o_sc_appbar_title",
            run: "click",
        },
        {
            content: "Saved",
            trigger: `${CARD} .o_sc_autosave[data-sc-field="mobile"][data-sc-state="saved"]`,
        },
        {
            content: "Done: back to read mode",
            trigger: `${CARD} button[data-sc-edit-done]`,
            run: "click",
        },
        {
            content: "The link dials the new number, without a reload",
            trigger: `${MOBILE}[href="tel:+15145550177"]`,
            run() {
                if (!window.__scTapNoReload) {
                    throw new Error("the page reloaded");
                }
                const link = document.querySelector(MOBILE);
                if (link.textContent.trim() !== "+1 514-555-0177") {
                    throw new Error(`link text is « ${link.textContent} »`);
                }
            },
        },
    ],
});
