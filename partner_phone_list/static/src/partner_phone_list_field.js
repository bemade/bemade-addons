// Copyright 2026 Bemade Inc. License LGPL-3.0 or later.
// Phonebook widget for res.partner.phone_ids: the form shows the contact's
// Phone and Mobile as text (click to dial); a phonebook button opens a dialog
// that edits the number list of the SAME record (no server round-trip), so it
// works on new contacts and in the child-contact popup.
import { Component, useSubEnv } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { charField } from "@web/views/fields/char/char_field";
import { PhoneField, phoneField } from "@web/views/fields/phone/phone_field";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

// The SMS module patches PhoneField with an ``enableButton`` prop (and its
// SMS button). This module does not depend on SMS: pass the prop only when
// the patch is there.
function withSmsButton(props, enabled) {
    if ("enableButton" in PhoneField.props) {
        return { ...props, enableButton: Boolean(enabled) };
    }
    return props;
}

export class PartnerPhoneListDialog extends Component {
    static template = "partner_phone_list.PartnerPhoneListDialog";
    static components = { Dialog, X2ManyField };
    static props = {
        close: Function,
        fieldProps: Object,
        config: { type: Object, optional: true },
    };

    setup() {
        if (this.props.config) {
            useSubEnv({ config: this.props.config });
        }
        this.record = this.props.fieldProps.record;
        this.readonly = Boolean(this.props.fieldProps.readonly);
        // A saved main contact is saved with the dialog; a new contact or a
        // child contact keeps the changes until its own form is saved.
        this.persist = !this.readonly && this.record.config.isRoot && !this.record.isNew;
        this.canDiscard = this.persist && !this.record.dirty;
        this.env.dialogData.dismiss = () => this.dismiss();
        useBus(this.record.model.bus, "update", () => this.render(true));
    }

    get title() {
        return _t("Phone numbers");
    }

    get saveLabel() {
        if (this.readonly) {
            return _t("Close");
        }
        return this.persist ? _t("Save") : _t("Done");
    }

    get list() {
        return this.record.data[this.props.fieldProps.name];
    }

    async onSave() {
        if (!this.readonly) {
            if (!(await this.list.leaveEditMode())) {
                return;
            }
            if (this.persist && !(await this.record.save())) {
                return;
            }
        }
        this.props.close();
    }

    async onDiscard() {
        await this.record.discard();
        this.props.close();
    }

    async dismiss() {
        if (this.canDiscard) {
            return this.onDiscard();
        }
        if (!this.readonly) {
            await this.list.leaveEditMode({ discard: true });
        }
        this.props.close();
    }
}

export class PartnerPhoneListField extends Component {
    static template = "partner_phone_list.PartnerPhoneListField";
    static components = { PhoneField };
    static props = { ...X2ManyField.props };

    setup() {
        this.dialog = useService("dialog");
    }

    get record() {
        return this.props.record;
    }

    get lines() {
        return this.record.data[this.props.name].records;
    }

    get topLine() {
        return this.lines[0];
    }

    get firstMobileLine() {
        return this.lines.find((line) => line.data.type === "mobile");
    }

    get phone() {
        return this.record.data.phone || "";
    }

    get mobile() {
        return this.record.data.mobile || "";
    }

    /** Mobile gets its own row unless it is already the top number. */
    get showMobile() {
        const firstMobile = this.firstMobileLine;
        return Boolean(this.mobile) && (!firstMobile || firstMobile !== this.topLine);
    }

    get topTypeLabel() {
        const top = this.topLine;
        if (!top) {
            return "";
        }
        const selection = top.fields.type.selection || [];
        const option = selection.find(([value]) => value === top.data.type);
        return option ? option[1] : "";
    }

    get smsAvailable() {
        // a child contact not saved yet has no record for the SMS composer
        return (
            Boolean(this.record.data.phone_sms_available) &&
            (Boolean(this.record.resId) || this.record.config.isRoot)
        );
    }

    phoneProps(fieldName, sms) {
        return withSmsButton(
            { name: fieldName, record: this.record, readonly: true },
            sms && this.smsAvailable
        );
    }

    get openTitle() {
        return _t("Phone numbers");
    }

    openDialog() {
        this.dialog.add(PartnerPhoneListDialog, {
            fieldProps: { ...this.props },
            config: this.env.config,
        });
    }
}

export const partnerPhoneListField = {
    ...x2ManyField,
    component: PartnerPhoneListField,
    displayName: _t("Phone numbers (phonebook)"),
    supportedTypes: ["one2many"],
};

registry.category("fields").add("partner_phone_list", partnerPhoneListField);

/**
 * Number column of the list: the standard phone widget, with an SMS button on
 * saved Mobile numbers only (the composer is opened on the contact).
 */
export class PartnerPhoneNumberField extends Component {
    static template = "partner_phone_list.PartnerPhoneNumberField";
    static components = { PhoneField };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get innerProps() {
        const { enableButton: _enableButton, ...props } = this.props;
        return withSmsButton(props, false);
    }

    get showSms() {
        const { record } = this.props;
        return (
            Boolean(this.props.readonly) &&
            record.data.type === "mobile" &&
            Boolean(record.data.sms_available) &&
            Boolean(record.data.number) &&
            Boolean(record.resId) &&
            !record.dirty
        );
    }

    get smsTitle() {
        return _t("Send SMS");
    }

    async onSms() {
        const action = await this.orm.call("res.partner.phone", "action_send_sms", [
            [this.props.record.resId],
        ]);
        await this.action.doAction(action);
    }
}

registry.category("fields").add("partner_phone_number", {
    ...phoneField,
    component: PartnerPhoneNumberField,
    // read at call time: the SMS module patches phoneField.extractProps
    extractProps: (...args) => phoneField.extractProps(...args),
});

// Contacts list: Phone / Mobile columns with a minimum width (in px, option
// ``min_width``; default: room for "+1 514-555-0100 ext. 200").
registry.category("fields").add("partner_phone_list_char", {
    ...charField,
    listViewWidth: ({ options }) => [options?.min_width || 200],
});
