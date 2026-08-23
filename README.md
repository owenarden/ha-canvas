# Canvas LMS for Home Assistant

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=owenarden&repository=ha-canvas&category=Integration)

Bring Canvas assignments directly into Home Assistant. This fork creates a master calendar for the logged-in student account and individual calendars for active courses.

## Features
- **Master Calendar**: A single view across all active courses.
- **Per-Course Calendars**: Separate calendar entities for each active class.
- **Arbitrary Calendar Ranges**: Home Assistant date-range queries fetch assignments directly from Canvas rather than relying only on Canvas's rolling upcoming-events feed.
- **Submission State**: Calendar descriptions include workflow status plus Canvas submission metadata such as missing, late, excused, submission type, and submitted timestamp when available.
- **Assignment Details**: Course name and points possible are included.
- **Easy Links**: Calendar events link directly to the Canvas assignment.

## Installation

### HACS (Recommended)
1. Ensure [HACS](https://hacs.xyz/) is installed.
2. Click the badge above or navigate to HACS > Integrations > 3-dot menu > Custom Repositories.
3. Add `https://github.com/owenarden/ha-canvas` with category `Integration`.
4. Search for **Canvas Student** and install it.
5. Restart Home Assistant.

### Manual
1. Download the `canvas_student` folder from `custom_components`.
2. Paste it into your Home Assistant `/config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration
1. Go to **Settings > Devices & Services > Add Integration**.
2. Search for **Canvas Student**.
3. **Base URL**: Enter the school's Canvas URL.
4. **Access Token**:
   - Log into the student's Canvas account.
   - Go to **Account > Settings**.
   - Scroll to **Approved Integrations** and create a new access token.
   - Paste that token into Home Assistant.

## Four-week dashboard example

This repository includes optional generic Home Assistant examples under `examples/home_assistant/`:

- `packages/student_canvas.yaml` — a trigger-based template sensor that calls `calendar.get_events` every 15 minutes and stores the next 28 days of assignments.
- `lovelace/student_canvas_4_week_card.yaml` — a core Markdown Lovelace card that groups assignments by due date and visually distinguishes completed, missing, late, excused, and upcoming work.

The package uses `calendar.canvas_student_calendar` as a placeholder for the master Canvas calendar entity. Replace that placeholder with the actual master calendar entity created by the integration in your Home Assistant instance.

The example sensor created by the package is:

- `sensor.canvas_student_assignments_28_days`

To use Home Assistant packages, ensure `configuration.yaml` contains:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Then copy `examples/home_assistant/packages/student_canvas.yaml` into `/config/packages/`, replace the calendar entity placeholder, restart Home Assistant, and add the Lovelace YAML from `examples/home_assistant/lovelace/student_canvas_4_week_card.yaml` as a Manual card.

## Notes
- The coordinator still refreshes basic profile/course/upcoming-event data every 15 minutes.
- Home Assistant calendar range queries fetch assignment data directly per active course and follow Canvas pagination.
- Submission flags reflect what Canvas reports. An `unsubmitted` assignment is not necessarily missing; use the `Missing`, `Late`, `Excused`, and submission-type fields to distinguish cases.

---
*Disclaimer: This integration is not affiliated with or endorsed by Instructure/Canvas LMS.*
