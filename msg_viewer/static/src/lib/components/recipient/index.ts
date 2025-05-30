import type { Message, Recipient } from "../../scripts/msg/types/message";
import { createFragmentFromTemplate } from "../../scripts/utils/html-template-util";
import template from "./index.html" with { type: "text" };

export function recipientsFragments(message: Message): DocumentFragment[] {
  const toRecipients = toSet(message.content.toRecipients);
  const ccRecipients = toSet(message.content.ccRecipients);

  const to = [];
  const cc = [];
  for (const recipient of message.recipients) {
    if (toRecipients.has(recipient.name)) {
      to.push(recipient);
    } else if (ccRecipients.has(recipient.name)) {
      cc.push(recipient);
    }
  }

  return [recipientHTML(to), recipientHTML(cc)];
}

function recipientHTML(recipients: Recipient[]): DocumentFragment {
  const recipFragments = recipients.map(recipient => {
    const model: RecipientViewModel = { 
      name: recipient.name, 
      email: recipient.email ? `&lt;${recipient.email}&gt;` : "" 
    };

    return createFragmentFromTemplate(template, model);
  });

  const fragment = document.createDocumentFragment();
  fragment.append(...recipFragments);
  return fragment;
}

function toSet(recipStr: string) {
  if (!recipStr) return new Set();
  
  return new Set(recipStr.endsWith('\x00') 
    ? recipStr.slice(0, -1).split("; ")
    : recipStr.split("; "));
}

interface RecipientViewModel {
  name: string,
  email: string
}