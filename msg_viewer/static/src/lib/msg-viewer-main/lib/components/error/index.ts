import { createFragmentFromTemplate } from "../../scripts/utils/html-template-util";
const template = await Bun.file("./lib/components/error/index.html").text();

export function errorFragment(error: string): DocumentFragment {
  return createFragmentFromTemplate(template, { error });
}
