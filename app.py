from __future__ import annotations

import copy
from datetime import date, datetime, time

import streamlit as st

from canvas_course import fetch_modules_with_items, update_assignment_dates, update_module, update_module_item
from canvas_nav import apply_navigation
from generator import PAGE_TEMPLATE_NAMES, build_module_titles, generate_imscc


st.set_page_config(page_title="Canvas Template Builder", layout="wide")
st.markdown(
    """
    <style>
    :root {
      --brand: #0f4c5c;
      --brand-soft: #e6f0f3;
      --ok: #0f9d58;
      --warn: #b26a00;
    }
    .hero {
      padding: 1rem 1.2rem;
      border-radius: 12px;
      background: linear-gradient(135deg, #f7fbfc 0%, #eef6f8 100%);
      border: 1px solid #d7e7ec;
      margin-bottom: 0.8rem;
    }
    .hero h1 {
      margin: 0 0 0.25rem 0;
      color: var(--brand);
      font-size: 1.8rem;
    }
    .hero p {
      margin: 0;
      color: #2f3f46;
      font-size: 0.95rem;
    }
    .metric-chip {
      display: inline-block;
      padding: 0.2rem 0.55rem;
      margin-right: 0.35rem;
      border-radius: 999px;
      background: var(--brand-soft);
      color: var(--brand);
      font-size: 0.8rem;
      font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="hero">
      <h1>Canvas Course Template Builder</h1>
      <p>Build a Canvas-ready IMSCC package with a step-by-step wizard. No JSON or YAML required.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Accessibility: labeled controls, keyboard-friendly wizard flow, preview confirmation before export.")

STEP_LABELS = {
    1: "Template Type",
    2: "Module Naming",
    3: "Module Layout",
    4: "Page Templates",
    5: "Preview & Generate",
}
WORKFLOW_OPTIONS = [
    "Template Builder (Steps 1-5)",
    "Canvas Navigation Update",
    "Course Editor (Safe Scope)",
]


DEFAULT_LAYOUT_PRESETS = {
    "Minimal": [
        {"type": "Page", "title_pattern": "{module_folder}: Overview and To Do List", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
    ],
    "Standard": [
        {"type": "Page", "title_pattern": "{module_folder}: Overview and To Do List", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Page", "title_pattern": "{module_folder}: Checklist", "page_template": "Checklist", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Assignment placeholder", "title_pattern": "{module_folder}: Assignment", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": "Add assignment expectations and rubric notes."},
        {"type": "Page", "title_pattern": "{module_folder}: Notes", "page_template": "Notes", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Page", "title_pattern": "{module_folder}: Next Week", "page_template": "Wrap-up", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
    ],
    "Scaffolded": [
        {"type": "Page", "title_pattern": "{module_folder}: Overview and To Do List", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Page", "title_pattern": "{module_folder}: Checklist", "page_template": "Checklist", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Page", "title_pattern": "{module_folder}: Notes", "page_template": "Notes", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Assignment placeholder", "title_pattern": "{module_folder}: Assignment", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": "Add assignment expectations and rubric notes."},
        {"type": "Page", "title_pattern": "{module_folder}: Next Week", "page_template": "Wrap-up", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
    ],
    "Project-Based": [
        {"type": "Page", "title_pattern": "{module_folder}: Overview and To Do List", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Page", "title_pattern": "{module_folder}: Checklist", "page_template": "Checklist", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Assignment placeholder", "title_pattern": "{module_folder}: Assignment", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 50, "submission_type": "File Upload", "instructions": "Milestone expectations and due date notes."},
        {"type": "Page", "title_pattern": "{module_folder}: Notes", "page_template": "Notes", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
        {"type": "Page", "title_pattern": "{module_folder}: Next Week", "page_template": "Wrap-up", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""},
    ],
}

DEFAULT_PAGE_TEMPLATES = {
    "Overview": {
        "header_title": "Overview",
        "sections": {
            "Objectives": "List measurable learning objectives.",
            "To Do": "Summarize required tasks for this module.",
        },
    },
    "Checklist": {
        "header_title": "Checklist",
        "sections": {
            "Reading": "List reading assignments here.",
            "Videos": "List lecture videos or media links.",
            "Submission info": "Summarize what must be submitted.",
        },
    },
    "Notes": {
        "header_title": "Notes",
        "sections": {
            "Key Concepts": "Capture core ideas and definitions.",
            "Examples": "Add worked examples or sample problems.",
            "Notes": "Space for additional instructor notes.",
        },
    },
    "Resources": {
        "header_title": "Resources",
        "sections": {
            "Links": "Curated links, tools, and references.",
            "Support": "Office hours, tutoring, and support channels.",
        },
    },
    "Wrap-up": {
        "header_title": "Wrap-up",
        "sections": {
            "Summary": "Review what students should retain.",
            "Next Steps": "Preview the next module.",
        },
    },
}


def _init_state() -> None:
    defaults = {
        "step": 1,
        "workflow_mode": WORKFLOW_OPTIONS[0],
        "template_type": "Weekly",
        "module_count": 4,
        "start_number": 1,
        "custom_names_text": "",
        "prefix": "Week",
        "include_topic": False,
        "topics_map": [],
        "topic_edit_index": 0,
        "page_naming_style": "Include module title",
        "include_overview": True,
        "include_checklist": True,
        "include_assignment": True,
        "include_notes": True,
        "include_next_week": True,
        "layout_items": copy.deepcopy(DEFAULT_LAYOUT_PRESETS["Standard"]),
        "unpublished": True,
        "page_templates": copy.deepcopy(DEFAULT_PAGE_TEMPLATES),
        "canvas_url": "https://kaskaskiacollege.instructure.com",
        "canvas_course_id": "",
        "canvas_token": "",
        "nav_update_results": [],
        "course_editor_modules": [],
        "course_editor_original_modules": [],
        "course_editor_apply_results": [],
        "course_editor_fetch_status": "",
        "editor_widget_nonce": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.step < 1 or st.session_state.step > 5:
        st.session_state.step = 1


def _sync_prefix_default() -> None:
    t = st.session_state.template_type
    if t == "Weekly" and st.session_state.prefix in {"", "Unit"}:
        st.session_state.prefix = "Week"
    if t == "Unit" and st.session_state.prefix in {"", "Week"}:
        st.session_state.prefix = "Unit"


def _get_custom_names() -> list[str]:
    return [line.strip() for line in st.session_state.custom_names_text.splitlines() if line.strip()]


def _get_topics() -> list[str]:
    return [str(topic).strip() for topic in st.session_state.topics_map]


def _topic_module_labels() -> list[str]:
    if st.session_state.template_type == "Custom list":
        names = _get_custom_names()
        return names
    count = int(st.session_state.module_count)
    start_number = int(st.session_state.start_number)
    prefix = str(st.session_state.prefix).strip() or ("Week" if st.session_state.template_type == "Weekly" else "Unit")
    return [f"{prefix} {n}" for n in range(start_number, start_number + count)]


def _sync_topics_map() -> None:
    labels = _topic_module_labels()
    current = list(st.session_state.topics_map)
    if len(current) < len(labels):
        current.extend([""] * (len(labels) - len(current)))
    elif len(current) > len(labels):
        current = current[: len(labels)]
    st.session_state.topics_map = current
    if st.session_state.topic_edit_index >= len(labels):
        st.session_state.topic_edit_index = 0


def _build_layout_items_from_options() -> list[dict]:
    prefix = "{module_title}: " if st.session_state.page_naming_style == "Include module title" else ""
    items: list[dict] = []
    if st.session_state.include_overview:
        items.append(
            {"type": "Page", "title_pattern": f"{prefix}Overview and To Do List", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""}
        )
    if st.session_state.include_checklist:
        items.append(
            {"type": "Page", "title_pattern": f"{prefix}Checklist", "page_template": "Checklist", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""}
        )
    if st.session_state.include_assignment:
        items.append(
            {"type": "Assignment placeholder", "title_pattern": f"{prefix}Assignment", "page_template": "Overview", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": "Add assignment expectations and rubric notes."}
        )
    if st.session_state.include_notes:
        items.append(
            {"type": "Page", "title_pattern": f"{prefix}Notes", "page_template": "Notes", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""}
        )
    if st.session_state.include_next_week:
        items.append(
            {"type": "Page", "title_pattern": f"{prefix}Next Week", "page_template": "Wrap-up", "folder": "__AUTO_MODULE__", "points": 100, "submission_type": "Online", "instructions": ""}
        )
    return items


def _module_folder_title(module_title: str) -> str:
    return module_title


def _render_item_title(title_pattern: str, module_title: str, module_number: int, module_folder: str) -> str:
    pattern = title_pattern.strip() or "{module_title} Item"
    return pattern.format(n=module_number, module_title=module_title, module_folder=module_folder)


def _preview_rows(config: dict) -> list[dict]:
    rows: list[dict] = []
    module_titles = build_module_titles(config)
    for idx, module_title in enumerate(module_titles, start=1):
        module_folder = _module_folder_title(module_title)
        for item in config["layout_items"]:
            rows.append(
                {
                    "Module": module_title,
                    "Folder": module_folder,
                    "Type": item["type"],
                    "Item Title": _render_item_title(item["title_pattern"], module_title, idx, module_folder),
                }
            )
    return rows


def _current_config() -> dict:
    return {
        "template_type": st.session_state.template_type,
        "module_count": st.session_state.module_count,
        "start_number": st.session_state.start_number,
        "custom_module_names": _get_custom_names(),
        "prefix": st.session_state.prefix,
        "include_topic": st.session_state.include_topic,
        "topics": _get_topics(),
        "module_folders": [],
        "folder_header_style": "Folder only",
        "layout_items": st.session_state.layout_items,
        "page_templates": st.session_state.page_templates,
        "unpublished": st.session_state.unpublished,
    }


def _fetch_course_editor_data() -> None:
    modules = fetch_modules_with_items(
        st.session_state.canvas_url.strip(),
        st.session_state.canvas_course_id.strip(),
        st.session_state.canvas_token.strip(),
    )
    st.session_state.course_editor_modules = modules
    st.session_state.course_editor_original_modules = copy.deepcopy(modules)
    st.session_state.course_editor_apply_results = []
    st.session_state.editor_widget_nonce += 1
    st.session_state.course_editor_fetch_status = f"Loaded {len(modules)} modules."


def _compute_editor_changes(original: list[dict], current: list[dict]) -> list[dict]:
    changes: list[dict] = []
    original_map = {int(m["module_id"]): m for m in original}
    for module in current:
        module_id = int(module["module_id"])
        orig_module = original_map.get(module_id)
        if not orig_module:
            continue
        for field in ("name", "published", "position"):
            if module[field] != orig_module[field]:
                changes.append(
                    {
                        "Entity": "Module",
                        "ID": str(module_id),
                        "Field": field,
                        "From": str(orig_module[field]),
                        "To": str(module[field]),
                    }
                )

        original_items = {int(i["item_id"]): i for i in orig_module.get("items", [])}
        for item in module.get("items", []):
            item_id = int(item["item_id"])
            orig_item = original_items.get(item_id)
            if not orig_item:
                continue
            for field in ("title", "published", "position"):
                if item[field] != orig_item[field]:
                    changes.append(
                        {
                            "Entity": "Module Item",
                            "ID": f"{module_id}/{item_id}",
                            "Field": field,
                            "From": str(orig_item[field]),
                            "To": str(item[field]),
                        }
                    )
            if str(item.get("type") or "").strip().lower() == "assignment":
                for field in ("due_at", "unlock_at", "lock_at"):
                    if str(item.get(field) or "") != str(orig_item.get(field) or ""):
                        changes.append(
                            {
                                "Entity": "Assignment Dates",
                                "ID": f"{module_id}/{item_id}",
                                "Field": field,
                                "From": str(orig_item.get(field) or ""),
                                "To": str(item.get(field) or ""),
                            }
                        )
    return changes


def _apply_course_editor_changes() -> list[str]:
    results: list[str] = []
    original_map = {int(m["module_id"]): m for m in st.session_state.course_editor_original_modules}
    for module in st.session_state.course_editor_modules:
        module_id = int(module["module_id"])
        orig_module = original_map.get(module_id)
        if not orig_module:
            continue
        module_changed = any(module[field] != orig_module[field] for field in ("name", "published", "position"))
        if module_changed:
            update_module(
                st.session_state.canvas_url.strip(),
                st.session_state.canvas_course_id.strip(),
                st.session_state.canvas_token.strip(),
                module_id,
                name=str(module["name"]),
                published=bool(module["published"]),
                position=int(module["position"]),
            )
            results.append(f"Module {module_id}: updated")

        original_items = {int(i["item_id"]): i for i in orig_module.get("items", [])}
        for item in module.get("items", []):
            item_id = int(item["item_id"])
            orig_item = original_items.get(item_id)
            if not orig_item:
                continue
            item_changed = any(item[field] != orig_item[field] for field in ("title", "published", "position"))
            if item_changed:
                update_module_item(
                    st.session_state.canvas_url.strip(),
                    st.session_state.canvas_course_id.strip(),
                    st.session_state.canvas_token.strip(),
                    module_id,
                    item_id,
                    title=str(item["title"]),
                    published=bool(item["published"]),
                    position=int(item["position"]),
                )
                results.append(f"Module Item {module_id}/{item_id}: updated")
            assignment_date_changed = str(item.get("type") or "").strip().lower() == "assignment" and any(
                item.get(field, "") != orig_item.get(field, "") for field in ("due_at", "unlock_at", "lock_at")
            )
            if assignment_date_changed and item.get("content_id"):
                update_assignment_dates(
                    st.session_state.canvas_url.strip(),
                    st.session_state.canvas_course_id.strip(),
                    st.session_state.canvas_token.strip(),
                    int(item["content_id"]),
                    due_at=str(item.get("due_at") or ""),
                    unlock_at=str(item.get("unlock_at") or ""),
                    lock_at=str(item.get("lock_at") or ""),
                )
                results.append(f"Assignment Dates {module_id}/{item_id}: updated")
    return results


def _parse_iso_datetime(iso_value: str) -> tuple[date, time]:
    if not iso_value:
        return date.today(), time(23, 59)
    cleaned = iso_value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.date(), parsed.time().replace(microsecond=0)
    except ValueError:
        return date.today(), time(23, 59)


def _to_iso_datetime(d: date, t: time) -> str:
    return datetime.combine(d, t).replace(microsecond=0).isoformat()


def _can_advance_from_step(step: int) -> tuple[bool, str]:
    if step == 1 and st.session_state.template_type == "Custom list" and not _get_custom_names():
        return False, "Add at least one module name for Custom list."
    if step == 3 and not st.session_state.layout_items:
        return False, "Select at least one item type in Step 3."
    return True, ""


def _step_nav() -> None:
    can_advance, reason = _can_advance_from_step(st.session_state.step)
    left, center, right = st.columns([1, 2, 1])
    with left:
        st.button("Back", disabled=st.session_state.step <= 1, on_click=lambda: st.session_state.update(step=max(1, st.session_state.step - 1)))
    with center:
        st.markdown(
            f"<div style='text-align:center; font-weight:600;'>Step {st.session_state.step}: {STEP_LABELS[st.session_state.step]}</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.button("Next", disabled=st.session_state.step >= 5 or not can_advance, on_click=lambda: st.session_state.update(step=min(5, st.session_state.step + 1)))
    if reason:
        st.info(reason)


def _render_navigation_update() -> None:
    st.subheader("Canvas Navigation Update")
    st.caption("Optional: apply navigation settings directly to your Canvas course after import.")
    st.text_input("Canvas URL", key="canvas_url", placeholder="https://school.instructure.com")
    st.text_input("Course ID", key="canvas_course_id", placeholder="12345")
    st.text_input("API Token", key="canvas_token", type="password")

    if st.button("Update Navigation Settings", type="primary"):
        if not st.session_state.canvas_url.strip() or not st.session_state.canvas_course_id.strip() or not st.session_state.canvas_token.strip():
            st.error("Canvas URL, Course ID, and API Token are all required.")
        else:
            try:
                results = apply_navigation(
                    st.session_state.canvas_url.strip(),
                    st.session_state.canvas_course_id.strip(),
                    st.session_state.canvas_token.strip(),
                )
                st.session_state.nav_update_results = results
                st.success("Navigation settings updated.")
            except Exception as exc:
                st.error(f"Navigation update failed: {exc}")

    if st.session_state.nav_update_results:
        st.markdown("**Update results**")
        st.code("\n".join(st.session_state.nav_update_results))


def _render_course_editor() -> None:
    st.subheader("Course Editor (Safe Scope)")
    st.caption("Fetch existing modules and module items, then update names, publish state, and order.")
    st.info("Safe scope: module name/publish/order + module item title/publish/order + assignment due/available/until date-times.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Canvas URL", key="canvas_url", placeholder="https://school.instructure.com")
    with c2:
        st.text_input("Course ID", key="canvas_course_id", placeholder="12345")
    with c3:
        st.text_input("API Token", key="canvas_token", type="password")

    fetch_disabled = not (
        st.session_state.canvas_url.strip()
        and st.session_state.canvas_course_id.strip()
        and st.session_state.canvas_token.strip()
    )
    if st.button("Fetch Course Data", disabled=fetch_disabled):
        try:
            _fetch_course_editor_data()
            st.success(st.session_state.course_editor_fetch_status)
        except Exception as exc:
            st.error(f"Fetch failed: {exc}")

    if st.session_state.course_editor_fetch_status and not st.session_state.course_editor_modules:
        st.warning(st.session_state.course_editor_fetch_status)

    if st.session_state.course_editor_modules:
        nonce = st.session_state.editor_widget_nonce
        modules_for_display = sorted(st.session_state.course_editor_modules, key=lambda m: int(m.get("position", 0)))
        assignment_item_count = sum(
            1
            for m in modules_for_display
            for i in m.get("items", [])
            if str(i.get("type") or "").strip().lower() == "assignment"
        )
        if assignment_item_count == 0:
            st.warning(
                "No real Canvas Assignment items were found in these modules. "
                "Date/time controls appear only for Assignment items (not Page placeholders)."
            )
        else:
            st.caption(f"Assignment items with editable dates found: {assignment_item_count}")
        for module in modules_for_display:
            module_id = int(module["module_id"])
            with st.expander(f"Module {module['position']}: {module['name']} (ID {module_id})", expanded=False):
                mc1, mc2, mc3 = st.columns([5, 2, 2])
                with mc1:
                    module["name"] = st.text_input(
                        "Module Name",
                        value=str(module["name"]),
                        key=f"ed_m_name_{nonce}_{module_id}",
                    )
                with mc2:
                    module["published"] = st.checkbox(
                        "Published",
                        value=bool(module["published"]),
                        key=f"ed_m_pub_{nonce}_{module_id}",
                    )
                with mc3:
                    module["position"] = int(
                        st.number_input(
                            "Position",
                            min_value=1,
                            step=1,
                            value=int(module["position"]),
                            key=f"ed_m_pos_{nonce}_{module_id}",
                        )
                    )

                st.markdown("**Module Items**")
                items_for_display = sorted(module.get("items", []), key=lambda i: int(i.get("position", 0)))
                for item in items_for_display:
                    item_id = int(item["item_id"])
                    ic1, ic2, ic3 = st.columns([5, 2, 2])
                    with ic1:
                        item["title"] = st.text_input(
                            f"Item Title ({item['type']})",
                            value=str(item["title"]),
                            key=f"ed_i_title_{nonce}_{module_id}_{item_id}",
                        )
                    with ic2:
                        item["published"] = st.checkbox(
                            "Published",
                            value=bool(item["published"]),
                            key=f"ed_i_pub_{nonce}_{module_id}_{item_id}",
                        )
                    with ic3:
                        item["position"] = int(
                            st.number_input(
                                "Position",
                                min_value=1,
                                step=1,
                                value=int(item["position"]),
                                key=f"ed_i_pos_{nonce}_{module_id}_{item_id}",
                            )
                        )
                    st.caption(f"Item ID: {item_id}")
                    if str(item.get("type") or "").strip().lower() == "assignment":
                        st.caption("Assignment date settings")
                        for field_key, label in [
                            ("due_at", "Due Date"),
                            ("unlock_at", "Available From"),
                            ("lock_at", "Until"),
                        ]:
                            current_iso = str(item.get(field_key) or "")
                            has_value_default = bool(current_iso)
                            enabled = st.checkbox(
                                f"{label} set",
                                value=has_value_default,
                                key=f"ed_i_dt_enabled_{nonce}_{module_id}_{item_id}_{field_key}",
                            )
                            if enabled:
                                default_date, default_time = _parse_iso_datetime(current_iso)
                                dc1, dc2 = st.columns(2)
                                with dc1:
                                    selected_date = st.date_input(
                                        f"{label} date",
                                        value=default_date,
                                        key=f"ed_i_dt_date_{nonce}_{module_id}_{item_id}_{field_key}",
                                    )
                                with dc2:
                                    selected_time = st.time_input(
                                        f"{label} time",
                                        value=default_time,
                                        key=f"ed_i_dt_time_{nonce}_{module_id}_{item_id}_{field_key}",
                                    )
                                item[field_key] = _to_iso_datetime(selected_date, selected_time)
                            else:
                                item[field_key] = ""

        pending_changes = _compute_editor_changes(
            st.session_state.course_editor_original_modules,
            st.session_state.course_editor_modules,
        )
        st.markdown("**Pending Changes**")
        if pending_changes:
            st.table(pending_changes)
        else:
            st.success("No pending changes.")

        if st.button("Apply Safe-Scope Changes", type="primary", disabled=not pending_changes):
            try:
                results = _apply_course_editor_changes()
                st.session_state.course_editor_apply_results = results
                st.session_state.course_editor_original_modules = copy.deepcopy(st.session_state.course_editor_modules)
                if results:
                    st.success(f"Applied {len(results)} updates.")
                else:
                    st.info("No updates were necessary.")
            except Exception as exc:
                st.error(f"Apply failed: {exc}")

        if st.session_state.course_editor_apply_results:
            st.markdown("**Apply Results**")
            st.code("\n".join(st.session_state.course_editor_apply_results))


_init_state()
_sync_prefix_default()

with st.sidebar:
    st.subheader("Workflow")
    st.selectbox("Choose workflow", WORKFLOW_OPTIONS, key="workflow_mode")
    st.divider()
    st.subheader("Wizard Navigation")
    if st.session_state.workflow_mode == WORKFLOW_OPTIONS[0]:
        selected_step = st.radio(
            "Jump to step",
            options=[1, 2, 3, 4, 5],
            format_func=lambda i: f"{i}. {STEP_LABELS[i]}",
            index=st.session_state.step - 1,
        )
        if selected_step != st.session_state.step:
            st.session_state.step = selected_step
            st.rerun()

        st.markdown("**Progress**")
        for i in range(1, 6):
            marker = "[Done]" if i < st.session_state.step else ("[Now]" if i == st.session_state.step else "[Next]")
            st.write(f"{marker} {i}. {STEP_LABELS[i]}")
    else:
        st.caption("Step navigation is used only for the Template Builder workflow.")

    st.divider()
    if st.button("Reset Wizard"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

titles_preview = build_module_titles(_current_config())
st.markdown(
    f"""
    <span class="metric-chip">Modules: {len(titles_preview)}</span>
    <span class="metric-chip">Items per Module: {len(st.session_state.layout_items)}</span>
    <span class="metric-chip">Total Items: {len(titles_preview) * len(st.session_state.layout_items)}</span>
    """,
    unsafe_allow_html=True,
)
if st.session_state.workflow_mode == WORKFLOW_OPTIONS[0]:
    _step_nav()

if st.session_state.workflow_mode == WORKFLOW_OPTIONS[0] and st.session_state.step == 1:
    st.subheader("Step 1: Template Type")
    st.caption("Choose a module structure that matches how you teach.")
    st.radio("Select template type", ["Weekly", "Unit", "Custom list"], key="template_type", horizontal=True)
    if st.session_state.template_type in {"Weekly", "Unit"}:
        c1, c2 = st.columns(2)
        with c1:
            module_options = list(range(1, 31))
            default_index = module_options.index(st.session_state.module_count) if st.session_state.module_count in module_options else 3
            st.selectbox("Number of modules", module_options, index=default_index, key="module_count")
        with c2:
            st.number_input("Start number", min_value=1, max_value=1000, key="start_number")
    else:
        st.text_area(
            "Module names (one per line)",
            key="custom_names_text",
            height=200,
            placeholder="Introduction\nResearch Methods\nFinal Project",
        )

elif st.session_state.workflow_mode == WORKFLOW_OPTIONS[0] and st.session_state.step == 2:
    st.subheader("Step 2: Module Naming Options")
    st.caption("Define naming rules and optional topics for each module.")
    st.text_input("Prefix text", key="prefix")
    st.checkbox("Include topic", key="include_topic")
    if st.session_state.include_topic:
        _sync_topics_map()
        labels = _topic_module_labels()
        st.caption("Select a module, then enter its topic.")
        st.selectbox(
            "Select module",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            key="topic_edit_index",
        )
        idx = st.session_state.topic_edit_index
        current_topic = st.session_state.topics_map[idx] if labels else ""
        updated_topic = st.text_input("Topic for selected module", value=current_topic, key=f"topic_value_{idx}")
        st.session_state.topics_map[idx] = updated_topic

        preview_topics = []
        for i, label in enumerate(labels):
            topic = st.session_state.topics_map[i].strip()
            preview_topics.append(f"{label}: {topic if topic else '[Topic]'}")
        st.markdown("**Topic Assignments**")
        st.code("\n".join(preview_topics) if preview_topics else "(No modules to edit)")
    titles = build_module_titles(_current_config())
    st.markdown("**Live Preview**")
    preview = "\n".join(f"{idx}. {title}" for idx, title in enumerate(titles, start=1))
    st.code(preview or "(No module titles yet)")

elif st.session_state.workflow_mode == WORKFLOW_OPTIONS[0] and st.session_state.step == 3:
    st.subheader("Step 3: Module Layout Builder")
    st.caption("Choose which standard items appear inside each module folder.")
    st.radio("Page naming", ["Include module title", "Simple page titles"], key="page_naming_style", horizontal=True)

    st.checkbox("Create items as unpublished", key="unpublished")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox("Overview", key="include_overview")
        st.checkbox("Checklist", key="include_checklist")
    with c2:
        st.checkbox("Assignments", key="include_assignment")
        st.checkbox("Notes", key="include_notes")
    with c3:
        st.checkbox("Next Week", key="include_next_week")

    if st.button("Apply Item Options"):
        st.session_state.layout_items = _build_layout_items_from_options()
        st.rerun()

    if not st.session_state.layout_items:
        st.session_state.layout_items = _build_layout_items_from_options()

    st.markdown("**Selected Items (inside each module folder)**")
    for item in st.session_state.layout_items:
        st.write(f"- {item['title_pattern']}")

elif st.session_state.workflow_mode == WORKFLOW_OPTIONS[0] and st.session_state.step == 4:
    st.subheader("Step 4: Page Template Editor")
    st.caption("Edit each template. Content is rendered as consistent HTML in generated pages.")
    for template_name in PAGE_TEMPLATE_NAMES:
        template = st.session_state.page_templates[template_name]
        with st.expander(template_name, expanded=template_name == "Overview"):
            template["header_title"] = st.text_input(
                f"{template_name} header title",
                value=template.get("header_title", template_name),
                key=f"header_{template_name}",
            )
            for section_name, section_value in list(template.get("sections", {}).items()):
                template["sections"][section_name] = st.text_area(
                    f"{template_name} / {section_name}",
                    value=section_value,
                    key=f"section_{template_name}_{section_name}",
                )

elif st.session_state.workflow_mode == WORKFLOW_OPTIONS[0] and st.session_state.step == 5:
    st.subheader("Step 5: Generate")
    st.caption("Review the final structure before creating your IMSCC package.")
    config = _current_config()
    titles = build_module_titles(config)
    st.write(f"Modules: {len(titles)}")
    st.write(f"Items per module: {len(st.session_state.layout_items)}")
    st.write(f"Total pages: {len(titles) * len(st.session_state.layout_items)}")
    st.markdown("**Preview structure**")
    preview_rows = _preview_rows(config)
    if preview_rows:
        st.write("Screen reader-friendly preview table:")
        st.table(preview_rows)
        for idx, module_title in enumerate(titles, start=1):
            folder_title = _module_folder_title(module_title)
            with st.expander(f"{module_title} -> {folder_title}", expanded=idx == 1):
                for item in [row for row in preview_rows if row["Module"] == module_title]:
                    st.write(f"- {item['Item Title']} ({item['Type']})")
    else:
        st.warning("No items selected. Go back to Step 3 and select at least one item.")

    confirm_preview = st.checkbox("I confirm this preview matches what I want to import", value=False)
    can_generate = bool(preview_rows) and confirm_preview
    if st.button("Generate .imscc", type="primary", disabled=not can_generate):
        try:
            imscc_bytes = generate_imscc(config)
            st.session_state.generated_bytes = imscc_bytes
            st.success("Cartridge generated.")
        except Exception as exc:
            st.error(f"Generation failed: {exc}")

    if st.session_state.get("generated_bytes"):
        st.download_button(
            "Download .imscc",
            data=st.session_state.generated_bytes,
            file_name="canvas_course_template.imscc",
            mime="application/zip",
        )

elif st.session_state.workflow_mode == WORKFLOW_OPTIONS[1]:
    _render_navigation_update()
else:
    _render_course_editor()
