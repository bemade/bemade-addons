import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { user } from "@web/core/user";

export class AssignDialog extends Component {
    static template = "conversation_base.AssignDialog";
    static components = { Dialog, RecordSelector };
    static props = {
        close: Function,
        onConfirm: Function,
        count: { type: Number, optional: true },
    };

    get title() {
        return _t("Assign");
    }

    setup() {
        this.state = useState({ userId: false, teamId: false });
    }

    onUserChange(resId) {
        this.state.userId = resId;
    }

    onTeamChange(resId) {
        this.state.teamId = resId;
    }

    assignMe() {
        this.state.userId = user.userId;
    }

    get canConfirm() {
        return Boolean(this.state.userId || this.state.teamId);
    }

    async confirm() {
        if (!this.canConfirm) {
            return;
        }
        await this.props.onConfirm({ userId: this.state.userId, teamId: this.state.teamId });
        this.props.close();
    }
}
