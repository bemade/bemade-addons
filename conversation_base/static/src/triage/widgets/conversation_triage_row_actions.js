import {AssignDialog} from "../dialogs/assign_dialog";
import {Component} from "@odoo/owl";
import {SnoozeDialog} from "../dialogs/snooze_dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";
import {useService} from "@web/core/utils/hooks";

const MODEL = "mail.conversation";

/**
 * Per-row triage buttons. Each shows the inverse action when it applies
 * (Handled <-> Back to my list, Done <-> Reopen, Snooze <-> Unsnooze), so
 * every action is reversible in one click. Labels follow the #4193
 * vocabulary: the per-user action is "Handled", never "Archive".
 */
export class ConversationTriageRowActions extends Component {
  static template = "conversation_base.ConversationTriageRowActions";
  static props = {...standardWidgetProps};

  setup() {
    this.orm = useService("orm");
    this.dialog = useService("dialog");
  }

  get data() {
    return this.props.record.data;
  }

  get handleLabel() {
    return this.data.my_handled ? _t("Back to my list") : _t("Handled");
  }

  get doneLabel() {
    return this.data.state === "done" ? _t("Reopen") : _t("Done");
  }

  get snoozeLabel() {
    return this.isSnoozed ? _t("Unsnooze") : _t("Snooze…");
  }

  get isSnoozed() {
    return Boolean(this.data.my_snoozed || this.data.state === "snoozed");
  }

  async call(ev, method, args = [], kwargs = {}) {
    ev.stopPropagation();
    await this.orm.call(MODEL, method, [[this.props.record.resId], ...args], {
      ...kwargs,
      context: {conversation_triage: true},
    });
    await this.props.record.model.load();
  }

  onHandle(ev) {
    return this.call(
      ev,
      this.data.my_handled ? "action_triage_unhandle" : "action_triage_handle"
    );
  }

  onDone(ev) {
    return this.call(
      ev,
      this.data.state === "done" ? "action_triage_reopen" : "action_triage_done"
    );
  }

  onSnooze(ev) {
    if (this.isSnoozed) {
      return this.call(ev, "action_triage_unsnooze");
    }
    ev.stopPropagation();
    this.dialog.add(SnoozeDialog, {
      onConfirm: ({until, team}) =>
        this.call(ev, "action_triage_snooze", [until, team]),
    });
  }

  onAssignMe(ev) {
    return this.call(ev, "action_triage_assign_me");
  }

  onAssign(ev) {
    ev.stopPropagation();
    this.dialog.add(AssignDialog, {
      onConfirm: ({userId, teamId}) => {
        const kwargs = {};
        if (userId) {
          kwargs.user_id = userId;
        }
        if (teamId) {
          kwargs.team_id = teamId;
        }
        return this.call(ev, "action_triage_assign", [], kwargs);
      },
    });
  }
}

export const conversationTriageRowActions = {
  component: ConversationTriageRowActions,
};

registry
  .category("view_widgets")
  .add("conversation_triage_row_actions", conversationTriageRowActions);
