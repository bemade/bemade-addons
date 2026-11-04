import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const SOURCE_URL = new URL("../src/hermes_boutons.js", import.meta.url);

async function loadClickHandler(href) {
  const fetchCalls = [];
  const context = vm.createContext({
    console,
    URL,
    URLSearchParams,
    odoo: {csrf_token: "secret-csrf-token"},
    fetch: (...args) => {
      fetchCalls.push(args);
      return Promise.resolve({ok: true, status: 204});
    },
    window: {location: new URL("https://odoo.example/web")},
  });
  context.globalThis = context;

  const modules = new Map();
  const mockModule = (specifier, source) => {
    modules.set(
      specifier,
      new vm.SourceTextModule(source, {context, identifier: specifier})
    );
  };
  mockModule(
    "@mail/core/common/message",
    "export class Message { setup() {} }"
  );
  mockModule(
    "@web/core/utils/patch",
    `export function patch(target, extension) {
      Object.setPrototypeOf(extension, {setup() {}});
      globalThis.hermesExtension = extension;
    }`
  );
  mockModule(
    "@odoo/owl",
    `export function useEffect(effect) {
      globalThis.hermesEffect = effect;
    }`
  );
  mockModule(
    "@web/core/utils/hooks",
    `export function useService() {
      return {add() {}};
    }`
  );
  mockModule(
    "./hermes_url",
    await readFile(new URL("../src/hermes_url.js", import.meta.url), "utf8")
  );

  const source = await readFile(SOURCE_URL, "utf8");
  const productionModule = new vm.SourceTextModule(source, {
    context,
    identifier: SOURCE_URL.href,
  });
  await productionModule.link((specifier) => modules.get(specifier));
  await productionModule.evaluate();

  context.hermesExtension.setup.call({messageBody: {}, message: {body: "body"}});

  let clickHandler;
  const link = {
    addEventListener(eventName, handler) {
      if (eventName === "click") {
        clickHandler = handler;
      }
    },
    closest() {
      return null;
    },
    getAttribute(name) {
      return name === "href" ? href : null;
    },
    removeEventListener() {},
  };
  context.hermesEffect({
    querySelectorAll() {
      return [link];
    },
  });

  let defaultPrevented = false;
  clickHandler({
    currentTarget: link,
    preventDefault() {
      defaultPrevented = true;
    },
  });
  await Promise.resolve();

  return {defaultPrevented, fetchCalls};
}

test("un href Hermes forgé ne déclenche aucun fetch et ne divulgue pas le CSRF", async () => {
  const forgedUrls = [
    "https://attacker.example/hermes/repondre?canal=7&cmd=/approve",
    "/web?canal=7&cmd=/approve",
    "/hermes/repondre?canal=not-a-number&cmd=/approve",
    "/hermes/repondre?canal=7&cmd=/evil",
    "/hermes/repondre?canal=7&cmd=/approve&next=https://attacker.example",
    "/hermes/repondre?canal=7&canal=8&cmd=/approve",
  ];

  for (const href of forgedUrls) {
    const {fetchCalls} = await loadClickHandler(href);
    assert.equal(fetchCalls.length, 0, `fetch appelé pour ${href}`);
    assert.equal(
      fetchCalls.some(([, options]) =>
        options?.body?.toString().includes("secret-csrf-token")
      ),
      false,
      `jeton CSRF divulgué pour ${href}`
    );
  }
});

test("les douze commandes légitimes conservent le POST protégé", async () => {
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
    const href = `/hermes/repondre?canal=7&cmd=${encodeURIComponent(command)}`;
    const {defaultPrevented, fetchCalls} = await loadClickHandler(href);

    assert.equal(defaultPrevented, true);
    assert.equal(fetchCalls.length, 1, `fetch absent pour ${command}`);
    const [url, options] = fetchCalls[0];
    assert.equal(
      url,
      `https://odoo.example/hermes/repondre?canal=7&cmd=${encodeURIComponent(command)}`
    );
    assert.equal(options.method, "POST");
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.body.toString(), "csrf_token=secret-csrf-token");
    assert.equal(options.headers["X-Hermes-Ajax"], "1");
  }
});
