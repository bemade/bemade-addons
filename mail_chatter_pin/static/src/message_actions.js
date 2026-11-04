import {_t} from "@web/core/l10n/translation";
import {registerMessageAction} from "@mail/core/common/message_actions";

registerMessageAction("chatter-pin", {
  condition: ({message, thread}) => message.canChatterPin(thread),
  icon: "fa fa-thumb-tack",
  name: ({message}) => (message.pinned_at ? _t("Unpin") : _t("Pin")),
  onSelected: ({message}) => message.chatterTogglePin(),
  sequence: 65,
});
