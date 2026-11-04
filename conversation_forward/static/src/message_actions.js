import {_t} from "@web/core/l10n/translation";
import {registerMessageAction} from "@mail/core/common/message_actions";

registerMessageAction("conversation-forward", {
  condition: ({message, thread}) =>
    thread?.model === "mail.conversation" &&
    message.thread?.eq(thread) &&
    ["comment", "email"].includes(message.message_type),
  icon: "fa fa-share",
  name: _t("Forward"),
  onSelected: async ({message, owner, thread}) => {
    const {orm, action} = owner.env.services;
    const wizard = await orm.call(
      "mail.conversation",
      "action_open_forward_wizard",
      [[thread.id]],
      {message_id: message.id}
    );
    action.doAction(wizard, {onClose: () => thread.fetchNewMessages()});
  },
  sequence: 72,
});
