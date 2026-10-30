/*
 * Task 1624, owner UAT round 2 (2026-10-29) — the dashboard's three zones
 * (left / right / bottom) in a browser (tests/test_dashboard_tours_1624.py).
 * Synthetic data; language-independent triggers.
 *
 * - « sc_1624_zones_dnd » (laptop 1440 px): « Configurer » shows left and
 *   right side by side, bottom under both; drag « Aujourd'hui » from the
 *   left zone into the right one, then into the bottom one (each drop saved
 *   by fetch, no reload); after a reload it is still there, and the
 *   dashboard renders it full width under the two columns.
 * - « sc_1624_zones_move » (phone 390 px): the zones are stacked; « Move
 *   to » puts « Indicateurs » in the left zone (no reload), ▲ moves it up
 *   within the zone; the dashboard reads left, then right, then bottom in
 *   one column.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function noHorizontalScroll() {
    const doc = document.documentElement;
    assert(doc.scrollWidth <= doc.clientWidth + 1, `horizontal scroll (${doc.scrollWidth} > ${doc.clientWidth})`);
}

const frame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()));

/** A mouse drag of ``handle`` into the zone list ``group`` (dropped at its
 * end), as pointer events: down on the handle, moves past the drag
 * tolerance, the zone's « pointerenter » (which a synthetic move does not
 * fire by itself), up. The page's sortable helper does the rest. */
async function dragInto(handle, group) {
    const from = handle.getBoundingClientRect();
    const to = group.getBoundingClientRect();
    const x = from.left + from.width / 2;
    const y = from.top + from.height / 2;
    const tx = to.left + to.width / 2;
    const ty = to.bottom - 12;
    const at = (cx, cy, bubbles = true) => ({
        bubbles, cancelable: true, composed: true, clientX: cx, clientY: cy,
        button: 0, buttons: 1, pointerId: 1, pointerType: "mouse", isPrimary: true,
    });
    handle.dispatchEvent(new PointerEvent("pointerdown", at(x, y)));
    for (let i = 1; i <= 12; i++) {
        document.body.dispatchEvent(new PointerEvent("pointermove", at(x + ((tx - x) * i) / 12, y + ((ty - y) * i) / 12)));
        await frame();
    }
    group.dispatchEvent(new PointerEvent("pointerenter", at(tx, ty, false)));
    await frame();
    document.body.dispatchEvent(new PointerEvent("pointermove", at(tx, ty)));
    await frame();
    document.body.dispatchEvent(new PointerEvent("pointerup", at(tx, ty)));
    await frame();
}

const ZONE = (zone) => `ol[data-sc-dash-zone="${zone}"]`;
const ITEM = (id) => `li[data-sc-dash-item="${id}"]`;
const rect = (selector) => document.querySelector(selector).getBoundingClientRect();
const zoneIds = (zone) =>
    [...document.querySelectorAll(`${ZONE(zone)} > li[data-sc-dash-item]`)].map((el) => el.dataset.scDashItem);

tours.add("sc_1624_zones_dnd", {
    steps: () => [
        {
            content: "« Configure »: left and right side by side, bottom under both",
            trigger: `${ZONE("bottom")} ${ITEM("watch")}`,
            run() {
                const left = rect('[data-sc-dash-cfg-zone="left"]');
                const right = rect('[data-sc-dash-cfg-zone="right"]');
                const bottom = rect('[data-sc-dash-cfg-zone="bottom"]');
                assert(Math.abs(left.top - right.top) < 2 && left.right <= right.left, "left | right");
                assert(bottom.top >= Math.max(left.bottom, right.bottom) - 1, "bottom under both");
                assert(bottom.width > left.width * 1.5, "bottom spans the width");
                assert(zoneIds("left")[0] === "today", `left: ${zoneIds("left")}`);
                window.__sc1624ZonesNoReload = true;
                noHorizontalScroll();
            },
        },
        {
            content: "Drag « Today » into the right zone",
            trigger: `${ZONE("left")} ${ITEM("today")} [data-sc-dash-drag]`,
            async run() {
                await dragInto(this.anchor, document.querySelector(ZONE("right")));
            },
        },
        {
            content: "Dropped in the right zone and saved (no reload)",
            trigger: `[data-sc-dash-zones][data-sc-dash-dropped="1"] ${ZONE("right")} ${ITEM("today")}`,
            run() {
                assert(window.__sc1624ZonesNoReload, "the page reloaded");
                assert(!zoneIds("left").includes("today"), "gone from the left");
                const select = document.querySelector(`${ITEM("today")} select[data-sc-dash-zone-select]`);
                assert(select.value === "right", "« Move to » follows");
            },
        },
        {
            content: "Drag « Today » into the bottom zone",
            trigger: `${ZONE("right")} ${ITEM("today")} [data-sc-dash-drag]`,
            async run() {
                await dragInto(this.anchor, document.querySelector(ZONE("bottom")));
            },
        },
        {
            content: "Dropped in the bottom zone and saved",
            trigger: `[data-sc-dash-zones][data-sc-dash-dropped="2"] ${ZONE("bottom")} ${ITEM("today")}`,
            run() {
                window.location.reload();
            },
            expectUnloadPage: true,
        },
        {
            content: "After a reload, still in the bottom zone",
            trigger: `${ZONE("bottom")} ${ITEM("today")}`,
            run() {
                assert(!zoneIds("right").includes("today") && !zoneIds("left").includes("today"), "only in the bottom");
                window.location.href = "/my/home";
            },
            expectUnloadPage: true,
        },
        {
            content: "The dashboard: « Today » full width under the two columns",
            trigger: '[data-sc-zone="bottom"] section[data-sc-instance="today"]',
            run() {
                const left = rect('[data-sc-zone="left"]');
                const right = rect('[data-sc-zone="right"]');
                const today = this.anchor.getBoundingClientRect();
                assert(Math.abs(left.top - right.top) < 2 && left.right <= right.left, "two columns");
                assert(today.top >= Math.max(left.bottom, right.bottom) - 1, "under both columns");
                assert(today.width > left.width * 1.5, "full width");
                noHorizontalScroll();
            },
        },
    ],
});

tours.add("sc_1624_zones_move", {
    steps: () => [
        {
            content: "« Configure » on a phone: the zones stacked",
            trigger: `${ZONE("right")} ${ITEM("indicators")} select[data-sc-dash-zone-select]`,
            run() {
                const left = rect('[data-sc-dash-cfg-zone="left"]');
                const right = rect('[data-sc-dash-cfg-zone="right"]');
                const bottom = rect('[data-sc-dash-cfg-zone="bottom"]');
                assert(left.bottom <= right.top + 1 && right.bottom <= bottom.top + 1, "left / right / bottom");
                assert(!document.querySelector(`${ITEM("indicators")} [data-sc-dash-zone-go]:not([hidden])`), "no-JS OK hidden");
                window.__sc1624ZonesNoReload = true;
                noHorizontalScroll();
            },
        },
        {
            content: "« Move to »: Left",
            trigger: `${ITEM("indicators")} select[data-sc-dash-zone-select]`,
            run: "select left",
        },
        {
            content: "« Indicators » moved to the end of the left zone (no reload)",
            trigger: `${ZONE("left")} ${ITEM("indicators")}`,
            async run() {
                assert(window.__sc1624ZonesNoReload, "the page reloaded");
                const ids = zoneIds("left");
                assert(ids[ids.length - 1] === "indicators", `left: ${ids}`);
                await waitFor(
                    () => document.querySelector(`${ITEM("indicators")} button[data-sc-dash-move="down"]`).disabled,
                    "▼ disabled at the zone's end"
                );
            },
        },
        {
            content: "▲ moves it up within the zone",
            trigger: `${ITEM("indicators")} button[data-sc-dash-move="up"]:not([disabled])`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "One up, still in the left zone",
            trigger: `${ZONE("left")} ${ITEM("indicators")}`,
            run() {
                const ids = zoneIds("left");
                assert(ids.indexOf("indicators") === ids.indexOf("missing_timesheets") - 1, `left: ${ids}`);
                window.location.href = "/my/home";
            },
            expectUnloadPage: true,
        },
        {
            content: "The dashboard on a phone: one column, left then right then bottom",
            trigger: '[data-sc-zone="left"] section[data-sc-instance="indicators"]',
            run() {
                const zones = [...document.querySelectorAll("[data-sc-dashboard] > [data-sc-zone]")];
                assert(zones.map((z) => z.dataset.scZone).join() === "left,right,bottom", "zone order");
                const sections = [...document.querySelectorAll("section[data-sc-instance]")];
                for (let i = 1; i < sections.length; i++) {
                    const a = sections[i - 1].getBoundingClientRect();
                    const b = sections[i].getBoundingClientRect();
                    assert(b.top >= a.bottom - 1 && Math.abs(a.left - b.left) < 2, "one column, in order");
                }
                noHorizontalScroll();
            },
        },
    ],
});
