const HERMES_COMMANDS = new Set([
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
]);

export function getHermesApprovalUrl(href, origin) {
  let url = null;
  try {
    url = new URL(href, origin);
  } catch {
    return null;
  }
  const params = [...url.searchParams];
  const canal = url.searchParams.get("canal");
  const cmd = url.searchParams.get("cmd");
  if (
    url.origin !== origin ||
    url.pathname !== "/hermes/repondre" ||
    url.hash ||
    params.length !== 2 ||
    params.some(([name]) => name !== "canal" && name !== "cmd") ||
    !/^\d+$/.test(canal ?? "") ||
    !HERMES_COMMANDS.has(cmd)
  ) {
    return null;
  }
  return url.href;
}
