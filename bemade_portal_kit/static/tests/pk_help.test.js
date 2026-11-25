/*
 * Task 5200 (P5) — pk_help: the app bar « ? » follows the page's tab only
 * when the page says its key is refined by the tab (data-pk-help-tabbed);
 * no list of pages in the script. Synthetic fixtures only.
 */
import { afterEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { browser } from "@web/core/browser/browser";

import { pkHelpUrlFor } from "@bemade_portal_kit/js/pk_help";
import "@bemade_portal_kit/js/pk_tabs";

const MAP = JSON.stringify({ "group.members": "/pk/t/help/members", group: "/pk/t/help/group" });

function mount(tabbed) {
    getFixture().innerHTML = `<div class="o_pk_app" data-pk-app-shell="1">
        <header><a href="/pk/t/help/group" data-pk-help="1" data-pk-help-key="group" data-pk-help-base="group"
            data-pk-help-home="/pk/t/help/home" data-pk-help-map='${MAP}' ${tabbed ? 'data-pk-help-tabbed="1"' : ""}>?</a></header>
        <nav data-pk-tabs="1">
            <a href="/pk/t/page?tab=members" class="pk_t_members" data-pk-tab="members">Members</a>
            <a href="/pk/t/page?tab=other" class="pk_t_other" data-pk-tab="other">Other</a>
        </nav>
        <section data-pk-tab-panel="members" hidden="">m</section>
        <section data-pk-tab-panel="other" hidden="">o</section>
    </div>`;
    return getFixture().querySelector("a[data-pk-help]");
}

describe("pk_help", () => {
    afterEach(() => {
        browser.history.replaceState(null, "", "/pk/t/page");
    });

    test("pkHelpUrlFor: the tab's article, else the base's, else the home", () => {
        const link = mount(true);
        expect(pkHelpUrlFor(link, "members")).toBe("/pk/t/help/members");
        expect(pkHelpUrlFor(link, "other")).toBe("/pk/t/help/group");
        expect(pkHelpUrlFor(link, "")).toBe("/pk/t/help/group");
        link.dataset.pkHelpMap = "{}";
        expect(pkHelpUrlFor(link, "members")).toBe("/pk/t/help/home");
        link.dataset.pkHelpMap = "not json";
        expect(pkHelpUrlFor(link, "members")).toBe("/pk/t/help/home");
    });

    test("a tab switch re-points the link of a tabbed page", () => {
        const link = mount(true);
        getFixture().querySelector(".pk_t_members").click();
        expect(link.getAttribute("href")).toBe("/pk/t/help/members");
        expect(link.dataset.pkHelpKey).toBe("group.members");
        getFixture().querySelector(".pk_t_other").click();
        expect(link.getAttribute("href")).toBe("/pk/t/help/group");
        expect(link.dataset.pkHelpKey).toBe("group.other");
    });

    test("without the tab flag the link stays the page's", () => {
        const link = mount(false);
        getFixture().querySelector(".pk_t_members").click();
        expect(link.getAttribute("href")).toBe("/pk/t/help/group");
        expect(link.dataset.pkHelpKey).toBe("group");
    });
});
