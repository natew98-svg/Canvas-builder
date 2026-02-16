# Canvas IMSCC Template Builder

A Streamlit app that helps instructors create a Canvas-importable IMS Common Cartridge (`.imscc`) using a form-based wizard.

## Features

- 5-step wizard (no YAML/JSON editing needed)
- Module naming for Weekly, Unit, or Custom list formats
- Reorderable module layout builder with presets
- Auto module folder headers (`Week N` or `Module N`) with selectable item set
- Canvas navigation defaults in export set to show `Announcements`, `Modules`, and `Grades` (best effort; Canvas admin settings can override)
- Safe-scope Canvas course editor (in-app):
  - fetch existing modules and items
  - edit module name/publish/order
  - edit module item title/publish/order
  - edit assignment due date, available-from, and until date/time
  - preview pending changes before apply
- Page template editor for Overview, Checklist, Notes, Resources, and Wrap-up
- Generates a single `.imscc` file for Canvas import
- Includes placeholder support for Assignment, Discussion, and Quiz items (implemented as pages in v1)
- Accessibility-minded output and workflow:
  - labeled form controls in the wizard
  - required pre-export preview confirmation
  - generated HTML pages use semantic landmarks (`main`, section headings), language metadata, and skip links

## Project files

- `app.py` - Streamlit UI wizard
- `generator.py` - IMSCC generator logic (unit-testable)
- `test_generator.py` - pytest tests
- `requirements.txt` - dependencies
- `canvas_nav.py` - post-import Canvas navigation updater
- `canvas_course.py` - Canvas course editor API helpers

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

## Run tests

```bash
pytest -q
```

## Import into Canvas

1. Generate and download `canvas_course_template.imscc` from Step 5.
2. In Canvas, open your blank course.
3. Go to `Settings` -> `Import Course Content`.
4. Content Type: `Common Cartridge 1.x Package`.
5. Choose the generated `.imscc` file.
6. Select import options and start import.
7. After import, review modules and page content, then publish as needed.

## Enforce Navigation Visibility (Post-Import)

Some Canvas environments ignore or override navigation settings from cartridge import.  
Use the helper script to force visibility so only `Announcements`, `Modules`, and `Grades` are shown.

```bash
python /Users/nathan/Documents/College/canvas_nav.py \
  --canvas-url "https://YOUR-SCHOOL.instructure.com" \
  --course-id "12345" \
  --token "YOUR_CANVAS_API_TOKEN"
```

Notes:
- This uses Canvas API after import, which is more reliable than relying on cartridge navigation defaults.
- `Home` and `Settings` are managed by Canvas and are not force-hidden by this script.

## Edit Existing Course (Safe Scope)

In the app, go to `Step 7: Course Editor (Safe Scope)`:

1. Enter `Canvas URL`, `Course ID`, and `API Token`.
2. Click `Fetch Course Data`.
3. Edit only the supported fields:
   - module: name, published, position
   - module item: title, published, position
   - assignment items: due date/time, available from date/time, until date/time
4. Review `Pending Changes`.
5. Click `Apply Safe-Scope Changes`.

## Notes

- In this first pass, Assignment/Discussion/Quiz placeholders are exported as pages with labeled content.
- The generator is structured so real assignment/discussion/quiz objects can be added later.
