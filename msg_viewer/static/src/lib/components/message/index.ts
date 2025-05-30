import type { DirectoryEntry } from "../../scripts/msg/compound-file/directory/types/directory-entry";
import type { Message, MessageContent } from "../../scripts/msg/types/message";
import { createFragmentFromTemplate } from "../../scripts/utils/html-template-util";
import { attachmentsFragment } from "../attachment";
import { embeddedMsgsFragment } from "../embedded-msg";
import { recipientsFragments } from "../recipient";
import template from "./index.html" with { type: "text" };

export function messageFragment(message: Message, renderDir: (dir: DirectoryEntry) => void): DocumentFragment {
  const [toRecip, ccRecip] = recipientsFragments(message);

  const model: MessageViewModel = {
    title: message.content.subject,
    name: getName(message.content),
    date: getDate(message.content),
    rawContent: message.content.body,
  };

  const container = createFragmentFromTemplate(template, model);
  addFragmentToContainer(container, ".msg-attachs", attachmentsFragment(message), false);
  addFragmentToContainer(container, ".msg-embedded-msgs", embeddedMsgsFragment(message, renderDir), true);
  addFragmentToContainer(container, ".msg-recip-to", toRecip, false);
  addFragmentToContainer(container, ".msg-recip-cc", ccRecip, false);

  container.querySelector(".msg-close-btn")?.addEventListener("click", (e) => {
    const $btn = e.currentTarget as HTMLElement;
    const $msg = $btn.closest(".msg")!;
    const $container = $msg.parentElement!;
    $msg.remove();

    const lastChild = $container.lastChild as HTMLElement;
    if (lastChild) {
      lastChild.classList.remove("hidden");
    }
  });

  return container;
}

function addFragmentToContainer(container: DocumentFragment, className: string, fragment: DocumentFragment, removeIfEmpty: boolean) {
  const element = container.querySelector(className);
  if (!element) return;

  if (fragment.children.length === 0 && removeIfEmpty) {
    element.parentElement?.remove();
    return;
  }

  element.replaceChildren(fragment);
}

function getName(content: MessageContent): string {
  let name = content.senderName ?? "";
  if (content.senderEmail) {
    name += ` &lt;${content.senderEmail}&gt;`;
  }
  return name;
}

function getDate(content: MessageContent): string {
  return content.date?.toLocaleString('en-US', {
    weekday: "short",
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: "UTC",
    timeZoneName: "short"
  }) ?? "";
}

interface MessageViewModel {
  title: string,
  name: string,
  date: string,
  rawContent: string,
}
