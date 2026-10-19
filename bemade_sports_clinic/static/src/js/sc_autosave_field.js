/*
 * Task 1542 (epic #1535) — sc_autosave_field, the addon's first OWL public
 * component. Mounted from QWeb with
 *   <owl-component name="bemade_sports_clinic.sc_autosave_field" props="{...}"/>
 * (core PublicComponentInteraction, like portal.signature_form).
 *
 * Two modes:
 *
 * - « draft »: the value stays a LOCAL draft on the device while typing
 *   (sc_draft_store, per db + user + record key). It comes back after
 *   leaving the page or losing signal (« Brouillon restauré »), and is
 *   dropped once the server holds the same value (the enclosing form was
 *   published), on « Jeter le brouillon », on logout, and — task 1539 — when
 *   a page carrying data-sc-draft-clear for its key prefix loads (the
 *   « created » / « added » landing of a NEW injury or note). The field is a
 *   real form field (props.name): the enclosing form posts as before.
 *
 * - « server »: POST /my/app/save/<model>/<id> ({field, value, write_date}).
 *   Task 1539 (owner decision 2026-09-28): saved when the user LEAVES the
 *   field (blur / change), never while typing — one note-history row and
 *   one chatter line per field actually changed. Visible state
 *   (enregistrement / enregistré / erreur / hors ligne — en attente);
 *   offline or network failure queues the value in the draft store and
 *   replays it when back online; a 409 (THIS field changed elsewhere since
 *   it was loaded — the route compares old_value) shows the conflict banner (« Garder
 *   le mien » re-sends over the newer write_date, « Prendre le leur » takes
 *   the server value). ``instant`` fields (status, visibility: segmented
 *   buttons) save on click and offer « Annuler » in the shell toast, which
 *   re-posts the previous value through the same route.
 *   Task 1600: a 428 « confirm_identity » answer (a portal user changing a
 *   player's existing name / date of birth) shows a confirm banner
 *   (old → new); « Confirm » re-posts with confirm=1, « Cancel » restores
 *   the saved value. Nothing is written before the confirmation.
 *
 * Task 1582: ``replace`` (server-mode textarea, opt-in — the injury notes
 * only) turns the editor into a « replace » editor: the current text is shown
 * read-only (« Current text ») above an EMPTY « New note » editor, saving
 * REPLACES the text (the old one stays in the note history), « Reuse current
 * text » copies it in for a small edit, an empty editor never saves (clearing
 * stays the explicit « Clear »). Every other field is unchanged.
 *
 * Input types: textarea | text | email | tel | date | select | segmented |
 * date_na (a date + « N/A » box, value "na" or YYYY-MM-DD) | tags (CSV of the
 * chosen option keys: removable chips + a search box suggesting a few options).
 *
 * Task 1594: a sibling save may answer THIS field's fresh choices
 * (``also[field].options``, e.g. a country change → the new country's
 * provinces); ``hideEmpty`` hides a select left with no real choice.
 *
 * Task 1608 (owner decisions 2026-10-14 / 2026-10-17):
 * - « form » mode (third mode): no autosave, no draft — the value (a tags
 *   CSV) is written to the enclosing form's hidden input ``target`` (its
 *   id), which the form posts as before (the event create form's teams and
 *   assigned staff);
 * - tags BROWSE: focusing the search box with an empty query opens the FULL
 *   scrollable list of the options left to pick (no cap), typing narrows it
 *   (the words match the option or its group), arrows + Enter pick, Escape
 *   closes; a pick closes the list (review fixes 2026-10-18); options may carry a group ([key, label, groupLabel, groupKey]):
 *   headings separate the groups when more than one is shown;
 * - ``groupSelect`` (the id of a <select>): its value narrows the options to
 *   that group (« » = all) and drops the chosen ones of another group (the
 *   event form's organization select, task 1597).
 *
 * Owner review 2026-10-14:
 * - a date / date-time / time input saves only once its value is COMPLETE:
 *   when the user leaves it (blur), presses Enter, or picks a value in the
 *   picker — never on each « change » while typing (typing the day « 15 »
 *   used to save « 01 » then « 15 »); a half-typed value is never sent;
 * - saves are SERIALIZED: while one is in flight, the latest value waits and
 *   is sent once the first answers, with the fresh write_date / old_value
 *   (two racing saves made the second one a false 409 and a Postgres
 *   « could not serialize access » error);
 * - a 409 whose current value is a value THIS field itself sent is not a
 *   conflict (no banner): the field adopts it and sends its latest value.
 */
import { Component, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { readDraft, removeDraft, writeDraft } from "@bemade_sports_clinic/js/sc_draft_store";

const DRAFT_DEBOUNCE = 300;
// Owner review 2026-10-14: inputs whose value is only complete once the
// user leaves them (or picks in the picker).
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

export class ScAutosaveField extends Component {
    static template = "bemade_sports_clinic.ScAutosaveField";
    static props = {
        mode: { type: String, optional: true }, // "draft" (default) | "server" | "form"
        name: { type: String, optional: true },
        naName: { type: String, optional: true }, // date_na, draft mode
        inputType: { type: String, optional: true },
        inputId: { type: String, optional: true },
        label: { type: String, optional: true },
        hint: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        value: { optional: true },
        options: { type: Array, optional: true }, // [[value, label], ...]
        hideEmpty: { type: Boolean, optional: true }, // task 1594
        required: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        instant: { type: Boolean, optional: true },
        clearable: { type: Boolean, optional: true },
        undoMessage: { type: String, optional: true },
        // A history sheet opened from a link next to the label (sc_app_ui).
        historySheet: { type: String, optional: true },
        historyLabel: { type: String, optional: true },
        // Task 1582: the « replace » editor (server-mode textarea only).
        replace: { type: Boolean, optional: true },
        draftKey: { type: String, optional: true },
        // Task 1608: form mode (the hidden input the value is written to)
        // and the select narrowing a tags field's options to one group.
        target: { type: String, optional: true },
        groupSelect: { type: String, optional: true },
        // server mode
        model: { type: String, optional: true },
        recordId: { type: Number, optional: true },
        field: { type: String, optional: true },
        writeDate: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.inputRef = useRef("input");
        this.listRef = useRef("list");
        this.state = useState({
            // Task 1582: in replace mode ``value`` is the NEW text being
            // written (empty on edit) and ``current`` the text the server holds.
            value: this.props.replace ? "" : asText(this.props.value),
            current: asText(this.props.value),
            status: "idle", // idle | dirty | draft | saving | saved | queued | error | conflict
            restored: false,
            conflict: null,
            savedAt: "",
            message: "",
            error: "",
            query: "", // tags: the search box
            // Task 1608: tags — the option list is open (browse), the option
            // the arrows point at, the group the options are narrowed to.
            open: false,
            active: -1,
            group: "",
            identity: null, // task 1600: {message, old, new} awaiting confirmation
            // Task 1601: the « updated on … by … » stamp under the field; a
            // save answers the fresh one (``hint``).
            hint: this.props.hint || "",
            // Task 1594: choices answered by a sibling save (null = props').
            options: null,
        });
        this.writeDate = this.props.writeDate || "";
        // The field value the server last held (sent as old_value: a record
        // written since — e.g. a sibling field saved — is not a conflict
        // while THIS field is unchanged there).
        this.lastSaved = asText(this.props.value);
        this.timer = null;
        // Owner review 2026-10-14: one save at a time (see the header).
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
        // it under « also », e.g. « Resolved » → the resolution date).
        this.onSiblingSaved = (ev) => {
            const detail = ev.detail || {};
            // Review fixes 2026-10-18: a TWIN island of the same field (the
            // player header's edit mode and the Medical card both edit the
            // actual return date; since review-fixes-1018b the allergies live
            // only in the header) follows the other's save.
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
            document.addEventListener("sc:saved", this.onSiblingSaved);
        }
        this.onGroupChange = (ev) => this.applyGroup(ev.target.value || "");
        onMounted(() => {
            this.restore();
            const select = this.groupSelectEl;
            if (select) {
                select.addEventListener("change", this.onGroupChange);
                this.applyGroup(select.value || "");
            }
        });
        // Task 1608: the option the arrows point at stays in view.
        useEffect(
            (active) => {
                const list = this.listRef.el;
                const el = list && active >= 0 && list.querySelector(`[data-sc-tags-index="${active}"]`);
                if (el && el.scrollIntoView) {
                    el.scrollIntoView({ block: "nearest" });
                }
            },
            () => [this.state.active]
        );
        onWillUnmount(() => {
            clearTimeout(this.timer);
            window.removeEventListener("online", this.onOnline);
            document.removeEventListener("sc:saved", this.onSiblingSaved);
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

    /** Task 1594: a ``hideEmpty`` select with nothing but the blank choice. */
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

    /** Task 1608: written to the form's hidden input, never saved / drafted. */
    get isForm() {
        return this.props.mode === "form";
    }

    get groupSelectEl() {
        return this.props.groupSelect ? document.getElementById(this.props.groupSelect) : null;
    }

    /** Task 1582: the opt-in « replace » editor (server-mode textarea). */
    get isReplace() {
        return Boolean(this.props.replace) && this.isServer && this.type === "textarea";
    }

    /** « Clear » is offered while there is something to clear. */
    get canClear() {
        if (!this.props.clearable || this.props.disabled) {
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

    get identityChange() {
        const identity = this.state.identity || {};
        return `${identity.old || "—"} → ${identity.new || "—"}`;
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
            // The server already holds it (published): the draft is done.
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
        // Inside an edit card's hidden edit view: ask sc_app_ui to open it.
        const card = this.inputRef.el && this.inputRef.el.closest("[data-sc-edit-card]");
        if (card) {
            card.dispatchEvent(new CustomEvent("sc:edit-open", { bubbles: true }));
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
            // Task 1582: an empty « New note » never saves (never clears),
            // and the untouched current text is not a change.
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

    /** « Effacer »: an explicit clear, saved (or drafted) at once. */
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

    /** Task 1582: « Reuse current text » — a small edit of the current text. */
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

    /** Task 1608: the options a group narrowing leaves (« » = every group). */
    get groupOptions() {
        const group = this.state.group;
        return group ? this.options.filter((opt) => String(opt[3] || "") === group) : this.options;
    }

    /**
     * Task 1608 (owner decision 2026-10-17: full visibility): the options left
     * to pick — ALL of them with an empty query (browse), else the ones every
     * typed word matches (in the option or its group). Never capped.
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
        if (this.props.disabled || this.state.open) {
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
    }

    /** Focus left the field (not to its own list): the list closes. */
    onTagsFocusout(ev) {
        const root = ev.currentTarget;
        if (ev.relatedTarget && root.contains(ev.relatedTarget)) {
            return;
        }
        setTimeout(() => {
            if (!root.contains(document.activeElement)) {
                this.closeTags();
            }
        }, 0);
    }

    /**
     * Pick an option. Review fixes 2026-10-18 (#1608): the list CLOSES right
     * after a pick, whatever picked it; focusing / clicking the search box
     * again (or ArrowDown / typing) reopens it. A tap / click leaves the box
     * (the phone keyboard closes; focusing it again reopens the list); the
     * keyboard (Enter) keeps the focus in the search box.
     */
    addTag(key, ev) {
        this.state.query = "";
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

    /**
     * Task 1608: narrow the options to ``group`` (« » = all) and drop the
     * chosen options of another group (an event never mixes organizations).
     */
    applyGroup(group) {
        this.state.group = group;
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
        if (this.props.disabled || String(value) === this.state.value) {
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
            new CustomEvent("sc:toast", {
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

    keepDraft() {
        if (norm(this.state.value) === norm(this.props.value)) {
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
     * Owner review 2026-10-14: ONE save at a time. A save asked while
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
        this.state.identity = null;
        if (navigator.onLine === false) {
            this.queue();
            return false;
        }
        this.state.status = "saving";
        this.state.error = "";
        const sent = this.state.value;
        this.rememberSent(norm(sent));
        try {
            const result = await scFetch(this.saveUrl, {
                method: "POST",
                data: Object.assign(
                    {
                        field: this.props.field,
                        value: sent,
                        write_date: this.writeDate,
                        old_value: this.lastSaved,
                    },
                    confirm ? { confirm: "1" } : {}
                ),
                toast: false,
            });
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
                // Task 1582: the saved text becomes the current one; the
                // editor is empty again for the next replacement.
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
            // Lets the page reflect a save elsewhere (e.g. the player's
            // status pill, owner review 2026-10-10).
            document.dispatchEvent(
                new CustomEvent("sc:saved", {
                    detail: {
                        model: this.props.model,
                        recordId: this.props.recordId,
                        field: this.props.field,
                        result,
                        source: this,
                    },
                })
            );
            return true;
        } catch (error) {
            if (error.status === 428 && error.payload && error.payload.confirm_identity) {
                // Task 1600: changing a player's existing name / date of
                // birth is an explicit step — nothing was saved yet.
                this.state.identity = error.payload;
                this.state.status = "confirm";
            } else if (error.status === 409 && error.payload && this.isOwnConflict(error.payload)) {
                // Owner review 2026-10-14: the newer value is one THIS field
                // sent (an earlier save of ours) — not someone else's change.
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

    /** Task 1600: « Confirm » on the identity banner — the same save, confirmed. */
    confirmIdentity() {
        this.save({ confirm: true });
    }

    /** « Cancel »: back to the value the server holds, nothing saved. */
    cancelIdentity() {
        this.state.identity = null;
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

registry.category("public_components").add("bemade_sports_clinic.sc_autosave_field", ScAutosaveField);
