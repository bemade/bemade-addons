import { messageFragment } from "../components/message";
import { errorFragment } from "../components/error";
import type { Message } from "./msg/types/message";
import { parse, parseDir } from "@molotochok/msg-viewer";

const $file = document.getElementById("file")!;

$file.addEventListener("change", async (event) => {
  const target = event.target as HTMLInputElement;
  if (target?.files?.length === 0) return;
  updateMessage(target.files!);
});

// To reset the file input
$file.addEventListener("click", (event) => (event.target as HTMLInputElement).value = "");


const target = document.documentElement;
target.addEventListener("dragover", (event) => event.preventDefault());
target.addEventListener("drop", (event) => {
  event.preventDefault();
  
  const files = event.dataTransfer!.files;
  if (files.length == 0) return;
  if (!files[0].name.endsWith(".msg")) return;
  
  const $file = document.getElementById("file")! as HTMLInputElement;
  $file.files = files;
  updateMessage(files);
});

async function updateMessage(files: FileList) {
  const arrayBuffer = await files[0].arrayBuffer();
  const $msg = document.getElementById("msg")!;
  renderMessage($msg, 
    () => parse(new DataView(arrayBuffer)), 
    (fragment) => $msg.replaceChildren(fragment)
  );
}

function renderMessage($msg: HTMLElement, getMessage: () => Message, updateDom: (fragment: DocumentFragment) => void) {
  let fragment: DocumentFragment;
  try {    
    const message = getMessage();
    fragment = messageFragment(message, dir => {
      renderMessage($msg,
        () => parseDir(message.file, dir), 
        (fragment) => {
          for (let i = 0; i < $msg.children.length; i++) {
            const child = $msg.children[i] as HTMLElement;
            child.classList.add("hidden");
          };
          $msg.appendChild(fragment)
        }
      );
    });
  } catch (e) {
    window.gtag('event', 'exception', { 'description': e, 'fatal': true });
    fragment = errorFragment(`An error occured during the parsing of the .msg file. Error: ${e}`);
  }

  updateDom(fragment);
}