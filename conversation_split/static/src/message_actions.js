import {_t} from "@web/core/l10n/translation";
import {registerMessageAction} from "@mail/core/common/message_actions";

registerMessageAction("conversation-split", {
  condition: ({message, thread}) =>
    thread?.model === "mail.conversation" &&
    message.thread?.eq(thread) &&
    typeof message.id === "number" &&
    message.message_type !== "user_notification",
  icon: "fa fa-scissors",
  name: _t("Split from here"),
  onSelected: async ({message, owner, thread}) => {
    const {orm, action} = owner.env.services;
    const wizard = await orm.call(
      "mail.conversation",
      "action_open_split_wizard",
      [[thread.id]],
      {message_id: message.id}
    );
    action.doAction(wizard, {onClose: () => thread.fetchNewMessages()});
  },
  sequence: 73,
});
