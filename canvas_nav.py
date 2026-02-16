from __future__ import annotations

import argparse
import json
import sys
from urllib import parse, request
from urllib.error import HTTPError


VISIBLE_TABS = {"announcements", "modules", "grades"}


def _api_request(base_url: str, path: str, token: str, method: str = "GET", data: dict | None = None) -> dict | list:
    url = base_url.rstrip("/") + path
    encoded = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if data is not None:
        encoded = parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = request.Request(url=url, method=method, headers=headers, data=encoded)
    with request.urlopen(req) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def apply_navigation(base_url: str, course_id: str, token: str) -> None:
    tabs = _api_request(base_url, f"/api/v1/courses/{course_id}/tabs", token, "GET")
    if not isinstance(tabs, list):
        raise RuntimeError("Unexpected tabs response from Canvas API.")

    results: list[str] = []
    for tab in tabs:
        tab_id = tab.get("id")
        if not tab_id:
            continue
        if tab_id in {"home", "settings"}:
            results.append(f"{tab_id}: skipped")
            continue

        hidden = tab_id not in VISIBLE_TABS
        try:
            _api_request(
                base_url,
                f"/api/v1/courses/{course_id}/tabs/{tab_id}",
                token,
                "PUT",
                {"hidden": "true" if hidden else "false"},
            )
            state = "hidden" if hidden else "visible"
            results.append(f"{tab_id}: {state}")
        except HTTPError as err:
            results.append(f"{tab_id}: skipped (HTTP {err.code})")

    # Best-effort: set course home to Modules
    try:
        _api_request(
            base_url,
            f"/api/v1/courses/{course_id}",
            token,
            "PUT",
            {"course[default_view]": "modules"},
        )
        results.append("default_view: modules")
    except HTTPError as err:
        results.append(f"default_view: skipped (HTTP {err.code})")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Set Canvas course navigation visibility.")
    parser.add_argument("--canvas-url", required=True, help="Canvas base URL, e.g. https://school.instructure.com")
    parser.add_argument("--course-id", required=True, help="Canvas course ID")
    parser.add_argument("--token", required=True, help="Canvas API token")
    args = parser.parse_args()

    try:
        results = apply_navigation(args.canvas_url, args.course_id, args.token)
        for line in results:
            print(line)
    except HTTPError as err:
        print(f"Canvas API error: HTTP {err.code}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
