export function createFragmentFromTemplate<T>(html: string, obj: T): DocumentFragment {
  const element = document.createElement("div");
  element.innerHTML = fillHTMLTemplate(html, obj);

  const fragment = document.createDocumentFragment();
  while(element.children.length > 0) {
    fragment.appendChild(element.children[0]);
  }  

  return fragment;
}

/**
 * Fills an HTML template with object values in place of {{object.key}}
 */
export function fillHTMLTemplate<T>(html: string, obj: T): string {
  return html.replace(/{{(.*?)}}/g, (_m: string, key: string) => {
    return obj[key.trim() as keyof typeof obj] as string;
  })
}