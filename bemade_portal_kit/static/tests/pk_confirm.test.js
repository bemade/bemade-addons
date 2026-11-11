/*
 * Task 5197 (P2) — pk_confirm: where pkLeavePage lands (the « home » rule).
 * Synthetic fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { PENDING_TOAST_KEY, pkConfirm, pkHomeOf, pkLeaveTarget } from "@bemade_portal_kit/js/pk_confirm";

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

describe("pk_confirm: storage key", () => {
    test("task 5198 (P3a): the pending toast key takes the pk_ prefix", () => {
        expect(PENDING_TOAST_KEY).toBe("pk_pending_toast:v1");
    });
});

describe("pk_confirm: the confirm sheet", () => {
    test("task 5344 (P3b1): the sheet takes the kit's o_pk_* classes", async () => {
        getFixture().innerHTML = '<div class="o_pk_app"></div>';
        const answer = pkConfirm({ title: "Remove?", message: "Synthetic message", confirm: "Remove" });
        const dialog = document.querySelector("dialog[data-pk-confirm]");
        expect(dialog.closest(".o_pk_app")).not.toBe(null);
        expect(dialog.classList.contains("o_pk_sheet")).toBe(true);
        expect(dialog.classList.contains("o_pk_confirm_sheet")).toBe(true);
        expect(dialog.querySelector(".o_pk_sheet_title").textContent).toBe("Remove?");
        expect(dialog.querySelector(".o_pk_confirm_message").textContent).toBe("Synthetic message");
        expect(dialog.querySelector("[data-pk-confirm-ok]").classList.contains("o_pk_btn_danger")).toBe(true);
        expect(dialog.querySelector("[data-pk-confirm-cancel]").classList.contains("o_pk_btn_ghost")).toBe(true);
        expect(dialog.querySelector('[class*="o_sc_"]')).toBe(null);
        dialog.querySelector("[data-pk-confirm-cancel]").click();
        expect(await answer).toBe(false);
        dialog.remove();
    });
});
