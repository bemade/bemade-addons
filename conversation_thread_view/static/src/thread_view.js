// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Component, onMounted, onWillStart, useChildSubEnv, useState} from "@odoo/owl";
import {Composer} from "@mail/core/common/composer";
import {ControlPanel} from "@web/search/control_panel/control_panel";
import {Thread} from "@mail/core/common/thread";
import {openReplyDialog} from "@conversation_draft/reply_dialog";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * A conversation laid out as an email thread: the messages oldest first, each
 * with its own Reply / Forward, and the same actions at the bottom. An
 * optional prototype next to the form; opening it writes nothing.
 *
 * The messages are the stock mail Thread component, so rendering, sanitizing,
 * attachments, internal-note styling and the conversation message actions
 * (Reply and Forward, Split, ...) are the ones the form's chatter uses. There
 * is deliberately no native "Send message" here: replies go through the
 * shared reply draft, in a pop-up.
 */
export class ConversationThreadView extends Component {
  static template = "conversation_thread_view.ThreadView";
  static components = {ControlPanel, Thread, Composer};
  static props = ["*"];

  setup() {
    this.store = useService("mail.store");
    this.orm = useService("orm");
    this.action = useService("action");
    this.conversationId = this.props.action.context?.active_id;
    this.state = useState({
      summary: null,
      thread: undefined,
      composerType: false,
      // Read by the stock message actions through ``env.inChatter``.
      aside: false,
      disabled: false,
      toggleComposer: (mode, {force = false} = {}) =>
        this.toggleComposer(mode, {force}),
    });
    useChildSubEnv({inChatter: this.state, conversationThreadView: true});
    onWillStart(async () => {
      this.state.summary = await this.orm.call(
        "mail.conversation",
        "thread_view_summary",
        [[this.conversationId]]
      );
    });
    onMounted(() => {
      const thread = this.store.Thread.insert({
        model: "mail.conversation",
        id: this.conversationId,
      });
      this.state.thread = thread;
      thread.fetchThreadData(["messages"]);
    });
  }

  get canPost() {
    return Boolean(this.state.thread?.canPostMessage);
  }

  toggleComposer(mode = false, {force = false} = {}) {
    this.state.composerType = !force && this.state.composerType === mode ? false : mode;
  }

  onPostCallback() {
    this.state.composerType = false;
    this.state.thread.fetchNewMessages();
  }

  onClickReply() {
    return openReplyDialog(this.env, this.state.thread);
  }

  async onClickForward() {
    const thread = this.state.thread;
    const wizard = await this.orm.call(
      "mail.conversation",
      "action_open_forward_wizard",
      [[thread.id]]
    );
    await this.action.doAction(wizard, {
      onClose: () => thread.fetchNewMessages(),
    });
  }

  onClickFormView() {
    return this.action.doAction(
      {
        type: "ir.actions.act_window",
        res_model: "mail.conversation",
        res_id: this.conversationId,
        views: [[false, "form"]],
        target: "current",
      },
      {stackPosition: "replaceCurrentAction"}
    );
  }
}

registry.category("actions").add("conversation_thread_view", ConversationThreadView);
