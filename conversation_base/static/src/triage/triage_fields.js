// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {deserializeDateTime} from "@web/core/l10n/dates";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

/** Avatars (or initials) of the first participants, then "+N". */
export class ConversationParticipantsField extends Component {
  static template = "conversation_base.ConversationParticipantsField";
  static props = {...standardFieldProps};

  get payload() {
    return this.props.record.data[this.props.name] || {items: [], extra: 0};
  }

  avatarUrl(item) {
    return `/web/image/res.partner/${item.partner_id}/avatar_128`;
  }
}

export const conversationParticipantsField = {
  component: ConversationParticipantsField,
  displayName: _t("Conversation participants"),
  supportedTypes: ["json"],
};
registry
  .category("fields")
  .add("conversation_participants", conversationParticipantsField);

/** Chips for the records a conversation is about. */
export class ConversationLinksField extends Component {
  static template = "conversation_base.ConversationLinksField";
  static props = {...standardFieldProps};

  setup() {
    this.action = useService("action");
  }

  get payload() {
    return this.props.record.data[this.props.name] || {items: [], extra: 0};
  }

  openLink(ev, item) {
    // Do not let the row click open the conversation as well.
    ev.stopPropagation();
    ev.preventDefault();
    if (item.restricted || !item.res_id) {
      return;
    }
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: item.res_model,
      res_id: item.res_id,
      views: [[false, "form"]],
    });
  }
}

export const conversationLinksField = {
  component: ConversationLinksField,
  displayName: _t("Conversation linked records"),
  supportedTypes: ["json"],
};
registry.category("fields").add("conversation_links", conversationLinksField);

const CHANNEL_ICONS = {
  gmail: "fa-google",
  imap: "fa-envelope-o",
  internal: "fa-comments-o",
};

/** Channel icon with its name as a tooltip. */
export class ConversationChannelField extends Component {
  static template = "conversation_base.ConversationChannelField";
  static props = {...standardFieldProps};

  get channel() {
    return this.props.record.data[this.props.name] || "internal";
  }

  get icon() {
    return CHANNEL_ICONS[this.channel] || "fa-envelope-o";
  }

  get title() {
    return this.channel === "internal" ? _t("Internal") : this.channel;
  }
}

export const conversationChannelField = {
  component: ConversationChannelField,
  displayName: _t("Conversation channel"),
  supportedTypes: ["char"],
};
registry.category("fields").add("conversation_channel", conversationChannelField);

/** "3 hours ago", with the full date as the tooltip. */
export class ConversationRelativeTimeField extends Component {
  static template = "conversation_base.ConversationRelativeTimeField";
  static props = {...standardFieldProps};

  get value() {
    const value = this.props.record.data[this.props.name];
    if (!value) {
      return false;
    }
    // Record.data already holds a luxon DateTime; only strings need parsing.
    return typeof value === "string" ? deserializeDateTime(value) : value;
  }

  get relative() {
    return this.value ? this.value.toRelative() : "";
  }

  get full() {
    return this.value
      ? this.value.toLocaleString(this.value.constructor.DATETIME_MED)
      : "";
  }
}

export const conversationRelativeTimeField = {
  component: ConversationRelativeTimeField,
  displayName: _t("Relative time"),
  supportedTypes: ["datetime"],
};
registry
  .category("fields")
  .add("conversation_relative_time", conversationRelativeTimeField);
