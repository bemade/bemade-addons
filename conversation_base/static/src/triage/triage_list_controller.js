import { useState, useSubEnv } from "@odoo/owl";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { ListController } from "@web/views/list/list_controller";
import { AssignDialog } from "./dialogs/assign_dialog";
import { SnoozeDialog } from "./dialogs/snooze_dialog";

const MODEL = "mail.conversation";
// Targets inside which bare keys must keep their native meaning.
const KEY_GUARD = "button, a, input:not([type=checkbox]), textarea, select, .o_data_cell, .o_searchview, .modal";

/**
 * Triage list controller: selection actions ("Snooze...", "Assign...") and
 * the keyboard accelerator. Bare keys go through the native hotkey service
 * (``useHotkey``), which already ignores inputs and blocked UIs; the only
 * custom logic is the focused-row index, range selection and re-focusing
 * after rows leave the list.
 *
 * Every action goes through an explicit-ids RPC, never through a domain.
 */
export class TriageListController extends ListController {
    static template = "conversation_base.TriageListView";

    setup() {
        super.setup();
        this.triage = useState({ focusedResId: false });
        useSubEnv({ triage: this.triage });
        const nav = { isAvailable: () => this.hotkeysAvailable, allowRepeat: true };
        const act = { isAvailable: () => this.hotkeysAvailable };
        useHotkey("j", () => this.moveFocus(1), nav);
        useHotkey("k", () => this.moveFocus(-1), nav);
        useHotkey("shift+j", () => this.moveFocus(1, true), nav);
        useHotkey("shift+k", () => this.moveFocus(-1, true), nav);
        useHotkey("e", () => this.triageAction("action_triage_done"), act);
        useHotkey("s", () => this.onClickSnooze(), act);
        useHotkey("a", () => this.triageAction("action_triage_assign_me"), act);
        useHotkey("enter", () => this.openFocused(), {
            isAvailable: (target) =>
                this.hotkeysAvailable && !(target && target.closest && target.closest(KEY_GUARD)),
        });
        useHotkey("escape", () => this.clearSelection(), {
            isAvailable: (target) =>
                this.model.root.selection.length > 0 &&
                !(target && target.closest && target.closest(".o_searchview, .modal")),
        });
    }

    // ------------------------------------------------------------------
    // Focus / selection helpers
    // ------------------------------------------------------------------

    get hotkeysAvailable() {
        return this.model.isReady && !this.model.root.editedRecord;
    }

    get visibleRecords() {
        const root = this.model.root;
        if (root.isGrouped) {
            return root.groups.flatMap((group) => (group.list ? group.list.records : []));
        }
        return root.records;
    }

    get focusedIndex() {
        const resId = this.triage.focusedResId;
        return resId ? this.visibleRecords.findIndex((r) => r.resId === resId) : -1;
    }

    get focusedRecord() {
        const index = this.focusedIndex;
        return index >= 0 ? this.visibleRecords[index] : null;
    }

    /** The records an action applies to: the selection, else the focused row. */
    get actionRecords() {
        const selection = this.model.root.selection;
        if (selection.length) {
            return [...selection];
        }
        const focused = this.focusedRecord;
        return focused ? [focused] : [];
    }

    moveFocus(step, extend = false) {
        const records = this.visibleRecords;
        if (!records.length) {
            return;
        }
        let index = this.focusedIndex;
        if (index < 0) {
            index = step > 0 ? 0 : records.length - 1;
            if (!extend) {
                this.triage.focusedResId = records[index].resId;
                return;
            }
        }
        if (extend) {
            records[index].toggleSelection(true);
        }
        const next = Math.max(0, Math.min(records.length - 1, index + step));
        this.triage.focusedResId = records[next].resId;
        if (extend) {
            records[next].toggleSelection(true);
        }
    }

    clearSelection() {
        for (const record of [...this.model.root.selection]) {
            record.toggleSelection(false);
        }
    }

    /** After rows left the list, focus the row now sitting at the same index
     * (the next one), or the last row when the end of the list was reached. */
    refocus(index) {
        const records = this.visibleRecords;
        if (!records.length) {
            this.triage.focusedResId = false;
            return;
        }
        const current = this.triage.focusedResId;
        if (current && records.some((r) => r.resId === current)) {
            return;
        }
        this.triage.focusedResId = records[Math.min(Math.max(index, 0), records.length - 1)].resId;
    }

    openFocused() {
        const record = this.actionRecords[0];
        if (record) {
            return this.openRecord(record);
        }
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------

    async triageAction(method, args = [], kwargs = {}, records = this.actionRecords) {
        if (!records.length) {
            return;
        }
        const visible = this.visibleRecords;
        const index = Math.min(...records.map((r) => visible.indexOf(r)).filter((i) => i >= 0));
        await this.orm.call(MODEL, method, [records.map((r) => r.resId), ...args], {
            ...kwargs,
            context: { conversation_triage: true },
        });
        await this.model.load();
        this.refocus(Number.isFinite(index) ? index : 0);
    }

    onClickSnooze() {
        const records = this.actionRecords;
        if (!records.length) {
            return;
        }
        this.dialogService.add(SnoozeDialog, {
            count: records.length,
            onConfirm: ({ until, team }) =>
                this.triageAction("action_triage_snooze", [until, team], {}, records),
        });
    }

    onClickAssign() {
        const records = this.actionRecords;
        if (!records.length) {
            return;
        }
        this.dialogService.add(AssignDialog, {
            count: records.length,
            onConfirm: ({ userId, teamId }) => {
                const kwargs = {};
                if (userId) {
                    kwargs.user_id = userId;
                }
                if (teamId) {
                    kwargs.team_id = teamId;
                }
                return this.triageAction("action_triage_assign", [], kwargs, records);
            },
        });
    }
}
