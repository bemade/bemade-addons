// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).

/**
 * Open the conversation's reply draft in a pop-up over the conversation, then
 * refresh the thread once the pop-up closes (a send, a discard or a plain
 * close) so the sent message shows up without a page reload.
 *
 * @param {Object} env the calling component's environment
 * @param {Object} thread the conversation's mail thread
 * @param {number} [messageId] the message being answered; omitted for a reply
 *     to the conversation as a whole
 */
export async function openReplyDialog(env, thread, messageId) {
  const {orm, action} = env.services;
  const dialogAction = await orm.call(
    "mail.conversation",
    "action_open_draft",
    [[thread.id]],
    {message_id: messageId || false}
  );
  await action.doAction(dialogAction, {onClose: () => thread.fetchNewMessages()});
}
