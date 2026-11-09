/*
 * Task 5197 (P2) — pk_confirm: where pkLeavePage lands (the « home » rule).
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { pkHomeOf, pkLeaveTarget } from "@bemade_portal_kit/js/pk_confirm";

const O = "https://app.example";
const PLAYERS = { home: "/my/things", sameParams: ["thing_id"] };

describe("pk_confirm: pkLeaveTarget", () => {
    test("no referrer: the home", () => {
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5`, "", PLAYERS)).toBe("/my/things");
    });

    test("no home given: /my", () => {
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5`, "")).toBe("/my");
    });

    test("another origin or a page outside /my: the home", () => {
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5`, "https://other.example/my/team", PLAYERS)).toBe(
            "/my/things"
        );
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5`, `${O}/web`, PLAYERS)).toBe("/my/things");
    });

    test("the same page (path and query): the home", () => {
        expect(pkLeaveTarget(`${O}/my/team?team_id=2`, `${O}/my/team?team_id=2`, PLAYERS)).toBe(
            "/my/things"
        );
    });

    test("another in-app page: back to it", () => {
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5`, `${O}/my/team?team_id=2&tab=list`, PLAYERS)).toBe(
            "/my/team?team_id=2&tab=list"
        );
    });

    test("another record of the same page: back to it", () => {
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5`, `${O}/my/thing?thing_id=4`, PLAYERS)).toBe(
            "/my/thing?thing_id=4"
        );
    });

    test("the same record, another view state: the home", () => {
        expect(pkLeaveTarget(`${O}/my/thing?thing_id=5&tab=notes`, `${O}/my/thing?thing_id=5`, PLAYERS)).toBe(
            "/my/things"
        );
    });

    test("the same record on a sub-page: the home", () => {
        expect(
            pkLeaveTarget(`${O}/my/thing/activities?thing_id=5`, `${O}/my/thing?thing_id=5`, PLAYERS)
        ).toBe("/my/things");
    });

    test("pages without the named params compare path and query", () => {
        expect(pkLeaveTarget(`${O}/my/team?team_id=1`, `${O}/my/team?team_id=2`, PLAYERS)).toBe(
            "/my/team?team_id=2"
        );
    });

    test("without named params, a different query is another page", () => {
        expect(
            pkLeaveTarget(`${O}/my/thing?thing_id=5&tab=notes`, `${O}/my/thing?thing_id=5`, { home: "/my/things" })
        ).toBe("/my/thing?thing_id=5");
    });
});

describe("pk_confirm: pkHomeOf", () => {
    test("reads data-pk-home and data-pk-home-same-params", () => {
        getFixture().innerHTML =
            '<div class="root" data-pk-home="/my/things" data-pk-home-same-params="thing_id, other_id"></div>';
        expect(pkHomeOf(getFixture().querySelector(".root"))).toEqual({
            home: "/my/things",
            sameParams: ["thing_id", "other_id"],
        });
    });

    test("falls back to /my and no named params", () => {
        getFixture().innerHTML = '<div class="root"></div>';
        expect(pkHomeOf(getFixture().querySelector(".root"))).toEqual({ home: "/my", sameParams: null });
        expect(pkHomeOf(null)).toEqual({ home: "/my", sameParams: null });
    });
});
