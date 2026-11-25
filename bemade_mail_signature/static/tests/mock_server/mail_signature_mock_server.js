import {
  parseRequestParams,
  registerRoute,
} from "@mail/../tests/mock_server/mail_mock_server";
import {serverState} from "@web/../tests/web_test_helpers";

/**
 * Mock of `/bemade_mail_signature/block`, registered for every mail unit test
 * so that the composer patch never hits an unmocked route (in this suite or in
 * any other addon's suite loaded alongside it). Same shape as the server: the
 * current user's signature wrapped in the folded block, "" without signature
 * or on a Discuss channel.
 */
registerRoute("/bemade_mail_signature/block", async function (request) {
  const {thread_model, thread_id} = await parseRequestParams(request);
  if (!thread_id || thread_model === "discuss.channel") {
    return "";
  }
  const [user] = this.env["res.users"].browse(serverState.userId);
  const signature = user?.signature;
  if (!signature) {
    return "";
  }
  return `<div class="o_bemade_mail_signature" data-o-mail-quote="1"><div>-- <br>${signature}</div></div>`;
});
