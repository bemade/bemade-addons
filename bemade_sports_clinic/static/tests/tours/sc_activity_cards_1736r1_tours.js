/*
 * Task 1736 r1 (owner 2026-11-01) — an activity card edited in place, its
 * details popout and « Done », in a browser
 * (tests/test_activity_cards_tours_1736r1.py, phone 390 px and laptop
 * 1366 px). Synthetic data; language-independent triggers. The test passes
 * the activity's id (?x1736=) and the new assignee's id (?xuser=).
 *
 * - the card's trash is hidden; its pencil (rightmost) turns the card into
 *   its edit view (the fields mounted on that first tap), the trash shows
 *   left of the ✓;
 * - the due date, the assignee and the note save as they change;
 * - the ✓ closes the card: the trash hides, the card shows the new date;
 * - the trash (while editing) asks first (« No » keeps it);
 * - a tap on the card opens its details popout (no page change);
 * - « Done » completes it.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function param(name) {
    return new URLSearchParams(window.location.search).get(name);
}

function shown(el) {
    if (!el || el.hidden) {
        return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

function noHorizontalScroll() {
    const doc = document.documentElement;
    assert(doc.scrollWidth <= doc.clientWidth + 1, `horizontal scroll (${doc.scrollWidth} > ${doc.clientWidth})`);
}

const PANEL = 'section[data-pk-tab-panel="activities"]';
const CARD = `${PANEL} [data-sc-activity-row]`;

function card() {
    return document.querySelector(`${CARD}[data-sc-activity-row="${param("x1736")}"]`);
}

function setValue(el, value) {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    // A text field saves when it is left (headless: no real blur).
    el.dispatchEvent(new FocusEvent("blur"));
}

tours.add("sc_1736r1_activity_card", {
    steps: () => [
        {
            content: "The card: trash hidden, the pencil rightmost, no field mounted yet",
            trigger: `${CARD} button[data-sc-action="activity.edit"]`,
            run() {
                const el = card();
                assert(el, "the activity's card");
                const trash = el.querySelector("button.o_pk_card_trash");
                assert(trash && !shown(trash), "the trash shows before editing");
                const icons = [...el.querySelector("[data-sc-card-icons]").querySelectorAll("button")];
                assert(icons[icons.length - 1].dataset.pkEditToggle === "1", "the pencil is not rightmost");
                assert(!el.querySelector("owl-component"), "fields mounted before the pencil");
                assert(!el.querySelector('[data-sc-action="activity.reschedule"], [data-sc-action="activity.reassign"]'),
                    "Reschedule / Reassign still on the card");
                noHorizontalScroll();
                el.querySelector('button[data-sc-action="activity.edit"]').click();
            },
        },
        {
            content: "Edit view: the fields are mounted, the trash shows left of the ✓",
            trigger: `${CARD}[data-pk-edit-open] .o_pk_autosave[data-pk-autosave-field="date_deadline"] input[type="date"]`,
            run() {
                const el = card();
                assert(el.dataset.pkEditOpen === "1", "another card opened");
                assert(shown(el.querySelector("button.o_pk_card_trash")), "no trash while editing");
                assert(el.querySelector("button[data-pk-edit-toggle]").dataset.pkEditToggleDone === "1", "no ✓");
                assert(!el.querySelector("template[data-pk-lazy-edit]"), "the template is still there");
                for (const field of ["summary", "date_deadline", "user_id", "note"]) {
                    assert(el.querySelector(`.o_pk_autosave[data-pk-autosave-field="${field}"]`), `no ${field} field`);
                }
                noHorizontalScroll();
                setValue(el.querySelector('.o_pk_autosave[data-pk-autosave-field="date_deadline"] input[type="date"]'), "2031-05-06");
            },
        },
        {
            content: "The due date is saved",
            trigger: `${CARD}[data-pk-edit-open] .o_pk_autosave[data-pk-autosave-field="date_deadline"][data-pk-autosave-state="saved"]`,
            run() {
                const select = card().querySelector('.o_pk_autosave[data-pk-autosave-field="user_id"] select');
                assert(select, "no assignee select");
                assert([...select.options].some((o) => o.value === param("xuser")), "the new assignee is offered");
                setValue(select, param("xuser"));
            },
        },
        {
            content: "The assignee is saved",
            trigger: `${CARD}[data-pk-edit-open] .o_pk_autosave[data-pk-autosave-field="user_id"][data-pk-autosave-state="saved"]`,
            run() {
                setValue(card().querySelector('.o_pk_autosave[data-pk-autosave-field="note"] textarea'), "SC1736r1 tour note");
            },
        },
        {
            content: "The note is saved; close with the ✓",
            trigger: `${CARD}[data-pk-edit-open] .o_pk_autosave[data-pk-autosave-field="note"][data-pk-autosave-state="saved"]`,
            run() {
                card().querySelector("button[data-pk-edit-toggle]").click();
            },
        },
        {
            content: "Closed: the trash hides, the card shows the new date",
            trigger: `${CARD}:not([data-pk-edit-open]) .o_pk_row_subtitle:contains(2031)`,
            run() {
                const el = card();
                assert(!el.dataset.pkEditOpen, "still editing");
                assert(!shown(el.querySelector("button.o_pk_card_trash")), "the trash still shows");
                el.querySelector('button[data-sc-action="activity.edit"]').click();
            },
        },
        {
            content: "Edit again: the trash asks first",
            trigger: `${CARD}[data-pk-edit-open] button.o_pk_card_trash:not([hidden])`,
            run: "click",
        },
        {
            content: "The confirmation, for this activity; « No » keeps it",
            trigger: "dialog#sc_activity_cancel_sheet[open]",
            run() {
                assert(this.anchor.querySelector('input[name="activity_id"]').value === param("x1736"), "another activity");
                this.anchor.querySelector("[data-pk-sheet-close]").click();
                card().querySelector("button[data-pk-edit-toggle]").click();
            },
        },
        {
            content: "Tap the card: its details popout opens (same page)",
            trigger: `${CARD}:not([data-pk-edit-open]) a.o_pk_link_row_main[data-pk-sheet-url]`,
            run() {
                window.__sc1736r1Url = window.location.href;
                card().querySelector("a.o_pk_link_row_main").click();
            },
        },
        {
            content: "The popout shows the details",
            trigger: "dialog#sc_activity_detail_sheet[open] [data-sc-activity-popout-body]",
            run() {
                const body = this.anchor;
                assert(body.dataset.scActivityPopoutBody === param("x1736"), "another activity's details");
                assert(body.textContent.includes("SC1736r1 tour note"), "the new note is not shown");
                assert(body.querySelector('[data-sc-activity-creator]'), "no creator");
                assert(window.location.href === window.__sc1736r1Url, "the page changed");
                noHorizontalScroll();
                body.closest("dialog").querySelector("[data-pk-sheet-close]").click();
            },
        },
        {
            content: "« Done » (last) completes it",
            trigger: `${CARD} .o_sc_activity_actions button[data-sc-action="activity.complete"]`,
            run() {
                const actions = card().querySelector(".o_sc_activity_actions");
                const buttons = [...actions.querySelectorAll("button")];
                assert(buttons[buttons.length - 1].dataset.scAction === "activity.complete", "« Done » is not last");
                buttons[buttons.length - 1].click();
            },
        },
        {
            content: "Submit",
            trigger: "dialog#sc_activity_complete_sheet[open] button[type=submit]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Completed",
            trigger: PANEL,
            run() {
                assert(window.location.search.includes("success=activity_done"), window.location.search);
            },
        },
    ],
});
