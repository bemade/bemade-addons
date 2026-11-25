/*
 * Task 5370 (P4b) — pk_form_guard: the app-wide form rule moved to the kit.
 * Each built-in rule, a rule a consumer registers (« pk_guard_rules »), the
 * manual opt-out, the error params from the texts host, the refusal marker
 * (a banner's text or a toast's message) and the field errors of a fetched
 * page. Synthetic fixtures only.
 */
import { afterEach, beforeEach, describe, expect, getFixture, mockFetch, test, tick } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";

import {
    GUARD_HEADER,
    guardBoot,
    guardErrorParams,
    guardReason,
    guardRefresh,
    guardRefusal,
} from "@bemade_portal_kit/js/pk_form_guard";

const TEXTS = '<span hidden="" data-pk-guard-texts="1" data-missing="Fill in:" data-generic="Not saved." data-offline="Offline."></span>';

function mount(formHtml, { texts = TEXTS, formAttrs = 'data-pk-guard="1"' } = {}) {
    getFixture().innerHTML = `<div class="o_pk_app">${texts}
        <form action="/pk/test/form" method="post" class="o_pk_form" ${formAttrs}>
            ${formHtml}
            <div class="o_pk_form_actions"><button type="submit" class="o_pk_btn">Save</button></div>
        </form></div>`;
    return getFixture().querySelector("form");
}

function fieldHtml(name, label, attrs = "") {
    return `<div class="o_pk_field"><label for="pk_t_${name}">${label}</label>
        <input id="pk_t_${name}" name="${name}" ${attrs}/></div>`;
}

async function until(check) {
    for (let i = 0; i < 50 && !check(); i++) {
        await tick();
    }
}

describe("pk_form_guard", () => {
    beforeEach(() => patchTranslations());

    afterEach(() => {
        for (const key of ["pk_test_even", "pk_test_tag"]) {
            if (registry.category("pk_guard_rules").contains(key)) {
                registry.category("pk_guard_rules").remove(key);
            }
        }
    });

    test("the header is the kit's", () => {
        expect(GUARD_HEADER).toBe("X-Pk-Guard");
    });

    test("the kit registers the four built-in rules", () => {
        const rules = registry.category("pk_guard_rules");
        for (const key of ["required", "together", "after", "not_future"]) {
            expect(rules.contains(key)).toBe(true);
        }
        expect(rules.contains("assign")).toBe(false);
    });

    test("a required field: its label, after the texts host's prefix", () => {
        const form = mount(fieldHtml("title", "Title", "required=\"\"") + fieldHtml("code", "Code", 'data-pk-required="The code"'));
        expect(guardReason(form)).toBe("Fill in: Title, The code");
        form.querySelector('[name="title"]').value = "x";
        form.querySelector('[name="code"]').value = "y";
        expect(guardReason(form)).toBe("");
    });

    test("without a texts host the kit's own prefix applies", () => {
        const form = mount(fieldHtml("title", "Title", "required=\"\""), { texts: "" });
        expect(guardReason(form)).toBe("Complete: Title");
    });

    test("the old data-sc-required marker is not read", () => {
        const form = mount(fieldHtml("code", "Code", 'data-sc-required="1"'));
        expect(guardReason(form)).toBe("");
    });

    test("rule « required »: a named field", () => {
        const rules = JSON.stringify([{ type: "required", field: "note", label: "Note" }]);
        const form = mount('<input type="hidden" name="note" value=""/>', {
            formAttrs: `data-pk-guard="1" data-pk-guard-rules='${rules}'`,
        });
        expect(guardReason(form)).toBe("Fill in: Note");
        form.querySelector('[name="note"]').value = "x";
        expect(guardReason(form)).toBe("");
    });

    test("rule « together »: all or none, its message from a keyed span", () => {
        const rules = JSON.stringify([{ type: "together", fields: ["a", "b"], key: "pair" }]);
        const form = mount(
            fieldHtml("a", "A") + fieldHtml("b", "B") + '<span hidden="" data-pk-guard-msg="pair">Both or none.</span>',
            { formAttrs: `data-pk-guard="1" data-pk-guard-rules='${rules}'` }
        );
        expect(guardReason(form)).toBe("");
        form.querySelector('[name="a"]').value = "x";
        expect(guardReason(form)).toBe("Both or none.");
        form.querySelector('[name="b"]').value = "y";
        expect(guardReason(form)).toBe("");
    });

    test("rule « after »: not before the other date", () => {
        const rules = JSON.stringify([{ type: "after", field: "end", than: "start", message: "End before start." }]);
        const form = mount(fieldHtml("start", "Start") + fieldHtml("end", "End"), {
            formAttrs: `data-pk-guard="1" data-pk-guard-rules='${rules}'`,
        });
        form.querySelector('[name="start"]').value = "2026-05-10";
        form.querySelector('[name="end"]').value = "2026-05-09";
        expect(guardReason(form)).toBe("End before start.");
        form.querySelector('[name="end"]').value = "2026-05-10";
        expect(guardReason(form)).toBe("");
    });

    test("rule « not_future »: a date not after today", () => {
        const rules = JSON.stringify([{ type: "not_future", field: "day", message: "Not in the future." }]);
        const form = mount(fieldHtml("day", "Day"), { formAttrs: `data-pk-guard="1" data-pk-guard-rules='${rules}'` });
        form.querySelector('[name="day"]').value = "2999-01-01";
        expect(guardReason(form)).toBe("Not in the future.");
        form.querySelector('[name="day"]').value = "2000-01-01";
        expect(guardReason(form)).toBe("");
    });

    test("a rule a consumer registers: check and missing", () => {
        registry.category("pk_guard_rules").add("pk_test_even", {
            check: (rule, ctx) => (Number(ctx.named(rule.field).value) % 2 ? ctx.message(rule) : ""),
        });
        registry.category("pk_guard_rules").add("pk_test_tag", {
            missing: (rule, ctx) => (ctx.form.querySelector("[data-pk-test-tag]") ? "" : rule.label),
        });
        const rules = JSON.stringify([
            { type: "pk_test_even", field: "n", message: "An even number." },
            { type: "unknown_type", field: "n" },
        ]);
        const form = mount(fieldHtml("n", "N"), { formAttrs: `data-pk-guard="1" data-pk-guard-rules='${rules}'` });
        form.querySelector('[name="n"]').value = "3";
        expect(guardReason(form)).toBe("An even number.");
        form.querySelector('[name="n"]').value = "4";
        expect(guardReason(form)).toBe("");
        form.dataset.pkGuardRules = JSON.stringify([{ type: "pk_test_tag", label: "A tag" }]);
        expect(guardReason(form)).toBe("Fill in: A tag");
    });

    test("a field's block (data-pk-guard-block) holds the form", () => {
        const form = mount('<div class="o_pk_tags_field" data-pk-guard-block="Pick a tag first."></div>');
        expect(guardReason(form)).toBe("Pick a tag first.");
    });

    test("boot: novalidate, the slots, a greyed submit with its reason", () => {
        const form = mount(fieldHtml("title", "Title", "required=\"\""));
        guardBoot(getFixture());
        expect(form.noValidate).toBe(true);
        const submit = form.querySelector('button[type="submit"]');
        const line = form.querySelector("[data-pk-guard-reason]");
        expect(line.classList.contains("o_pk_guard_reason")).toBe(true);
        expect(form.querySelector("[data-pk-guard-error]")).not.toBe(null);
        expect(submit.getAttribute("aria-disabled")).toBe("true");
        expect(submit.getAttribute("aria-describedby")).toBe(line.id);
        expect(line.textContent).toBe("Fill in: Title");
        expect(line.hidden).toBe(false);
    });

    test("a submit with a reason is stopped and flashes the reason line", () => {
        const form = mount(fieldHtml("title", "Title", "required=\"\""));
        guardBoot(getFixture());
        let reachedForm = false;
        form.addEventListener("submit", (ev) => {
            reachedForm = true;
            ev.preventDefault();
        });
        form.requestSubmit();
        expect(reachedForm).toBe(false);
        expect(form.querySelector("[data-pk-guard-reason]").classList.contains("o_pk_reason_flash")).toBe(true);
    });

    test("the manual opt-out: no boot, no stop; guardRefresh still serves the owner", () => {
        // novalidate: the browser's own check would hold the submit first.
        const form = mount(fieldHtml("title", "Title", "required=\"\""), {
            formAttrs: 'data-pk-guard="1" data-pk-guard-mode="manual" novalidate=""',
        });
        guardBoot(getFixture());
        expect(form.querySelector("[data-pk-guard-reason]")).toBe(null);
        expect(form.querySelector("[data-pk-guard-error]")).toBe(null);
        let prevented = null;
        form.addEventListener("submit", (ev) => {
            prevented = ev.defaultPrevented;
            ev.preventDefault();
        });
        form.requestSubmit();
        expect(prevented).toBe(false);
        form.insertAdjacentHTML("beforeend", '<p id="pk_t_line" data-pk-guard-reason="1" hidden=""></p>');
        guardRefresh(form, "Owner's reason");
        expect(form.querySelector("#pk_t_line").textContent).toBe("Owner's reason");
    });

    test("error params: « error » by default, more from the texts host", () => {
        mount("", { texts: "" });
        expect(guardErrorParams()).toEqual(["error"]);
        expect(guardRefusal("/my/x?error=Refused", "", 200)).toEqual({ message: "Refused" });
        expect(guardRefusal("/my/x?other_error=Refused", "", 200)).toBe(null);
        mount("", {
            texts: '<span hidden="" data-pk-guard-texts="1" data-pk-guard-error-params="error other_error"></span>',
        });
        expect(guardErrorParams()).toEqual(["error", "other_error"]);
        expect(guardRefusal("/my/x?other_error=Refused", "", 200)).toEqual({ message: "Refused" });
    });

    test("refusal markers: a banner's text, a field error, a carried message", () => {
        expect(guardRefusal("/my/x", '<div data-pk-flash-error="1"> Not  allowed </div>', 200)).toEqual({
            message: "Not allowed",
        });
        expect(guardRefusal("/my/x", '<p data-pk-error-for="name">Too long</p>', 200)).toEqual({
            message: "Too long",
            field: "name",
        });
        expect(guardRefusal("/my/x", '<p data-pk-field-error="date_end">Too late</p>', 200)).toEqual({
            message: "Too late",
            field: "date_end",
        });
        // A toast carries its message in the marker (its text is empty).
        expect(guardRefusal("/my/x", '<div class="o_pk_toast" data-pk-flash-error="Refused by the server"></div>', 200)).toEqual({
            message: "Refused by the server",
        });
        expect(guardRefusal("/my/x", "<p>fine</p>", 500)).toEqual({ message: "" });
        expect(guardRefusal("/my/x", "<p>fine</p>", 200)).toBe(null);
    });

    test("the old sc markers are not read", () => {
        expect(guardRefusal("/my/x", '<div data-sc-flash-error="1">Old</div><p data-sc-error-for="a">Old</p>', 200)).toBe(null);
        expect(
            guardRefusal("/my/x", '<div class="o_pk_toast" data-sc-notify="Old" data-sc-notify-tone="error"></div>', 200)
        ).toBe(null);
    });

    test("fetch mode: X-Pk-Guard, and a field error of the page lands under its field", async () => {
        const form = mount(fieldHtml("name", "Name"), { formAttrs: 'data-pk-guard="1" data-pk-guard-mode="fetch"' });
        guardBoot(getFixture());
        form.querySelector('[name="name"]').value = "A very long name";
        let headers = null;
        mockFetch((input, init) => {
            headers = new Headers(init.headers);
            return new Response('<html><body><p data-pk-error-for="name">Too long</p></body></html>', {
                status: 200,
                headers: { "Content-Type": "text/html" },
            });
        });
        form.requestSubmit();
        await until(() => form.querySelector("[data-pk-guard-field-error]"));
        expect(headers.get("X-Pk-Guard")).toBe("1");
        const note = form.querySelector('[data-pk-guard-field-error="name"]');
        expect(note.textContent).toBe("Too long");
        const input = form.querySelector('[name="name"]');
        expect(input.getAttribute("aria-invalid")).toBe("true");
        expect(input.dataset.pkGuardInvalid).toBe("1");
        expect(input.value).toBe("A very long name");
    });

    test("fetch mode: a refusal without a field shows in the error slot", async () => {
        const form = mount(fieldHtml("name", "Name"), { formAttrs: 'data-pk-guard="1" data-pk-guard-mode="fetch"' });
        guardBoot(getFixture());
        mockFetch(() => new Response('<div data-pk-flash-error="Refused by the server"></div>', { status: 200 }));
        form.requestSubmit();
        const box = form.querySelector("[data-pk-guard-error]");
        await until(() => !box.hidden);
        expect(box.textContent).toBe("Refused by the server");
    });
});
