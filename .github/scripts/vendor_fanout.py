#!/usr/bin/env python3
# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Fan-out: open ``vendor-bump`` MRs in consuming client repos for new addon tags.

Runs right after ``vendor_autotag`` in the SAME GitHub Actions workflow — a
``GITHUB_TOKEN``-created tag cannot trigger a separate tag-triggered workflow, so
fan-out is chained in-process rather than tag-triggered.

Cross-forge: bemade-addons is on GitHub, most consumers are on GitLab
(git.bemade.org) — pushes/MRs there authenticate with ``CI_BOT_TOKEN``. Consumers
are listed in ``.github/vendor-consumers.yml`` (a config list; API discovery is a
later add). For each new ``<addon>/<version>`` and each consumer whose
``addons.lock`` pins that addon, fan-out branches ``vendor-bump/<addon>-<version>``,
runs ``odoo-dev vendor bump``, and opens an MR — idempotently (an existing branch
is skipped).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

CONSUMERS_FILE = ".github/vendor-consumers.yml"


# --- pure, unit-tested logic ----------------------------------------------------


def load_created(path: str) -> list[dict]:
    """The ``[{addon, version, tag}]`` list emitted by vendor_autotag."""
    p = Path(path)
    if not p.is_file():
        return []
    return json.loads(p.read_text() or "[]")


def load_consumers(path: str = CONSUMERS_FILE) -> list[dict]:
    """Parse the consumer registry → ``[{url, branch}]`` (branch optional)."""
    p = Path(path)
    if not p.is_file():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    return list(data.get("consumers") or [])


def lockfile_addons(clone_dir: str) -> set[str]:
    """The set of addon names pinned by a consumer's ``addons.lock``."""
    lock = Path(clone_dir) / "addons.lock"
    if not lock.is_file():
        return set()
    data = yaml.safe_load(lock.read_text()) or {}
    return set(data) if isinstance(data, dict) else set()


def bump_branch(addon: str, version: str) -> str:
    return f"vendor-bump/{addon}-{version}"


def plan_fanout(created: list[dict], consumer_pins: dict[str, set]) -> list[dict]:
    """Given created tags and each consumer's pinned addons, return the work items
    ``[{url, addon, version, branch}]`` — one per (consumer, addon) that the
    consumer actually pins."""
    items = []
    for entry in created:
        addon, version = entry["addon"], entry["version"]
        for url, pins in consumer_pins.items():
            if addon in pins:
                items.append(
                    {
                        "url": url,
                        "addon": addon,
                        "version": version,
                        "branch": bump_branch(addon, version),
                    }
                )
    return items


# --- git / forge orchestration (integration; run only in CI) --------------------


def _run(*args: str, cwd: str | None = None, check: bool = False):
    r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()}")
    return r


def _auth_url(url: str) -> str:
    """Inject CI_BOT_TOKEN for git.bemade.org https clones/pushes."""
    token = os.environ.get("CI_BOT_TOKEN", "")
    if token and url.startswith("https://git.bemade.org/"):
        return url.replace("https://", f"https://oauth2:{token}@", 1)
    return url


def _remote_branch_exists(auth_url: str, branch: str) -> bool:
    r = _run("git", "ls-remote", "--heads", auth_url, branch)
    return bool(r.stdout.strip())


def process_item(item: dict, workdir: str) -> str:
    """Clone → vendor bump → push branch → open MR for one work item.

    Returns a short status string. Idempotent: an existing remote branch is a skip.
    """
    url, addon, version, branch = (
        item["url"], item["addon"], item["version"], item["branch"]
    )
    auth = _auth_url(url)
    entry = next((c for c in load_consumers() if c["url"] == url), {})
    base = entry.get("branch")

    if _remote_branch_exists(auth, branch):
        return f"skip {url} {branch}: branch already exists"

    dest = Path(workdir) / addon.replace("/", "_") / Path(url).stem
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone = ["git", "clone", "--depth", "1"]
    if base:
        clone += ["-b", base]
    r = _run(*clone, auth, str(dest))
    if r.returncode != 0:
        return f"FAIL clone {url}: {r.stderr.strip()}"

    if addon not in lockfile_addons(str(dest)):
        return f"skip {url}: does not pin {addon}"

    _run("git", "-C", str(dest), "checkout", "-b", branch, check=True)
    r = _run("odoo-dev", "vendor", "bump", addon, "--version", version, cwd=str(dest))
    if r.returncode != 0:
        return f"FAIL bump {url} {addon}: {r.stderr.strip()}"
    _run("git", "-C", str(dest), "add", "-A", check=True)
    _run(
        "git", "-C", str(dest), "-c", "user.email=bot@bemade.org",
        "-c", "user.name=vendor-fanout",
        "commit", "-m", f"chore(vendor): bump {addon} to {version}", check=True,
    )
    r = _run("git", "-C", str(dest), "push", auth, branch)
    if r.returncode != 0:
        return f"FAIL push {url} {branch}: {r.stderr.strip()}"

    title = f"vendor: bump {addon} to {version}"
    body = (
        f"Automated fan-out from bemade-addons `{addon}/{version}`. Re-pins "
        f"`vendored/{addon}` to the newly tagged version."
    )
    if "git.bemade.org" in url:
        mr = _run(
            "glab", "mr", "create", "--repo", url, "--source-branch", branch,
            *(["--target-branch", base] if base else []),
            "--title", title, "--description", body, "--yes",
            cwd=str(dest),
        )
    else:  # GitHub consumer
        mr = _run(
            "gh", "pr", "create", "--head", branch,
            *(["--base", base] if base else []),
            "--title", title, "--body", body, cwd=str(dest),
        )
    if mr.returncode != 0:
        return f"pushed {url} {branch} but MR-open FAILED: {mr.stderr.strip()}"
    return f"opened MR {url} {branch}"


def main() -> None:
    created = load_created(os.environ.get("AUTOTAG_OUTPUT", ""))
    if not created:
        print("fan-out: no new tags; nothing to do")
        return
    consumers = load_consumers()
    if not consumers:
        print("fan-out: no consumers registered; nothing to do")
        return

    import tempfile

    workdir = tempfile.mkdtemp(prefix="fanout-")
    # Discover each consumer's pins by a shallow clone (once per consumer).
    consumer_pins: dict[str, set] = {}
    for c in consumers:
        auth = _auth_url(c["url"])
        d = Path(workdir) / "probe" / Path(c["url"]).stem
        d.parent.mkdir(parents=True, exist_ok=True)
        clone = ["git", "clone", "--depth", "1"]
        if c.get("branch"):
            clone += ["-b", c["branch"]]
        r = _run(*clone, auth, str(d))
        consumer_pins[c["url"]] = lockfile_addons(str(d)) if r.returncode == 0 else set()

    items = plan_fanout(created, consumer_pins)
    if not items:
        print("fan-out: no consumer pins any of the new tags")
        return
    failures = 0
    for item in items:
        status = process_item(item, workdir)
        print(status)
        if status.startswith("FAIL"):
            failures += 1
    if failures:
        sys.exit(f"fan-out: {failures} item(s) failed")


if __name__ == "__main__":
    main()
