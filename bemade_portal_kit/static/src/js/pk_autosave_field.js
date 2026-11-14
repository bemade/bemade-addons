/*
 * Task 5382 (P4c3) — pk_autosave_field, the kit's autosave field (an OWL
 * public component; it was the first consumer's, task 1542). Mounted from
 * QWeb with the kit's template:
 *   <t t-call="bemade_portal_kit.pk_field_autosave"><t t-set="props" t-value="pk_field_props(...)"/></t>
 * i.e. <owl-component name="bemade_portal_kit.pk_autosave_field" props="{...}"/>
 * (core PublicComponentInteraction). The props come from the kit's builders
 * (tools/field_props.py: pk_field_props, pk_draft_props, pk_form_props).
 *
 * Three modes:
 *
 * - « draft »: the value stays a LOCAL draft on the device while typing
 *   (pk_draft_store, per db + user + record key; the key is the caller's
 *   ``draftKey``). It comes back after leaving the page or losing signal
 *   (« Draft restored »), and is dropped once the server holds the same value
 *   (the enclosing form was posted), on « Discard the draft », on logout, and
 *   when a page carrying data-pk-draft-clear for its key prefix loads (the
 *   landing of a NEW record). The field is a real form field (props.name):
 *   the enclosing form posts as before.
 *
 * - « server »: POST /my/app/save/<model>/<id> ({field, value, write_date,
 *   old_value}). Saved when the user LEAVES the field (blur / change), never
 *   while typing. Visible state (saving / saved / error / offline —
 *   pending); offline or a network failure queues the value in the draft
 *   store and replays it when back online; a 409 (THIS field changed
 *   elsewhere since it was loaded — the route compares old_value) shows the
 *   conflict banner (« Keep mine » re-sends over the newer write_date, « Take
 *   theirs » takes the server value). ``instant`` fields (segmented buttons,
 *   tags) save on click and offer « Undo » in the shell toast, which re-posts
 *   the previous value through the same route.
 *   A 428 answer ``{confirm: true, message, old, new[, detail]}`` (the save
 *   spec's ``confirm`` hook: a change that must be confirmed) shows a confirm
 *   banner (old → new); « Confirm » re-posts with confirm=1, « Cancel »
 *   restores the saved value. Nothing is written before the confirmation.
 *   A save answering ``lost_access`` (the change ended the viewer's access to
 *   the record) leaves the page with its message (pkLeavePage).
 *
 * - « form »: no autosave, no draft — the value (a tags CSV) is written to the
 *   enclosing form's hidden input ``target`` (its id), which the form posts.
 *
 * ``replace`` (server-mode textarea, opt-in) turns the editor into a
 * « replace » editor: the current text is shown read-only
 * (``replaceCurrentLabel``, default « Current text ») above an EMPTY editor
 * (``replaceNewLabel``, default « New text »); saving REPLACES the text,
 * ``replaceReuseLabel`` (default « Reuse current text ») copies it in for a
 * small edit, an empty editor never saves (clearing stays the explicit
 * « Clear »).
 *
 * Input types: textarea | text | email | tel | date | select | segmented |
 * date_na (a date + « N/A » switch, value "na" or YYYY-MM-DD) | tags (CSV of
 * the chosen option keys: removable chips + a search box).
 *
 * A sibling save may answer THIS field's fresh choices / value / lock
 * (``also[field]``); ``hideEmpty`` hides a select left with no real choice.
 *
 * Tags: focusing the search box with an empty query opens the FULL
 * scrollable list of the options left to pick (no cap), typing narrows it
 * (the words match the option or its group), arrows + Enter pick, Escape
 * closes; a pick closes the list. Options may carry a group ([key, label,
 * groupLabel, groupKey]): headings separate the groups when more than one is
 * shown. ``groupSelect`` (the id of a <select>): its value narrows the
 * options to that group (« » = all); a change that would drop chosen options
 * of another group asks first (``groupConfirmMessage`` with « %s » = the
 * dropped labels, ``groupConfirmLabel``; « Cancel » restores the select).
 * In form mode, text left typed that matches no option is an inline error
 * that blocks the form (``data-pk-guard-block``, read by the form guard).
 *
 * The picker hook: ``picker`` / ``pickerKey`` set ``data-pk-picker`` /
 * ``data-pk-picker-key`` on a select (a consumer's type-to-filter picker
 * enhances it); ``optionMeta`` ({value: {key: text}}) sets
 * ``data-pk-meta-<key>`` on each option.
 *
 * Date-like inputs save only once their value is COMPLETE: when the user
 * leaves it (blur), presses Enter, or picks a value in the picker — never on
 * each « change » while typing; a half-typed value is never sent. Saves are
 * SERIALIZED: while one is in flight, the latest value waits and is sent once
 * the first answers, with the fresh write_date / old_value. A 409 whose
 * current value is a value THIS field itself sent is not a conflict (no
 * banner): the field adopts it and sends its latest value.
 *
 * Markers on the root: data-pk-autosave (mode), data-pk-autosave-field,
 * data-pk-autosave-state, data-pk-autosave-restored; inside: data-pk-value,
 * data-pk-tags-open, -tags-index, -tags-typed-error, -tags-group-notice,
 * data-pk-replace, data-pk-group-confirm-box, -group-cancel, -group-confirm.
 */
import { Component, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { pkFetch } from "@bemade_portal_kit/js/pk_fetch";
import { readDraft, removeDraft, writeDraft } from "@bemade_portal_kit/js/pk_draft_store";
import { DATE_BOUNDS, isValidDateValue } from "@bemade_portal_kit/js/pk_date_bounds";
import { pkConfirm, pkLeavePage } from "@bemade_portal_kit/js/pk_confirm";

const DRAFT_DEBOUNCE = 300;
// Inputs whose value is only complete once the user leaves them (or picks
// in the picker).
const DATE_LIKE_TYPES = ["date", "datetime-local", "time", "month", "week", "date_na"];
// The values this field sent lately (a 409 answering one of them is ours).
const SENT_MEMORY = 5;

function fold(text) {
    return String(text || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
}

function norm(value) {
    return (value === null || value === undefined || value === false ? "" : String(value)).trim();
}

function asText(value) {
    return norm(value) === "" ? "" : String(value);
}

export class PkAutosaveField extends Component {
    static template = "bemade_portal_kit.PkAutosaveField";
    static props = {
        mode: { type: String, optional: true }, // "draft" (default) | "server" | "form"
        name: { type: String, optional: true },
        naName: { type: String, optional: true }, // date_na, draft mode
        inputType: { type: String, optional: true },
        inputId: { type: String, optional: true },
        label: { type: String, optional: true },
        // The label is visually hidden (a title above names the field; the
        // label stays its accessible name).
        labelHidden: { type: Boolean, optional: true },
        hint: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        value: { optional: true },
        options: { type: Array, optional: true }, // [[value, label], ...]
        hideEmpty: { type: Boolean, optional: true },
        required: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        instant: { type: Boolean, optional: true },
        clearable: { type: Boolean, optional: true },
        undoMessage: { type: String, optional: true },
        // A history sheet opened from a link next to the label (the kit's pk_sheets.js).
        historySheet: { type: String, optional: true },
        historyLabel: { type: String, optional: true },
        // The « replace » editor (server-mode textarea only) and its labels.
        replace: { type: Boolean, optional: true },
        replaceCurrentLabel: { type: String, optional: true },
        replaceNewLabel: { type: String, optional: true },
        replaceReuseLabel: { type: String, optional: true },
        draftKey: { type: String, optional: true },
        // Form mode (the hidden input the value is written to) and the
        // select narrowing a tags field's options to one group, with the
        // texts of its confirm (« %s » = the dropped labels) and notice.
        target: { type: String, optional: true },
        groupSelect: { type: String, optional: true },
        groupConfirmMessage: { type: String, optional: true },
        groupConfirmLabel: { type: String, optional: true },
        groupNotice: { type: String, optional: true },
        // server mode
        model: { type: String, optional: true },
        recordId: { type: Number, optional: true },
        field: { type: String, optional: true },
        writeDate: { type: String, optional: true },
        // Per-field date bounds (default 1900 .. 9999 — the 4-digit year
        // cap).
        min: { type: String, optional: true },
        max: { type: String, optional: true },
        // The picker hook on a select (a consumer's type-to-filter picker):
        // data-pk-picker, data-pk-picker-key, and per option
        // data-pk-meta-<key> from optionMeta ({value: {key: text}}).
        picker: { type: Boolean, optional: true },
        pickerKey: { type: String, optional: true },
        optionMeta: { type: Object, optional: true },
        // The empty option of a select is shown, never chosen.
        lockEmpty: { type: Boolean, optional: true },
        // {access: [keys], title ("%s" = the tag), message, confirm,
        // cancel} — removing the LAST chosen « access » tag (the one that
        // gives the viewer access to the record) asks first.
        confirmRemove: { type: Object, optional: true },
        // The « saved » wording of this field (e.g. « Sent » where a save IS
        // the sending) — « <label> · hh:mm ».
        savedLabel: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.inputRef = useRef("input");
        this.listRef = useRef("list");
        this.state = useState({
            // In replace mode ``value`` is the NEW text being written (empty
            // on edit) and ``current`` the text the server holds.
            value: this.props.replace ? "" : asText(this.props.value),
            // null = follow props.disabled.
            locked: null,
            current: asText(this.props.value),
            status: "idle", // idle | dirty | draft | saving | saved | queued | error | conflict
            restored: false,
            conflict: null,
            savedAt: "",
            message: "",
            error: "",
            query: "", // tags: the search box
            // Tags: the option list is open (browse), the option the arrows
            // point at, the group the options are narrowed to.
            open: false,
            active: -1,
            group: "",
            // Form mode: typed text matching no option (an inline error that
            // also blocks the form's submit), and the notice after a group
            // change dropped chosen options.
            typedError: "",
            groupNotice: "",
            // A group change that would drop chosen options waits for its
            // answer: {from, to, names} (nothing dropped until confirmed).
            groupConfirm: null,
            confirm: null, // a 428 {message, old, new, detail} awaiting confirmation
            // The stamp under the field (``hint``); a save answers the fresh
            // one.
            hint: this.props.hint || "",
            // Choices answered by a sibling save (null = props').
            options: null,
        });
        this.writeDate = this.props.writeDate || "";
        // The field value the server last held (sent as old_value: a record
        // written since — e.g. a sibling field saved — is not a conflict
        // while THIS field is unchanged there).
        this.lastSaved = asText(this.props.value);
        this.timer = null;
        // One save at a time (see the header).
        this.inFlight = null;
        this.pendingSave = null;
        this.sentValues = [];
        // A date-like input being typed into (keyboard): its « change »
        // events are not a commit — blur / Enter / a picker pick are.
        this.typing = false;
        this.onOnline = () => {
            if (this.state.status === "queued") {
                this.save();
            }
        };
        // A sibling field's save that also set THIS field (the save answers
        // it under « also », e.g. a status that sets a date).
        this.onSiblingSaved = (ev) => {
            const detail = ev.detail || {};
            // A TWIN island of the same field (the same record field edited
            // in two places of the page) follows the other's save.
            if (
                detail.source &&
                detail.source !== this &&
                detail.field === this.props.field &&
                detail.model === this.props.model &&
                detail.recordId === this.props.recordId &&
                detail.result &&
                detail.result.value !== undefined &&
                !this.isReplace &&
                !["dirty", "saving"].includes(this.state.status)
            ) {
                const twin = asText(detail.result.value);
                this.state.value = twin;
                this.lastSaved = twin;
                this.writeDate = detail.result.write_date;
                if (detail.result.hint !== undefined) {
                    this.state.hint = detail.result.hint || "";
                }
                return;
            }
            const also = detail.result && detail.result.also;
            if (
                !also ||
                !(this.props.field in also) ||
                detail.model !== this.props.model ||
                detail.recordId !== this.props.recordId
            ) {
                return;
            }
            if (Array.isArray(also[this.props.field].options)) {
                this.state.options = also[this.props.field].options;
            }
            // A sibling's save may lock / unlock this field.
            if (also[this.props.field].disabled !== undefined) {
                this.state.locked = Boolean(also[this.props.field].disabled);
            }
            if (["dirty", "saving"].includes(this.state.status)) {
                return;
            }
            const value = asText(also[this.props.field].value);
            if (this.isReplace) {
                this.state.current = value;
            } else {
                this.state.value = value;
            }
            this.lastSaved = value;
            this.writeDate = detail.result.write_date;
        };
        if (this.isServer) {
            document.addEventListener("pk:saved", this.onSiblingSaved);
        }
        this.onGroupChange = (ev) => this.requestGroup(ev.target.value || "");
        // An add panel reset after a successful create (« pk:form-reset » on
        // its form, pk_list_header.js): a form-mode field goes back to its
        // default, a draft-mode one is emptied and its device draft dropped.
        this.onFormReset = (ev) => {
            const anchor = this.inputRef.el || (this.props.target && document.getElementById(this.props.target));
            if (this.isServer || !anchor || !(ev.target instanceof Element) || !ev.target.contains(anchor)) {
                return;
            }
            if (this.isForm) {
                this.state.value = asText(this.props.value);
                this.state.query = "";
                this.state.open = false;
                this.state.active = -1;
                this.writeTarget();
            } else {
                this.discardDraft();
            }
        };
        document.addEventListener("pk:form-reset", this.onFormReset);
        onMounted(() => {
            this.restore();
            const select = this.groupSelectEl;
            if (select) {
                select.addEventListener("change", this.onGroupChange);
                this.applyGroup(select.value || "");
            }
        });
        // The option the arrows point at stays in view.
        useEffect(
            (active) => {
                const list = this.listRef.el;
                const el = list && active >= 0 && list.querySelector(`[data-pk-tags-index="${active}"]`);
                if (el && el.scrollIntoView) {
                    el.scrollIntoView({ block: "nearest" });
                }
            },
            () => [this.state.active]
        );
        onWillUnmount(() => {
            clearTimeout(this.timer);
            window.removeEventListener("online", this.onOnline);
            document.removeEventListener("pk:saved", this.onSiblingSaved);
            document.removeEventListener("pk:form-reset", this.onFormReset);
            const select = this.groupSelectEl;
            if (select) {
                select.removeEventListener("change", this.onGroupChange);
            }
        });
        if (this.isServer) {
            window.addEventListener("online", this.onOnline);
        }
    }

    /** The choices: the latest a sibling save answered, else the props'. */
    get options() {
        return this.state.options || this.props.options || [];
    }

    /** A ``hideEmpty`` select with nothing but the blank choice. */
    get isHidden() {
        return (
            Boolean(this.props.hideEmpty) &&
            this.type === "select" &&
            !this.options.some((opt) => norm(opt[0]) !== "")
        );
    }

    get isServer() {
        return this.props.mode === "server";
    }

    /** Form mode: written to the form's hidden input, never saved / drafted. */
    get isForm() {
        return this.props.mode === "form";
    }

    get groupSelectEl() {
        return this.props.groupSelect ? document.getElementById(this.props.groupSelect) : null;
    }

    /** The opt-in « replace » editor (server-mode textarea). */
    get isReplace() {
        return Boolean(this.props.replace) && this.isServer && this.type === "textarea";
    }

    /** « Clear » is offered while there is something to clear. */
    get canClear() {
        if (!this.props.clearable || this.isDisabled) {
            return false;
        }
        return Boolean(this.isReplace ? this.state.current : this.state.value);
    }

    get type() {
        return this.props.inputType || "text";
    }

    /** A date / date-time / time input: saved only once complete. */
    get isDateLike() {
        return DATE_LIKE_TYPES.includes(this.type);
    }

    /** Disabled by the props, or locked by a sibling's save. */
    get isDisabled() {
        // The tags wait while a group change asks for its answer.
        if (this.state.groupConfirm) {
            return true;
        }
        return this.state.locked === undefined || this.state.locked === null
            ? Boolean(this.props.disabled)
            : this.state.locked;
    }

    /** The input's bounds (props, else the 4-digit-year cap). */
    get dateBounds() {
        const bounds = DATE_BOUNDS[this.type === "date_na" ? "date" : this.type] || {};
        return { min: this.props.min || bounds.min, max: this.props.max || bounds.max };
    }

    /** A value worth keeping (empty, or an in-range date). */
    isKeepable(value) {
        return !this.isDateLike || isValidDateValue(this.type, value);
    }

    /** The browser holds a half-typed (invalid) date / time. */
    get isIncomplete() {
        const el = this.inputRef.el;
        return Boolean(
            this.isDateLike && el && el.validity && el.validity.badInput
        );
    }

    get isNa() {
        return this.state.value === "na";
    }

    get dateValue() {
        return this.isNa ? "" : this.state.value;
    }

    get key() {
        if (this.props.draftKey) {
            return this.props.draftKey;
        }
        return `${this.props.model}.${this.props.recordId}.${this.props.field}`;
    }

    get statusLabel() {
        switch (this.state.status) {
            case "draft":
                return _t("Draft kept on this device");
            case "saving":
                return _t("Saving…");
            case "saved":
                if (this.props.savedLabel) {
                    return this.state.savedAt
                        ? `${this.props.savedLabel} · ${this.state.savedAt}`
                        : this.props.savedLabel;
                }
                return this.state.savedAt ? _t("Saved · %s", this.state.savedAt) : _t("Saved");
            case "queued":
                return _t("Offline — pending");
            case "error":
                return _t("Error — not saved");
            case "conflict":
                return _t("Changed elsewhere");
            case "confirm":
                return _t("To confirm");
            default:
                return "";
        }
    }

    get conflictText() {
        const by = this.state.conflict && this.state.conflict.by;
        return by
            ? _t("%s changed this field while you were typing.", by)
            : _t("This field was changed elsewhere while you were typing.");
    }

    /** The 428 confirm banner's « old → new ». */
    get confirmChangeText() {
        const pending = this.state.confirm || {};
        return `${pending.old || "—"} → ${pending.new || "—"}`;
    }

    get replaceCurrentLabel() {
        return this.props.replaceCurrentLabel || _t("Current text");
    }

    get replaceNewLabel() {
        return this.props.replaceNewLabel || _t("New text");
    }

    get replaceReuseLabel() {
        return this.props.replaceReuseLabel || _t("Reuse current text");
    }

    get groupConfirmLabel() {
        return this.props.groupConfirmLabel || _t("Change");
    }

    get naLabel() {
        return _t("N/A");
    }

    get noMatchLabel() {
        return _t("No match");
    }

    removeLabel(label) {
        return _t("Remove %s", label);
    }

    // ------------------------------------------------------------ restore
    restore() {
        if (this.isForm) {
            return;
        }
        const draft = readDraft(this.key);
        if (!draft) {
            return;
        }
        if (!this.isKeepable(draft.value)) {
            // A draft holding an out-of-range / malformed date
            // (« 202610-10-10 ») is dropped, never brought back.
            removeDraft(this.key);
            return;
        }
        if (this.isServer) {
            // A queued (unsent) value: show it and send it again.
            this.state.value = draft.value;
            this.writeDate = draft.writeDate || this.writeDate;
            this.state.status = "queued";
            if (navigator.onLine !== false) {
                this.save();
            }
            return;
        }
        if (norm(draft.value) === norm(this.props.value)) {
            // The server already holds it (posted): the draft is done.
            removeDraft(this.key);
            return;
        }
        this.state.value = draft.value;
        this.state.restored = true;
        this.state.status = "draft";
        const details = this.inputRef.el && this.inputRef.el.closest("details");
        if (details) {
            details.open = true;
        }
        // Inside an edit card's hidden edit view: ask the kit (pk_edit_cards.js) to open it.
        const card = this.inputRef.el && this.inputRef.el.closest("[data-pk-edit-card]");
        if (card) {
            card.dispatchEvent(new CustomEvent("pk:edit-open", { bubbles: true }));
        }
    }

    discardDraft() {
        removeDraft(this.key);
        this.state.value = asText(this.props.value);
        this.state.restored = false;
        this.state.status = "idle";
    }

    // -------------------------------------------------------------- input
    onInput() {
        clearTimeout(this.timer);
        this.state.status = "dirty";
        if (!this.isServer && !this.isForm) {
            this.timer = setTimeout(() => this.keepDraft(), DRAFT_DEBOUNCE);
        }
    }

    /** blur / change: the user left the field (or picked a value). */
    commit() {
        this.typing = false;
        if (this.state.status !== "dirty") {
            return;
        }
        if (this.isIncomplete) {
            // A half-typed date is never sent (it would read as a clear).
            return;
        }
        clearTimeout(this.timer);
        if (this.isReplace && (norm(this.state.value) === "" || this.state.value === this.lastSaved)) {
            // An empty replace editor never saves (never clears), and the
            // untouched current text is not a change.
            this.state.status = "idle";
            return;
        }
        if (this.isServer) {
            this.save();
        } else if (this.isForm) {
            this.state.status = "idle";
        } else {
            this.keepDraft();
        }
    }

    /** « Clear »: an explicit clear, saved (or drafted) at once. */
    clear() {
        this.state.value = "";
        this.state.status = "dirty";
        if (this.isReplace) {
            // The explicit clear bypasses the « empty never saves » rule.
            this.save();
            return;
        }
        this.commit();
    }

    /** « Reuse current text » — a small edit of the current text. */
    reuseCurrent() {
        this.state.value = this.state.current;
        const el = this.inputRef.el;
        if (el) {
            // The textarea gets the value on the next render (t-model).
            el.value = this.state.current;
            el.focus();
            el.setSelectionRange(0, 0);
            el.scrollTop = 0;
        }
    }

    onChange() {
        this.state.status = "dirty";
        if (this.isDateLike && this.typing) {
            // Typed, not picked: the value may not be the final one yet
            // (« 01 » on the way to « 15 ») — saved on blur / Enter.
            return;
        }
        this.commit();
    }

    /** Date-like inputs: Enter commits, any other key means « typing ». */
    onDateKeydown(ev) {
        if (!this.isDateLike) {
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.commit();
        } else if (ev.key !== "Tab" && ev.key !== "Shift") {
            this.typing = true;
        }
    }

    /** A pointer on the input (opening the picker): the next change is a pick. */
    onDatePointer() {
        this.typing = false;
    }

    onNaToggle(ev) {
        if (ev.target.checked) {
            this.state.value = "na";
        } else {
            this.state.value = "";
            // Nothing to save until a date is picked (the model refuses a
            // blank date without « N/A »).
            this.state.status = "idle";
            return;
        }
        this.onChange();
    }

    // --------------------------------------------------------------- tags
    get checkedKeys() {
        return (this.state.value || "").split(",").map((key) => key.trim()).filter(Boolean);
    }

    isChecked(key) {
        return this.checkedKeys.includes(String(key));
    }

    get chosenOptions() {
        const keys = this.checkedKeys;
        return this.options.filter((opt) => keys.includes(String(opt[0])));
    }

    /** The options a group narrowing leaves (« » = every group). */
    get groupOptions() {
        const group = this.state.group;
        return group ? this.options.filter((opt) => String(opt[3] || "") === group) : this.options;
    }

    /**
     * The options left to pick — ALL of them with an empty query (browse),
     * else the ones every typed word matches (in the option or its group).
     * Never capped.
     */
    get tagMatches() {
        const words = fold(this.state.query).trim().split(/\s+/).filter(Boolean);
        return this.groupOptions
            .filter((opt) => !this.isChecked(opt[0]))
            .filter((opt) => {
                const text = fold(`${opt[1]} ${opt[2] || ""}`);
                return words.every((word) => text.includes(word));
            });
    }

    /** The list rows: the options, with a heading per group when more than one is shown. */
    get tagRows() {
        const matches = this.tagMatches;
        const groups = new Set(matches.map((opt) => opt[2] || ""));
        const headings = groups.size > 1;
        const rows = [];
        let current = null;
        matches.forEach((opt, index) => {
            const group = opt[2] || "";
            if (headings && group !== current) {
                rows.push({ key: `group:${group}`, heading: true, label: group });
            }
            current = group;
            rows.push({ key: String(opt[0]), heading: false, label: opt[1], value: opt[0], index });
        });
        return rows;
    }

    get tagsListId() {
        return `${this.props.inputId || this.key}_options`;
    }

    get tagsActiveId() {
        return this.state.open && this.state.active >= 0
            ? `${this.tagsListId}_${this.state.active}`
            : undefined;
    }

    /** Focus / click in the search box: the full list opens (browse). */
    openTags() {
        if (this.isDisabled || this.state.open) {
            return;
        }
        this.state.open = true;
        this.state.active = -1;
        const el = this.inputRef.el;
        if (el && el.scrollIntoView) {
            el.scrollIntoView({ block: "start", behavior: "smooth" });
        }
    }

    closeTags() {
        this.state.open = false;
        this.state.active = -1;
    }

    onTagsInput() {
        this.state.open = true;
        this.state.active = -1;
        this.setTypedError("");
    }

    /**
     * Form mode: the text left typed in the search box when the focus leaves
     * it (a tap on the form's submit included). An option whose label
     * is exactly that text (accents, case and spaces ignored) is picked —
     * never a silent drop; anything else is an inline error that also keeps
     * the form from submitting (``data-pk-guard-block``, read by the form
     * guard) until the text is picked, fixed or cleared.
     */
    commitTyped() {
        if (!this.isForm || this.type !== "tags") {
            return;
        }
        const typed = this.state.query.trim();
        if (!typed) {
            this.setTypedError("");
            return;
        }
        const norm = (text) => fold(text).trim().replace(/\s+/g, " ");
        const exact = this.groupOptions.find((opt) => !this.isChecked(opt[0]) && norm(opt[1]) === norm(typed));
        if (exact) {
            this.state.query = "";
            this.onCheck(exact[0], true);
            this.setTypedError("");
            return;
        }
        const already = this.options.find((opt) => this.isChecked(opt[0]) && norm(opt[1]) === norm(typed));
        if (already) {
            this.state.query = "";
            this.setTypedError("");
            return;
        }
        this.setTypedError(_t("Nothing matches « %s »: pick it from the list.", typed));
    }

    setTypedError(message) {
        if (this.state.typedError === message) {
            return;
        }
        this.state.typedError = message;
        this.syncGuardBlock();
    }

    /**
     * The form guard's block of this field (``data-pk-guard-block``): typed
     * text matching nothing, or a group change awaiting its answer.
     */
    syncGuardBlock() {
        const input = this.inputRef.el;
        const root = input && input.closest(".o_pk_tags_field");
        if (!root) {
            return;
        }
        const message = this.state.typedError || (this.state.groupConfirm ? this.groupConfirmText : "");
        if ((root.dataset.pkGuardBlock || "") === message) {
            return;
        }
        if (message) {
            root.dataset.pkGuardBlock = message;
        } else {
            delete root.dataset.pkGuardBlock;
        }
        if (this.state.typedError) {
            input.setAttribute("aria-invalid", "true");
        } else {
            input.removeAttribute("aria-invalid");
        }
        // The form guard follows (reason line, greyed submit).
        input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /** Focus left the field (not to its own list): the list closes. */
    onTagsFocusout(ev) {
        const root = ev.currentTarget;
        if (ev.relatedTarget && root.contains(ev.relatedTarget)) {
            return;
        }
        this.commitTyped();
        setTimeout(() => {
            if (!root.contains(document.activeElement)) {
                this.closeTags();
            }
        }, 0);
    }

    /**
     * Pick an option. The list CLOSES right after a pick, whatever picked it;
     * focusing / clicking the search box again (or ArrowDown / typing)
     * reopens it. A tap / click leaves the box
     * (the phone keyboard closes; focusing it again reopens the list); the
     * keyboard (Enter) keeps the focus in the search box.
     */
    addTag(key, ev) {
        this.state.query = "";
        this.setTypedError("");
        this.state.groupNotice = "";
        this.onCheck(key, true);
        this.closeTags();
        const pointer = Boolean(ev && ev.detail > 0);
        const input = this.inputRef.el;
        if (!input) {
            return;
        }
        if (pointer) {
            if (document.activeElement === input) {
                input.blur();
            }
        } else if (document.activeElement !== input) {
            input.focus();
        }
    }

    onTagKeydown(ev) {
        if (ev.target !== this.inputRef.el && ev.target !== this.listRef.el) {
            return; // a chip's « × » keeps its own keys
        }
        const matches = this.tagMatches;
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            if (!this.state.open) {
                this.openTags();
            }
            if (!matches.length) {
                return;
            }
            const step = ev.key === "ArrowDown" ? 1 : -1;
            const next = this.state.active < 0 ? (step > 0 ? 0 : matches.length - 1) : this.state.active + step;
            this.state.active = Math.max(0, Math.min(matches.length - 1, next));
        } else if (ev.key === "Enter") {
            // Never submits the enclosing form.
            ev.preventDefault();
            const pick =
                this.state.open && this.state.active >= 0
                    ? matches[this.state.active]
                    : this.state.query.trim()
                      ? matches[0]
                      : null;
            if (pick) {
                this.addTag(pick[0]);
            }
        } else if (ev.key === "Escape") {
            if (this.state.open || this.state.query) {
                ev.preventDefault();
                ev.stopPropagation();
            }
            this.state.query = "";
            this.closeTags();
        }
    }

    /** The chosen options a switch to ``group`` would drop (another group's). */
    droppedFor(group) {
        if (!group) {
            return [];
        }
        const byKey = new Map(this.options.map((opt) => [String(opt[0]), opt]));
        return this.checkedKeys
            .map((key) => byKey.get(key))
            .filter((opt) => opt && String(opt[3] || "") !== group);
    }

    /**
     * The group select changed. Dropping chosen options is never silent nor
     * immediate — an inline warning asks first (``groupConfirmLabel`` /
     * « Cancel »); nothing to drop applies at once.
     */
    requestGroup(group) {
        if (this.state.groupConfirm && group === this.state.groupConfirm.from) {
            // Back to the group in force (« Cancel », or picked again).
            this.state.groupConfirm = null;
            this.syncGuardBlock();
            return;
        }
        if (group === this.state.group && !this.state.groupConfirm) {
            return;
        }
        const dropped = this.droppedFor(group);
        if (dropped.length) {
            const from = this.state.groupConfirm ? this.state.groupConfirm.from : this.state.group;
            this.state.groupConfirm = { from, to: group, names: dropped.map((opt) => opt[1]) };
            this.state.open = false; // the picker waits for the answer
            this.syncGuardBlock();
            return;
        }
        this.state.groupConfirm = null;
        this.applyGroup(group);
        this.syncGuardBlock();
    }

    get groupConfirmText() {
        const pending = this.state.groupConfirm;
        if (!pending) {
            return "";
        }
        const names = pending.names.join(", ");
        return this.props.groupConfirmMessage
            ? this.props.groupConfirmMessage.replace("%s", names)
            : _t("Changing this removes the other group's choices: %s.", names);
    }

    confirmGroup() {
        const pending = this.state.groupConfirm;
        if (!pending) {
            return;
        }
        this.state.groupConfirm = null;
        this.applyGroup(pending.to);
        this.syncGuardBlock();
    }

    /** « Cancel »: the former group back in the select; the choices kept. */
    cancelGroup() {
        const pending = this.state.groupConfirm;
        if (!pending) {
            return;
        }
        this.state.groupConfirm = null;
        this.syncGuardBlock();
        const select = this.groupSelectEl;
        if (select) {
            select.value = pending.from;
            // A picker enhancing the select follows it.
            select.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    applyGroup(group, { notify = false } = {}) {
        this.state.group = group;
        this.state.groupNotice = "";
        if (!group) {
            return;
        }
        const byKey = new Map(this.options.map((opt) => [String(opt[0]), opt]));
        const keep = this.checkedKeys.filter((key) => {
            const opt = byKey.get(key);
            return !opt || String(opt[3] || "") === group;
        });
        if (keep.length !== this.checkedKeys.length) {
            this.onPick(keep.join(","));
            // Never a silent drop — say it, under the field.
            if (notify) {
                this.state.groupNotice =
                    this.props.groupNotice || _t("The choices of another group were removed.");
            }
        }
    }

    /** Form mode: the value goes to the form's hidden input. */
    writeTarget() {
        const el = this.props.target && document.getElementById(this.props.target);
        if (el) {
            el.value = this.state.value;
            el.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    /** Removing a tag that would end the viewer's access asks first. */
    async onRemoveTag(key) {
        const rule = this.props.confirmRemove;
        const access = new Set((rule && rule.access) || []);
        const others = this.checkedKeys.filter((k) => String(k) !== String(key) && access.has(String(k)));
        if (rule && access.has(String(key)) && !others.length) {
            const label = (this.options.find((opt) => String(opt[0]) === String(key)) || [key, key])[1];
            const go = await pkConfirm({
                title: String(rule.title || "").replace("%s", label),
                message: rule.message,
                confirm: rule.confirm,
                cancel: rule.cancel,
            });
            if (!go) {
                return; // the tag stays, nothing saved
            }
            this.leaving = true;
        }
        this.onCheck(key, false);
    }

    onCheck(key, checked) {
        const keys = new Set(this.checkedKeys);
        if (checked) {
            keys.add(String(key));
        } else {
            keys.delete(String(key));
        }
        this.onPick([...keys].sort((a, b) => Number(a) - Number(b)).join(","));
    }

    onPick(value) {
        if (this.isDisabled || String(value) === this.state.value) {
            return;
        }
        const previous = this.state.value;
        this.state.value = String(value);
        this.state.status = "dirty";
        if (this.isServer) {
            this.save().then((ok) => {
                if (ok && this.props.instant) {
                    this.offerUndo(previous);
                }
            });
        } else if (this.isForm) {
            this.writeTarget();
            this.state.status = "idle";
        } else {
            this.keepDraft();
        }
    }

    offerUndo(previous) {
        document.dispatchEvent(
            new CustomEvent("pk:toast", {
                detail: {
                    message: this.props.undoMessage || _t("Change saved"),
                    actionLabel: _t("Undo"),
                    action: () => {
                        this.state.value = previous;
                        this.save();
                    },
                },
            })
        );
    }

    /**
     * The toast of a save the SERVER can undo (« Cleared · Undo »):
     * ``undo`` = {url, token, message, action,
     * ms}. The restore answers like a save of this field (its siblings, the
     * pills and the lists follow, « pk:saved »).
     */
    offerServerUndo(undo) {
        const { model, recordId, field } = this.props;
        document.dispatchEvent(
            new CustomEvent("pk:toast", {
                detail: {
                    message: undo.message || _t("Change saved"),
                    actionLabel: undo.action || _t("Undo"),
                    duration: undo.ms,
                    action: async () => {
                        try {
                            const result = await pkFetch(undo.url, {
                                method: "POST",
                                data: { token: undo.token },
                                toast: false,
                            });
                            document.dispatchEvent(
                                new CustomEvent("pk:saved", {
                                    detail: { model, recordId, field: result.field || field, result, source: "server-undo" },
                                })
                            );
                        } catch (error) {
                            document.dispatchEvent(
                                new CustomEvent("pk:toast", {
                                    detail: {
                                        message:
                                            (error && error.payload && error.payload.message) ||
                                            _t("This change can no longer be undone."),
                                    },
                                })
                            );
                        }
                    },
                },
            })
        );
    }

    keepDraft() {
        if (norm(this.state.value) === norm(this.props.value) || !this.isKeepable(this.state.value)) {
            removeDraft(this.key);
            this.state.status = "idle";
            return;
        }
        this.state.status = writeDraft(this.key, { value: this.state.value }) ? "draft" : "idle";
    }

    // --------------------------------------------------------------- save
    get saveUrl() {
        return `/my/app/save/${encodeURIComponent(this.props.model)}/${this.props.recordId}`;
    }

    queue() {
        writeDraft(this.key, { value: this.state.value, writeDate: this.writeDate });
        this.state.status = "queued";
    }

    /**
     * ONE save at a time. A save asked while
     * another is in flight waits for it, then sends the value the field
     * holds THEN (the latest), over the fresh write_date / old_value.
     *
     * @returns {Promise<boolean>} saved
     */
    save(options = {}) {
        clearTimeout(this.timer);
        if (this.inFlight) {
            // Sent once the current save answers (the latest asked wins).
            this.pendingSave = { options };
            return this.inFlight;
        }
        this.inFlight = this.runSaves(options).finally(() => {
            this.inFlight = null;
        });
        return this.inFlight;
    }

    /** The save loop: one request at a time, then the waiting one, if any. */
    async runSaves(options) {
        let ok = false;
        let next = options;
        // A guard: a save never loops on 409s answered by our own values.
        for (let round = 0; next && round < SENT_MEMORY; round++) {
            this.pendingSave = null;
            const sent = this.state.value;
            ok = await this.sendSave(next);
            const pending = this.pendingSave;
            next = null;
            if (!pending) {
                break;
            }
            this.pendingSave = null;
            if (["conflict", "confirm", "queued"].includes(this.state.status)) {
                // The user decides first (banner) / offline: nothing more now.
                break;
            }
            if (!pending.options.confirm && this.state.value === this.lastSaved && !this.isReplace) {
                // The server already holds the latest value.
                this.state.status = "saved";
                ok = true;
                break;
            }
            if (this.state.status === "error" && this.state.value === sent) {
                break;
            }
            next = pending.options;
        }
        return ok;
    }

    rememberSent(value) {
        this.sentValues = [...this.sentValues.filter((v) => v !== value), value].slice(-SENT_MEMORY);
    }

    /** @returns {Promise<boolean>} saved */
    async sendSave({ confirm = false } = {}) {
        this.state.confirm = null;
        if (navigator.onLine === false) {
            this.queue();
            return false;
        }
        this.state.status = "saving";
        this.state.error = "";
        const sent = this.state.value;
        this.rememberSent(norm(sent));
        try {
            const result = await pkFetch(this.saveUrl, {
                method: "POST",
                data: Object.assign(
                    {
                        field: this.props.field,
                        value: sent,
                        write_date: this.writeDate,
                        old_value: this.lastSaved,
                    },
                    confirm ? { confirm: "1" } : {},
                    this.leaving ? { leaving: "1" } : {}
                ),
                toast: false,
            });
            // The save ended the viewer's access to this record (a confirmed
            // removal, or a stale page): leave it.
            if (result && result.lost_access) {
                this.state.status = "saved";
                this.leavePage(result.message);
                return true;
            }
            this.leaving = false;
            this.writeDate = result.write_date;
            // The value typed meanwhile (a save waiting) is never overwritten.
            const changedSince = this.state.value !== sent;
            if (result.value !== undefined && this.type !== "textarea" && !changedSince) {
                this.state.value = asText(result.value);
            }
            this.lastSaved = result.value !== undefined ? asText(result.value) : sent;
            if (result.value !== undefined) {
                this.rememberSent(norm(result.value));
            }
            if (this.isReplace) {
                // The saved text becomes the current one; the editor is
                // empty again for the next replacement.
                this.state.current = this.lastSaved;
                if (!changedSince) {
                    this.state.value = "";
                }
            }
            this.state.message = result.message || "";
            if (result.hint !== undefined) {
                this.state.hint = result.hint || "";
            }
            removeDraft(this.key);
            const now = new Date();
            this.state.savedAt = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
            this.state.status = this.pendingSave ? "saving" : changedSince ? "dirty" : "saved";
            this.state.conflict = null;
            // Lets the page reflect a save elsewhere (e.g. a status pill).
            document.dispatchEvent(
                new CustomEvent("pk:saved", {
                    detail: {
                        model: this.props.model,
                        recordId: this.props.recordId,
                        field: this.props.field,
                        result,
                        source: this,
                    },
                })
            );
            // A save that cleared related data answers a one-shot « Undo »
            // (the server restores).
            if (result.undo) {
                this.offerServerUndo(result.undo);
            }
            return true;
        } catch (error) {
            if (error.status === 428 && error.payload && error.payload.confirm) {
                // A change the save spec wants confirmed — nothing was saved
                // yet.
                this.state.confirm = error.payload;
                this.state.status = "confirm";
            } else if (error.status === 409 && error.payload && this.isOwnConflict(error.payload)) {
                // The newer value is one THIS field sent (an earlier save of
                // ours) — not someone else's change.
                this.writeDate = error.payload.current_write_date;
                this.lastSaved = asText(error.payload.current_value);
                if (norm(this.state.value) === norm(this.lastSaved)) {
                    this.state.status = this.pendingSave ? "saving" : "saved";
                    return true;
                }
                // Send the latest value over the fresh write_date (runSaves).
                this.pendingSave = this.pendingSave || { options: {} };
                this.state.status = "saving";
                return false;
            } else if (error.status === 409 && error.payload) {
                this.state.conflict = error.payload;
                this.state.status = "conflict";
            } else if (error.status === 0) {
                this.queue();
            } else {
                this.state.status = "error";
                this.state.error = (error.payload && error.payload.message) || "";
            }
            return false;
        }
    }

    /** A 409 answering a value this field itself sent lately. */
    isOwnConflict(payload) {
        return this.sentValues.includes(norm(payload.current_value));
    }

    /** « Confirm » on the confirm banner — the same save, confirmed. */
    confirmChange() {
        this.save({ confirm: true });
    }

    /** « Cancel »: back to the value the server holds, nothing saved. */
    cancelChange() {
        this.state.confirm = null;
        this.state.value = this.isReplace ? "" : this.lastSaved;
        this.state.status = "idle";
        removeDraft(this.key);
    }

    keepMine() {
        this.writeDate = this.state.conflict.current_write_date;
        this.lastSaved = asText(this.state.conflict.current_value);
        this.state.conflict = null;
        this.save();
    }

    /** Leave the page (pkLeavePage; a test double replaces it). */
    leavePage(message) {
        pkLeavePage(message);
    }

    /** The option's ``data-pk-meta-<key>`` attributes (``optionMeta``). */
    optionAttrs(value) {
        const meta = (this.props.optionMeta && this.props.optionMeta[value]) || {};
        const attrs = {};
        for (const [key, text] of Object.entries(meta)) {
            if (text !== null && text !== undefined && text !== false && text !== "") {
                attrs[`data-pk-meta-${key}`] = String(text);
            }
        }
        return attrs;
    }

    takeTheirs() {
        const conflict = this.state.conflict;
        const theirs = asText(conflict.current_value);
        if (this.isReplace) {
            this.state.current = theirs;
            this.state.value = "";
        } else {
            this.state.value = theirs;
        }
        this.writeDate = conflict.current_write_date;
        this.lastSaved = theirs;
        this.state.conflict = null;
        removeDraft(this.key);
        this.state.status = "saved";
    }
}

registry.category("public_components").add("bemade_portal_kit.pk_autosave_field", PkAutosaveField);
