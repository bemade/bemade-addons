/*
 * Task 5381 (P4c2) — pk_edit_cards: the edit cards' pencil ↔ ✓, their
 * edit-only controls (also from outside the card, data-pk-edit-for),
 * « Done », the cards that open on load, « pk:edit-open », the hashed
 * <details> and the read views a save refreshes in place (« pk:saved »).
 * Synthetic fixtures only.
 */
import { afterEach, beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";

import { bootEditCards, setCardEditing } from "@bemade_portal_kit/js/pk_edit_cards";

const PENCIL = '<svg class="o_pk_icon" viewBox="0 0 24 24"><path d="M1 1"/></svg>';

function card(key, { open = false, onLoad = false, inner = "" } = {}) {
    return `<section class="o_pk_edit_card" data-pk-edit-card="${key}"
            ${open ? 'data-pk-edit-open="1"' : ""} ${onLoad ? 'data-pk-edit-open-on-load="1"' : ""}>
        <div class="o_pk_edit_card_head">
            <button type="button" class="pk_t_toggle" data-pk-edit-toggle="1" aria-expanded="false"
                    aria-label="Edit" title="Edit">${PENCIL}</button>
            <button type="button" class="pk_t_trash" data-pk-edit-only="1" hidden="">trash</button>
        </div>
        <div data-pk-edit-view="read" ${open ? 'hidden=""' : ""}>read ${inner}</div>
        <div data-pk-edit-view="edit" ${open ? "" : 'hidden=""'}>
            <input class="pk_t_input" name="x"/>
            <button type="button" class="pk_t_done" data-pk-edit-done="1">Done</button>
        </div>
    </section>`;
}

function mount(inner, rootAttrs = "") {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1" ${rootAttrs}>${inner}</div>`;
    return getFixture().querySelector(".o_pk_app");
}

function views(el) {
    return {
        read: el.querySelector(':scope > [data-pk-edit-view="read"]'),
        edit: el.querySelector(':scope > [data-pk-edit-view="edit"]'),
    };
}

describe("pk_edit_cards", () => {
    beforeEach(() => {
        patchTranslations();
    });

    afterEach(() => {
        browser.history.replaceState(null, "", "/pk/t/page");
    });

    test("the pencil opens the card: a ✓ with the root's label, the edit-only controls show", () => {
        const root = mount(card("identity"), 'data-pk-edit-done-label="Finish it"');
        const el = root.querySelector("[data-pk-edit-card]");
        const toggle = el.querySelector(".pk_t_toggle");
        const trash = el.querySelector(".pk_t_trash");
        toggle.click();
        expect(el.dataset.pkEditOpen).toBe("1");
        expect(views(el).edit.hidden).toBe(false);
        expect(views(el).read.hidden).toBe(true);
        expect(trash.hidden).toBe(false);
        expect(toggle.getAttribute("aria-expanded")).toBe("true");
        expect(toggle.dataset.pkEditToggleDone).toBe("1");
        expect(toggle).toHaveClass("o_pk_edit_toggle_done");
        expect(toggle.getAttribute("aria-label")).toBe("Finish it");
        expect(toggle.getAttribute("title")).toBe("Finish it");
        expect(toggle.querySelector("svg").innerHTML).toInclude("M20 6L9 17l-5-5");
        // The ✓ closes it: the pencil, its label and icon come back.
        toggle.click();
        expect(el.dataset.pkEditOpen).toBe(undefined);
        expect(views(el).edit.hidden).toBe(true);
        expect(views(el).read.hidden).toBe(false);
        expect(trash.hidden).toBe(true);
        expect(toggle.getAttribute("aria-expanded")).toBe("false");
        expect(toggle.dataset.pkEditToggleDone).toBe(undefined);
        expect(toggle).not.toHaveClass("o_pk_edit_toggle_done");
        expect(toggle.getAttribute("aria-label")).toBe("Edit");
        expect(toggle.querySelector("svg").innerHTML).toBe('<path d="M1 1"></path>');
    });

    test("without a label on the root, the kit's own text", () => {
        const root = mount(card("identity"));
        const toggle = root.querySelector(".pk_t_toggle");
        toggle.click();
        expect(toggle.getAttribute("aria-label")).toBe("Finish editing");
    });

    test("the old markers do nothing", () => {
        const root = mount(`<section data-pk-edit-card="old">
            <button type="button" class="pk_t_old" data-sc-edit-toggle="1">e</button>
            <div data-sc-edit-view="edit" hidden="">edit</div></section>`);
        root.querySelector(".pk_t_old").click();
        expect(root.querySelector("[data-pk-edit-card]").dataset.pkEditOpen).toBe(undefined);
        expect(root.querySelector('[data-sc-edit-view="edit"]').hidden).toBe(true);
    });

    test("« Done » closes the card and asks for the refresh at once", () => {
        const root = mount(card("identity", { open: true }));
        const el = root.querySelector("[data-pk-edit-card]");
        const asked = [];
        const listener = () => asked.push(1);
        document.addEventListener("pk:refresh-now", listener);
        el.querySelector(".pk_t_done").click();
        document.removeEventListener("pk:refresh-now", listener);
        expect(el.dataset.pkEditOpen).toBe(undefined);
        expect(views(el).edit.hidden).toBe(true);
        expect(asked).toEqual([1]);
    });

    test("a control outside the card opens it (data-pk-edit-for)", () => {
        const root = mount(`<section data-pk-edit-card="injury">
            <header>
                <button type="button" class="pk_t_bar_pencil" data-pk-edit-toggle="1" data-pk-edit-for="details">e</button>
                <button type="button" class="pk_t_bar_trash" data-pk-edit-only="1" data-pk-edit-for="details" hidden="">t</button>
            </header>
            <details class="pk_t_fold">
                <summary>more</summary>
                ${card("details")}
            </details>
        </section>`);
        const inner = root.querySelector('[data-pk-edit-card="details"]');
        const outer = root.querySelector('[data-pk-edit-card="injury"]');
        root.querySelector(".pk_t_bar_pencil").click();
        expect(inner.dataset.pkEditOpen).toBe("1");
        expect(outer.dataset.pkEditOpen).toBe(undefined);
        // A folded card unfolds first.
        expect(root.querySelector(".pk_t_fold").open).toBe(true);
        expect(root.querySelector(".pk_t_bar_trash").hidden).toBe(false);
        expect(root.querySelector(".pk_t_bar_pencil").dataset.pkEditToggleDone).toBe("1");
        root.querySelector(".pk_t_bar_pencil").click();
        expect(inner.dataset.pkEditOpen).toBe(undefined);
        expect(root.querySelector(".pk_t_bar_trash").hidden).toBe(true);
    });

    test("setCardEditing is exported and announces the edit view", () => {
        const root = mount(card("identity"));
        const el = root.querySelector("[data-pk-edit-card]");
        const opened = [];
        el.addEventListener("pk:edit-view-open", () => opened.push(1));
        setCardEditing(el, true);
        expect(el.dataset.pkEditOpen).toBe("1");
        expect(opened).toEqual([1]);
        setCardEditing(el, false);
        expect(el.dataset.pkEditOpen).toBe(undefined);
    });

    test("a card marked to open on load opens; a rendered-open card shows its ✓", () => {
        const root = mount(card("epipen", { onLoad: true }) + card("created", { open: true }));
        bootEditCards();
        const epipen = root.querySelector('[data-pk-edit-card="epipen"]');
        const created = root.querySelector('[data-pk-edit-card="created"]');
        expect(epipen.dataset.pkEditOpen).toBe("1");
        expect(views(epipen).edit.hidden).toBe(false);
        expect(created.querySelector(".pk_t_toggle").dataset.pkEditToggleDone).toBe("1");
        expect(created.querySelector(".pk_t_trash").hidden).toBe(false);
    });

    test("pk:edit-open opens the card the event comes from; sc:edit-open does not", () => {
        const root = mount(card("a") + card("b"));
        const a = root.querySelector('[data-pk-edit-card="a"]');
        const b = root.querySelector('[data-pk-edit-card="b"]');
        a.querySelector(".pk_t_input").dispatchEvent(new CustomEvent("sc:edit-open", { bubbles: true }));
        expect(a.dataset.pkEditOpen).toBe(undefined);
        a.querySelector(".pk_t_input").dispatchEvent(new CustomEvent("pk:edit-open", { bubbles: true }));
        expect(a.dataset.pkEditOpen).toBe("1");
        expect(b.dataset.pkEditOpen).toBe(undefined);
    });

    test("a refreshed fragment brings the open card's controls back in sync", () => {
        const root = mount(card("a", { open: true }));
        const trash = root.querySelector(".pk_t_trash");
        trash.hidden = true;
        document.dispatchEvent(new CustomEvent("pk:fragments"));
        expect(trash.hidden).toBe(false);
    });

    test("a link to #<details id> opens that <details>", () => {
        mount('<details id="pk_t_add"><summary>Add</summary>form</details>');
        browser.history.replaceState(null, "", "/pk/t/page#pk_t_add");
        bootEditCards();
        expect(getFixture().querySelector("#pk_t_add").open).toBe(true);
    });

    test("pk:saved refreshes the read views in place, hide-empty holders follow", () => {
        mount(`<dl>
            <dd><span data-pk-display="res.partner:7:name">Old</span></dd>
            <dd><a class="pk_t_phone" data-pk-display="res.partner:7:phone" data-pk-display-href="tel" href="tel:1">1</a></dd>
            <span class="pk_t_holder" data-pk-display-hide-empty="1">
                <span data-pk-display="res.partner:7:date_end">2026-01-01</span>
            </span>
            <span class="pk_t_old" data-sc-display="res.partner:7:name">Old</span>
        </dl>`);
        document.dispatchEvent(new CustomEvent("pk:saved", {
            detail: {
                model: "res.partner", recordId: 7, field: "name",
                result: { display: "New", also: { phone: { display: "+1 555 0100" }, date_end: { display: "" } } },
            },
        }));
        const fixture = getFixture();
        expect(fixture.querySelector('[data-pk-display="res.partner:7:name"]').textContent).toBe("New");
        expect(fixture.querySelector(".pk_t_phone").getAttribute("href")).toBe("tel:+15550100");
        expect(fixture.querySelector(".pk_t_holder").hidden).toBe(true);
        expect(fixture.querySelector(".pk_t_old").textContent).toBe("Old");
    });
});
