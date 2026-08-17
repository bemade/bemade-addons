import {expect, test} from "@odoo/hoot";

import {getHermesApprovalUrl} from "../src/hermes_url";

const ORIGIN = "https://odoo.example";

test("rejette les href qui ne désignent pas une commande Hermes autorisée", () => {
  const forgedUrls = [
    "https://attacker.example/hermes/repondre?canal=7&cmd=/approve",
    "/web?canal=7&cmd=/approve",
    "/hermes/repondre?canal=not-a-number&cmd=/approve",
    "/hermes/repondre?canal=7&cmd=/evil",
    "/hermes/repondre?canal=7&cmd=/approve&next=https://attacker.example",
    "/hermes/repondre?canal=7&canal=8&cmd=/approve",
  ];

  for (const href of forgedUrls) {
    expect(getHermesApprovalUrl(href, ORIGIN)).toBe(null);
  }
});

test("accepte les douze commandes Hermes légitimes", () => {
  const commands = [
    "/approve",
    "/approve session",
    "/approve always",
    "/deny",
    "!approve",
    "!approve session",
    "!approve always",
    "!deny",
    ".approve",
    ".approve session",
    ".approve always",
    ".deny",
  ];

  for (const command of commands) {
    const query = `canal=7&cmd=${encodeURIComponent(command)}`;
    expect(getHermesApprovalUrl(`/hermes/repondre?${query}`, ORIGIN)).toBe(
      `${ORIGIN}/hermes/repondre?${query}`
    );
  }
});
