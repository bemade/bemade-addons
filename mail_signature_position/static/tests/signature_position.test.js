/**
 * Use case: Reply All and Forward put the signature where the company wants it.
 *
 * Acceptance criteria
 * -------------------
 * - Setting `below` (default): the composer body is Odoo's standard layout —
 *   empty typing line, quote ("On ... wrote" + blockquote, or the
 *   "Forwarded message" header + body), then the signature last.
 * - Setting `above`: the signature comes right after the empty typing line and
 *   before the reply container / the "Forwarded message" header. It appears
 *   exactly once.
 * - No signature on the user: no signature block in either mode, and the body
 *   is the same as with `below`.
 * - The setting reaches the client as a global store value
 *   (`store.mail_signature_position`), the shape the server sends.
 */
import {
  asyncStep,
  getService,
  mockService,
  onRpc,
  serverState,
  waitForSteps,
} from "@web/../tests/web_test_helpers";
import {
  click,
  contains,
  defineMailModels,
  openFormView,
  start,
  startServer,
} from "@mail/../tests/mail_test_helpers";
import {describe, expect, test} from "@odoo/hoot";

describe.current.tags("desktop");
defineMailModels();

const SIGNATURE = "<p>Sam Signer, Example Inc.</p>";

/**
 * Prepare a partner with one incoming email, open its chatter, run the given
 * message action and return the composer body (as a detached DOM tree).
 *
 * @param {"Reply All"|"Forward"} actionName
 * @param {{position?: string, signature?: string|false}} options
 */
async function getComposerBody(actionName, {position, signature = SIGNATURE} = {}) {
  const pyEnv = await startServer();
  const partnerId = pyEnv["res.partner"].create({name: "Customer Record"});
  const authorId = pyEnv["res.partner"].create({
    name: "Alex Sender",
    email: "alex.sender@example.com",
  });
  pyEnv["mail.message"].create({
    author_id: authorId,
    body: "<p>Original question</p>",
    message_type: "email",
    model: "res.partner",
    res_id: partnerId,
    subject: "Original subject",
  });
  if (signature) {
    pyEnv["res.users"].write([serverState.userId], {signature});
  }
  onRpc("/mail/thread/recipients", () => []);
  onRpc("ir.attachment", "copy", () => []);
  let body = "";
  mockService("action", {
    doAction(action) {
      if (action?.res_model === "mail.compose.message") {
        body = action.context.default_body;
        asyncStep("composer");
        return;
      }
      return super.doAction(...arguments);
    },
  });
  await start();
  if (position) {
    // Same shape as the server's `store.add_global_values(...)` payload.
    getService("mail.store").insert({Store: {mail_signature_position: position}});
  }
  await openFormView("res.partner", partnerId);
  await contains(".o-mail-Message");
  await click(".o-mail-Message [title='Expand']");
  await click(
    `.o-dropdown-item:contains('${actionName}'), .o-mail-Message [title='${actionName}']`
  );
  await waitForSteps(["composer"]);
  const root = document.createElement("div");
  root.innerHTML = body.toString();
  return root;
}

/** Index, among the top-level nodes of `root`, of the first node matching. */
function indexOf(root, predicate) {
  return [...root.children].findIndex(predicate);
}
const isSignature = (el) => Boolean(el.querySelector(".o-signature-container"));
const isReplyQuote = (el) => el.classList.contains("o_mail_reply_container");
const isForwardHeader = (el) => el.textContent.includes("Forwarded message");
const isTypingLine = (el) => el.tagName === "DIV" && el.innerHTML === "<br>";

test("store accepts the server's mail_signature_position global value", async () => {
  await start();
  const store = getService("mail.store");
  expect(store.mail_signature_position).toBe("below");
  store.insert({Store: {mail_signature_position: "above"}});
  expect(store.mail_signature_position).toBe("above");
});

test("Reply All, below (default): signature after the quote", async () => {
  const root = await getComposerBody("Reply All");
  expect(isTypingLine(root.children[0])).toBe(true);
  const quote = indexOf(root, isReplyQuote);
  const sig = indexOf(root, isSignature);
  expect(quote).toBe(1);
  expect(sig).toBeGreaterThan(quote);
  expect(root.querySelectorAll(".o-signature-container")).toHaveLength(1);
  expect(root.querySelector(".o-signature-container").textContent).toInclude(
    "Sam Signer"
  );
});

test("Reply All, above: signature right after the typing line, before the quote", async () => {
  const root = await getComposerBody("Reply All", {position: "above"});
  expect(isTypingLine(root.children[0])).toBe(true);
  const sig = indexOf(root, isSignature);
  const quote = indexOf(root, isReplyQuote);
  expect(sig).toBe(1);
  expect(quote).toBeGreaterThan(sig);
  expect(root.querySelector(".o_mail_reply_container").textContent).toInclude("wrote");
  expect(root.querySelectorAll(".o-signature-container")).toHaveLength(1);
});

test("Forward, below (default): signature after the forwarded message", async () => {
  const root = await getComposerBody("Forward");
  expect(isTypingLine(root.children[0])).toBe(true);
  const header = indexOf(root, isForwardHeader);
  const sig = indexOf(root, isSignature);
  expect(header).toBe(1);
  expect(sig).toBeGreaterThan(header);
  expect(root.querySelectorAll(".o-signature-container")).toHaveLength(1);
});

test("Forward, above: signature right after the typing line, before the header", async () => {
  const root = await getComposerBody("Forward", {position: "above"});
  expect(isTypingLine(root.children[0])).toBe(true);
  const sig = indexOf(root, isSignature);
  const header = indexOf(root, isForwardHeader);
  expect(sig).toBe(1);
  expect(header).toBeGreaterThan(sig);
  expect(root.querySelectorAll(".o-signature-container")).toHaveLength(1);
});

test("no signature: nothing added, above renders like below (Reply All)", async () => {
  const above = await getComposerBody("Reply All", {
    position: "above",
    signature: false,
  });
  expect(above.querySelectorAll(".o-signature-container")).toHaveLength(0);
  expect(indexOf(above, isReplyQuote)).toBe(1);
});

test("no signature: nothing added, above renders like below (Forward)", async () => {
  const above = await getComposerBody("Forward", {position: "above", signature: false});
  expect(above.querySelectorAll(".o-signature-container")).toHaveLength(0);
  expect(indexOf(above, isForwardHeader)).toBe(1);
});
