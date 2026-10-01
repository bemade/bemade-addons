import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { _t } from "@web/core/l10n/translation";
import { serializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;

export class SnoozeDialog extends Component {
    static template = "conversation_base.SnoozeDialog";
    static components = { Dialog, DateTimeInput };
    static props = {
        close: Function,
        onConfirm: Function,
        count: { type: Number, optional: true },
    };

    get title() {
        return _t("Snooze");
    }

    setup() {
        this.state = useState({ team: false, custom: DateTime.now().plus({ days: 1 }) });
    }

    get presets() {
        const now = DateTime.now();
        const morning = { hour: 9, minute: 0, second: 0, millisecond: 0 };
        return [
            { key: "later", label: _t("Later today"), value: now.plus({ hours: 3 }) },
            {
                key: "tomorrow",
                label: _t("Tomorrow 09:00"),
                value: now.plus({ days: 1 }).set(morning),
            },
            {
                key: "monday",
                label: _t("Next Monday 09:00"),
                value: now.startOf("week").plus({ weeks: 1 }).set(morning),
            },
        ];
    }

    onCustomChange(value) {
        this.state.custom = value;
    }

    async confirm(value) {
        if (!value) {
            return;
        }
        await this.props.onConfirm({ until: serializeDateTime(value), team: this.state.team });
        this.props.close();
    }
}
