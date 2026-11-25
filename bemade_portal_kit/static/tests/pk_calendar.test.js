/*
 * Task 5200 (P5) — pk_calendar: the calendar component moved to the kit,
 * neutral texts by default, the consumer's legend texts and filter
 * parameter as props. FullCalendar is not loaded here: the pure helpers and
 * the component's methods are tested on synthetic events. Synthetic only.
 */
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";

import { PkCalendar, staffDotBackground, staffLegend } from "@bemade_portal_kit/js/pk_calendar";

function getter(name, self) {
    return Object.getOwnPropertyDescriptor(PkCalendar.prototype, name).get.call(self);
}

function fakeCalendar(props, activeStaff = "") {
    const self = Object.create(PkCalendar.prototype);
    Object.defineProperty(self, "props", { value: props });
    self.activeStaff = activeStaff;
    self.calendar = {
        formatIso: () => "2026-03-02",
        getDate: () => new Date(2026, 2, 2),
        view: { type: "dayGridMonth" },
    };
    return self;
}

describe("pk_calendar", () => {
    beforeEach(() => patchTranslations());

    test("staffDotBackground: one colour, or equal conic slices", () => {
        expect(staffDotBackground(["#111111"])).toBe("#111111");
        expect(staffDotBackground(["#111111", "#222222"])).toBe(
            "conic-gradient(#111111 0.00% 50.00%, #222222 50.00% 100.00%)"
        );
    });

    test("staffLegend: the assigned people by name, unique, and the unassigned flag", () => {
        const events = [
            { extendedProps: { staff: [{ id: 2, name: "Zed", color: "#222222" }] } },
            { extendedProps: { staff: [{ id: 1, name: "Ada", color: "#111111" }, { id: 2, name: "Zed", color: "#222222" }] } },
            { extendedProps: { staff: [] } },
        ];
        const legend = staffLegend(events);
        expect(legend.people.map((p) => p.name)).toEqual(["Ada", "Zed"]);
        expect(legend.unassigned).toBe(true);
        expect(staffLegend([events[0]]).unassigned).toBe(false);
    });

    test("legend texts: neutral defaults, the props when given", () => {
        const plain = fakeCalendar({});
        expect(String(getter("legendTitle", plain))).toBe("Assigned");
        expect(String(getter("showAllLabel", plain))).toBe("Show all");
        expect(String(getter("unassignedLabel", plain))).toBe("Unassigned");
        expect(getter("assigneeParam", plain)).toBe("assignee");
        const own = fakeCalendar({
            legendTitle: "Crew", showAllLabel: "Every crew member", unassignedLabel: "Nobody", assigneeParam: "who",
        });
        expect(getter("legendTitle", own)).toBe("Crew");
        expect(getter("showAllLabel", own)).toBe("Every crew member");
        expect(getter("unassignedLabel", own)).toBe("Nobody");
        expect(getter("assigneeParam", own)).toBe("who");
    });

    test("filterUrl: the assignee parameter (default or prop), the date and view in the hash", () => {
        const plain = fakeCalendar({});
        const url = new URL(plain.filterUrl({ id: 5, name: "Ada" }, "https://pk.test/pk/t/cal?x=1"));
        expect(url.searchParams.get("assignee")).toBe("5");
        expect(url.searchParams.get("x")).toBe("1");
        const hash = new URLSearchParams(url.hash.slice(1));
        expect(hash.get("pk_date")).toBe("2026-03-02");
        expect(hash.get("pk_view")).toBe("dayGridMonth");

        const own = fakeCalendar({ assigneeParam: "who" }, "5");
        // The active person again: the filter is removed (show all).
        const back = new URL(own.filterUrl({ id: 5, name: "Ada" }, "https://pk.test/pk/t/cal?who=5"));
        expect(back.searchParams.has("who")).toBe(false);
        const other = new URL(own.filterUrl({ id: 6, name: "Zed" }, "https://pk.test/pk/t/cal?who=5"));
        expect(other.searchParams.get("who")).toBe("6");
        expect(other.searchParams.has("assignee")).toBe(false);
    });

    test("legendLabel: show only someone, or show all when they are the filter", () => {
        const own = fakeCalendar({ showAllLabel: "Every crew member" }, "5");
        expect(own.legendLabel({ id: 5, name: "Ada" })).toBe("Every crew member");
        expect(String(own.legendLabel({ id: 6, name: "Zed" }))).toBe("Show only Zed");
    });
});
