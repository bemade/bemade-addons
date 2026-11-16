/**
 * Use case: the chatter composer shows the signature exactly as it is sent.
 *
 * Acceptance criteria
 * -------------------
 * - « Send message »: the server-provided signature block is shown under the
 *   input, with an « Edit » link.
 * - « Edit » opens the full composer (mail.compose.message).
 * - « Log note »: no signature block.
 * - A user without signature: no block.
 * - « Remove signature » posts with `email_add_signature: false` (the server
 *   then adds nothing); « Add signature » brings the block back.
 */
import {
  asyncStep,
  mockService,
  serverState,
  waitForSteps,
} from "@web/../tests/web_test_helpers";
import {
  click,
  contains,
  defineMailModels,
  insertText,
  onRpcBefore,
  openFormView,
  start,
  startServer,
} from "@mail/../tests/mail_test_helpers";
import {describe, test} from "@odoo/hoot";

describe.current.tags("desktop");
defineMailModels();

const SIGNATURE = "<p>Sam Signer, Example Widgets Inc.</p>";

async function openPartner({signature = SIGNATURE} = {}) {
  const pyEnv = await startServer();
  const partnerId = pyEnv["res.partner"].create({name: "Casey Customer"});
  pyEnv["res.users"].write([serverState.userId], {signature});
  return partnerId;
}

test("send message shows the signature block", async () => {
  const partnerId = await openPartner();
  await start();
  await openFormView("res.partner", partnerId);
  await click("button", {text: "Send message"});
  await contains(".o_bemade_mail_signature_preview .o_bemade_mail_signature", {
    text: "-- Sam Signer, Example Widgets Inc.",
  });
  await contains(".o_bemade_mail_signature_preview .o_bemade_mail_signature_edit", {
    text: "Edit",
  });
});

test("log note hides the signature block", async () => {
  const partnerId = await openPartner();
  await start();
  await openFormView("res.partner", partnerId);
  await click("button", {text: "Send message"});
  await contains(".o_bemade_mail_signature_preview");
  await click("button", {text: "Log note"});
  await contains(".o-mail-Composer");
  await contains(".o_bemade_mail_signature_preview", {count: 0});
});

test("no signature, no block", async () => {
  const partnerId = await openPartner({signature: false});
  await start();
  await openFormView("res.partner", partnerId);
  await click("button", {text: "Send message"});
  await contains(".o-mail-Composer");
  await contains(".o_bemade_mail_signature_preview", {count: 0});
});

test("edit opens the full composer", async () => {
  const partnerId = await openPartner();
  mockService("action", {
    doAction(action) {
      if (action?.res_model === "mail.compose.message") {
        asyncStep("full composer");
        return;
      }
      return super.doAction(...arguments);
    },
  });
  await start();
  await openFormView("res.partner", partnerId);
  await click("button", {text: "Send message"});
  await click(".o_bemade_mail_signature_edit");
  await waitForSteps(["full composer"]);
});

test("remove then restore the signature", async () => {
  const partnerId = await openPartner();
  onRpcBefore("/mail/message/post", (args) => {
    asyncStep(`post signature=${args.post_data.email_add_signature}`);
  });
  await start();
  await openFormView("res.partner", partnerId);
  await click("button", {text: "Send message"});
  await click(".o_bemade_mail_signature_remove");
  await contains(".o_bemade_mail_signature_block", {count: 0});
  await click(".o_bemade_mail_signature_restore");
  await contains(".o_bemade_mail_signature_block");
  await click(".o_bemade_mail_signature_remove");
  await insertText(".o-mail-Composer-input", "no signature");
  await click(".o-mail-Composer button[aria-label='Send']:enabled");
  await waitForSteps(["post signature=false"]);
});
