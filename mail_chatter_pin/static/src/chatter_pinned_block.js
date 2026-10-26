import {Component, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {htmlToTextContentInline} from "@mail/utils/common/format";
import {useService} from "@web/core/utils/hooks";

/**
 * Compact list of the messages pinned on a record, shown on top of the chatter.
 *
 * @typedef {Object} Props
 * @property {import("models").Thread} thread
 * @extends {Component<Props, Env>}
 */
export class ChatterPinnedBlock extends Component {
  static template = "mail_chatter_pin.ChatterPinnedBlock";
  static props = ["thread"];

  setup() {
    this.store = useService("mail.store");
    this.state = useState({open: true, expanded: {}});
  }

  get isInternalUser() {
    return this.store.self_partner?.main_user_id?.share === false;
  }

  /** Pinned notes and emails of this record, most recently pinned first. */
  get messages() {
    return this.props.thread.pinnedMessages.filter(
      (message) => message.thread?.eq(this.props.thread) && !message.isEmpty
    );
  }

  get title() {
    return _t("Pinned (%(count)s)", {count: this.messages.length});
  }

  preview(message) {
    return htmlToTextContentInline(message.body);
  }

  toggle() {
    this.state.open = !this.state.open;
  }

  async onClickMessage(message) {
    this.state.expanded[message.id] = !this.state.expanded[message.id];
    await this.env.messageHighlight?.highlightMessage(message, this.props.thread);
  }

  async onClickUnpin(message) {
    await message.chatterTogglePin();
  }
}
