/*
 * Review round 3 of #1722 / #1723 (owner UAT 2026-10-27) — an Organisation
 * picked once, from the type-to-search picker, sticks on the first try
 * (tests/test_org_pick_round3.py).
 *
 * The bug: a press on a list option took the focus from the box; the box's
 * focusout closed the list 150 ms later, so a press held longer than that
 * (a normal trackpad / mouse click) was released over a hidden list and the
 * pick was lost. ``heldPick`` replays such a click as the browser does: a
 * cancelable mousedown on the option — the focus leaves the box unless the
 * page prevents it —, a 400 ms hold, then mouseup + click on whatever is
 * under the pointer by then.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const FORM = "form[data-sc-event-form]";
const ORG = `${FORM} select[name="organization_id"]`;
const TEAMS = `${FORM} [data-sc-event-pick="teams"]`;
const HOLD_MS = 400;

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
        await new Promise((resolve) => setTimeout(resolve, 50));
    }
}

const mouse = (type, x, y) =>
    new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, detail: 1, view: window });

/** Open the picker of ``select`` and click the option ``label``, held HOLD_MS. */
async function heldPick(select, label) {
    const picker = select.nextElementSibling;
    const input = picker.querySelector(".o_sc_picker_input");
    input.focus();
    input.click();
    await waitFor(() => !picker.querySelector(".o_sc_picker_list").hidden, "the list opens");
    const option = [...picker.querySelectorAll(".o_sc_picker_option")].find(
        (el) => el.textContent.trim() === label
    );
    assert(option, `« ${label} » is listed`);
    // Centred: never under the phone's fixed bottom bar.
    option.scrollIntoView({ block: "center" });
    const box = option.getBoundingClientRect();
    const x = box.left + box.width / 2;
    const y = box.top + box.height / 2;
    if (option.dispatchEvent(mouse("mousedown", x, y))) {
        // Not prevented: the browser moves the focus off the box (the
        // option is not focusable).
        input.blur();
    }
    await new Promise((resolve) => setTimeout(resolve, HOLD_MS));
    const under = document.elementFromPoint(x, y) || document.body;
    under.dispatchEvent(mouse("mouseup", x, y));
    under.dispatchEvent(mouse("click", x, y));
}

function labelOf(select) {
    return select.selectedOptions[0].textContent.trim();
}

function pickOrg(label) {
    return {
        content: `Pick the organisation « ${label} » once, a held click`,
        trigger: `${ORG} + .o_sc_picker .o_sc_picker_input`,
        async run() {
            await heldPick(document.querySelector(ORG), label);
        },
    };
}

function pickTeam(label) {
    return [
        { content: "Focus the teams box", trigger: `${TEAMS} input.o_sc_tags_search`, run: "click" },
        { content: `Pick « ${label} »`, trigger: `${TEAMS} .o_sc_tags_option:contains("${label}")`, run: "click" },
        { content: `« ${label} » chosen`, trigger: `${TEAMS} .o_sc_tag:contains("${label}")` },
    ];
}

function stuck(label, { warning = false } = {}) {
    return {
        content: `« ${label} » stuck on the first pick${warning ? ", the drop warning shows" : ", no warning"}`,
        trigger: `${ORG} + .o_sc_picker .o_sc_picker_input:value("${label}")`,
        run() {
            const select = document.querySelector(ORG);
            assert(labelOf(select) === label, `the organisation is « ${labelOf(select)} »`);
            assert(select.nextElementSibling.querySelector(".o_sc_picker_list").hidden, "the list stayed open");
            const box = document.querySelector(`${TEAMS} [data-sc-org-confirm-box]`);
            assert(Boolean(box) === warning, warning ? "no drop warning" : "a drop warning with no team to drop");
        },
    };
}

// From « All organizations », no team chosen: the pick sticks, no warning.
tours.add("sc_r3_org_pick_no_teams", {
    steps: () => [
        {
            content: "The form opens on « All organizations »",
            trigger: `${ORG} + .o_sc_picker .o_sc_picker_input`,
            run() {
                assert(!document.querySelector(ORG).value, "an organisation is already set");
            },
        },
        pickOrg("PC Org"),
        stuck("PC Org"),
    ],
});

// A team chosen first: an organisation that keeps it sticks with no
// warning; one that would drop it sticks and warns (#1723).
tours.add("sc_r3_org_pick_with_teams", {
    steps: () => [
        ...pickTeam("PC Team A"),
        pickOrg("PC Org"),
        stuck("PC Org"),
        {
            content: "The team is kept",
            trigger: `${TEAMS} .o_sc_tag:contains("PC Team A")`,
        },
        pickOrg("ZZ Org 1597"),
        stuck("ZZ Org 1597", { warning: true }),
    ],
});

// The events list's filters: the same picker, the page follows the pick.
tours.add("sc_r3_org_pick_filters", {
    steps: () => [
        {
            content: "Open the filters",
            trigger: "details.o_sc_disclosure:has(#sc_ev_org) > summary",
            run() {
                this.anchor.closest("details").open = true;
            },
        },
        {
            content: "Pick « ZZ Org 1597 » once, a held click",
            trigger: "#sc_ev_org + .o_sc_picker .o_sc_picker_input",
            async run() {
                await heldPick(document.querySelector("#sc_ev_org"), "ZZ Org 1597");
            },
            expectUnloadPage: true,
        },
        {
            content: "The list is filtered on it",
            trigger: "#sc_ev_org + .o_sc_picker .o_sc_picker_input:value(ZZ Org 1597)",
            run() {
                const select = document.querySelector("#sc_ev_org");
                assert(labelOf(select) === "ZZ Org 1597", `the filter is « ${labelOf(select)} »`);
                assert(new URL(location.href).searchParams.get("organization_id") === select.value, "not in the URL");
            },
        },
    ],
});
