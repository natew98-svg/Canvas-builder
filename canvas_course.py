from __future__ import annotations

import json
from typing import Any
from urllib import parse, request


def _api_request(
    base_url: str,
    path: str,
    token: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> Any:
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


def fetch_modules_with_items(base_url: str, course_id: str, token: str) -> list[dict[str, Any]]:
    modules = _api_request(
        base_url,
        f"/api/v1/courses/{course_id}/modules?include[]=items&per_page=100",
        token,
        "GET",
    )
    if not isinstance(modules, list):
        raise RuntimeError("Unexpected Canvas API response for modules.")

    normalized: list[dict[str, Any]] = []
    for module in sorted(modules, key=lambda m: int(m.get("position") or 0)):
        items = module.get("items") or []
        normalized_items: list[dict[str, Any]] = []
        for item in sorted(items, key=lambda i: int(i.get("position") or 0)):
            if not item.get("id"):
                continue
            normalized_items.append(
                {
                    "item_id": int(item["id"]),
                    "content_id": int(item["content_id"]) if item.get("content_id") is not None else None,
                    "title": str(item.get("title") or ""),
                    "published": bool(item.get("published", False)),
                    "position": int(item.get("position") or 0),
                    "type": str(item.get("type") or "Unknown"),
                    "due_at": str(item.get("due_at") or ""),
                    "unlock_at": str(item.get("unlock_at") or ""),
                    "lock_at": str(item.get("lock_at") or ""),
                }
            )

        normalized.append(
            {
                "module_id": int(module["id"]),
                "name": str(module.get("name") or ""),
                "published": bool(module.get("published", False)),
                "position": int(module.get("position") or 0),
                "items": normalized_items,
            }
        )
    return normalized


def update_module(
    base_url: str,
    course_id: str,
    token: str,
    module_id: int,
    *,
    name: str,
    published: bool,
    position: int,
) -> None:
    _api_request(
        base_url,
        f"/api/v1/courses/{course_id}/modules/{module_id}",
        token,
        "PUT",
        {
            "module[name]": name,
            "module[published]": "true" if published else "false",
            "module[position]": str(position),
        },
    )


def update_module_item(
    base_url: str,
    course_id: str,
    token: str,
    module_id: int,
    item_id: int,
    *,
    title: str,
    published: bool,
    position: int,
) -> None:
    _api_request(
        base_url,
        f"/api/v1/courses/{course_id}/modules/{module_id}/items/{item_id}",
        token,
        "PUT",
        {
            "module_item[title]": title,
            "module_item[published]": "true" if published else "false",
            "module_item[position]": str(position),
        },
    )


def update_assignment_dates(
    base_url: str,
    course_id: str,
    token: str,
    assignment_id: int,
    *,
    due_at: str,
    unlock_at: str,
    lock_at: str,
) -> None:
    payload = {
        "assignment[due_at]": due_at or "",
        "assignment[unlock_at]": unlock_at or "",
        "assignment[lock_at]": lock_at or "",
    }
    _api_request(
        base_url,
        f"/api/v1/courses/{course_id}/assignments/{assignment_id}",
        token,
        "PUT",
        payload,
    )
