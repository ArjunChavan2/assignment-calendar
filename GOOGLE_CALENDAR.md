# Google Calendar

Assignments and deadlines live on Google Calendar, not just on the local site.

- **Classes** (lectures, labs, discussions) are recurring events on the
  **School Schedule** calendar (`akchavan@umich.edu`), created by hand with room
  locations. The scraper does not touch them.
- **Assignments** are generated from `APP_CONFIG.assignments` in `config.js` and
  pushed to that same calendar.

## How assignments get there

`gcal-export.js` reads `config.js` and writes two files:

| File | Purpose |
| --- | --- |
| `calendar.ics` | RFC 5545 feed, served by GitHub Pages — subscribe to it in Google Calendar |
| `gcal-events.json` | The same events as JSON, for scripted syncing |

```bash
node gcal-export.js
```

**Only deadlines from today onward are exported.** `config.js` keeps the whole
term's history, but a feed should not backfill a finished term into the calendar
every time someone subscribes. Pass `--include-past` when you actually want the
backfill, or `--from` to pick an explicit window.

Useful flags:

```bash
node gcal-export.js --include-past          # keep deadlines already passed
node gcal-export.js --from 2026-01-01 --to 2026-05-01
node gcal-export.js --work-blocks           # also emit workPlan study blocks
node gcal-export.js --json                  # print events, write nothing
```

With a finished term in `config.js` and no newer data, the feed is legitimately
empty (a valid, event-free `VCALENDAR`). It fills back in on the next scrape.

`scrape_assignments.py` runs the export automatically (step 11) and commits
`calendar.ics` alongside `config.js`, so every scrape refreshes the feed.

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
- `colorId` matches the course's existing recurring class events:
  270 Flamingo, 370 Sage, 442 Blueberry, STATS 250 Banana, TC 300 Grape.
- Reminders: 1 day and 2 hours before (1 day / 1 hour for exams).
- Every description ends with `Synced from assignment-calendar [<id>]`.

That marker is the handle for the whole set. To find or remove every synced
event, search Google Calendar for `Synced from assignment-calendar` — class
events and personal events do not carry it.

## Term rollover

`scrape_assignments.py` keys the term off four constants near the top:

```python
TERM_NAME  = "Fall 2026"
TERM_START = "2026-08-31"
TERM_END   = "2026-12-12"   # exclusive upper bound for the Canvas planner query
```

Each new term: update those, replace `courses` in `config.js`, empty
`assignments`/`autoCompleted`, and refresh `CANVAS_COURSE_MAP`,
`GRADESCOPE_COURSES`, and the prefix map in `generate_canvas_id()`.
Canvas course IDs auto-discover from enrollment, so `CANVAS_COURSE_IDS` can
stay empty.

Class meetings are **not** generated from `config.js` — they are recurring
Google Calendar events created by hand from the Wolverine Access schedule.

## History

The Winter 2026 term (176 deadlines) was synced to the calendar on 2026-08-30 and
removed the same day at the user's request — it was a finished term and added only
clutter. Removing it is why the exporter now defaults to future-only.

On 2026-08-31 the project was retargeted to Fall 2026 (EECS 367, EECS 373,
EECS 445, CLCIV 371). The Winter config was saved to `backups/`. The Winter
course-website scrapers (`scrape_eecs270_website`, `scrape_eecs370_website`)
are no longer called but kept as reference implementations.
