/*
 * Task 1620 — « Mon compte » / « Sécurité » in the shell
 * (tests/test_account_security_tours_1620.py).
 *
 * sc_1620_account (review fixes 2026-10-18 b: pencil cards; round 2,
 * 1018c: each field autosaves, « Done » closes): Paramètres → Mon compte;
 * read cards, no company / page save / card save-cancel; the province
 * select as tall as the inputs; a new city saves on blur (« Saved » next
 * to the field); clearing the street saves (optional now); « Done » → the
 * read view; an email the core validation refuses shows its error on the
 * field and in the contact card, a good one clears it; a new phone saves
 * with Enter; no reload; back → Paramètres.
 * sc_1620_security: Paramètres → Sécurité; the core « show password » eye;
 * a wrong current password comes back with its error; the right one shows
 * the success banner; the delete-account sheet opens and closes (nothing
 * submitted); back → Paramètres.
 * Language-independent triggers (ids, names, data-sc-*).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function leave(el) {
    el.blur();
    el.dispatchEvent(new FocusEvent("blur")); // headless CI
}

function noOverflow() {
    const doc = document.documentElement;
    assert(doc.scrollWidth <= window.innerWidth + 1,
        `horizontal overflow: ${doc.scrollWidth} > ${window.innerWidth}`);
}

// The start page we come back to through history.back() reloads itself
// when it is restored from the back/forward cache (a fresh tour run, as in
// the 1579 / 1618 tours).
function reloadIfRestored() {
    window.addEventListener("pageshow", (ev) => {
        if (ev.persisted) {
            window.location.reload();
        }
    });
}

const FORM = ".o_customer_address_fill form.address_autoformat";
const CONTACT = `${FORM} section[data-sc-edit-card="account-contact"]`;
const ADDRESS = `${FORM} section[data-sc-edit-card="account-address"]`;

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function setValue(el, value) {
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    leave(el);
}

function readText(card) {
    return document.querySelector(`${card} [data-sc-edit-view="read"]`).textContent;
}

// Review fixes 2026-10-18 b: two pencil cards; round 2 (1018c): each field
// autosaves on its own, « Done » closes the card.
function fieldBox(card, name) {
    return document.querySelector(`${card} [name="${name}"]`).closest(".o_sc_field");
}

function stateOf(card, name) {
    return fieldBox(card, name).dataset.scState || "";
}

function waitState(card, name, state) {
    return waitFor(() => stateOf(card, name) === state, `${name} ${state} (is ${stateOf(card, name)})`);
}

tours.add("sc_1620_account", {
    url: "/my/app/settings",
    steps: () => [
        {
            content: "Paramètres → Mon compte",
            trigger: '#sc_account a[href$="/my/account"]',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "The shell page: two read cards, no company, no save / cancel",
            trigger: `.o_sc_app ${CONTACT} [data-sc-edit-view="read"]`,
            run() {
                window.__sc1018bNoReload = "1";
                assert(document.querySelector("a[data-sc-back]"), "no back arrow");
                assert(!document.querySelector("header#top"), "website header shown");
                assert(readText(CONTACT).includes("PC Coach"), "name not in the read view");
                assert(readText(ADDRESS).includes("Testville"), "city not in the read view");
                assert(!document.querySelector('[name="company_name"], [name="vat"], #save_address'),
                    "company fields or a page-level save");
                assert(!document.querySelector("[data-sc-account-save], [data-sc-account-cancel]"),
                    "a card save / cancel is left");
                assert(document.querySelector(`${CONTACT} [data-sc-edit-view="edit"]`).hidden, "edit open");
                noOverflow();
            },
        },
        {
            content: "Address pencil: the province select is as tall as the inputs",
            trigger: `${ADDRESS} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            trigger: `${ADDRESS}[data-sc-edit-open] select[name="state_id"]`,
            run() {
                const h = (sel) => document.querySelector(`${ADDRESS} ${sel}`).getBoundingClientRect().height;
                const city = h('input[name="city"]');
                const country = h('select[name="country_id"]');
                const state = h('select[name="state_id"]');
                assert(Math.abs(state - country) <= 2, `province ${state}px vs country ${country}px`);
                assert(Math.abs(state - city) <= 4, `province ${state}px vs input ${city}px`);
                assert(document.querySelector(`${ADDRESS} button[data-sc-edit-done]`), "no Done");
                noOverflow();
            },
        },
        {
            content: "A new city saves on its own (blur): « Saved » next to the field",
            trigger: `${ADDRESS} input[name="city"]`,
            async run() {
                setValue(this.anchor, "Synthetic City");
                await waitState(ADDRESS, "city", "saved");
                const label = fieldBox(ADDRESS, "city").querySelector("label");
                const state = label.querySelector("[data-sc-account-state]");
                assert(state && !state.hidden && state.textContent.trim(), "no visible save state in the label");
                noOverflow();
            },
        },
        {
            content: "1018c: the street is optional now — clearing it saves",
            trigger: `${ADDRESS} input[name="street"]`,
            async run() {
                setValue(this.anchor, "");
                await waitState(ADDRESS, "street", "saved");
                assert(!document.querySelector(`${ADDRESS} [data-sc-account-errors] h5`), "an address error");
            },
        },
        {
            content: "« Done » closes the card: the read view shows the new city, no reload",
            trigger: `${ADDRESS} button[data-sc-edit-done]`,
            run: "click",
        },
        {
            trigger: `${ADDRESS}:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
            async run() {
                await waitFor(() => readText(ADDRESS).includes("Synthetic City"), "address read view");
                assert(!readText(ADDRESS).includes("1 Synthetic Street"), "street still shown");
                assert(window.__sc1018bNoReload === "1", "the page reloaded");
            },
        },
        {
            content: "Contact pencil",
            trigger: `${CONTACT} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "An email the server refuses (the browser accepts it): error on the field and in the card",
            trigger: `${CONTACT}[data-sc-edit-open] input[name="email"]`,
            async run() {
                setValue(this.anchor, "coach@localhost");
                await waitState(CONTACT, "email", "error");
            },
        },
        {
            content: "The core error, inside the card being edited",
            trigger: `${CONTACT} [data-sc-account-errors] h5`,
            run() {
                assert(document.querySelector(`${FORM} input[name="email"]`).classList.contains("is-invalid"),
                    "email not flagged");
                assert(!document.querySelector(`${ADDRESS} [data-sc-account-errors] h5`), "error in the other card");
                assert(document.querySelector(`${CONTACT}[data-sc-edit-open]`), "card closed on error");
            },
        },
        {
            content: "Back to a good email: saved, the error goes",
            trigger: `${CONTACT} input[name="email"]`,
            async run() {
                setValue(this.anchor, "pc.coach@example.com");
                await waitState(CONTACT, "email", "saved");
                assert(!document.querySelector(`${CONTACT} [data-sc-account-errors] h5`), "error left");
                assert(!this.anchor.classList.contains("is-invalid"), "email still flagged");
            },
        },
        {
            content: "A new phone, saved with Enter",
            trigger: `${CONTACT} input[name="phone"]`,
            async run() {
                this.anchor.focus();
                this.anchor.value = "+1 514-555-0177";
                this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
                document.querySelector(FORM).requestSubmit();
                await waitState(CONTACT, "phone", "saved");
                assert(window.__sc1018bNoReload === "1", "the page reloaded");
            },
        },
        {
            content: "« Done »: the read view shows the new phone",
            trigger: `${CONTACT} button[data-sc-edit-done]`,
            run: "click",
        },
        {
            trigger: `${CONTACT}:not([data-sc-edit-open]) [data-sc-edit-view="read"]:not([hidden])`,
            async run() {
                await waitFor(() => readText(CONTACT).replace(/\D/g, "").includes("5145550177"),
                    "read view refreshed");
                assert(readText(ADDRESS).includes("Synthetic City"), "address lost");
                assert(window.__sc1018bNoReload === "1", "the page reloaded");
            },
        },
        {
            content: "Back → Paramètres",
            trigger: "a[data-sc-back]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "On Paramètres",
            trigger: '#sc_account a[href$="/my/security"]',
        },
    ],
});

const PW = '#sc_security_password form[action="/my/security"]';

function passwordSteps(old, next) {
    return [
        { trigger: `${PW} input[name="old"]`, run: `edit ${old}` },
        { trigger: `${PW} input[name="new1"]`, run: `edit ${next}` },
        { trigger: `${PW} input[name="new2"]`, run: `edit ${next}` },
        {
            trigger: `${PW} input[name="new2"]`,
            run() {
                leave(this.anchor);
            },
        },
        {
            content: "Change password",
            trigger: `${PW} button[type="submit"]`,
            run: "click",
            expectUnloadPage: true,
        },
    ];
}

tours.add("sc_1620_security", {
    url: "/my/app/settings",
    steps: () => [
        {
            content: "Paramètres → Sécurité",
            trigger: '#sc_account a[href$="/my/security"]',
            run(helpers) {
                reloadIfRestored();
                return helpers.click();
            },
            expectUnloadPage: true,
        },
        {
            content: "The shell page",
            trigger: `.o_sc_app .o_portal_security_body ${PW}`,
            run() {
                assert(document.querySelector("a[data-sc-back]"), "no back arrow");
                assert(document.querySelector("#portal_revoke_all_sessions_popup"), "no « log out everywhere »");
                noOverflow();
            },
        },
        {
            content: "The core eye shows the password",
            trigger: `${PW} input[name="old"] + .o_show_password`,
            run: "click",
        },
        {
            trigger: `${PW} input[name="old"][type="text"]`,
        },
        {
            trigger: `${PW} input[name="old"] + .o_show_password`,
            run: "click",
        },
        {
            trigger: `${PW} input[name="old"][type="password"]`,
        },
        ...passwordSteps("not-the-password", "pc-coach-tour-1620"),
        {
            content: "The core error, in the shell",
            trigger: '.o_sc_app [data-sc-error-for="old"]',
        },
        ...passwordSteps("pc-coach", "pc-coach-tour-1620"),
        {
            content: "Changed",
            trigger: '.o_sc_app [data-sc-section="security.password.done"]',
        },
        {
            content: "Open « Delete account »",
            trigger: 'button[data-sc-sheet-open="sc_deactivate_account_sheet"]',
            run: "click",
        },
        {
            content: "The sheet asks for the password and the login",
            trigger: 'dialog#sc_deactivate_account_sheet[open] input[name="password"]',
            run() {
                assert(document.querySelector('dialog#sc_deactivate_account_sheet[open] input[name="validation"]'),
                    "no login confirmation");
            },
        },
        {
            content: "Cancel",
            trigger: "dialog#sc_deactivate_account_sheet[open] .o_sc_form_actions [data-sc-sheet-close]",
            run: "click",
        },
        {
            content: "Closed",
            trigger: "dialog#sc_deactivate_account_sheet:not([open]):not(:visible)",
        },
        {
            content: "Back → Paramètres",
            trigger: "a[data-sc-back]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "On Paramètres",
            trigger: '#sc_account a[href$="/my/account"]',
        },
    ],
});
