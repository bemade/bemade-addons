import type { DirectoryEntry } from "../../scripts/msg/compound-file/directory/types/directory-entry";
import type { Message } from "../../scripts/msg/types/message";
import { createFragmentFromTemplate } from "../../scripts/utils/html-template-util";
const template = await Bun.file("./lib/components/embedded-msg/index.html").text();

export function embeddedMsgsFragment(message: Message, onClick: (entry: DirectoryEntry) => void): DocumentFragment {
  const elements = message.attachments
    .filter(attachment => attachment.embeddedMsgObj)
    .map(attachment => {
      const model: EmbeddedMsgViewModel = { 
        name: attachment.displayName 
      };

      const fragment = createFragmentFromTemplate(template, model);
      fragment.children[0].addEventListener("click", () => onClick(attachment.embeddedMsgObj));
      return fragment;
    });

  const fragment = document.createDocumentFragment();
  fragment.append(...elements);
  return fragment;
}

interface EmbeddedMsgViewModel {
  name: string, 
}
