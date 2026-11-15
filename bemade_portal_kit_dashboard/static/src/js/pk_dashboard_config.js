/*
 * Task 5202 (kit P7) — the dashboard's configure sheet
 * (/my/app/dashboard/configure, pk_dash_configure). Inert outside .o_pk_app.
 * Moved from the first consumer (task 1624), same behaviour.
 *
 * Each instance row is ONE form (form[data-pk-dash-instance]) posting to its
 * own action (…/configure/save). Saved as you go: any change in the form
 * (the on / off switch, a scope picker — the form-mode tag fields write
 * their hidden input and fire « change » —, a filter) is posted at once with
 * fetch; the title after a pause in typing. The server answers JSON
 * {ok} / {ok: false, error}: a refusal shows INSIDE the form
 * ([data-pk-guard-error]), nothing else moves; a success shows « Saved » in
 * the row's status line. The « Save » button is the no-JS fallback (hidden
 * here).
 *
 * « Restore the default » and « Remove » ask first (pkConfirm; texts from
 * the form's data-pk-confirm-* attributes, translated server-side).
 *
 * The three zones (left / right / bottom, ol[data-pk-dash-zone]); the move
 * route is the zones' data-pk-dash-move-url:
 * - laptop: drag a row by its handle ([data-pk-dash-drag]) within a zone or
 *   to another one — Odoo's sortable helper (@web/core/utils/sortable, set
 *   up without OWL as the « sortable » service does); the drop posts the
 *   zone and the position by fetch; a refusal puts the page back as it was
 *   (reload);
 * - « Move to » (select[data-pk-dash-zone-select]): picking a zone posts at
 *   once and moves the row to the end of that zone (no reload);
 * - after either, ▲ / ▼ follow (disabled at a zone's edges).
 */
import { _t } from "@web/core/l10n/translation";
import { reactive } from "@odoo/owl";
import { useSortable } from "@web/core/utils/sortable";
import { throttleForAnimation } from "@web/core/utils/timing";
import { pkConfirm } from "@bemade_portal_kit/js/pk_confirm";

export const PK_DASH_TITLE_DELAY = 700;
const timers = new WeakMap();
const env = {
    fetch: (...args) => window.fetch(...args),
    confirm: (options) => pkConfirm(options),
    reload: () => window.location.reload(),
};

/** Tests: swap the network, the confirmation and the reload. */
export function pkDashMock(overrides) {
    const previous = { ...env };
    Object.assign(env, overrides);
    return () => Object.assign(env, previous);
}

function inApp(el) {
    return Boolean(el && el.closest && el.closest(".o_pk_app"));
}

function instanceForm(target) {
    const form = target && target.closest && target.closest("form[data-pk-dash-instance]");
    return form && inApp(form) ? form : null;
}

/** The form's fields as a URL-encoded body: one value per name (the last,
 *  as the form would read), a multi filter's values (its ``<name>_present``
 *  marker) as repeated keys. */
export function pkDashBody(form) {
    const data = new FormData(form);
    const multi = new Set();
    for (const name of data.keys()) {
        if (name.endsWith("_present")) {
            multi.add(name.slice(0, -"_present".length));
        }
    }
    const body = new URLSearchParams();
    for (const [name, value] of data.entries()) {
        if (multi.has(name)) {
            body.append(name, value);
        } else {
            body.set(name, value);
        }
    }
    return body;
}

function setStatus(form, text) {
    const status = form.querySelector("[data-pk-dash-status]");
    if (status) {
        status.textContent = text;
    }
}

function setError(form, message) {
    const slot = form.querySelector("[data-pk-guard-error]");
    if (slot) {
        slot.textContent = message || "";
        slot.hidden = !message;
    }
}

async function post(url, body) {
    const response = await env.fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
        body,
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || !payload.ok) {
        throw new Error((payload && payload.error) || _t("This change could not be saved."));
    }
    return payload;
}

/** Post one instance form; the outcome shows in it. */
export async function pkDashSave(form) {
    form.dataset.pkDashSaving = "1";
    setStatus(form, _t("Saving…"));
    try {
        await post(form.action, pkDashBody(form));
        setError(form, "");
        setStatus(form, _t("Saved"));
        syncRow(form);
    } catch (error) {
        const offline = error instanceof TypeError;
        setError(form, offline ? _t("No connection: this change was not saved.") : error.message);
        setStatus(form, "");
    } finally {
        delete form.dataset.pkDashSaving;
    }
}

/** The row's look follows its switch and title (no reload). */
function syncRow(form) {
    const item = form.closest("[data-pk-dash-item]");
    const toggle = form.querySelector('input[role="switch"][name="enabled"]');
    if (item && toggle) {
        item.classList.toggle("o_pk_dash_cfg_off", !toggle.checked);
    }
    const title = form.querySelector('input[name="title"]');
    const label = form.querySelector(".o_pk_dash_cfg_switch .o_pk_switch_label");
    if (title && label) {
        label.textContent = title.value.trim() || title.placeholder;
    }
}

function schedule(form, delay) {
    clearTimeout(timers.get(form));
    timers.set(form, setTimeout(() => pkDashSave(form), delay));
}

// ------------------------------------------------------------------ zones
function zonesRoot() {
    return document.querySelector(".o_pk_app [data-pk-dash-zones]");
}

/** Post a move (``{instance_id, zone, position}``) to the zones' route. */
export function pkDashMove(data) {
    const root = zonesRoot();
    const csrf = root && root.querySelector('input[name="csrf_token"]');
    return post(root.dataset.pkDashMoveUrl, new URLSearchParams({ csrf_token: csrf ? csrf.value : "", ...data }));
}

/** ▲ / ▼ and « Move to » follow each row's zone and place. */
export function pkDashSyncZones() {
    for (const list of document.querySelectorAll(".o_pk_app ol[data-pk-dash-zone]")) {
        const items = [...list.querySelectorAll(":scope > li[data-pk-dash-item]")];
        items.forEach((item, index) => {
            const up = item.querySelector('button[data-pk-dash-move="up"]');
            const down = item.querySelector('button[data-pk-dash-move="down"]');
            if (up) {
                up.disabled = index === 0;
            }
            if (down) {
                down.disabled = index === items.length - 1;
            }
            const select = item.querySelector("select[data-pk-dash-zone-select]");
            if (select) {
                select.value = list.dataset.pkDashZone;
            }
        });
    }
}

function showMoveError(item, message) {
    const form = item && item.querySelector("form[data-pk-dash-instance]");
    if (form) {
        setError(form, message);
    }
}

/** « Move to »: post, then move the row to the end of its new zone. */
export async function pkDashMoveTo(select) {
    const item = select.closest("li[data-pk-dash-item]");
    const zone = select.value;
    const target = document.querySelector(`.o_pk_app ol[data-pk-dash-zone="${zone}"]`);
    if (!item || !target) {
        return;
    }
    try {
        await pkDashMove({ instance_id: item.dataset.pkDashItem, zone });
        target.appendChild(item);
        pkDashSyncZones();
        showMoveError(item, "");
        item.scrollIntoView({ block: "nearest" });
    } catch (error) {
        pkDashSyncZones();
        showMoveError(item, error.message);
    }
}

/** A drop of ``element`` into the zone ``list``: post its zone and place
 *  (an empty zone gets the row appended). */
export async function pkDashDropped(element, list) {
    const root = zonesRoot();
    if (element.parentElement !== list) {
        list.appendChild(element);
    }
    const items = [...list.querySelectorAll(":scope > li[data-pk-dash-item]")];
    try {
        await pkDashMove({
            instance_id: element.dataset.pkDashItem,
            zone: list.dataset.pkDashZone,
            position: String(items.indexOf(element)),
        });
        pkDashSyncZones();
        root.dataset.pkDashDropped = String(Number(root.dataset.pkDashDropped || 0) + 1);
    } catch {
        env.reload();
    }
}

function initSortable(root) {
    const setups = new Map();
    const setupHooks = {
        wrapState: reactive,
        throttle: throttleForAnimation,
        addListener: (el, type, listener, options) => el.addEventListener(type, listener, options),
        setup: (setupFn, dependenciesFn) => setups.set(setupFn, dependenciesFn),
        teardown: () => {},
    };
    useSortable({
        setupHooks,
        ref: { el: root },
        elements: "li[data-pk-dash-item]",
        groups: "ol[data-pk-dash-zone]",
        connectGroups: true,
        handle: "[data-pk-dash-drag]",
        placeholderClasses: ["o_pk_dash_cfg_placeholder"],
        applyChangeOnDrop: true,
        // ``parent`` = the zone dropped into (``group`` is the one the row
        // came from).
        onDrop: ({ element, parent, group }) => pkDashDropped(element, parent || group || element.parentElement),
    });
    for (const [setupFn, dependenciesFn] of setups) {
        setupFn(...dependenciesFn());
    }
}

document.addEventListener("change", (ev) => {
    const select = ev.target.closest && ev.target.closest("select[data-pk-dash-zone-select]");
    if (select && inApp(select)) {
        pkDashMoveTo(select);
        return;
    }
    const form = instanceForm(ev.target);
    if (!form) {
        return;
    }
    // A switch's « off » twin follows pk_switch.js (capture phase) first.
    schedule(form, ev.target.name === "title" ? 0 : 50);
});

document.addEventListener("input", (ev) => {
    const form = instanceForm(ev.target);
    if (form && ev.target.name === "title") {
        schedule(form, PK_DASH_TITLE_DELAY);
    }
});

document.addEventListener("submit", (ev) => {
    const form = ev.target;
    if (instanceForm(form) === form) {
        ev.preventDefault();
        pkDashSave(form);
        return;
    }
    // « Restore the default » and « Remove » (an item's red trash) ask first.
    if (form.matches && form.matches("form[data-pk-dash-reset-form], form[data-pk-dash-remove-form]") && inApp(form)) {
        if (form.dataset.pkDashConfirmed) {
            return;
        }
        ev.preventDefault();
        Promise.resolve(
            env.confirm({
                title: form.dataset.pkConfirmTitle,
                message: form.dataset.pkConfirmMessage,
                confirm: form.dataset.pkConfirmOk,
                cancel: form.dataset.pkConfirmCancel,
            })
        ).then((ok) => {
            if (ok) {
                form.dataset.pkDashConfirmed = "1";
                form.submit();
            }
        });
    }
});

/** Hide the no-JS buttons, set up the drag-and-drop. */
export function pkDashInitConfigure() {
    const root = zonesRoot();
    if (!root) {
        return false;
    }
    for (const button of document.querySelectorAll(".o_pk_app [data-pk-dash-save]")) {
        button.hidden = true;
    }
    // « Move to » saves on pick: its no-JS « OK » goes.
    for (const button of document.querySelectorAll(".o_pk_app [data-pk-dash-zone-go]")) {
        button.hidden = true;
    }
    initSortable(root);
    return true;
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", pkDashInitConfigure);
} else {
    pkDashInitConfigure();
}
