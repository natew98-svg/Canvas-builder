from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
import io
import json
import re
from typing import Any
from uuid import uuid4
import xml.etree.ElementTree as ET
import zipfile


PAGE_TEMPLATE_NAMES = ["Overview", "Checklist", "Notes", "Resources", "Wrap-up"]
CANVAS_TAB_IDS = {
    "home": 0,
    "syllabus": 1,
    "pages": 2,
    "assignments": 3,
    "quizzes": 4,
    "grades": 5,
    "people": 6,
    "groups": 7,
    "discussions": 8,
    "modules": 10,
    "files": 11,
    "conferences": 12,
    "settings": 13,
    "announcements": 14,
    "outcomes": 15,
    "collaborations": 16,
    "rubrics": 18,
}


@dataclass
class GeneratedItem:
    module_index: int
    module_title: str
    item_index: int
    module_position: int
    item_type: str
    title: str
    slug: str
    page_template: str
    folder: str
    folder_display_title: str
    body_html: str


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or f"item-{uuid4().hex[:8]}"


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_module_titles(config: dict[str, Any]) -> list[str]:
    template_type = config.get("template_type", "Weekly")
    if template_type == "Custom list":
        names = config.get("custom_module_names", [])
        titles = [str(n).strip() for n in names if str(n).strip()]
        return titles

    count = max(1, _safe_int(config.get("module_count"), 1))
    start_number = _safe_int(config.get("start_number"), 1)
    prefix = str(config.get("prefix") or ("Week" if template_type == "Weekly" else "Unit")).strip()

    include_topic = bool(config.get("include_topic", False))
    topics = [str(t).strip() for t in config.get("topics", [])]
    titles: list[str] = []
    for idx in range(count):
        number = start_number + idx
        base = f"{prefix} {number}".strip()
        topic = topics[idx] if idx < len(topics) else ""
        if include_topic:
            if topic:
                titles.append(f"{base}: {topic}")
            else:
                titles.append(f"{base}: [Topic]")
        else:
            titles.append(base)
    return titles


def _render_pattern(pattern: str, module_title: str, module_number: int) -> str:
    clean_pattern = pattern.strip() or "{module_title}"
    return clean_pattern.format(n=module_number, module_title=module_title, module_folder=module_title)


def _module_folder_title(config: dict[str, Any], module_title: str, module_number: int) -> str:
    return module_title


def _build_page_body_html(title: str, template_name: str, template_config: dict[str, Any], item: dict[str, Any]) -> str:
    header_title = str(template_config.get("header_title") or title)
    sections = template_config.get("sections") or {}
    title_id = _slugify(title)

    parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8' />",
        "<meta name='viewport' content='width=device-width, initial-scale=1' />",
        "<title>{}</title>".format(html.escape(title)),
        "</head>",
        "<body>",
        "<a href='#main-content'>Skip to main content</a>",
        "<main id='main-content' role='main'>",
        f"<h1 id='{title_id}'>{html.escape(title)}</h1>",
        f"<p><strong>Page Template:</strong> {html.escape(template_name)}</p>",
        f"<p><strong>Template Header:</strong> {html.escape(header_title)}</p>",
    ]

    if item["type"] == "Assignment placeholder":
        points = _safe_int(item.get("points"), 100)
        submission_type = str(item.get("submission_type") or "Online")
        instructions = str(item.get("instructions") or "Add assignment details here.")
        parts.extend(
            [
                "<section aria-labelledby='assignment-details'>",
                "<h2 id='assignment-details'>Assignment Details</h2>",
                f"<p><strong>Points:</strong> {points}</p>",
                f"<p><strong>Submission Type:</strong> {html.escape(submission_type)}</p>",
                f"<p>{html.escape(instructions)}</p>",
                "</section>",
            ]
        )
    elif item["type"] in {"Discussion placeholder", "Quiz placeholder"}:
        instructions = str(item.get("instructions") or "Add instructions here.")
        parts.extend(
            [
                "<section aria-labelledby='instructor-notes'>",
                "<h2 id='instructor-notes'>Instructor Notes</h2>",
                f"<p>{html.escape(instructions)}</p>",
                "</section>",
            ]
        )

    for section_name, section_body in sections.items():
        section_name_clean = str(section_name).strip()
        section_body_clean = str(section_body).strip()
        if not section_name_clean and not section_body_clean:
            continue
        section_heading = section_name_clean or "Section"
        section_id = _slugify(f"{title}-{section_heading}")
        parts.append(f"<section aria-labelledby='{section_id}'>")
        parts.append(f"<h2 id='{section_id}'>{html.escape(section_heading)}</h2>")
        if section_body_clean:
            for paragraph in section_body_clean.splitlines():
                if paragraph.strip():
                    parts.append(f"<p>{html.escape(paragraph.strip())}</p>")
        else:
            parts.append("<p>[Add content]</p>")
        parts.append("</section>")

    parts.extend(["</main>", "</body>", "</html>"])
    return "\n".join(parts)


def _build_items(config: dict[str, Any], module_titles: list[str]) -> list[GeneratedItem]:
    items_cfg = config.get("layout_items", [])
    templates_cfg = config.get("page_templates", {})
    folder_names = [str(name).strip() for name in config.get("module_folders", []) if str(name).strip()]
    folder_header_style = str(config.get("folder_header_style") or "Folder only")
    generated: list[GeneratedItem] = []

    for module_idx, module_title in enumerate(module_titles, start=1):
        pos = 1
        emitted_folders: set[str] = set()
        for item_idx, item in enumerate(items_cfg, start=1):
            item_type = str(item.get("type", "Page"))
            title_pattern = str(item.get("title_pattern") or "{module_title} Item")
            module_folder_title = _module_folder_title(config, module_title, module_idx)
            title = (title_pattern.strip() or "{module_title} Item").format(
                n=module_idx,
                module_title=module_title,
                module_folder=module_folder_title,
            )
            template_name = str(item.get("page_template") or "Overview")
            folder = str(item.get("folder") or "").strip()
            if folder and folder_names and folder not in folder_names:
                folder = folder_names[0]
            if folder == "__AUTO_MODULE__":
                folder = module_folder_title
            template_cfg = templates_cfg.get(template_name, {})
            if item_type != "Page":
                template_name = "Overview"
                template_cfg = templates_cfg.get(template_name, {})

            if folder and folder not in emitted_folders:
                if folder_header_style == "Module + Folder":
                    folder_display_title = f"{module_title} - {folder}"
                else:
                    folder_display_title = folder
                generated.append(
                    GeneratedItem(
                        module_index=module_idx,
                        module_title=module_title,
                        item_index=0,
                        module_position=pos,
                        item_type="Module Folder",
                        title=folder_display_title,
                        slug="",
                        page_template="",
                        folder=folder,
                        folder_display_title=folder_display_title,
                        body_html="",
                    )
                )
                emitted_folders.add(folder)
                pos += 1

            slug = _slugify(f"{module_idx}-{title}")
            body_html = _build_page_body_html(title, template_name, template_cfg, item)
            generated.append(
                GeneratedItem(
                    module_index=module_idx,
                    module_title=module_title,
                    item_index=item_idx,
                    module_position=pos,
                    item_type=item_type,
                    title=title,
                    slug=slug,
                    page_template=template_name,
                    folder=folder,
                    folder_display_title="",
                    body_html=body_html,
                )
            )
            pos += 1
    return generated


def _build_module_meta_xml(module_titles: list[str], items: list[GeneratedItem], unpublished: bool) -> bytes:
    workflow_state = "unpublished" if unpublished else "active"
    root = ET.Element(
        "modules",
        attrib={
            "migration_id": f"migr-{uuid4().hex}",
            "xmlns": "http://canvas.instructure.com/xsd/cccv1p0",
        },
    )

    for module_idx, module_title in enumerate(module_titles, start=1):
        module_el = ET.SubElement(root, "module", attrib={"identifier": f"module-{module_idx}"})
        ET.SubElement(module_el, "title").text = module_title
        ET.SubElement(module_el, "workflow_state").text = workflow_state
        ET.SubElement(module_el, "position").text = str(module_idx)
        items_el = ET.SubElement(module_el, "items")

        module_items = [i for i in items if i.module_index == module_idx]
        for item in module_items:
            item_el = ET.SubElement(items_el, "item", attrib={"identifier": f"module-{module_idx}-pos-{item.module_position}"})
            ET.SubElement(item_el, "title").text = item.title
            ET.SubElement(item_el, "position").text = str(item.module_position)
            if item.item_type == "Module Folder":
                ET.SubElement(item_el, "indent").text = "0"
                ET.SubElement(item_el, "content_type").text = "ContextModuleSubHeader"
            else:
                ET.SubElement(item_el, "indent").text = "1" if item.folder else "0"
                ET.SubElement(item_el, "content_type").text = "WikiPage"
            ET.SubElement(item_el, "workflow_state").text = workflow_state
            if item.item_type != "Module Folder":
                ET.SubElement(item_el, "page_url").text = item.slug

    xml_body = ET.tostring(root, encoding="utf-8")
    return b"<?xml version='1.0' encoding='UTF-8'?>\n" + xml_body


def _build_manifest_xml(module_titles: list[str], items: list[GeneratedItem]) -> bytes:
    manifest = ET.Element(
        "manifest",
        attrib={
            "identifier": f"man-{uuid4().hex}",
            "xmlns": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1",
            "xmlns:lom": "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource",
            "xmlns:imsmd": "http://www.imsglobal.org/xsd/imsmd_v1p2",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 "
                "http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imscp_v1p1.xsd"
            ),
        },
    )
    metadata = ET.SubElement(manifest, "metadata")
    ET.SubElement(metadata, "schema").text = "IMS Common Cartridge"
    ET.SubElement(metadata, "schemaversion").text = "1.1.0"

    organizations = ET.SubElement(manifest, "organizations")
    organization = ET.SubElement(organizations, "organization", attrib={"identifier": "ORG1", "structure": "rooted-hierarchy"})
    ET.SubElement(organization, "title").text = "Course Modules"

    resources = ET.SubElement(manifest, "resources")
    module_meta_resource = ET.SubElement(
        resources,
        "resource",
        attrib={
            "identifier": "RES-MODULE-META",
            "type": "associatedcontent/imscc_xmlv1p1/learning-application-resource",
            "href": "course_settings/module_meta.xml",
        },
    )
    ET.SubElement(module_meta_resource, "file", attrib={"href": "course_settings/module_meta.xml"})
    ET.SubElement(module_meta_resource, "file", attrib={"href": "course_settings/course_settings.xml"})

    for module_idx, module_title in enumerate(module_titles, start=1):
        module_item = ET.SubElement(organization, "item", attrib={"identifier": f"ORG-MODULE-{module_idx}"})
        ET.SubElement(module_item, "title").text = module_title
        module_items = [i for i in items if i.module_index == module_idx]
        folder_nodes: dict[str, ET.Element] = {}
        for module_item_entry in module_items:
            if module_item_entry.item_type == "Module Folder":
                folder_name = module_item_entry.folder
                folder_nodes[folder_name] = ET.SubElement(
                    module_item,
                    "item",
                    attrib={"identifier": f"ORG-FOLDER-{module_idx}-{module_item_entry.module_position}"},
                )
                ET.SubElement(folder_nodes[folder_name], "title").text = module_item_entry.title
                continue

            page = module_item_entry
            res_id = f"RES-PAGE-{module_idx}-{page.item_index}"
            parent = folder_nodes.get(page.folder, module_item)
            child = ET.SubElement(
                parent,
                "item",
                attrib={"identifier": f"ORG-PAGE-{module_idx}-{page.item_index}", "identifierref": res_id},
            )
            ET.SubElement(child, "title").text = page.title

            res = ET.SubElement(
                resources,
                "resource",
                attrib={"identifier": res_id, "type": "webcontent", "href": f"wiki_content/{page.slug}.html"},
            )
            ET.SubElement(res, "file", attrib={"href": f"wiki_content/{page.slug}.html"})

    xml_body = ET.tostring(manifest, encoding="utf-8")
    return b"<?xml version='1.0' encoding='UTF-8'?>\n" + xml_body


def _build_course_settings_xml(config: dict[str, Any]) -> bytes:
    visible_ids = [
        CANVAS_TAB_IDS["announcements"],
        CANVAS_TAB_IDS["modules"],
        CANVAS_TAB_IDS["grades"],
    ]
    all_tab_ids = sorted(set(CANVAS_TAB_IDS.values()))
    tab_config = []
    for tab_id in all_tab_ids:
        entry: dict[str, Any] = {"id": tab_id}
        if tab_id not in visible_ids:
            entry["hidden"] = True
        tab_config.append(entry)

    root = ET.Element("course", attrib={"xmlns": "http://canvas.instructure.com/xsd/cccv1p0"})
    ET.SubElement(root, "default_view").text = "modules"
    ET.SubElement(root, "tab_configuration").text = json.dumps(tab_config)
    xml_body = ET.tostring(root, encoding="utf-8")
    return b"<?xml version='1.0' encoding='UTF-8'?>\n" + xml_body


def generate_imscc(config: dict[str, Any]) -> bytes:
    module_titles = build_module_titles(config)
    if not module_titles:
        raise ValueError("No module titles were provided.")

    items = _build_items(config, module_titles)
    unpublished = bool(config.get("unpublished", True))

    module_meta_xml = _build_module_meta_xml(module_titles, items, unpublished)
    manifest_xml = _build_manifest_xml(module_titles, items)
    course_settings_xml = _build_course_settings_xml(config)

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", manifest_xml)
        zf.writestr("course_settings/module_meta.xml", module_meta_xml)
        zf.writestr("course_settings/course_settings.xml", course_settings_xml)
        zf.writestr(
            "course_settings/export_meta.json",
            (
                "{\n"
                f'  "generated_at_utc": "{datetime.now(timezone.utc).isoformat()}",\n'
                f'  "module_count": {len(module_titles)}\n'
                "}\n"
            ),
        )
        for item in items:
            if item.item_type == "Module Folder":
                continue
            zf.writestr(f"wiki_content/{item.slug}.html", item.body_html)

    output.seek(0)
    return output.getvalue()
