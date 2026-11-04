/*
 * Task 1589 — a coach sees only the activities assigned to them or created
 * by them, and completes their own from the player's Activities tab
 * (tests/test_activity_permissions_1589.py). Triggers are data attributes;
 * the synthetic summaries are data, not UI strings (language-independent).
 */
import { registry } from "@web/core/registry";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const PANEL = 'section[data-sc-tab-panel="activities"]:not([hidden])';

function rowTitles() {
    return [...document.querySelectorAll(`${PANEL} [data-sc-activity-row] .o_sc_row_title`)].map(
        (el) => el.textContent.trim()
    );
}

registry.category("web_tour.tours").add("sc_1589_coach_own_activities", {
    steps: () => [
        {
            content: "Only the coach's own activities are listed",
            trigger: `${PANEL} [data-sc-activity-row]`,
            run() {
                const titles = rowTitles().sort();
                assert(
                    JSON.stringify(titles) ===
                        JSON.stringify(["Coach assigned task", "Coach created task"]),
                    `rows: ${titles.join(" | ")}`
                );
            },
        },
        {
            content: "« Fait » on the activity assigned to the coach",
            trigger: `${PANEL} [data-sc-activity-row]:has(.o_sc_row_title:contains("Coach assigned task")) button[data-sc-action="activity.complete"]`,
            run: "click",
        },
        {
            content: "Feedback",
            trigger: 'dialog#sc_activity_complete_sheet[open] textarea[name="feedback"]',
            run: "edit Tour 1589 done",
        },
        {
            content: "Submit",
            trigger: "dialog#sc_activity_complete_sheet[open] button[type=submit]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Done, no error; only the created one remains",
            trigger: PANEL,
            run() {
                assert(window.location.search.includes("success=activity_done"), window.location.search);
                assert(!window.location.search.includes("error="), window.location.search);
                const titles = rowTitles();
                assert(
                    titles.length === 1 && titles[0] === "Coach created task",
                    `rows: ${titles.join(" | ")}`
                );
            },
        },
    ],
});
