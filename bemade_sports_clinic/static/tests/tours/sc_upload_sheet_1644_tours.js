/*
 * Task 1644 — the upload sheet on a phone (tests/test_upload_sheet_tours_1644.py,
 * 390 px): both callers (the player's Documents tab — now a sheet — and the
 * injury card's « Add documents »).
 *
 * - six files: the head (the picker) and Upload stay in view, only the
 *   middle scrolls (scrollHeight > clientHeight);
 * - the drop zone reads « Add files » on a phone (a button, same input);
 * - Upload turns « Uploading… », disabled, aria-busy; a second submit is
 *   refused; a page shown again (pageshow) is idle again;
 * - the player tab really posts: the documents are listed after the reload.
 *
 * The iPhone keyboard, the native picker and real scrolling stay UNVERIFIED
 * until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function setFiles(input, files) {
    const transfer = new DataTransfer();
    for (const file of files) {
        transfer.items.add(file);
    }
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

function sixFiles() {
    return [1, 2, 3, 4, 5, 6].map(
        (n) => new File([`synthetic ${n}`], `Synthetic 1644 ${n}.pdf`, { type: "application/pdf", lastModified: n })
    );
}

function visible(el) {
    return Boolean(el && el.getClientRects().length && getComputedStyle(el).display !== "none");
}

function checkLayout(sheetSelector) {
    const sheet = document.querySelector(`${sheetSelector}[open]`);
    assert(sheet, "the sheet is not open");
    const form = sheet.querySelector("form[data-sc-doc-upload]");
    setFiles(form.querySelector('input[type="file"]'), sixFiles());
    assert(form.querySelectorAll("[data-sc-file-list] li.o_sc_file").length === 6, "six rows expected");
    const scroll = form.querySelector("[data-sc-doc-scroll]");
    assert(scroll.scrollHeight > scroll.clientHeight + 10,
        `the middle does not scroll: ${scroll.scrollHeight} / ${scroll.clientHeight}`);
    scroll.scrollTop = scroll.scrollHeight;
    const submit = form.querySelector("[data-sc-doc-submit]").getBoundingClientRect();
    assert(submit.bottom <= window.innerHeight + 0.5 && submit.top >= 0,
        `Upload out of view: ${submit.top}-${submit.bottom} / ${window.innerHeight}`);
    const zone = form.querySelector("[data-sc-dropzone]").getBoundingClientRect();
    const why = () => {
        const cs = getComputedStyle(sheet);
        const r = sheet.getBoundingClientRect();
        const ss = getComputedStyle(scroll);
        const body = sheet.querySelector(".o_sc_sheet_body");
        return `#${sheet.id} modal=${sheet.matches(":modal")} open=${document.querySelectorAll("dialog[open]").length} ` +
            `pos=${cs.position} vh=${window.innerHeight} scrollY=${window.scrollY} sheet ${Math.round(r.top)}-${Math.round(r.bottom)} display=${cs.display} max-h=${cs.maxHeight} ` +
            `overflow=${cs.overflow} scrollTop=${sheet.scrollTop}; body scrollTop=${body.scrollTop} ` +
            `overflow=${getComputedStyle(body).overflow}; middle overflow=${ss.overflowY} h=${scroll.clientHeight}`;
    };
    assert(zone.top >= 0 && zone.bottom <= window.innerHeight, `the picker scrolled away: ${zone.top} (${why()})`);
    const title = sheet.querySelector(".o_sc_sheet_head").getBoundingClientRect();
    assert(title.top >= 0, "the sheet head left the screen");
    // Phone: the drop zone is a plain « Add files » button.
    assert(visible(form.querySelector(".o_sc_dropzone_text_touch")), "« Add files » not shown on a phone");
    assert(!visible(form.querySelector(".o_sc_dropzone_text")), "the drop-zone text still shows on a phone");
    return form;
}

function checkBusy(form) {
    const submit = form.querySelector("[data-sc-doc-submit]");
    assert(submit.disabled, "Upload stays enabled while sending");
    assert(form.getAttribute("aria-busy") === "true", "no aria-busy");
    assert(visible(submit.querySelector(".o_sc_btn_busy")), "no « Uploading… » label");
    assert(!visible(submit.querySelector(".o_sc_btn_idle")), "the idle label still shows");
    const cancel = form.querySelector("button[data-sc-sheet-close]");
    assert(!cancel || cancel.disabled, "Cancel stays enabled while sending");
}

tours.add("sc_1644_player_tab", {
    steps: () => [
        {
            content: "« + Ajouter » of the Documents list opens the sheet",
            trigger: '.o_sc_list_header button.o_sc_list_add[data-sc-sheet-open="sc_documents_upload"]',
            run: "click",
        },
        {
            content: "Six files: pinned head and Upload, the middle scrolls",
            trigger: "dialog#sc_documents_upload[open] .o_sc_dropzone",
            run() {
                checkLayout("dialog#sc_documents_upload");
            },
        },
        {
            content: "Upload: « Uploading… » at once, then the page changes",
            trigger: "dialog#sc_documents_upload[open] [data-sc-doc-submit]",
            run() {
                const form = this.anchor.closest("form");
                this.anchor.click();
                checkBusy(form);
            },
            expectUnloadPage: true,
        },
        {
            content: "The documents are listed",
            trigger: '.o_sc_app section[data-sc-tab-panel="documents"]:contains("Synthetic 1644 6.pdf")',
        },
    ],
});

tours.add("sc_1644_injury_card", {
    steps: () => [
        {
            content: "The card's « Add documents »",
            trigger: 'details.o_sc_injury_item[open] .o_sc_list_header button.o_sc_list_add[data-sc-action="injury.documents.add"]',
            run: "click",
        },
        {
            content: "Six files: pinned head and Upload; busy on submit; a second submit refused; idle again on pageshow",
            trigger: 'dialog[id$="_documents_add"][open] .o_sc_dropzone',
            run() {
                const form = checkLayout('dialog[id$="_documents_add"]');
                // A synthetic submit event runs the handlers without posting.
                const first = new Event("submit", { bubbles: true, cancelable: true });
                form.dispatchEvent(first);
                assert(!first.defaultPrevented, "a valid upload was blocked");
                checkBusy(form);
                const second = new Event("submit", { bubbles: true, cancelable: true });
                form.dispatchEvent(second);
                assert(second.defaultPrevented, "a second submit went through");
                const escape = new Event("cancel", { cancelable: true });
                form.closest("dialog").dispatchEvent(escape);
                assert(escape.defaultPrevented, "Escape would drop a busy upload");
                // (persisted: true would replay sc_fragments' « stale page » reload)
                window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: false }));
                const submit = form.querySelector("[data-sc-doc-submit]");
                assert(!submit.disabled && !form.hasAttribute("aria-busy"), "not idle after pageshow");
                assert(visible(submit.querySelector(".o_sc_btn_idle")), "idle label missing");
            },
        },
    ],
});
