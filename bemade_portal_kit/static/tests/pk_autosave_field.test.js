/*
 * Task 5382 (P4c3) — pk_autosave_field: the autosave field moved to the kit.
 * Mounted like on a page (<owl-component name="…" props="…">, the core
 * public_components interaction) with the kit alone: server saves (blur,
 * serialized, conflicts, offline queue), drafts, form mode, instant fields
 * and their undo, the 428 confirm, lost access, the replace editor, tags
 * (browse, group narrowing, group confirm, typed error), date commit rules,
 * sibling answers and the picker hook's markers. Synthetic fixtures only.
 */
import {
    advanceTime,
    afterEach,
    animationFrame,
    beforeEach,
    Deferred,
    describe,
    expect,
    getFixture,
    test,
    tick,
} from "@odoo/hoot";
import { setupInteractionWhiteList, startInteractions } from "@web/../tests/public/helpers";
import { onRpc, patchTranslations, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";

import { PkAutosaveField } from "@bemade_portal_kit/js/pk_autosave_field";
import { DRAFT_PREFIX } from "@bemade_portal_kit/js/pk_draft_store";
import { bootShell } from "@bemade_portal_kit/js/pk_shell";

const KEY = "bemade_portal_kit.pk_autosave_field";
const SCOPE = "pk_t_db:7:";
const SAVE_URL = "/my/app/save/x.thing/7";

function serverProps(extra = {}) {
    return {
        mode: "server",
        model: "x.thing",
        recordId: 7,
        field: "name",
        writeDate: "2026-01-01 10:00:00",
        label: "Name",
        inputType: "text",
        inputId: "pk_x_thing_7_name",
        value: "Alpha",
        ...extra,
    };
}

function owl(props, key = KEY) {
    const json = JSON.stringify(props).replace(/&/g, "&amp;").replace(/'/g, "&#39;");
    return `<owl-component name="${key}" props='${json}'></owl-component>`;
}

async function mount(inner) {
    setupInteractionWhiteList("public_components");
    await startInteractions(
        `<div class="o_pk_app" data-pk-app-shell="1" data-pk-db="pk_t_db" data-pk-uid="7">${inner}</div>`
    );
    // The fields mount, then render what onMounted restored.
    for (let i = 0; i < 3; i++) {
        await tick();
        await animationFrame();
    }
    return getFixture().querySelector(".o_pk_autosave");
}

async function until(check) {
    for (let i = 0; i < 60 && !check(); i++) {
        await tick();
        await animationFrame();
    }
}

function drafts() {
    return Object.keys(window.localStorage).filter((key) => key.startsWith(DRAFT_PREFIX)).sort();
}

function json(body, status = 200) {
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/**
 * The save route's double on the mock server (``onRpc``, before the mount):
 * ``answer(fields, n)`` returns the Response (or a promise of it); a throw
 * is a network failure.
 */
function route(answer, url = SAVE_URL) {
    const posts = [];
    onRpc(url, async (request) => {
        // The posted form body (URLSearchParams), read back as its encoded text.
        const body = await (await request.blob()).text();
        const fields = Object.fromEntries(new URLSearchParams(body).entries());
        posts.push({ url: new URL(request.url).pathname, fields });
        return await answer(fields, posts.length);
    });
    return posts;
}

function saved(fields, n) {
    return json({ ok: true, value: fields.value, write_date: `2026-01-02 10:00:0${n}` });
}

async function type(el, value) {
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    await animationFrame();
}

async function blur(el) {
    el.dispatchEvent(new Event("blur"));
    el.blur();
    await animationFrame();
}

function state(field) {
    return field.dataset.pkAutosaveState;
}

describe("pk_autosave_field", () => {
    let listeners = [];

    beforeEach(() => {
        patchTranslations();
        window.odoo = window.odoo || {};
        window.odoo.csrf_token = "pk-test-token";
    });

    afterEach(() => {
        for (const [type, handler] of listeners) {
            document.removeEventListener(type, handler);
        }
        listeners = [];
        for (const key of drafts()) {
            window.localStorage.removeItem(key);
        }
    });

    function watch(type) {
        const seen = [];
        const handler = (ev) => seen.push(ev.detail);
        document.addEventListener(type, handler);
        listeners.push([type, handler]);
        return seen;
    }

    // ------------------------------------------------------------ registry
    test("registered under the kit's key; a consumer's alias key mounts the same class", async () => {
        const components = registry.category("public_components");
        expect(components.get(KEY)).toBe(PkAutosaveField);
        expect(PkAutosaveField.template).toBe("bemade_portal_kit.PkAutosaveField");
        components.add("pk_test.alias_field", PkAutosaveField, { force: true });
        try {
            const field = await mount(owl(serverProps(), "pk_test.alias_field"));
            expect(field.dataset.pkAutosave).toBe("server");
            expect(field.dataset.pkAutosaveField).toBe("name");
        } finally {
            components.remove("pk_test.alias_field");
        }
    });

    test("markers: mode, field, state, restored (the kit's names only)", async () => {
        const field = await mount(owl(serverProps()));
        expect(field.dataset.pkAutosave).toBe("server");
        expect(field.dataset.pkAutosaveField).toBe("name");
        expect(field.dataset.pkAutosaveState).toBe("idle");
        expect(field.dataset.pkAutosaveRestored).toBe("0");
        expect(field.outerHTML).not.toMatch(/data-sc-|o_sc_/);
        expect(field.querySelector("input").id).toBe("pk_x_thing_7_name");
    });

    // ---------------------------------------------------------- server save
    test("server: typing does not save; leaving the field saves once (pk:saved)", async () => {
        const posts = route(saved);
        const events = watch("pk:saved");
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Beta");
        expect(state(field)).toBe("dirty");
        expect(posts).toHaveLength(0);
        await blur(input);
        await until(() => state(field) === "saved");
        expect(posts).toHaveLength(1);
        expect(posts[0].url).toBe(SAVE_URL);
        expect(posts[0].fields).toEqual({
            field: "name",
            value: "Beta",
            write_date: "2026-01-01 10:00:00",
            old_value: "Alpha",
            csrf_token: "pk-test-token",
        });
        expect(field.querySelector(".o_pk_save_state").textContent).toMatch(/^Saved · \d+:\d\d$/);
        expect(events).toHaveLength(1);
        expect(events[0].model).toBe("x.thing");
        expect(events[0].recordId).toBe(7);
        expect(events[0].field).toBe("name");
        // Leaving again without a change does not save.
        await blur(input);
        expect(posts).toHaveLength(1);
    });

    test("server: saves are serialized, the latest value goes over the fresh write date", async () => {
        const first = new Deferred();
        const posts = route((fields, n) => (n === 1 ? first : saved(fields, n)));
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Beta");
        await blur(input);
        await type(input, "Gamma");
        await blur(input);
        await type(input, "Delta");
        await blur(input);
        expect(posts).toHaveLength(1);
        first.resolve(json({ ok: true, value: "Beta", write_date: "2026-01-02 10:00:01" }));
        await until(() => state(field) === "saved");
        expect(posts).toHaveLength(2);
        expect(posts[1].fields.value).toBe("Delta");
        expect(posts[1].fields.write_date).toBe("2026-01-02 10:00:01");
        expect(posts[1].fields.old_value).toBe("Beta");
    });

    test("server: a 409 shows the conflict; « Keep mine » re-sends over theirs", async () => {
        const posts = route((fields, n) =>
            n === 1
                ? json({ current_value: "Theirs", current_write_date: "2026-01-03 09:00:00", by: "Pat" }, 409)
                : saved(fields, n)
        );
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Mine");
        await blur(input);
        await until(() => state(field) === "conflict");
        const banner = field.querySelector(".o_pk_conflict_banner");
        expect(banner).not.toBe(null);
        expect(banner.textContent).toInclude("Pat changed this field while you were typing.");
        banner.querySelectorAll("button")[0].click(); // Keep mine
        await until(() => state(field) === "saved");
        expect(posts).toHaveLength(2);
        expect(posts[1].fields.value).toBe("Mine");
        expect(posts[1].fields.write_date).toBe("2026-01-03 09:00:00");
        expect(posts[1].fields.old_value).toBe("Theirs");
        expect(field.querySelector(".o_pk_conflict_banner")).toBe(null);
    });

    test("server: « Take theirs » takes the server value without saving", async () => {
        const posts = route(() =>
            json({ current_value: "Theirs", current_write_date: "2026-01-03 09:00:00" }, 409)
        );
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Mine");
        await blur(input);
        await until(() => state(field) === "conflict");
        expect(field.querySelector(".o_pk_conflict_banner").textContent).toInclude(
            "This field was changed elsewhere while you were typing."
        );
        field.querySelector(".o_pk_conflict_banner").querySelectorAll("button")[1].click(); // Take theirs
        await animationFrame();
        expect(state(field)).toBe("saved");
        expect(field.querySelector("input").value).toBe("Theirs");
        expect(posts).toHaveLength(1);
    });

    test("server: a 409 answering a value this field sent is not a conflict", async () => {
        const posts = route((fields) =>
            json({ current_value: fields.value, current_write_date: "2026-01-03 09:00:00" }, 409)
        );
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Mine");
        await blur(input);
        await until(() => state(field) === "saved");
        expect(field.querySelector(".o_pk_conflict_banner")).toBe(null);
        expect(posts).toHaveLength(1);
    });

    test("server: offline, the value is queued on the device and replayed once back online", async () => {
        let online = false;
        const posts = route((fields, n) => {
            if (!online) {
                throw new TypeError("Failed to fetch");
            }
            return saved(fields, n);
        });
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Queued");
        await blur(input);
        await until(() => state(field) === "queued");
        expect(field.querySelector(".o_pk_save_state").textContent).toBe("Offline — pending");
        expect(drafts()).toEqual([`${DRAFT_PREFIX}${SCOPE}x.thing.7.name`]);
        online = true;
        window.dispatchEvent(new Event("online"));
        await until(() => state(field) === "saved");
        expect(posts.at(-1).fields.value).toBe("Queued");
        expect(drafts()).toEqual([]);
    });

    // ---------------------------------------------------------------- draft
    test("draft: typing is kept on the device under the caller's key", async () => {
        const field = await mount(
            owl({ mode: "draft", name: "summary", draftKey: "thing:new:5:summary", label: "Summary",
                  inputType: "textarea", inputId: "pk_draft_summary", value: "" })
        );
        const area = field.querySelector("textarea");
        expect(area.getAttribute("name")).toBe("summary");
        await type(area, "Kept");
        await advanceTime(400);
        await animationFrame();
        expect(state(field)).toBe("draft");
        expect(JSON.parse(window.localStorage.getItem(`${DRAFT_PREFIX}${SCOPE}thing:new:5:summary`)).value).toBe(
            "Kept"
        );
        expect(field.querySelector(".o_pk_save_state").textContent).toBe("Draft kept on this device");
    });

    test("draft: restored on load, then discarded", async () => {
        window.localStorage.setItem(`${DRAFT_PREFIX}${SCOPE}thing:new:5:summary`, JSON.stringify({ value: "Was typed" }));
        const field = await mount(
            owl({ mode: "draft", name: "summary", draftKey: "thing:new:5:summary", label: "Summary",
                  inputType: "textarea", value: "" })
        );
        expect(field.dataset.pkAutosaveRestored).toBe("1");
        expect(field.querySelector("textarea").value).toBe("Was typed");
        const banner = field.querySelector(".o_pk_draft_banner");
        expect(banner.textContent).toInclude("Draft restored");
        banner.querySelector("button").click();
        await animationFrame();
        expect(field.dataset.pkAutosaveRestored).toBe("0");
        expect(field.querySelector("textarea").value).toBe("");
        expect(drafts()).toEqual([]);
    });

    test("draft: dropped when the server holds the same value", async () => {
        window.localStorage.setItem(`${DRAFT_PREFIX}${SCOPE}thing:5:summary`, JSON.stringify({ value: "Same" }));
        const field = await mount(
            owl({ mode: "draft", name: "summary", draftKey: "thing:5:summary", label: "Summary", value: "Same" })
        );
        expect(field.dataset.pkAutosaveRestored).toBe("0");
        expect(drafts()).toEqual([]);
    });

    test("draft: a prefix named by data-pk-draft-clear is not restored", async () => {
        window.localStorage.setItem(`${DRAFT_PREFIX}${SCOPE}thing:new:5:summary`, JSON.stringify({ value: "Old" }));
        getFixture().innerHTML =
            '<div class="o_pk_app" data-pk-app-shell="1" data-pk-db="pk_t_db" data-pk-uid="7">' +
            '<span data-pk-draft-clear="thing:new:5:"></span></div>';
        bootShell();
        const field = await mount(
            owl({ mode: "draft", name: "summary", draftKey: "thing:new:5:summary", label: "Summary", value: "" })
        );
        expect(field.dataset.pkAutosaveRestored).toBe("0");
        expect(drafts()).toEqual([]);
    });

    test("draft: pk:form-reset on the enclosing form empties the field and its draft", async () => {
        const field = await mount(
            `<form class="pk_t_form">${owl({ mode: "draft", name: "summary", draftKey: "thing:new:9:summary",
                                           label: "Summary", value: "" })}</form>`
        );
        const input = field.querySelector("input");
        await type(input, "Some");
        await blur(input);
        expect(drafts()).toHaveLength(1);
        getFixture().querySelector(".pk_t_form").dispatchEvent(new CustomEvent("pk:form-reset", { bubbles: true }));
        await animationFrame();
        expect(drafts()).toEqual([]);
        expect(field.querySelector("input").value).toBe("");
    });

    // ----------------------------------------------------------------- form
    test("form: a pick fills the form's hidden input, nothing saved or drafted", async () => {
        const posts = route(saved);
        const field = await mount(
            `<form><input type="hidden" id="pk_t_target" name="ids" value=""/>${owl({
                mode: "form", target: "pk_t_target", label: "Groups", inputType: "tags",
                inputId: "pk_t_target_field", value: "",
                options: [["1", "Alpha"], ["2", "Beta"]] })}</form>`
        );
        const changes = [];
        const hidden = getFixture().querySelector("#pk_t_target");
        hidden.addEventListener("change", () => changes.push(hidden.value));
        const search = field.querySelector(".o_pk_tags_search");
        search.focus();
        await animationFrame();
        field.querySelector('.o_pk_tags_option[data-pk-value="2"]').click();
        await animationFrame();
        expect(hidden.value).toBe("2");
        expect(changes).toEqual(["2"]);
        expect(posts).toHaveLength(0);
        expect(drafts()).toEqual([]);
        expect(state(field)).toBe("idle");
    });

    // ------------------------------------------------------- instant + undo
    test("instant: a segmented pick saves at once and offers « Undo » (pk:toast)", async () => {
        const posts = route(saved);
        const toasts = watch("pk:toast");
        const field = await mount(
            owl(serverProps({ field: "kind", inputType: "segmented", value: "a", instant: true,
                              undoMessage: "Kind changed", options: [["a", "A"], ["b", "B"]] }))
        );
        field.querySelector('button[data-pk-value="b"]').click();
        await until(() => toasts.length === 1);
        expect(posts).toHaveLength(1);
        expect(posts[0].fields.value).toBe("b");
        expect(field.querySelector('button[data-pk-value="b"]').getAttribute("aria-pressed")).toBe("true");
        expect(toasts[0].message).toBe("Kind changed");
        expect(toasts[0].actionLabel).toBe("Undo");
        toasts[0].action();
        await until(() => posts.length === 2);
        expect(posts[1].fields.value).toBe("a");
    });

    // ----------------------------------------------------------- 428 confirm
    test("confirm (428): nothing saved until « Confirm », which re-posts with confirm=1", async () => {
        const posts = route((fields, n) =>
            fields.confirm === "1"
                ? saved(fields, n)
                : json({ confirm: true, message: "Change this?", old: "Alpha", new: "Beta", detail: "It is logged." },
                       428)
        );
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Beta");
        await blur(input);
        await until(() => state(field) === "confirm");
        const banner = field.querySelector(".o_pk_confirm_banner");
        expect(banner.querySelector(".o_pk_banner_title").textContent).toBe("Change this?");
        expect(banner.querySelector(".o_pk_confirm_change").textContent).toBe("Alpha → Beta");
        expect(banner.querySelector(".o_pk_confirm_detail").textContent).toBe("It is logged.");
        expect(field.querySelector(".o_pk_save_state").textContent).toBe("To confirm");
        banner.querySelector(".o_pk_confirm_ok").click();
        await until(() => state(field) === "saved");
        expect(posts).toHaveLength(2);
        expect(posts[1].fields.confirm).toBe("1");
        expect(field.querySelector(".o_pk_confirm_banner")).toBe(null);
    });

    test("confirm (428): « Cancel » goes back to the saved value; no detail when none is answered", async () => {
        const posts = route(() => json({ confirm: true, message: "Change this?", old: "Alpha", new: "Beta" }, 428));
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Beta");
        await blur(input);
        await until(() => state(field) === "confirm");
        expect(field.querySelector(".o_pk_confirm_detail")).toBe(null);
        field.querySelector(".o_pk_confirm_cancel").click();
        await animationFrame();
        expect(state(field)).toBe("idle");
        expect(field.querySelector("input").value).toBe("Alpha");
        expect(posts).toHaveLength(1);
    });

    // ----------------------------------------------------------- lost access
    test("lost access: a save that ends access leaves the page with its message", async () => {
        route(() => json({ ok: true, lost_access: true, message: "Removed from the list" }));
        const left = [];
        // The test page never navigates: pkLeavePage is the field's leavePage.
        patchWithCleanup(PkAutosaveField.prototype, {
            leavePage(message) {
                left.push(message);
            },
        });
        const field = await mount(owl(serverProps()));
        const input = field.querySelector("input");
        await type(input, "Beta");
        await blur(input);
        await until(() => left.length);
        expect(left).toEqual(["Removed from the list"]);
        expect(state(field)).toBe("saved");
    });

    // ------------------------------------------------------- replace editor
    test("replace: the current text above an empty editor, the kit's default labels", async () => {
        const posts = route(saved);
        const field = await mount(
            owl(serverProps({ field: "body", inputType: "textarea", value: "Old text", replace: true,
                              clearable: true }))
        );
        const captions = [...field.querySelectorAll(".o_pk_replace_caption")].map((el) => el.textContent);
        expect(captions).toEqual(["Current text", "New text"]);
        expect(field.querySelector(".o_pk_replace_current_text").textContent).toBe("Old text");
        const area = field.querySelector('textarea[data-pk-replace="new"]');
        expect(area.value).toBe("");
        // An empty editor never saves.
        area.focus();
        await blur(area);
        expect(posts).toHaveLength(0);
        const reuse = field.querySelector(".o_pk_replace_reuse");
        expect(reuse.textContent).toBe("Reuse current text");
        reuse.click();
        await animationFrame();
        expect(field.querySelector('textarea[data-pk-replace="new"]').value).toBe("Old text");
        await type(area, "Replaced");
        await blur(area);
        await until(() => state(field) === "saved");
        expect(posts[0].fields.value).toBe("Replaced");
        expect(field.querySelector(".o_pk_replace_current_text").textContent).toBe("Replaced");
        expect(field.querySelector('textarea[data-pk-replace="new"]').value).toBe("");
    });

    test("replace: the consumer's own labels", async () => {
        const field = await mount(
            owl(serverProps({ field: "body", inputType: "textarea", value: "Old text", replace: true,
                              replaceCurrentLabel: "Now", replaceNewLabel: "New entry",
                              replaceReuseLabel: "Start from it" }))
        );
        const captions = [...field.querySelectorAll(".o_pk_replace_caption")].map((el) => el.textContent);
        expect(captions).toEqual(["Now", "New entry"]);
        expect(field.querySelector(".o_pk_replace_reuse").textContent).toBe("Start from it");
    });

    // ----------------------------------------------------------------- tags
    const TAG_OPTIONS = [
        ["1", "Alpha", "Group One", "g1"],
        ["3", "Gamma", "Group One", "g1"],
        ["2", "Beta", "Group Two", "g2"],
    ];

    function tagsForm(extra = {}, value = "") {
        return `<form>
            <select id="pk_t_group"><option value="">All</option><option value="g1">One</option>
                <option value="g2">Two</option></select>
            <input type="hidden" id="pk_t_tags" value="${value}"/>
            ${owl({ mode: "form", target: "pk_t_tags", label: "Items", inputType: "tags",
                    inputId: "pk_t_tags_field", value, options: TAG_OPTIONS, groupSelect: "pk_t_group", ...extra })}
        </form>`;
    }

    test("tags: focusing opens the full list (grouped), typing narrows, Enter picks", async () => {
        const field = await mount(tagsForm());
        const search = field.querySelector(".o_pk_tags_search");
        search.focus();
        await animationFrame();
        expect(field.querySelector(".o_pk_tags_field").dataset.pkTagsOpen).toBe("1");
        expect([...field.querySelectorAll(".o_pk_tags_group")].map((el) => el.textContent)).toEqual([
            "Group One",
            "Group Two",
        ]);
        expect(field.querySelectorAll("[data-pk-tags-index]")).toHaveLength(3);
        await type(search, "gam");
        expect(field.querySelectorAll("[data-pk-tags-index]")).toHaveLength(1);
        search.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
        await animationFrame();
        expect([...field.querySelectorAll(".o_pk_tag span")].map((el) => el.textContent)).toEqual(["Gamma"]);
        expect(getFixture().querySelector("#pk_t_tags").value).toBe("3");
    });

    test("tags: typed text matching nothing is an inline error that blocks the form", async () => {
        const field = await mount(tagsForm());
        const search = field.querySelector(".o_pk_tags_search");
        await type(search, "zzz");
        field.querySelector(".o_pk_tags_field").dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
        await advanceTime(10);
        await animationFrame();
        const error = field.querySelector("[data-pk-tags-typed-error]");
        expect(error.textContent).toBe("Nothing matches « zzz »: pick it from the list.");
        expect(field.querySelector(".o_pk_tags_field").dataset.pkGuardBlock).toBe(
            "Nothing matches « zzz »: pick it from the list."
        );
        // An exact label is picked instead.
        await type(search, "beta");
        field.querySelector(".o_pk_tags_field").dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
        await advanceTime(10);
        await animationFrame();
        expect(field.querySelector("[data-pk-tags-typed-error]")).toBe(null);
        expect(getFixture().querySelector("#pk_t_tags").value).toBe("2");
    });

    test("tags: the group select narrows the options; a change that drops choices asks first (kit texts)", async () => {
        const field = await mount(tagsForm({}, "3"));
        const select = getFixture().querySelector("#pk_t_group");
        select.value = "g1";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        await animationFrame();
        field.querySelector(".o_pk_tags_search").focus();
        await animationFrame();
        expect(field.querySelectorAll("[data-pk-tags-index]")).toHaveLength(1); // Alpha (Gamma is chosen)
        field.querySelector(".o_pk_tags_search").blur();
        select.value = "g2";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        await animationFrame();
        const box = field.querySelector("[data-pk-group-confirm-box]");
        expect(box.classList.contains("o_pk_group_confirm")).toBe(true);
        expect(box.querySelector(".o_pk_group_confirm_text").textContent).toBe(
            "Changing this removes the other group's choices: Gamma."
        );
        expect(box.querySelector("[data-pk-group-confirm]").textContent).toBe("Change");
        expect(field.querySelector(".o_pk_tags_search").disabled).toBe(true);
        expect(field.querySelector(".o_pk_tags_field").dataset.pkGuardBlock).toBe(
            "Changing this removes the other group's choices: Gamma."
        );
        box.querySelector("[data-pk-group-confirm]").click();
        await animationFrame();
        expect(field.querySelector("[data-pk-group-confirm-box]")).toBe(null);
        expect(getFixture().querySelector("#pk_t_tags").value).toBe("");
        expect(field.querySelector(".o_pk_tags_field").dataset.pkGuardBlock).toBe(undefined);
    });

    test("tags: the consumer's group texts; « Cancel » puts the former group back", async () => {
        const field = await mount(
            tagsForm({ groupConfirmMessage: "Switching drops: %s.", groupConfirmLabel: "Switch anyway" }, "3")
        );
        const select = getFixture().querySelector("#pk_t_group");
        select.value = "g2";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        await animationFrame();
        const box = field.querySelector("[data-pk-group-confirm-box]");
        expect(box.querySelector(".o_pk_group_confirm_text").textContent).toBe("Switching drops: Gamma.");
        expect(box.querySelector("[data-pk-group-confirm]").textContent).toBe("Switch anyway");
        box.querySelector("[data-pk-group-cancel]").click();
        await animationFrame();
        expect(select.value).toBe("");
        expect(field.querySelector("[data-pk-group-confirm-box]")).toBe(null);
        expect(getFixture().querySelector("#pk_t_tags").value).toBe("3");
    });

    // ----------------------------------------------------------------- dates
    test("date: typed digits do not save; leaving the field (or Enter) does", async () => {
        const posts = route(saved);
        const field = await mount(
            owl(serverProps({ field: "day", inputType: "date", value: "2026-01-10" }))
        );
        const input = field.querySelector("input");
        input.dispatchEvent(new KeyboardEvent("keydown", { key: "1", bubbles: true }));
        input.value = "2026-01-11";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        await animationFrame();
        expect(posts).toHaveLength(0);
        input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
        await until(() => state(field) === "saved");
        expect(posts).toHaveLength(1);
        expect(posts[0].fields.value).toBe("2026-01-11");
    });

    test("date: a pick in the picker saves at once; an out-of-range draft is dropped", async () => {
        const posts = route(saved);
        const field = await mount(
            owl(serverProps({ field: "day", inputType: "date", value: "2026-01-10" }))
        );
        const input = field.querySelector("input");
        expect(input.getAttribute("min")).toBe("1900-01-01");
        input.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
        input.value = "2026-01-12";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        await until(() => state(field) === "saved");
        expect(posts).toHaveLength(1);
        expect(posts[0].fields.value).toBe("2026-01-12");
    });

    // --------------------------------------------------------------- siblings
    test("also: a sibling's save answers this field's choices and value", async () => {
        route((fields) =>
            json({ ok: true, value: fields.value, write_date: "2026-01-02 10:00:00",
                   also: { region: { value: "r2", options: [["", ""], ["r2", "Region Two"]] } } })
        );
        await mount(
            owl(serverProps({ field: "zone", inputType: "select", value: "z1", options: [["z1", "Z1"], ["z2", "Z2"]] })) +
            owl(serverProps({ field: "region", inputType: "select", value: "", inputId: "pk_t_region",
                              hideEmpty: true, options: [["", ""]] }))
        );
        const [zone, region] = getFixture().querySelectorAll(".o_pk_autosave");
        expect(region.hidden).toBe(true);
        const select = zone.querySelector("select");
        select.value = "z2";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        await until(() => !region.hidden);
        expect([...region.querySelectorAll("option")].map((o) => o.value)).toEqual(["", "r2"]);
        expect(region.querySelector("select").value).toBe("r2");
    });

    // ---------------------------------------------------------- picker hook
    test("picker hook: generic markers on the select, option metadata as data-pk-meta-<key>", async () => {
        const field = await mount(
            owl(serverProps({ field: "owner_id", inputType: "select", value: "", picker: true, pickerKey: "owner",
                              lockEmpty: true, options: [["", "—"], ["1", "One"], ["2", "Two"]],
                              optionMeta: { 1: { group: "4,5", parent: "9" }, 2: { group: "6" } } }))
        );
        const select = field.querySelector("select");
        expect(select.dataset.pkPicker).toBe("1");
        expect(select.dataset.pkPickerKey).toBe("owner");
        const [empty, one, two] = select.querySelectorAll("option");
        expect(empty.disabled).toBe(true);
        expect(one.dataset.pkMetaGroup).toBe("4,5");
        expect(one.dataset.pkMetaParent).toBe("9");
        expect(two.dataset.pkMetaGroup).toBe("6");
        expect(two.dataset.pkMetaParent).toBe(undefined);
        expect(field.outerHTML).not.toMatch(/data-sc-/);
    });
});
