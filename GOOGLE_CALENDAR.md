# Google Calendar

Assignments and deadlines live on Google Calendar, not just on the local site.

- **Classes** (lectures, labs, discussions) are recurring events on the
  **School Schedule** calendar (`akchavan@umich.edu`), created by hand with room
  locations. The scraper does not touch them.
- **Assignments** are generated from `assignments.json` (course metadata comes
  from `courses.json`) and pushed to that same calendar.

## How assignments get there

`gcal-export.js` reads `courses.json` + `assignments.json` directly and writes
two files:

| File | Purpose |
| --- | --- |
| `calendar.ics` | RFC 5545 feed, served by GitHub Pages — subscribe to it in Google Calendar |
| `gcal-events.json` | The same events as JSON, for scripted syncing |

```bash
node gcal-export.js
```

**Only deadlines from today onward are exported.** `assignments.json` keeps the
whole term's history, but a feed should not backfill a finished term into the
calendar every time someone subscribes. Pass `--include-past` when you
actually want the backfill, or `--from` to pick an explicit window.

Useful flags:

```bash
node gcal-export.js --include-past          # keep deadlines already passed
node gcal-export.js --from 2026-01-01 --to 2026-05-01
node gcal-export.js --work-blocks           # also emit workPlan study blocks
node gcal-export.js --json                  # print events, write nothing
```

With a finished term in `assignments.json` and no newer data, the feed is
legitimately empty (a valid, event-free `VCALENDAR`). It fills back in on the
next scrape.

`scrape_assignments.py` runs the export automatically and, when run with
`--push`, commits `calendar.ics` alongside `assignments.json` and the
regenerated `config.js`, so every published scrape refreshes the feed.

## Subscribing

In Google Calendar → **Other calendars** → **+** → **From URL**, paste:

```
https://arjunchavan2.github.io/assignment-calendar/calendar.ics
```

Google re-fetches on its own schedule (typically several hours). The feed
declares `REFRESH-INTERVAL:PT6H`.

To load it immediately instead, use **Settings → Import & export → Import** with
a downloaded `calendar.ics`. UIDs are stable (`assignment-<id>@assignment-calendar`),
so re-importing updates existing events rather than duplicating them.

## Event conventions

- Title is `COURSE: Assignment Name`.
- A deadline becomes a 30-minute block **ending** at the due time, so the edge of
  the event is the deadline. Exams get 2 hours.
- Everything is marked **free** except exams, which block time.
- `colorId` matches the course's existing recurring class events (set per
  course as `gcalColorId` in `courses.json`): 367 Sage, 373 Flamingo,
  445 Blueberry, CLCIV 371 Grape.
- Reminders: 1 day and 2 hours before (1 day / 1 hour for exams).
- Every description ends with `Synced from assignment-calendar [<id>]`.

That marker is the handle for the whole set. To find or remove every synced
event, search Google Calendar for `Synced from assignment-calendar` — class
events and personal events do not carry it.

## Term rollover

`courses.json` is the single source of truth for the term — `scrape_assignments.py`,
`validate-config.js`, and `gcal-export.js` all read it directly, so a new term
means editing **only this file**:

```json
{
  "term": "Fall 2026",
  "termStart": "2026-08-31",
  "termEnd": "2026-12-12",
  "courses": {
    "eecs367": {
      "idPrefix": "367",
      "gcalColorId": "2",
      "canvasPatterns": ["eecs 367", "rob 380"],
      "canvasCourseId": null
    }
  }
}
```

For each course, set `canvasPatterns` (substrings matched against Canvas
course names) or a `gradescope` list (`{"url_id": ..., "label": ...}`), plus
`idPrefix` for generated assignment IDs and `gcalColorId` for the Google
Calendar color. Canvas course IDs auto-discover from enrollment, so
`canvasCourseId` can stay `null`.

Then empty `assignments`/`autoCompleted` in `assignments.json`, and run
`node build-config.js` to regenerate `config.js` for the site.

Class meetings are **not** generated from `courses.json` — they are recurring
Google Calendar events created by hand from the Wolverine Access schedule.

## History

The Winter 2026 term (176 deadlines) was synced to the calendar on 2026-08-30 and
removed the same day at the user's request — it was a finished term and added only
clutter. Removing it is why the exporter now defaults to future-only.

On 2026-08-31 the project was retargeted to Fall 2026 (EECS 367, EECS 373,
EECS 445, CLCIV 371). The Winter config was saved to `backups/`.

On 2026-09-06 `config.js` was split into `courses.json` (term/course config)
and `assignments.json` (scraper-owned data), with `config.js` now generated
from both by `build-config.js` — so index.html/classroom.html keep working
unchanged, but the scraper, validator, and calendar exporter all read
structured data directly instead of parsing `config.js` as text. The unused
Winter course-website scrapers (`scrape_eecs270_website`,
`scrape_eecs370_website`) and the redundant `data.json` export were removed.
