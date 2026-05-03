#!/usr/bin/env python3
"""Publish the Scriptable widget payload to a private GitHub repository."""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WIDGET_FILE = BASE_DIR / "build" / "widget" / "widget_summary.json"
DEFAULT_TARGET_PATH = "widget_summary.json"
DEFAULT_BRANCH = "main"


def github_request(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "TCG-Tracker-Widget-Publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            return 404, {}
        print(f"GitHub API returned HTTP {exc.code}: {body}", file=sys.stderr)
        return exc.code, {}
    except urllib.error.URLError as exc:
        print(f"Could not reach GitHub API: {exc}", file=sys.stderr)
        return 0, {}


def main() -> int:
    repo = os.getenv("WIDGET_PRIVATE_REPO", "").strip()
    token = os.getenv("WIDGET_PRIVATE_REPO_TOKEN", "").strip()
    branch = os.getenv("WIDGET_PRIVATE_BRANCH", DEFAULT_BRANCH).strip()
    target_path = os.getenv("WIDGET_PRIVATE_PATH", DEFAULT_TARGET_PATH).strip()
    widget_file = Path(os.getenv("WIDGET_SUMMARY_FILE", str(DEFAULT_WIDGET_FILE)))

    if not repo or not token:
        print("Skipping private widget publish: WIDGET_PRIVATE_REPO or WIDGET_PRIVATE_REPO_TOKEN is missing.")
        return 0

    if not widget_file.exists():
        print(f"Widget summary file does not exist: {widget_file}", file=sys.stderr)
        return 1

    content = widget_file.read_text(encoding="utf-8")
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"Widget summary is not valid JSON: {exc}", file=sys.stderr)
        return 1

    encoded_path = urllib.parse.quote(target_path, safe="/")
    encoded_ref = urllib.parse.quote(branch, safe="")
    url = f"https://api.github.com/repos/{repo}/contents/{encoded_path}"
    get_status, existing = github_request("GET", f"{url}?ref={encoded_ref}", token)
    if get_status not in {200, 404}:
        return 1

    payload = {
        "message": "Update TCG widget summary",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing.get("sha"):
        payload["sha"] = existing["sha"]

    put_status, _ = github_request("PUT", url, token, payload)
    if put_status not in {200, 201}:
        return 1

    print(f"Published private widget summary to {repo}:{branch}/{target_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
