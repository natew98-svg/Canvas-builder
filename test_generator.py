import io
import xml.etree.ElementTree as ET
import zipfile

from generator import generate_imscc


def _sample_config() -> dict:
    return {
        "template_type": "Weekly",
        "module_count": 3,
        "start_number": 1,
        "custom_module_names": [],
        "prefix": "Week",
        "include_topic": False,
        "topics": [],
        "layout_items": [
            {
                "type": "Page",
                "title_pattern": "{module_folder}: Overview and To Do List",
                "page_template": "Overview",
                "folder": "__AUTO_MODULE__",
                "points": 100,
                "submission_type": "Online",
                "instructions": "",
            },
            {
                "type": "Assignment placeholder",
                "title_pattern": "{module_folder}: Assignment",
                "page_template": "Overview",
                "folder": "__AUTO_MODULE__",
                "points": 20,
                "submission_type": "Online",
                "instructions": "Submit your response.",
            },
        ],
        "module_folders": [],
        "folder_scheme": "Week",
        "folder_header_style": "Folder only",
        "page_templates": {
            "Overview": {"header_title": "Overview", "sections": {"Objectives": "Test objectives"}},
            "Checklist": {"header_title": "Checklist", "sections": {}},
            "Notes": {"header_title": "Notes", "sections": {}},
            "Resources": {"header_title": "Resources", "sections": {}},
            "Wrap-up": {"header_title": "Wrap-up", "sections": {}},
        },
        "unpublished": True,
    }


def test_imscc_zip_is_created():
    data = generate_imscc(_sample_config())
    assert isinstance(data, bytes)
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        assert len(zf.namelist()) > 0


def test_required_files_exist():
    data = generate_imscc(_sample_config())
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = set(zf.namelist())
        assert "imsmanifest.xml" in names
        assert "course_settings/module_meta.xml" in names
        assert "course_settings/course_settings.xml" in names
        assert any(name.startswith("wiki_content/") and name.endswith(".html") for name in names)


def test_module_count_matches_selection():
    cfg = _sample_config()
    cfg["module_count"] = 4
    data = generate_imscc(cfg)
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        module_meta = zf.read("course_settings/module_meta.xml")

    root = ET.fromstring(module_meta)
    modules = root.findall("{http://canvas.instructure.com/xsd/cccv1p0}module")
    assert len(modules) == 4


def test_module_folders_exported_as_subheaders():
    data = generate_imscc(_sample_config())
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        module_meta = zf.read("course_settings/module_meta.xml")
    root = ET.fromstring(module_meta)
    ns = {"c": "http://canvas.instructure.com/xsd/cccv1p0"}
    subheaders = root.findall(".//c:item[c:content_type='ContextModuleSubHeader']", ns)
    assert len(subheaders) > 0


def test_manifest_contains_folder_group_items():
    data = generate_imscc(_sample_config())
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        manifest = zf.read("imsmanifest.xml")
    root = ET.fromstring(manifest)
    ns = {"m": "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"}
    folder_titles = [el.text for el in root.findall(".//m:item/m:title", ns) if el.text]
    assert "Week 1" in folder_titles


def test_course_navigation_defaults_include_announcements_modules_grades():
    data = generate_imscc(_sample_config())
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        settings_xml = zf.read("course_settings/course_settings.xml")
    root = ET.fromstring(settings_xml)
    ns = {"c": "http://canvas.instructure.com/xsd/cccv1p0"}
    default_view = root.find("c:default_view", ns)
    tabs = root.find("c:tab_configuration", ns)
    assert default_view is not None and default_view.text == "modules"
    assert tabs is not None
    assert '"id": 14' in tabs.text
    assert '"id": 10' in tabs.text
    assert '"id": 5' in tabs.text
