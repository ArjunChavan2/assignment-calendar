#!/Users/arjunchavan/tasky/assignment-calendar/.venv/bin/python3
"""
scrape_assignments.py
Scrape Canvas + Gradescope for assignments, update config.js, and push to GitHub.

Requirements:
    pip install selenium requests icalendar

Usage:
    python3 scrape_assignments.py              # scrape, update, push
    python3 scrape_assignments.py --dry-run    # preview changes, don't write
    python3 scrape_assignments.py --no-push    # update config.js but skip git push
    python3 scrape_assignments.py --headless   # run Chrome headless (skip if first run)

First run: Chrome opens so you can log into Canvas + Gradescope.
The browser profile persists at ~/.assignment-scraper-profile/ for future runs.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Dependency check ───────────────────────────────────────────────────

def check_deps():
    missing = []
    try:
        from selenium import webdriver  # noqa: F401
    except ImportError:
        missing.append("selenium")
    try:
        import requests  # noqa: F401
    except ImportError:
        missing.append("requests")
    try:
        from icalendar import Calendar  # noqa: F401
    except ImportError:
        missing.append("icalendar")
    if missing:
        sys.exit(f"Missing dependencies. Run:\n  pip install {' '.join(missing)}")

check_deps()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, JavascriptException
import requests
from icalendar import Calendar

# ── Constants ──────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / "tasky" / "assignment-calendar" / "config.js"
REPO_URL = "https://github.com/ArjunChavan2/assignment-calendar.git"
CANVAS_BASE = "https://umich.instructure.com"
ICS_URL = (
    "https://umich.instructure.com/feeds/calendars/"
    "user_1wR4Rqnv0y18q736ayBsqVKlbdf5xyjUUDKUyfDa.ics"
)
CHROME_PROFILE_DIR = Path.home() / ".assignment-scraper-profile"

GRADESCOPE_COURSES = {
    "stats250": [
        {"url_id": "1198964", "label": "STATS 250 EP/Labs/CS/Exams"},
        {"url_id": "1198968", "label": "STATS 250 Lecture Activities"},
    ],
    "eecs370": [
        {"url_id": "1199590", "label": "EECS 370"},
    ],
    "eecs442": [
        {"url_id": "1169657", "label": "EECS 442"},
    ],
}

# Course name → config key mapping for Canvas planner items
CANVAS_COURSE_MAP = {
    "eecs 270": "eecs270",
    "eecs 370": "eecs370",
    "eecs 442": "eecs442",
    "stats 250": "stats250",
    "tchnclcm 300": "tc300",
    "tc 300": "tc300",
}

TODAY = datetime.now().strftime("%Y-%m-%d")
TODAY_DISPLAY = datetime.now().strftime("%B %-d, %Y")  # e.g. "March 17, 2026"

# ── Timezone helpers ───────────────────────────────────────────────────

# DST transition: March 8, 2026 2:00 AM → EDT (UTC-4)
# November 1, 2026 2:00 AM → EST (UTC-5)
EDT = timezone(timedelta(hours=-4))
EST = timezone(timedelta(hours=-5))
DST_START_2026 = datetime(2026, 3, 8, 7, 0, 0, tzinfo=timezone.utc)  # 2AM EST = 7AM UTC
DST_END_2026 = datetime(2026, 11, 1, 6, 0, 0, tzinfo=timezone.utc)   # 2AM EDT = 6AM UTC


def utc_to_eastern(dt):
    """Convert a UTC datetime to Eastern Time, handling DST."""
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    if DST_START_2026 <= dt < DST_END_2026:
        return dt.astimezone(EDT)
    return dt.astimezone(EST)


def format_time_eastern(dt):
    """Format a datetime as '11:59 PM' style string in Eastern."""
    et = utc_to_eastern(dt)
    return et.strftime("%-I:%M %p")


def format_date_eastern(dt):
    """Format a datetime as 'YYYY-MM-DD' in Eastern."""
    et = utc_to_eastern(dt)
    return et.strftime("%Y-%m-%d")


# ── Parse config.js ───────────────────────────────────────────────────

def parse_config():
    """Use Node.js to parse config.js → (assignments list, autoCompleted list, raw text)."""
    raw = CONFIG_PATH.read_text()
    node_script = textwrap.dedent(f"""\
        const fs = require('fs');
        const src = fs.readFileSync('{CONFIG_PATH}', 'utf8');
        const fn = new Function(src + '; return APP_CONFIG;');
        const config = fn();
        console.log(JSON.stringify({{
            assignments: config.assignments,
            autoCompleted: config.autoCompleted,
            scrapeDate: config.scrapeDate
        }}));
    """)
    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"Failed to parse config.js:\n{result.stderr}")
    data = json.loads(result.stdout)
    return data["assignments"], data["autoCompleted"], raw


# ── Write config.js ───────────────────────────────────────────────────

def format_assignment_js(a):
    """Format a single assignment as a JS object literal matching the config style."""
    parts = [
        f'id: "{a["id"]}"',
        f'name: "{a["name"]}"',
        f'course: "{a["course"]}"',
        f'due: "{a["due"]}"',
    ]
    if a.get("time") is None:
        parts.append("time: null")
    else:
        parts.append(f'time: "{a["time"]}"')
    parts.append(f'type: "{a["type"]}"')
    parts.append(f'points: "{a["points"]}"')
    if isinstance(a.get("hours"), float) and a["hours"] == int(a["hours"]):
        parts.append(f'hours: {int(a["hours"])}')
    else:
        parts.append(f'hours: {a.get("hours", 1)}')
    if a.get("specUrl"):
        parts.append(f'specUrl: "{a["specUrl"]}"')
    return "    { " + ", ".join(parts) + " },"


def write_config(raw_text, assignments, auto_completed):
    """Update config.js by replacing scrapeDate, assignments array, and autoCompleted."""
    # Update scrapeDate
    raw_text = re.sub(
        r'scrapeDate:\s*"[^"]*"',
        f'scrapeDate: "{TODAY_DISPLAY}"',
        raw_text
    )

    # Build assignments block
    # Group assignments by course for comments
    course_order = ["eecs270", "eecs370", "eecs442", "stats250", "tc300"]
    course_labels = {
        "eecs270": "EECS 270", "eecs370": "EECS 370", "eecs442": "EECS 442",
        "stats250": "STATS 250", "tc300": "TCHNCLCM 300",
    }

    lines = []
    for course_key in course_order:
        course_assignments = [a for a in assignments if a["course"] == course_key]
        if not course_assignments:
            continue
        # Group by type within course
        type_groups = {}
        for a in course_assignments:
            t = a.get("type", "assignment")
            type_groups.setdefault(t, []).append(a)
        first_type = True
        for atype, items in type_groups.items():
            label = course_labels.get(course_key, course_key)
            type_label = {
                "project": "Projects", "quiz": "Quizzes", "exam": "Exams",
                "homework": "Homeworks", "prelab": "Pre-Labs", "ep": "EPs",
                "lab": "Labs", "casestudy": "Case Studies", "lecture": "Lecture Activities",
                "assignment": "", "reading": "Readings",
            }.get(atype, atype.title())
            comment_suffix = f" - {type_label}" if type_label else ""
            if first_type:
                lines.append(f"    // ===== {label}{comment_suffix} =====")
                first_type = False
            else:
                lines.append(f"    // {label}{comment_suffix}")
            for a in items:
                lines.append(format_assignment_js(a))

    assignments_block = "\n".join(lines)

    # Replace assignments array
    raw_text = re.sub(
        r'(assignments:\s*\[)\s*\n.*?\n(\s*\],)',
        f'\\1\n{assignments_block}\n\\2',
        raw_text,
        flags=re.DOTALL
    )

    # Build autoCompleted block
    ac_lines = []
    # Group by course prefix
    ac_groups = {"270": [], "370": [], "442": [], "s250": [], "tc": []}
    for aid in auto_completed:
        for prefix in ac_groups:
            if aid.startswith(prefix):
                ac_groups[prefix].append(aid)
                break
    ac_comments = {
        "270": "EECS 270", "370": "EECS 370", "442": "EECS 442",
        "s250": "STATS 250", "tc": "TC 300",
    }
    for prefix, ids in ac_groups.items():
        if not ids:
            continue
        ac_lines.append(f"    // {ac_comments[prefix]}")
        # Chunk into lines of ~5-6 IDs
        chunk_size = 6
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i:i+chunk_size]
            quoted = ",".join(f"'{x}'" for x in chunk)
            trailing = "," if i + chunk_size < len(ids) else ","
            ac_lines.append(f"    {quoted}{trailing}")

    ac_block = "\n".join(ac_lines)

    raw_text = re.sub(
        r'(autoCompleted:\s*\[)\s*\n.*?\n(\s*\])',
        f'\\1\n{ac_block}\n\\2',
        raw_text,
        flags=re.DOTALL
    )

    CONFIG_PATH.write_text(raw_text)
    return raw_text


# ── Selenium setup ─────────────────────────────────────────────────────

def make_driver(headless=False):
    """Create a Chrome WebDriver using a persistent profile for auth."""
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    if headless:
        opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(5)
    return driver


def wait_for_login(driver, url, check_fn, service_name):
    """Navigate to url; if check_fn(driver) is False, prompt user to log in."""
    driver.get(url)
    time.sleep(3)
    if not check_fn(driver):
        print(f"\n⚠  Please log into {service_name} in the browser window.")
        print("   Press Enter here when done...")
        input()
        time.sleep(2)
        if not check_fn(driver):
            print(f"   Still not logged into {service_name}. Skipping.")
            return False
    return True


# ── Canvas scraping ────────────────────────────────────────────────────

def scrape_canvas_planner(driver):
    """Fetch Canvas planner items via the API (executed in browser context)."""
    logged_in = wait_for_login(
        driver, CANVAS_BASE,
        lambda d: "login" not in d.current_url.lower(),
        "Canvas"
    )
    if not logged_in:
        return []

    print("   Fetching Canvas planner API...")
    try:
        items = driver.execute_script("""
            const resp = await fetch(
                "/api/v1/planner/items?start_date=2026-01-01&end_date=2026-05-01&per_page=100"
            );
            if (!resp.ok) return [];
            return await resp.json();
        """)
    except JavascriptException as e:
        print(f"   Canvas API error: {e}")
        return []

    print(f"   Got {len(items)} planner items from Canvas.")
    return items or []


def parse_canvas_items(items):
    """Convert Canvas planner items into our assignment dict format."""
    assignments = []
    for item in items:
        plannable = item.get("plannable", {})
        context_name = (item.get("context_name") or "").lower()
        course_key = None
        for pattern, key in CANVAS_COURSE_MAP.items():
            if pattern in context_name:
                course_key = key
                break
        if not course_key:
            continue  # skip courses we don't track

        # Skip STATS 250 from Canvas (use Gradescope instead)
        if course_key == "stats250":
            continue

        name = plannable.get("title", "Unknown")
        due_at = item.get("plannable_date") or plannable.get("due_at")
        if not due_at:
            continue

        # Parse ISO date
        try:
            dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        except ValueError:
            continue

        due_date = format_date_eastern(dt)
        due_time = format_time_eastern(dt)

        # Generate an ID based on course conventions
        assignment_id = generate_canvas_id(course_key, name, item)

        # Guess type
        atype = guess_type(name, item.get("plannable_type", ""))

        assignments.append({
            "id": assignment_id,
            "name": name,
            "course": course_key,
            "due": due_date,
            "time": due_time,
            "type": atype,
            "points": str(plannable.get("points_possible", "—")),
            "hours": guess_hours(atype),
        })
    return assignments


def generate_canvas_id(course_key, name, item):
    """Generate a config-style ID for a Canvas assignment."""
    name_lower = name.lower()
    prefix = {"eecs270": "270", "eecs370": "370", "eecs442": "442",
              "stats250": "s250", "tc300": "tc"}[course_key]

    if course_key == "tc300":
        # TC 300: tc-{descriptive-slug}
        slug = re.sub(r'[^a-z0-9]+', '-', name_lower).strip('-')[:30]
        return f"tc-{slug}"

    # Try to extract number patterns
    # Project N, HW N, Quiz N, Exam N, etc.
    m = re.search(r'project\s*(\d+)([a-z]?)', name_lower)
    if m:
        return f"{prefix}-p{m.group(1)}{m.group(2)}"

    m = re.search(r'(?:hw|homework)\s*(\d+)', name_lower)
    if m:
        return f"{prefix}-hw{m.group(1)}"

    m = re.search(r'quiz\s*(\d+)', name_lower)
    if m:
        return f"{prefix}-q{m.group(1)}"

    m = re.search(r'pre-?lab\s*(\d+)', name_lower)
    if m:
        return f"{prefix}-pl{m.group(1)}"

    if "midterm" in name_lower:
        return f"{prefix}-midterm"
    if "final" in name_lower and "exam" in name_lower:
        return f"{prefix}-final"
    if "exam" in name_lower:
        m = re.search(r'exam\s*(\d+)', name_lower)
        if m:
            return f"{prefix}-exam{m.group(1)}"
        return f"{prefix}-exam"

    # Fallback: slug
    slug = re.sub(r'[^a-z0-9]+', '-', name_lower).strip('-')[:20]
    return f"{prefix}-{slug}"


def guess_type(name, plannable_type):
    """Guess assignment type from name/plannable_type."""
    nl = name.lower()
    if "exam" in nl or "midterm" in nl or "final" in nl:
        return "exam"
    if "quiz" in nl:
        return "quiz"
    if "project" in nl:
        return "project"
    if "homework" in nl or nl.startswith("hw"):
        return "homework"
    if "pre-lab" in nl or "prelab" in nl:
        return "prelab"
    if "lab" in nl:
        return "lab"
    if plannable_type == "quiz":
        return "quiz"
    if plannable_type == "discussion_topic":
        return "assignment"
    return "assignment"


def guess_hours(atype):
    """Rough hour estimate by type."""
    return {"exam": 12, "project": 8, "homework": 6, "quiz": 1.5,
            "prelab": 1, "lab": 1.5, "ep": 2, "casestudy": 3,
            "lecture": 0.5, "assignment": 1}.get(atype, 1)


# ── Canvas ICS feed ────────────────────────────────────────────────────

def fetch_canvas_ics():
    """Fetch the Canvas ICS calendar feed (no auth needed)."""
    print("   Fetching Canvas ICS feed...")
    try:
        resp = requests.get(ICS_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"   ICS feed error: {e}")
        return []

    cal = Calendar.from_ical(resp.text)
    items = []
    for event in cal.walk("VEVENT"):
        summary = str(event.get("SUMMARY", ""))
        dtstart = event.get("DTSTART")
        if not dtstart:
            continue
        dt = dtstart.dt
        if isinstance(dt, datetime):
            due_date = format_date_eastern(dt)
            due_time = format_time_eastern(dt)
        else:
            due_date = dt.strftime("%Y-%m-%d")
            due_time = None

        # Try to identify the course from the summary or description
        description = str(event.get("DESCRIPTION", ""))
        course_key = None
        for pattern, key in CANVAS_COURSE_MAP.items():
            if pattern in summary.lower() or pattern in description.lower():
                course_key = key
                break

        items.append({
            "summary": summary,
            "due": due_date,
            "time": due_time,
            "course_key": course_key,
            "description": description,
        })

    print(f"   Got {len(items)} events from ICS feed.")
    return items


# ── Gradescope scraping ───────────────────────────────────────────────

def scrape_gradescope(driver, course_url_id, course_key, label):
    """Scrape assignments from a Gradescope course page."""
    url = f"https://www.gradescope.com/courses/{course_url_id}"
    driver.get(url)
    time.sleep(3)

    # Check if logged in
    if "login" in driver.current_url.lower() or "sessions" in driver.current_url.lower():
        print(f"\n⚠  Please log into Gradescope in the browser window.")
        print("   Press Enter here when done...")
        input()
        driver.get(url)
        time.sleep(3)

    print(f"   Scraping {label} ({course_url_id})...")

    # Extract assignment data from the page
    try:
        assignments_data = driver.execute_script("""
            const rows = document.querySelectorAll('tr.js-assignmentTableRow, table.table tbody tr');
            const results = [];
            rows.forEach(row => {
                const nameEl = row.querySelector('th.table--primaryLink a, td a.js-assignmentLink, th a');
                const statusEl = row.querySelector('.submissionStatus, .submission-status');
                const dueDateEl = row.querySelector('time, .submissionTimeChart--dueDate, td:nth-child(2)');

                if (!nameEl) return;

                const name = nameEl.textContent.trim();
                let dueText = '';
                if (dueDateEl) {
                    dueText = dueDateEl.getAttribute('datetime') || dueDateEl.textContent.trim();
                }
                const submitted = statusEl ?
                    statusEl.textContent.toLowerCase().includes('submitted') : false;

                results.push({name, dueText, submitted});
            });
            return results;
        """)
    except JavascriptException as e:
        print(f"   Gradescope scrape error for {label}: {e}")
        return [], []

    if not assignments_data:
        # Try alternative selector pattern
        try:
            assignments_data = driver.execute_script("""
                const rows = document.querySelectorAll('[class*="assignment"]');
                const results = [];
                rows.forEach(row => {
                    const name = row.querySelector('a, [class*="name"], [class*="title"]');
                    const due = row.querySelector('time, [class*="due"], [class*="date"]');
                    if (!name) return;
                    results.push({
                        name: name.textContent.trim(),
                        dueText: due ? (due.getAttribute('datetime') || due.textContent.trim()) : '',
                        submitted: row.textContent.toLowerCase().includes('submitted')
                    });
                });
                return results;
            """)
        except JavascriptException:
            assignments_data = []

    assignments = []
    submitted_ids = []

    for item in (assignments_data or []):
        name = item.get("name", "")
        due_text = item.get("dueText", "")
        submitted = item.get("submitted", False)

        if not name or not due_text:
            continue

        # Parse the due date
        due_date, due_time = parse_gradescope_date(due_text)
        if not due_date:
            continue

        # Generate ID
        aid = generate_gradescope_id(course_key, name)
        atype = guess_gradescope_type(course_key, name)

        assignments.append({
            "id": aid,
            "name": name,
            "course": course_key,
            "due": due_date,
            "time": due_time,
            "type": atype,
            "points": "—",
            "hours": guess_hours(atype),
        })

        if submitted:
            submitted_ids.append(aid)

    print(f"   Found {len(assignments)} assignments from {label}.")
    return assignments, submitted_ids


def parse_gradescope_date(text):
    """Parse a Gradescope date string into (YYYY-MM-DD, 'H:MM PM')."""
    # Try ISO format first (from datetime attribute)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return format_date_eastern(dt), format_time_eastern(dt)
    except (ValueError, TypeError):
        pass

    # Try common Gradescope text formats: "Mar 17, 2026 11:59 PM"
    for fmt in [
        "%b %d, %Y %I:%M %p",
        "%b %d, %Y at %I:%M %p",
        "%B %d, %Y %I:%M %p",
        "%B %d, %Y at %I:%M %p",
        "%Y-%m-%d %H:%M:%S %z",
        "%m/%d/%Y %I:%M %p",
    ]:
        try:
            dt = datetime.strptime(text.strip(), fmt)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%-I:%M %p")
        except ValueError:
            continue

    # Try to extract just a date
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0), None

    return None, None


def generate_gradescope_id(course_key, name):
    """Generate an ID for a Gradescope assignment following conventions."""
    nl = name.lower().strip()
    if course_key == "stats250":
        # EP 01 → s250-ep01
        m = re.search(r'ep\s*(\d+)', nl)
        if m:
            return f"s250-ep{int(m.group(1)):02d}"
        # Lab N → s250-labN
        m = re.search(r'lab\s*(\d+)', nl)
        if m:
            return f"s250-lab{m.group(1)}"
        # Case Study N → s250-csN
        m = re.search(r'case\s*study\s*(\d+)', nl)
        if m:
            return f"s250-cs{m.group(1)}"
        # Exam N → s250-examN
        m = re.search(r'exam\s*(\d+)', nl)
        if m:
            return f"s250-exam{m.group(1)}"
        # Lecture NN PW/GW → s250-lNNpw / s250-lNNgw
        m = re.search(r'lecture\s*(\d+)\s*(pw|gw)', nl)
        if m:
            return f"s250-l{int(m.group(1)):02d}{m.group(2)}"

    elif course_key == "eecs370":
        m = re.search(r'pre-?lab\s*(\d+)', nl)
        if m:
            return f"370-pl{m.group(1)}"
        m = re.search(r'(?:hw|homework)\s*(\d+)', nl)
        if m:
            return f"370-hw{m.group(1)}"
        m = re.search(r'project\s*(\d+)([a-z]?)', nl)
        if m:
            return f"370-p{m.group(1)}{m.group(2)}"

    elif course_key == "eecs442":
        m = re.search(r'(?:hw|homework)\s*(\d+)', nl)
        if m:
            return f"442-hw{m.group(1)}"
        m = re.search(r'quiz\s*(\d+)', nl)
        if m:
            return f"442-q{m.group(1)}"
        if "midterm" in nl:
            return "442-midterm"

    # Fallback
    prefix = {"eecs270": "270", "eecs370": "370", "eecs442": "442",
              "stats250": "s250", "tc300": "tc"}.get(course_key, course_key)
    slug = re.sub(r'[^a-z0-9]+', '-', nl).strip('-')[:25]
    return f"{prefix}-{slug}"


def guess_gradescope_type(course_key, name):
    """Guess assignment type for Gradescope items."""
    nl = name.lower()
    if "exam" in nl or "midterm" in nl or "final" in nl:
        return "exam"
    if "quiz" in nl:
        return "quiz"
    if "pre-lab" in nl or "prelab" in nl:
        return "prelab"
    if "lab" in nl:
        return "lab"
    if course_key == "stats250":
        if re.search(r'\bep\b', nl):
            return "ep"
        if "case study" in nl:
            return "casestudy"
        if "lecture" in nl:
            return "lecture"
    if "homework" in nl or nl.startswith("hw"):
        return "homework"
    if "project" in nl:
        return "project"
    return "assignment"


# ── Merge logic ────────────────────────────────────────────────────────

def merge_assignments(existing, new_items, auto_completed):
    """
    Merge new scraped assignments into the existing list.
    - Adds new assignments not already present (by ID).
    - Updates due dates/times if they've changed.
    - Adds past-due submitted items to autoCompleted.
    Returns (merged_assignments, updated_autoCompleted, changes_log).
    """
    existing_by_id = {a["id"]: a for a in existing}
    changes = []

    for item in new_items:
        aid = item["id"]
        if aid in existing_by_id:
            # Check if due date/time changed
            old = existing_by_id[aid]
            if old["due"] != item["due"]:
                changes.append(f"  UPDATED {aid}: due {old['due']} → {item['due']}")
                old["due"] = item["due"]
            if old.get("time") != item.get("time") and item.get("time"):
                changes.append(f"  UPDATED {aid}: time {old.get('time')} → {item['time']}")
                old["time"] = item["time"]
        else:
            # New assignment — insert it
            # Find the right position (after last assignment of same course & type)
            insert_idx = len(existing)
            for i, a in enumerate(existing):
                if a["course"] == item["course"] and a.get("type") == item.get("type"):
                    insert_idx = i + 1
            existing.insert(insert_idx, item)
            existing_by_id[aid] = item
            changes.append(f"  ADDED   {aid}: {item['name']} (due {item['due']})")

    # Add past-due submitted items to autoCompleted
    ac_set = set(auto_completed)
    for item in new_items:
        if item.get("_submitted") and item["id"] not in ac_set:
            auto_completed.append(item["id"])
            ac_set.add(item["id"])
            changes.append(f"  AUTO-COMPLETED {item['id']}")

    return existing, auto_completed, changes


# ── Validate config.js ────────────────────────────────────────────────

def validate_config():
    """Run Node.js to validate config.js syntax."""
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(f"""\
            const fs = require('fs');
            const src = fs.readFileSync('{CONFIG_PATH}', 'utf8');
            const fn = new Function(src + '; return APP_CONFIG;');
            const c = fn();
            console.log('OK ' + c.assignments.length + ' assignments');
        """)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ Validation FAILED:\n{result.stderr}")
        return False
    print(f"✅ {result.stdout.strip()}")
    return True


# ── Git push ──────────────────────────────────────────────────────────

def git_push():
    """Commit and push config.js via a clean /tmp clone (avoids FUSE issues)."""
    tmp_dir = "/tmp/ac-push"
    try:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        print("   Cloning repo to /tmp for push...")
        subprocess.run(
            ["git", "clone", REPO_URL, tmp_dir],
            check=True, capture_output=True, text=True
        )

        # Copy updated config.js
        shutil.copy2(CONFIG_PATH, os.path.join(tmp_dir, "config.js"))

        # Check if there's actually a diff
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=tmp_dir, capture_output=True, text=True
        )
        if not result.stdout.strip():
            print("   No changes to push.")
            return False

        # Configure git and commit
        date_str = datetime.now().strftime("%Y-%m-%d")
        cmds = [
            ["git", "config", "user.email", "akchavan@umich.edu"],
            ["git", "config", "user.name", "Arjun Chavan"],
            ["git", "add", "config.js"],
        ]
        for cmd in cmds:
            subprocess.run(cmd, cwd=tmp_dir, check=True, capture_output=True)

        # Show diff stat
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=tmp_dir, capture_output=True, text=True
        )
        print(f"   {result.stdout.strip()}")

        # Commit
        msg = f"chore: scrape {date_str} — update assignments + autoCompleted"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=tmp_dir, check=True, capture_output=True, text=True
        )

        # Push
        print("   Pushing to GitHub...")
        subprocess.run(
            ["git", "push"],
            cwd=tmp_dir, check=True, capture_output=True, text=True
        )
        print("   ✅ Pushed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"   ❌ Git error: {e.stderr}")
        return False
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape assignments and update config.js")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--no-push", action="store_true", help="Update config.js but don't push")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--skip-canvas", action="store_true", help="Skip Canvas scraping")
    parser.add_argument("--skip-gradescope", action="store_true", help="Skip Gradescope scraping")
    parser.add_argument("--skip-ics", action="store_true", help="Skip ICS feed")
    args = parser.parse_args()

    print(f"═══ Assignment Scraper — {TODAY} ═══\n")

    # 1. Parse current config
    print("1. Reading config.js...")
    assignments, auto_completed, raw_text = parse_config()
    print(f"   {len(assignments)} assignments, {len(auto_completed)} auto-completed\n")

    all_new = []
    all_submitted = []
    driver = None

    try:
        # 2. Canvas ICS feed (no browser needed)
        if not args.skip_ics:
            print("2. Fetching Canvas ICS feed...")
            ics_events = fetch_canvas_ics()
            # ICS events are used as supplementary data — we don't directly
            # create assignments from ICS since the planner API is more detailed.
            # But we can cross-reference dates.
            print()

        # 3. Set up browser for Canvas API + Gradescope
        needs_browser = not (args.skip_canvas and args.skip_gradescope)
        if needs_browser:
            print("3. Starting Chrome...")
            driver = make_driver(headless=args.headless)
            print()

        # 4. Canvas planner API
        if not args.skip_canvas and driver:
            print("4. Scraping Canvas planner...")
            canvas_items = scrape_canvas_planner(driver)
            parsed = parse_canvas_items(canvas_items)
            all_new.extend(parsed)
            print()
        else:
            print("4. Skipping Canvas.\n")

        # 5. Gradescope
        if not args.skip_gradescope and driver:
            print("5. Scraping Gradescope...")
            for course_key, courses in GRADESCOPE_COURSES.items():
                for course_info in courses:
                    gs_assignments, gs_submitted = scrape_gradescope(
                        driver, course_info["url_id"], course_key, course_info["label"]
                    )
                    all_new.extend(gs_assignments)
                    all_submitted.extend(gs_submitted)
            print()
        else:
            print("5. Skipping Gradescope.\n")

    finally:
        if driver:
            driver.quit()

    # 6. Merge
    print("6. Merging assignments...")
    # Mark submitted items
    submitted_set = set(all_submitted)
    for item in all_new:
        if item["id"] in submitted_set:
            item["_submitted"] = True

    merged, updated_ac, changes = merge_assignments(assignments, all_new, auto_completed)

    if not changes:
        print("   No changes detected.\n")
        if not args.dry_run:
            # Still update scrapeDate
            write_config(raw_text, merged, updated_ac)
            if validate_config() and not args.no_push:
                git_push()
        return

    print(f"   {len(changes)} change(s):")
    for c in changes:
        print(c)
    print()

    if args.dry_run:
        print("── Dry run — no files modified ──")
        return

    # 7. Write config.js
    print("7. Writing config.js...")
    write_config(raw_text, merged, updated_ac)
    print()

    # 8. Validate
    print("8. Validating config.js...")
    if not validate_config():
        print("   Aborting push due to validation failure.")
        return
    print()

    # 9. Push
    if args.no_push:
        print("9. Skipping push (--no-push).")
    else:
        print("9. Pushing to GitHub...")
        git_push()

    print("\nDone!")


if __name__ == "__main__":
    main()
