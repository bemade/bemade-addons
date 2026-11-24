/*
 * Task 5202 (kit P7) — pk_dashboard_config: the configure sheet saves as
 * you go, moves rows (« Move to », drag-and-drop drop) and asks before
 * « Remove » / « Restore the default ». Synthetic fixtures only (a fake
 * network and confirmation).
 */
import { advanceTime, afterEach, beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";

import {
    PK_DASH_TITLE_DELAY,
    pkDashBody,
    pkDashDropped,
    pkDashMock,
    pkDashMoveTo,
    pkDashSave,
    pkDashSyncZones,
} from "@bemade_portal_kit_dashboard/js/pk_dashboard_config";

let restore = null;
beforeEach(() => patchTranslations());
afterEach(() => restore && restore());

function item(id, zone) {
    return `
        <li data-pk-dash-item="${id}">
            <button type="submit" data-pk-dash-move="up"></button>
            <button type="submit" data-pk-dash-move="down"></button>
            <form action="/x/save" data-pk-dash-instance="${id}">
                <input type="hidden" name="instance_id" value="${id}"/>
                <input type="hidden" name="enabled" value="0"/>
                <input type="checkbox" role="switch" name="enabled" value="1" checked="checked"/>
                <input type="text" name="title" value="" placeholder="Widget ${id}"/>
                <input type="hidden" name="colors_present" value="1"/>
                <input type="checkbox" name="colors" value="red" checked="checked"/>
                <input type="checkbox" name="colors" value="blue" checked="checked"/>
                <span data-pk-dash-status="1"></span>
                <p data-pk-guard-error="1" hidden="hidden"></p>
            </form>
            <select data-pk-dash-zone-select="1">
                <option value="left" ${zone === "left" ? "selected" : ""}>Left</option>
                <option value="right" ${zone === "right" ? "selected" : ""}>Right</option>
                <option value="bottom" ${zone === "bottom" ? "selected" : ""}>Bottom</option>
            </select>
        </li>`;
}

function sheet() {
    getFixture().innerHTML = `
        <div class="o_pk_app">
            <div data-pk-dash-zones="1" data-pk-dash-move-url="/x/move">
                <input type="hidden" name="csrf_token" value="tok"/>
                <ol data-pk-dash-zone="left">${item("alpha", "left")}${item("beta", "left")}</ol>
                <ol data-pk-dash-zone="right">${item("gamma", "right")}</ol>
                <ol data-pk-dash-zone="bottom"></ol>
            </div>
            <form data-pk-dash-reset-form="1" action="/x/reset" data-pk-confirm-title="Sure?"
                  data-pk-confirm-message="All back" data-pk-confirm-ok="Yes" data-pk-confirm-cancel="No"></form>
        </div>`;
    return getFixture();
}

function network(answer) {
    const calls = [];
    restore = pkDashMock({
        fetch: async (url, options) => {
            calls.push({ url, body: new URLSearchParams(options.body) });
            const { status = 200, payload = { ok: true } } = answer(url) || {};
            return { ok: status < 400, json: async () => payload };
        },
    });
    return calls;
}

const zoneIds = (root, zone) =>
    [...root.querySelectorAll(`ol[data-pk-dash-zone="${zone}"] > li`)].map((li) => li.dataset.pkDashItem);

describe("pk_dashboard_config", () => {
    test("the body: one value per name (the last), a multi filter's values repeated", () => {
        const form = sheet().querySelector('form[data-pk-dash-instance="alpha"]');
        const body = pkDashBody(form);
        expect(body.getAll("enabled")).toEqual(["1"]);
        expect(body.getAll("colors")).toEqual(["red", "blue"]);
        expect(body.get("instance_id")).toBe("alpha");
    });

    test("save as you go: a change posts the row's form, « Saved » shows", async () => {
        const calls = network(() => null);
        const form = sheet().querySelector('form[data-pk-dash-instance="alpha"]');
        form.querySelector('input[value="blue"]').checked = false;
        form.querySelector('input[value="blue"]').dispatchEvent(new Event("change", { bubbles: true }));
        await advanceTime(100);
        expect(calls.length).toBe(1);
        expect(calls[0].url).toMatch(/\/x\/save$/);
        expect(calls[0].body.getAll("colors")).toEqual(["red"]);
        expect(form.querySelector("[data-pk-dash-status]").textContent).toBe("Saved");
    });

    test("the title saves after a pause in typing; the switch label follows", async () => {
        const calls = network(() => null);
        const form = sheet().querySelector('form[data-pk-dash-instance="alpha"]');
        const title = form.querySelector('input[name="title"]');
        title.value = "Mine";
        title.dispatchEvent(new Event("input", { bubbles: true }));
        await advanceTime(PK_DASH_TITLE_DELAY - 100);
        expect(calls.length).toBe(0);
        await advanceTime(200);
        expect(calls.length).toBe(1);
        expect(calls[0].body.get("title")).toBe("Mine");
    });

    test("a refusal shows inside the form, nothing else", async () => {
        network(() => ({ status: 400, payload: { ok: false, error: "Invalid setting." } }));
        const form = sheet().querySelector('form[data-pk-dash-instance="alpha"]');
        await pkDashSave(form);
        const slot = form.querySelector("[data-pk-guard-error]");
        expect(slot.textContent).toBe("Invalid setting.");
        expect(slot.hidden).toBe(false);
        expect(form.querySelector("[data-pk-dash-status]").textContent).toBe("");
    });

    test("« Move to »: posted to the zones' route, the row goes to the end of its zone", async () => {
        const calls = network(() => null);
        const root = sheet();
        const select = root.querySelector('li[data-pk-dash-item="alpha"] select');
        select.value = "right";
        await pkDashMoveTo(select);
        expect(calls[0].url).toBe("/x/move");
        expect(Object.fromEntries(calls[0].body)).toEqual({ csrf_token: "tok", instance_id: "alpha", zone: "right" });
        expect(zoneIds(root, "left")).toEqual(["beta"]);
        expect(zoneIds(root, "right")).toEqual(["gamma", "alpha"]);
        const beta = root.querySelector('li[data-pk-dash-item="beta"]');
        expect(beta.querySelector('[data-pk-dash-move="up"]').disabled).toBe(true);
        expect(beta.querySelector('[data-pk-dash-move="down"]').disabled).toBe(true);
    });

    test("« Move to » refused: the row stays, the error shows in it", async () => {
        network(() => ({ status: 400, payload: { ok: false, error: "No." } }));
        const root = sheet();
        const select = root.querySelector('li[data-pk-dash-item="alpha"] select');
        select.value = "bottom";
        await pkDashMoveTo(select);
        expect(zoneIds(root, "left")).toEqual(["alpha", "beta"]);
        expect(select.value).toBe("left");
        expect(root.querySelector('li[data-pk-dash-item="alpha"] [data-pk-guard-error]').textContent).toBe("No.");
    });

    test("drag-and-drop: the drop posts the zone and the position; an empty zone takes the row", async () => {
        const calls = network(() => null);
        const root = sheet();
        const gamma = root.querySelector('li[data-pk-dash-item="gamma"]');
        const bottom = root.querySelector('ol[data-pk-dash-zone="bottom"]');
        await pkDashDropped(gamma, bottom);
        expect(Object.fromEntries(calls[0].body)).toEqual({
            csrf_token: "tok", instance_id: "gamma", zone: "bottom", position: "0",
        });
        expect(zoneIds(root, "bottom")).toEqual(["gamma"]);
        expect(root.querySelector("[data-pk-dash-zones]").dataset.pkDashDropped).toBe("1");
    });

    test("drag-and-drop refused: the page is reloaded", async () => {
        let reloaded = 0;
        network(() => ({ status: 400, payload: { ok: false, error: "No." } }));
        const undo = pkDashMock({ reload: () => reloaded++ });
        const root = sheet();
        await pkDashDropped(root.querySelector('li[data-pk-dash-item="beta"]'), root.querySelector('ol[data-pk-dash-zone="right"]'));
        expect(reloaded).toBe(1);
        undo();
    });

    test("▲ / ▼ follow the rows' places", () => {
        const root = sheet();
        pkDashSyncZones();
        const [alpha, beta] = ["alpha", "beta"].map((id) => root.querySelector(`li[data-pk-dash-item="${id}"]`));
        expect(alpha.querySelector('[data-pk-dash-move="up"]').disabled).toBe(true);
        expect(alpha.querySelector('[data-pk-dash-move="down"]').disabled).toBe(false);
        expect(beta.querySelector('[data-pk-dash-move="down"]').disabled).toBe(true);
    });

    test("« Restore the default » asks first, with the form's texts; « No » submits nothing", async () => {
        const asked = [];
        let answer = false;
        restore = pkDashMock({ confirm: async (options) => { asked.push(options); return answer; } });
        const form = sheet().querySelector("form[data-pk-dash-reset-form]");
        let submitted = 0;
        form.submit = () => submitted++;
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
        await advanceTime(10);
        expect(asked).toEqual([{ title: "Sure?", message: "All back", confirm: "Yes", cancel: "No" }]);
        expect(submitted).toBe(0);
        answer = true;
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
        await advanceTime(10);
        expect(submitted).toBe(1);
        expect(form.dataset.pkDashConfirmed).toBe("1");
    });
});
