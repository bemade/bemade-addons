import { createFragmentFromTemplate } from "../../scripts/utils/html-template-util";
import template from "./index.html" with { type: "text" };

export function errorFragment(error: string): DocumentFragment {
  return createFragmentFromTemplate(template, { error });
}
