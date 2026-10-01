import { ListController } from "@web/views/list/list_controller";
import { AssignDialog } from "./dialogs/assign_dialog";
import { SnoozeDialog } from "./dialogs/snooze_dialog";

const MODEL = "mail.conversation";

/**
 * Triage list controller: selection actions ("Snooze...", "Assign...").
 *
 * Every action goes through an explicit-ids RPC, never through a domain.
 */
export class TriageListController extends ListController {
    static template = "conversation_base.TriageListView";

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------

    get actionRecords() {
        return [...this.model.root.selection];
    }

    async triageAction(method, args = [], kwargs = {}, records = this.actionRecords) {
        if (!records.length) {
            return;
        }
        await this.orm.call(MODEL, method, [records.map((r) => r.resId), ...args], {
            ...kwargs,
            context: { conversation_triage: true },
        });
        await this.model.load();
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
