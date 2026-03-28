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
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Terminal output helpers ─────────────────────────────────────────────

_RESET  = "\x1b[0m"
_BOLD   = "\x1b[1m"
_GREEN  = "\x1b[32m"
_YELLOW = "\x1b[33m"
_RED    = "\x1b[31m"
_CYAN   = "\x1b[36m"
_GRAY   = "\x1b[90m"

_TOTAL_STEPS = 11

def _step_header(n, label):
    bar = f"{_BOLD}{_CYAN}[{n}/{_TOTAL_STEPS}]{_RESET}"
    print(f"\n{bar} {_BOLD}{label}{_RESET}")

def _ok(msg=""):
    print(f"     {_GREEN}✓{_RESET} {msg}")

def _warn(msg):
    print(f"     {_YELLOW}⚠{_RESET}  {msg}")

def _err(msg):
    print(f"     {_RED}✗{_RESET} {msg}")

def _info(msg):
    print(f"     {_GRAY}→{_RESET} {msg}")


class Spinner:
    """Animated spinner for blocking operations. Use as a context manager."""
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label):
        self._label = label
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self._frames[i % len(self._frames)]
            sys.stdout.write(f"\r     {_CYAN}{frame}{_RESET} {self._label}   ")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        sys.stdout.write("\r" + " " * (len(self._label) + 12) + "\r")
        sys.stdout.flush()

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
GOOGLE_ACCOUNT = "akchavan@umich.edu"
ICS_URL = (
    "https://umich.instructure.com/feeds/calendars/"
    "user_1wR4Rqnv0y18q736ayBsqVKlbdf5xyjUUDKUyfDa.ics"
)
CHROME_PROFILE_DIR = Path.home() / ".assignment-scraper-profile"

# Canvas course IDs — maps config course key → Canvas course ID
# These are used for the per-course assignments API
# If a course ID is unknown, the scraper will try to discover it from enrolled courses
CANVAS_COURSE_IDS = {
    "eecs270": "815882",
    # Others will be auto-discovered from Canvas enrollment
}

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


DATA_JSON_PATH = Path.home() / "tasky" / "assignment-calendar" / "data.json"


def write_data_json(assignments, auto_completed):
    """Export assignments and autoCompleted as a clean data.json for external apps."""
    data = {
        "scrapeDate": TODAY_DISPLAY,
        "assignments": assignments,
        "autoCompleted": list(auto_completed),
    }
    DATA_JSON_PATH.write_text(json.dumps(data, indent=2))


# ── Selenium setup ─────────────────────────────────────────────────────

def make_driver(headless=False):
    """
    Launch Chrome with a persistent profile so logins are remembered
    between runs. First run requires signing in; after that cookies persist.
    """
    _info("Launching Chrome with saved profile…")
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    if headless:
        opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(5)
    _ok("Chrome ready")
    return driver


LOGIN_TIMEOUT = 120  # seconds to wait for manual login before giving up


def _google_active_accounts(driver):
    """Return the set of Google account emails currently signed in to the browser."""
    try:
        driver.get("https://accounts.google.com/")
        time.sleep(3)
        # accounts.google.com lists signed-in accounts as data-email attributes
        # and also in aria-labels; innerText is the most reliable fallback.
        emails = driver.execute_script("""
            const els = document.querySelectorAll('[data-email], [aria-label*="@"]');
            const found = new Set();
            els.forEach(el => {
                const e = el.getAttribute('data-email') || el.getAttribute('aria-label') || '';
                const m = e.match(/[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}/i);
                if (m) found.add(m[0].toLowerCase());
            });
            // Also scan body text as a fallback
            const body = document.body.innerText || '';
            const re = /[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}/gi;
            let m;
            while ((m = re.exec(body)) !== null) found.add(m[0].toLowerCase());
            return Array.from(found);
        """)
        return set(e.lower() for e in (emails or []))
    except Exception:
        return set()


def ensure_google_account(driver):
    """
    Verify the browser is signed into GOOGLE_ACCOUNT.
    If not, wait up to LOGIN_TIMEOUT seconds for the user to switch accounts.
    Returns True if the account is confirmed, False if timed out.
    """
    target = GOOGLE_ACCOUNT.lower()
    accounts = _google_active_accounts(driver)

    if target in accounts:
        _ok(f"Google account verified: {GOOGLE_ACCOUNT}")
        return True

    # Not signed in with the right account — tell the user and poll.
    if accounts:
        _warn(f"Signed in as: {', '.join(sorted(accounts))}")
    else:
        _warn("No Google account detected")

    print(f"\n  {_YELLOW}⚠{_RESET}  Please sign into {_BOLD}{GOOGLE_ACCOUNT}{_RESET} in the browser window.")
    print(f"       Go to accounts.google.com → Add account, then come back.")
    sys.stdout.flush()

    if sys.stdin.isatty():
        print(f"       Press Enter when done…")
        input()
        accounts = _google_active_accounts(driver)
        if target in accounts:
            _ok(f"Google account verified: {GOOGLE_ACCOUNT}")
            return True
        _err(f"Still not signed in as {GOOGLE_ACCOUNT} — aborting")
        return False

    # No TTY — poll until the account appears or timeout.
    deadline = time.time() + LOGIN_TIMEOUT
    while time.time() < deadline:
        time.sleep(4)
        remaining = int(deadline - time.time())
        sys.stdout.write(f"\r       Checking for {GOOGLE_ACCOUNT}… ({remaining}s remaining)   ")
        sys.stdout.flush()
        accounts = _google_active_accounts(driver)
        if target in accounts:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            _ok(f"Google account verified: {GOOGLE_ACCOUNT}")
            return True

    sys.stdout.write("\r" + " " * 60 + "\r")
    sys.stdout.flush()
    _err(f"Timed out waiting for {GOOGLE_ACCOUNT} — aborting scrape")
    return False


def wait_for_login(driver, url, check_fn, service_name):
    """Navigate to url; if check_fn(driver) is False, wait for the user to log in."""
    driver.get(url)
    time.sleep(3)
    if check_fn(driver):
        return True

    # Not logged in — wait for the user to log in via the visible browser window.
    if sys.stdin.isatty():
        print(f"\n  {_YELLOW}⚠{_RESET}  Please log into {_BOLD}{service_name}{_RESET} in the browser window.")
        print(f"       Press Enter here when done…")
        input()
        time.sleep(2)
        if not check_fn(driver):
            _warn(f"Still not logged into {service_name} — skipping")
            return False
        return True

    # No TTY (running from run-scraper.js) — poll until logged in or timeout.
    print(f"\n  {_YELLOW}⚠{_RESET}  {_BOLD}{service_name}{_RESET} needs login — waiting up to {LOGIN_TIMEOUT}s…")
    print(f"       Log in via the browser window that just opened.")
    sys.stdout.flush()
    deadline = time.time() + LOGIN_TIMEOUT
    interval = 3
    while time.time() < deadline:
        time.sleep(interval)
        remaining = int(deadline - time.time())
        sys.stdout.write(f"\r       Checking… ({remaining}s remaining)   ")
        sys.stdout.flush()
        if check_fn(driver):
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            _ok(f"Logged into {service_name}")
            return True
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()
    _err(f"Timed out waiting for {service_name} login — skipping")
    return False


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

    try:
        items = driver.execute_script("""
            const resp = await fetch(
                "/api/v1/planner/items?start_date=2026-01-01&end_date=2026-05-01&per_page=100"
            );
            if (!resp.ok) return [];
            return await resp.json();
        """)
    except JavascriptException as e:
        _err(f"Canvas API error: {e}")
        return []

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

        # Skip courses that use Gradescope instead of Canvas
        if course_key in ("stats250", "eecs442"):
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


def discover_canvas_course_ids(driver):
    """Fetch enrolled Canvas courses and map them to our config keys."""
    try:
        courses = driver.execute_script("""
            const all = [];
            let url = "/api/v1/courses?enrollment_state=active&per_page=100";
            while (url) {
                const resp = await fetch(url);
                if (!resp.ok) break;
                const data = await resp.json();
                all.push(...data);
                // Check for pagination
                const link = resp.headers.get("Link") || "";
                const next = link.match(/<([^>]+)>;\s*rel="next"/);
                url = next ? next[1] : null;
            }
            return all;
        """)
    except JavascriptException as e:
        _warn(f"Could not fetch Canvas courses: {e}")
        return {}

    discovered = dict(CANVAS_COURSE_IDS)  # start with known IDs
    for course in (courses or []):
        cname = (course.get("name") or "").lower()
        cid = str(course.get("id", ""))
        for pattern, key in CANVAS_COURSE_MAP.items():
            if pattern in cname and key not in discovered:
                discovered[key] = cid
                _info(f"Discovered Canvas course: {key} → {cid}")
    return discovered


def scrape_canvas_course_assignments(driver, course_key, course_id):
    """Fetch all assignments for a specific Canvas course via the API."""
    try:
        items = driver.execute_script("""
            const courseId = arguments[0];
            const all = [];
            let url = `/api/v1/courses/${courseId}/assignments?per_page=100&order_by=due_at`;
            while (url) {
                const resp = await fetch(url);
                if (!resp.ok) break;
                const data = await resp.json();
                all.push(...data);
                const link = resp.headers.get("Link") || "";
                const next = link.match(/<([^>]+)>;\s*rel="next"/);
                url = next ? next[1] : null;
            }
            return all;
        """, course_id)
    except JavascriptException as e:
        _warn(f"Canvas assignments API error for {course_key}: {e}")
        return []

    assignments = []
    for item in (items or []):
        name = item.get("name", "")
        due_at = item.get("due_at")
        if not name or not due_at:
            continue

        # Skip unpublished assignments
        if not item.get("published", True):
            continue

        try:
            dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        except ValueError:
            continue

        due_date = format_date_eastern(dt)
        due_time = format_time_eastern(dt)
        atype = guess_type(name, item.get("submission_types", [""])[0] if item.get("submission_types") else "")
        aid = generate_canvas_id(course_key, name, {"plannable": item})
        points = item.get("points_possible")

        assignments.append({
            "id": aid,
            "name": name,
            "course": course_key,
            "due": due_date,
            "time": due_time,
            "type": atype,
            "points": str(points) if points is not None else "—",
            "hours": guess_hours(atype),
            "specUrl": item.get("html_url", ""),
        })

    return assignments


def scrape_all_canvas_courses(driver):
    """Scrape assignments from all tracked Canvas courses."""
    # First, discover course IDs we don't already know
    course_ids = discover_canvas_course_ids(driver)

    all_assignments = []
    # Only scrape these courses from Canvas; others use Gradescope
    canvas_courses = ("eecs270", "eecs370", "tc300")
    for course_key in canvas_courses:
        cid = course_ids.get(course_key)
        if not cid:
            _warn(f"No Canvas course ID for {course_key}, skipping")
            continue

        _info(f"Fetching {course_key} (Canvas ID {cid})…")
        items = scrape_canvas_course_assignments(driver, course_key, cid)
        _info(f"  → {len(items)} assignments")
        all_assignments.extend(items)

    return all_assignments


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
    try:
        resp = requests.get(ICS_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        _warn(f"ICS feed error: {e}")
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

    return items


# ── Course website scraping ───────────────────────────────────────────

EECS270_URL = "https://www.eecs270.org/"
EECS370_URL = "https://eecs370.github.io/"


def scrape_eecs270_website(driver):
    """Scrape eecs270.org for projects, quizzes, exams with due dates."""
    driver.get(EECS270_URL)
    time.sleep(3)

    try:
        data = driver.execute_script(r"""
            const results = [];
            const seen = new Set();  // prevent duplicates within this scrape

            function addResult(item) {
                const key = item.id + '|' + item.date;
                if (seen.has(key)) return;
                seen.add(key);
                results.push(item);
            }

            // Date regex: matches "Mon Jan 13", "Thu Mar 25", "January 20, 2026",
            // "Mar 11", "1/13", etc. — broad enough to catch any date-like cell
            const dateRe = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*[,.\s]+(\w{3,9}\.?\s+\d{1,2})/i;
            const shortDateRe = /^(\w{3,9}\.?\s+\d{1,2})/i;
            const numDateRe = /^(\d{1,2})\/(\d{1,2})/;

            function extractDate(text) {
                text = (text || '').trim();
                // "Thu Jan 29" / "Monday March 25"
                let m = text.match(dateRe);
                if (m) return m[2].replace('.', '');
                // "Jan 29" / "March 25"
                m = text.match(shortDateRe);
                if (m && /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i.test(m[1])) return m[1].replace('.', '');
                return null;
            }

            // ── 1. Parse ALL tables on the page ──
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                const rows = table.querySelectorAll('tr');
                let currentDate = '';

                for (const row of rows) {
                    const cells = Array.from(row.querySelectorAll('td, th'));
                    if (cells.length < 1) continue;

                    // Try to extract a date from ANY cell in the row
                    for (const cell of cells) {
                        const d = extractDate(cell.textContent.trim());
                        if (d) { currentDate = d; break; }
                    }

                    // Now scan ALL cell text for assignment keywords
                    const rowText = cells.map(c => c.textContent.trim()).join(' | ');

                    // Quiz N (with optional topic in parens)
                    const quizMatches = rowText.matchAll(/Quiz\s*(\d+)(?:\s*[-:(]\s*([^)|]+))?/gi);
                    for (const qm of quizMatches) {
                        const num = qm[1];
                        const topic = qm[2] ? qm[2].trim() : '';
                        addResult({
                            name: topic ? `Quiz ${num} (${topic})` : `Quiz ${num}`,
                            type: 'quiz',
                            date: currentDate,
                            id: `270-q${num}`
                        });
                    }

                    // Exam N (but not "conflict" or "review")
                    const examMatches = rowText.matchAll(/Exam\s*(\d)\b/gi);
                    for (const em of examMatches) {
                        if (/conflict|review/i.test(rowText.substring(Math.max(0, em.index - 10), em.index + em[0].length + 20))) continue;
                        const timeMatch = rowText.match(/(\d{1,2}[:-]\d{2}\s*(pm|am|PM|AM))/);
                        addResult({
                            name: `Exam ${em[1]}`,
                            type: 'exam',
                            date: currentDate,
                            time: timeMatch ? timeMatch[1] : null,
                            id: `270-exam${em[1]}`
                        });
                    }

                    // Final Exam
                    if (/Final\s*Exam/i.test(rowText) && !/conflict/i.test(rowText)) {
                        const timeMatch = rowText.match(/(\d{1,2}[:-]\d{2}\s*(pm|am|PM|AM))/);
                        addResult({
                            name: 'Final Exam',
                            type: 'exam',
                            date: currentDate || rowText,
                            time: timeMatch ? timeMatch[1] : null,
                            id: '270-final'
                        });
                    }

                    // Project deadlines mentioned in schedule rows
                    // Matches: "P5 due", "Project 5 due", "P5", "Project 5 Signoff"
                    const projInRow = rowText.matchAll(/(?:Project|P)\s*(\d+)\s*([A-Za-z]*)/gi);
                    for (const pm of projInRow) {
                        const num = pm[1];
                        const suffix = (pm[2] || '').trim().toLowerCase();
                        // Skip if it's just a lecture topic mentioning a project
                        if (/lecture|topic|chapter|reading/i.test(rowText) && !/due|deadline|signoff|autograde/i.test(rowText)) continue;
                        if (/due|deadline|signoff|autograde|checkpoint/i.test(rowText) || /due|deadline/i.test(suffix)) {
                            let name = `Project ${num}`;
                            let idSuffix = '';
                            if (/signoff/i.test(suffix) || /signoff/i.test(rowText)) {
                                name += ' Signoff';
                                idSuffix = '-signoff';
                            } else if (/autograde/i.test(suffix) || /autograde/i.test(rowText)) {
                                name += ' Autograde';
                                idSuffix = '-auto';
                            } else if (/checkpoint/i.test(suffix) || /checkpoint/i.test(rowText)) {
                                name += ' Checkpoint';
                                idSuffix = '-cp';
                            }
                            addResult({
                                name: name,
                                type: 'project',
                                date: currentDate,
                                id: `270-p${num}${idSuffix}`
                            });
                        }
                    }

                    // Lab N
                    const labMatches = rowText.matchAll(/Lab\s*(\d+)/gi);
                    for (const lm of labMatches) {
                        // Skip if it's a column header or just "Lab" section label
                        if (/due|deadline|submit/i.test(rowText)) {
                            addResult({
                                name: `Lab ${lm[1]}`,
                                type: 'lab',
                                date: currentDate,
                                id: `270-lab${lm[1]}`
                            });
                        }
                    }

                    // Homework / HW N
                    const hwMatches = rowText.matchAll(/(?:Homework|HW)\s*(\d+)/gi);
                    for (const hm of hwMatches) {
                        if (/due|deadline|submit/i.test(rowText)) {
                            addResult({
                                name: `Homework ${hm[1]}`,
                                type: 'assignment',
                                date: currentDate,
                                id: `270-hw${hm[1]}`
                            });
                        }
                    }
                }
            }

            // ── 2. Project cards with due dates ──
            const headings = document.querySelectorAll('h1, h2, h3, h4, h5, [class*="card"] h2, [class*="card"] h3, [class*="card"] h4');
            headings.forEach(h => {
                const text = h.textContent.trim();
                const pm = text.match(/Project\s*(\d+)/i);
                if (!pm) return;
                const num = pm[1];

                // Search nearby elements and parent for a "Due" date
                let dueText = '';
                // Check siblings
                let el = h.nextElementSibling;
                for (let i = 0; i < 8 && el; i++) {
                    const t = el.textContent || '';
                    const dm = t.match(/Due[:\s]+([\w\s,]+\d{1,2}(?:[,\s]*\d{4})?)/i);
                    if (dm) { dueText = dm[1].trim(); break; }
                    el = el.nextElementSibling;
                }
                // Check parent container
                if (!dueText) {
                    const parent = h.closest('div, section, article, li');
                    if (parent) {
                        const dm = parent.textContent.match(/Due[:\s]+([\w\s,]+\d{1,2}(?:[,\s]*\d{4})?)/i);
                        if (dm) dueText = dm[1].trim();
                    }
                }
                // Check the heading text itself for inline dates
                if (!dueText) {
                    const dm = text.match(/Due[:\s]+([\w\s,]+\d{1,2})/i);
                    if (dm) dueText = dm[1].trim();
                }

                if (dueText) {
                    addResult({
                        name: text,
                        type: 'project',
                        date: dueText,
                        id: `270-p${num}`
                    });
                }
            });

            // ── 3. Scan all links and bold/strong text for deadlines ──
            const links = document.querySelectorAll('a, strong, b, em');
            links.forEach(el => {
                const text = el.textContent.trim();
                // "Quiz 15 due Jan 29" or similar inline mentions
                const qm = text.match(/Quiz\s*(\d+)/i);
                if (qm) {
                    const dateM = text.match(/(?:due|by)?\s*(\w{3,9}\.?\s+\d{1,2})/i);
                    if (dateM) {
                        addResult({
                            name: `Quiz ${qm[1]}`,
                            type: 'quiz',
                            date: dateM[1],
                            id: `270-q${qm[1]}`
                        });
                    }
                }
            });

            return results;
        """)
    except Exception as e:
        _warn(f"eecs270.org scrape error: {e}")
        return []

    # Convert to our assignment format
    assignments = []
    seen_ids = set()
    for item in (data or []):
        aid = item.get("id", "")
        if not aid or aid in seen_ids:
            continue
        seen_ids.add(aid)

        due_date = _parse_course_date(item.get("date", ""))
        if not due_date:
            continue

        assignments.append({
            "id": aid,
            "name": item["name"],
            "course": "eecs270",
            "due": due_date,
            "time": item.get("time"),
            "type": item.get("type", "assignment"),
            "points": "—",
            "hours": guess_hours(item.get("type", "assignment")),
        })

    return assignments


def scrape_eecs370_website(driver):
    """Scrape eecs370.github.io schedule table for projects, homeworks, exams."""
    driver.get(EECS370_URL)
    time.sleep(3)

    try:
        data = driver.execute_script("""
            const results = [];

            // Parse all tables — the schedule table has columns: Day, Lecture, Lab, Deadline, Readings
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                const headers = Array.from(table.querySelectorAll('th')).map(h => h.textContent.trim().toLowerCase());
                const dayIdx = headers.findIndex(h => h.includes('day'));
                const deadlineIdx = headers.findIndex(h => h.includes('deadline'));
                if (dayIdx === -1 || deadlineIdx === -1) continue;

                const rows = table.querySelectorAll('tbody tr, tr');
                let currentDate = '';
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length <= Math.max(dayIdx, deadlineIdx)) continue;

                    const dayText = cells[dayIdx]?.textContent?.trim() || '';
                    const deadlineText = cells[deadlineIdx]?.textContent?.trim() || '';

                    // Update current date
                    if (dayText && /\\w{3}\\s+\\w{3}\\s+\\d/.test(dayText)) {
                        currentDate = dayText;
                    }

                    if (!deadlineText || deadlineText === '-') continue;

                    // Parse deadline text: "P1a", "P2a", "HW 1", "P3 Checkpoint", etc.
                    // Project parts: P1a, P1s, P1m, P2a, P2l, P2r, P3, P4
                    const projMatch = deadlineText.match(/P(\\d)([a-z])?/g);
                    if (projMatch) {
                        projMatch.forEach(p => {
                            const m = p.match(/P(\\d)([a-z])?/);
                            if (m) {
                                const suffix = m[2] || '';
                                results.push({
                                    name: `Project ${m[1]}${suffix ? ' (' + suffix.toUpperCase() + ')' : ''}`,
                                    type: 'project',
                                    date: currentDate,
                                    id: `370-p${m[1]}${suffix}`
                                });
                            }
                        });
                    }

                    // Homework: "HW 1", "HW 2", etc.
                    const hwMatch = deadlineText.match(/HW\\s*(\\d+)/gi);
                    if (hwMatch) {
                        hwMatch.forEach(hw => {
                            const m = hw.match(/HW\\s*(\\d+)/i);
                            if (m) {
                                results.push({
                                    name: `Homework ${m[1]}`,
                                    type: 'homework',
                                    date: currentDate,
                                    id: `370-hw${m[1]}`
                                });
                            }
                        });
                    }

                    // Pre-Lab: "Pre-Lab N"
                    const plMatch = deadlineText.match(/Pre-?Lab\\s*(\\d+)/gi);
                    if (plMatch) {
                        plMatch.forEach(pl => {
                            const m = pl.match(/Pre-?Lab\\s*(\\d+)/i);
                            if (m) {
                                results.push({
                                    name: `Pre-Lab ${m[1]}`,
                                    type: 'prelab',
                                    date: currentDate,
                                    id: `370-pl${m[1]}`
                                });
                            }
                        });
                    }
                }
            }

            // Exam info section — look for Midterm and Final
            const body = document.body.innerText;

            const midMatch = body.match(/Midterm[:\\s]*.*?(\\w+day,?\\s+\\w+\\s+\\d{1,2}(?:th|st|nd|rd)?(?:,?\\s*\\d{4})?).*?(\\d{1,2}:\\d{2}\\s*(?:AM|PM))/i);
            if (midMatch) {
                results.push({
                    name: 'Midterm',
                    type: 'exam',
                    date: midMatch[1],
                    time: midMatch[2],
                    id: '370-midterm'
                });
            }

            const finalMatch = body.match(/Final[:\\s]*.*?(\\w+day,?\\s+\\w+\\s+\\d{1,2}(?:th|st|nd|rd)?(?:,?\\s*\\d{4})?).*?(\\d{1,2}:\\d{2}\\s*(?:AM|PM))/i);
            if (finalMatch) {
                results.push({
                    name: 'Final Exam',
                    type: 'exam',
                    date: finalMatch[1],
                    time: finalMatch[2],
                    id: '370-final'
                });
            }

            return results;
        """)
    except Exception as e:
        _warn(f"eecs370.github.io scrape error: {e}")
        return []

    # Convert to our assignment format
    assignments = []
    seen_ids = set()
    for item in (data or []):
        aid = item.get("id", "")
        if not aid or aid in seen_ids:
            continue
        seen_ids.add(aid)

        due_date = _parse_course_date(item.get("date", ""))
        if not due_date:
            continue

        assignments.append({
            "id": aid,
            "name": item["name"],
            "course": "eecs370",
            "due": due_date,
            "time": item.get("time"),
            "type": item.get("type", "assignment"),
            "points": "—",
            "hours": guess_hours(item.get("type", "assignment")),
        })

    return assignments


def _parse_course_date(text):
    """Parse dates from course websites like 'Thu Jan 29', 'January 20, 2026', 'Mar 11'."""
    if not text:
        return None

    text = text.strip()
    # Remove ordinal suffixes (1st, 2nd, 3rd, 23th, etc.)
    text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)
    # Remove leading day-of-week (Thu, Monday, etc.)
    text = re.sub(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*[,\s]+', '', text, flags=re.IGNORECASE)

    # Try common date formats
    for fmt in [
        "%B %d, %Y",   # January 20, 2026
        "%B %d %Y",    # January 20 2026
        "%b %d, %Y",   # Jan 20, 2026
        "%b %d %Y",    # Jan 20 2026
        "%B %d",        # January 20
        "%b %d",        # Jan 20
    ]:
        try:
            dt = datetime.strptime(text.strip(), fmt)
            # Default to 2026 if no year
            if dt.year == 1900:
                dt = dt.replace(year=2026)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


# ── Gradescope scraping ───────────────────────────────────────────────

def scrape_gradescope(driver, course_url_id, course_key, label):
    """Scrape assignments from a Gradescope course page."""
    url = f"https://www.gradescope.com/courses/{course_url_id}"
    driver.get(url)
    time.sleep(3)

    # Check if logged in — reuse wait_for_login's polling logic
    if "login" in driver.current_url.lower() or "sessions" in driver.current_url.lower():
        logged_in = wait_for_login(
            driver, url,
            lambda d: "login" not in d.current_url.lower() and "sessions" not in d.current_url.lower(),
            "Gradescope"
        )
        if not logged_in:
            return [], []
        time.sleep(2)

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
        _warn(f"Gradescope JS error for {label}: {e}")
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

def _normalize_name(name):
    """Normalize an assignment name for fuzzy matching."""
    return re.sub(r'[^a-z0-9]+', '', name.lower())


def merge_assignments(existing, new_items, auto_completed):
    """
    Merge new scraped assignments into the existing list.
    - Deduplicates new_items from multiple sources before merging.
    - Skips items that match existing ones by ID OR by similar name+course.
    - Updates due dates/times only if they've changed.
    - Adds past-due submitted items to autoCompleted.
    Returns (merged_assignments, updated_autoCompleted, changes_log).
    """
    existing_by_id = {a["id"]: a for a in existing}
    # Build a name lookup: "course::normalized_name" → id for fuzzy matching
    existing_by_name = {}
    for a in existing:
        key = f"{a['course']}::{_normalize_name(a['name'])}"
        existing_by_name[key] = a["id"]

    changes = []

    # Step 1: Deduplicate new_items themselves (multiple sources may produce the same item)
    deduped = {}
    for item in new_items:
        aid = item["id"]
        if aid not in deduped:
            deduped[aid] = item
    new_items = list(deduped.values())

    # Step 2: Merge into existing
    for item in new_items:
        aid = item["id"]
        name_key = f"{item['course']}::{_normalize_name(item['name'])}"

        # Check exact ID match
        if aid in existing_by_id:
            old = existing_by_id[aid]
            if old["due"] != item["due"]:
                changes.append(f"  UPDATED {aid}: due {old['due']} → {item['due']}")
                old["due"] = item["due"]
            if old.get("time") != item.get("time") and item.get("time"):
                changes.append(f"  UPDATED {aid}: time {old.get('time')} → {item['time']}")
                old["time"] = item["time"]
            continue

        # Check fuzzy name match (same course + same normalized name → skip as duplicate)
        if name_key in existing_by_name:
            continue  # Already exists under a different ID

        # New assignment — insert after last assignment of same course & type
        insert_idx = len(existing)
        for i, a in enumerate(existing):
            if a["course"] == item["course"] and a.get("type") == item.get("type"):
                insert_idx = i + 1
        existing.insert(insert_idx, item)
        existing_by_id[aid] = item
        existing_by_name[name_key] = aid
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
        _err(f"Validation failed:\n{result.stderr}")
        return False
    return True


# ── Git push ──────────────────────────────────────────────────────────

def git_push():
    """Commit and push config.js via a clean /tmp clone (avoids FUSE issues)."""
    tmp_dir = "/tmp/ac-push"
    try:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        subprocess.run(
            ["git", "clone", REPO_URL, tmp_dir],
            check=True, capture_output=True, text=True
        )

        # Copy updated config.js and data.json
        shutil.copy2(CONFIG_PATH, os.path.join(tmp_dir, "config.js"))
        shutil.copy2(DATA_JSON_PATH, os.path.join(tmp_dir, "data.json"))

        # Check if there's actually a diff
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=tmp_dir, capture_output=True, text=True
        )
        if not result.stdout.strip():
            return False

        # Configure git and commit
        date_str = datetime.now().strftime("%Y-%m-%d")
        cmds = [
            ["git", "config", "user.email", "akchavan@umich.edu"],
            ["git", "config", "user.name", "Arjun Chavan"],
            ["git", "add", "config.js", "data.json"],
        ]
        for cmd in cmds:
            subprocess.run(cmd, cwd=tmp_dir, check=True, capture_output=True)

        # Commit
        msg = f"chore: scrape {date_str} — update assignments + autoCompleted"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=tmp_dir, check=True, capture_output=True, text=True
        )

        subprocess.run(
            ["git", "push"],
            cwd=tmp_dir, check=True, capture_output=True, text=True
        )
        return True

    except subprocess.CalledProcessError as e:
        _err(f"Git error: {e.stderr}")
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
    parser.add_argument("--skip-websites", action="store_true", help="Skip course websites (eecs270.org, eecs370.github.io)")
    parser.add_argument("--skip-gradescope", action="store_true", help="Skip Gradescope scraping")
    parser.add_argument("--skip-ics", action="store_true", help="Skip ICS feed")
    args = parser.parse_args()

    print(f"\n{_BOLD}{'═' * 48}{_RESET}")
    print(f"  {_BOLD}Assignment Scraper{_RESET}  {_GRAY}{TODAY}{_RESET}")
    if args.dry_run:
        print(f"  {_YELLOW}DRY RUN — no files will be modified{_RESET}")
    print(f"{_BOLD}{'═' * 48}{_RESET}")

    # 1. Parse current config
    _step_header(1, "Reading config.js")
    with Spinner("Parsing config…"):
        assignments, auto_completed, raw_text = parse_config()
    _ok(f"{len(assignments)} assignments · {len(auto_completed)} auto-completed")

    all_new = []
    all_submitted = []
    driver = None

    try:
        # 2. Canvas ICS feed (no browser needed)
        if not args.skip_ics:
            _step_header(2, "Fetching Canvas ICS feed")
            with Spinner("Downloading ICS…"):
                ics_events = fetch_canvas_ics()
            _ok(f"{len(ics_events)} calendar events fetched")
        else:
            _step_header(2, "Canvas ICS feed")
            _info("Skipped (--skip-ics)")

        # 3. Set up browser and verify Google account
        needs_browser = not (args.skip_canvas and args.skip_gradescope)
        if needs_browser:
            _step_header(3, "Starting Chrome · verifying Google account")
            with Spinner("Launching browser" + (" (headless)" if args.headless else " — check your screen")):
                driver = make_driver(headless=args.headless)
            _ok("Browser ready")
            if not ensure_google_account(driver):
                return  # wrong/missing account and timed out
        else:
            _step_header(3, "Chrome")
            _info("Skipped (canvas + gradescope both skipped)")

        # 4. Canvas course assignments + planner API
        if not args.skip_canvas and driver:
            _step_header(4, "Canvas course assignments")
            with Spinner("Fetching per-course assignments…"):
                course_assignments = scrape_all_canvas_courses(driver)
            all_new.extend(course_assignments)
            _ok(f"{len(course_assignments)} assignments from Canvas courses")

            # Also fetch planner items (catches announcements/pages the assignments API misses)
            with Spinner("Fetching planner items…"):
                canvas_items = scrape_canvas_planner(driver)
            parsed = parse_canvas_items(canvas_items)
            all_new.extend(parsed)
            _ok(f"{len(canvas_items)} planner items → {len(parsed)} additional")
        else:
            _step_header(4, "Canvas")
            _info("Skipped (--skip-canvas)")

        # 5. EECS 270 course website
        if not args.skip_websites and driver:
            _step_header(5, "EECS 270 website (eecs270.org)")
            with Spinner("Scraping eecs270.org…"):
                eecs270_items = scrape_eecs270_website(driver)
            all_new.extend(eecs270_items)
            _ok(f"{len(eecs270_items)} assignments from eecs270.org")
        else:
            _step_header(5, "EECS 270 website")
            _info("Skipped (--skip-websites)")

        # 6. EECS 370 course website
        if not args.skip_websites and driver:
            _step_header(6, "EECS 370 website (eecs370.github.io)")
            with Spinner("Scraping eecs370.github.io…"):
                eecs370_items = scrape_eecs370_website(driver)
            all_new.extend(eecs370_items)
            _ok(f"{len(eecs370_items)} assignments from eecs370.github.io")
        else:
            _step_header(6, "EECS 370 website")
            _info("Skipped (--skip-websites)")

        # 7. Gradescope
        if not args.skip_gradescope and driver:
            _step_header(7, "Gradescope")
            total_gs = 0
            for course_key, courses in GRADESCOPE_COURSES.items():
                for course_info in courses:
                    with Spinner(f"Scraping {course_info['label']}…"):
                        gs_assignments, gs_submitted = scrape_gradescope(
                            driver, course_info["url_id"], course_key, course_info["label"]
                        )
                    all_new.extend(gs_assignments)
                    all_submitted.extend(gs_submitted)
                    total_gs += len(gs_assignments)
                    _ok(f"{course_info['label']}: {len(gs_assignments)} assignments"
                        + (f" · {len(gs_submitted)} submitted" if gs_submitted else ""))
        else:
            _step_header(7, "Gradescope")
            _info("Skipped (--skip-gradescope)")

    finally:
        if driver:
            driver.quit()

    # 8. Merge
    _step_header(8, "Merging assignments")
    submitted_set = set(all_submitted)
    for item in all_new:
        if item["id"] in submitted_set:
            item["_submitted"] = True

    merged, updated_ac, changes = merge_assignments(assignments, all_new, auto_completed)

    added   = [c for c in changes if c.strip().startswith("ADDED")]
    updated = [c for c in changes if c.strip().startswith("UPDATED")]
    autocmp = [c for c in changes if c.strip().startswith("AUTO-COMPLETED")]

    if not changes:
        _ok("No changes detected — config is already up to date")
        if not args.dry_run:
            with Spinner("Updating scrape date…"):
                write_config(raw_text, merged, updated_ac)
            if validate_config() and not args.no_push:
                _step_header(11, "Pushing to GitHub")
                with Spinner("Pushing…"):
                    git_push()
        _print_done(0, 0, 0)
        return

    _ok(f"{len(added)} added · {len(updated)} updated · {len(autocmp)} auto-completed")
    for c in added:
        _info(c.strip())
    for c in updated:
        _info(c.strip())
    for c in autocmp:
        _info(c.strip())

    if args.dry_run:
        print(f"\n  {_YELLOW}Dry run complete — no files modified.{_RESET}")
        _print_done(len(added), len(updated), len(autocmp))
        return

    # 9. Write config.js + data.json
    _step_header(9, "Writing config.js + data.json")
    with Spinner("Saving…"):
        write_config(raw_text, merged, updated_ac)
        write_data_json(merged, updated_ac)
    _ok(f"Saved → {CONFIG_PATH}")
    _ok(f"Saved → {DATA_JSON_PATH}")

    # 10. Validate
    _step_header(10, "Validating config.js")
    with Spinner("Checking syntax…"):
        valid = validate_config()
    if not valid:
        _err("Validation failed — aborting")
        return
    _ok(f"{len(merged)} assignments · syntax OK")

    # 11. Push
    _step_header(11, "Pushing to GitHub")
    if args.no_push:
        _info("Skipped (--no-push)")
    else:
        with Spinner("Cloning & pushing…"):
            pushed = git_push()
        if pushed:
            _ok("Pushed to GitHub")
        else:
            _warn("Nothing to push or push failed")

    _print_done(len(added), len(updated), len(autocmp))


def _print_done(added, updated, autocompleted):
    print(f"\n{_BOLD}{'─' * 48}{_RESET}")
    print(f"  {_GREEN}{_BOLD}Done!{_RESET}  "
          f"{_GREEN}+{added} added{_RESET}  "
          f"{_YELLOW}~{updated} updated{_RESET}  "
          f"{_GRAY}✓{autocompleted} auto-completed{_RESET}")
    print(f"{_BOLD}{'─' * 48}{_RESET}\n")


if __name__ == "__main__":
    main()
