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

CHROME_DEBUG_PORT = 9222


def make_driver(headless=False):
    """
    Connect to an already-running Chrome (via remote debugging) if available,
    so existing sessions and cookies are reused with no login required.
    Falls back to launching a new Chrome with a persistent profile.
    """
    # Try attaching to the user's existing Chrome first
    try:
        opts = ChromeOptions()
        opts.debugger_address = f"127.0.0.1:{CHROME_DEBUG_PORT}"
        driver = webdriver.Chrome(options=opts)
        driver.implicitly_wait(5)
        _ok(f"Attached to existing Chrome on port {CHROME_DEBUG_PORT} — using your saved sessions")
        return driver
    except Exception as e:
        _warn(f"Could not attach to existing Chrome (port {CHROME_DEBUG_PORT}): {e}")
        _warn("Falling back to a fresh Chrome profile — you may need to log in")
        _info(f"To fix: quit Chrome, then run: chrome")
        _info(f"Then verify with: curl http://localhost:{CHROME_DEBUG_PORT}/json/version")

    # Fall back: launch a new Chrome with a persistent profile
    _info("Launching new Chrome instance with saved profile…")
    opts = ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    if headless:
        opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(5)
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
        data = driver.execute_script("""
            const results = [];

            // 1. Project cards — look for elements with "Due" dates
            //    Cards have headings like "Project N: Name" and a red badge with "Due: Date"
            const allText = document.body.innerText;

            // 2. Parse schedule table for quizzes, labs, exams, and project deadlines
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                const rows = table.querySelectorAll('tr');
                let currentDate = '';
                for (const row of rows) {
                    const cells = row.querySelectorAll('td, th');
                    if (cells.length < 2) continue;

                    // First cell is often the date
                    const dateCell = cells[0]?.textContent?.trim();
                    if (dateCell && /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Jan|Feb|Mar|Apr|May|\\d)/.test(dateCell)) {
                        currentDate = dateCell;
                    }

                    // Scan all cells for assignment names
                    for (const cell of cells) {
                        const text = cell.textContent.trim();

                        // Quiz N
                        const qm = text.match(/Quiz\\s*(\\d+)/i);
                        if (qm) {
                            results.push({
                                name: `Quiz ${qm[1]}`,
                                type: 'quiz',
                                date: currentDate,
                                id: `270-q${qm[1]}`
                            });
                        }

                        // Exam
                        if (/Exam\\s*\\d/i.test(text) && !/conflict/i.test(text)) {
                            const em = text.match(/Exam\\s*(\\d)/i);
                            if (em) {
                                // Extract time if present
                                const timeMatch = text.match(/(\\d{1,2}[:-]\\d{2}\\s*(pm|am|PM|AM))/);
                                results.push({
                                    name: `Exam ${em[1]}`,
                                    type: 'exam',
                                    date: currentDate,
                                    time: timeMatch ? timeMatch[1] : null,
                                    id: `270-exam${em[1]}`
                                });
                            }
                        }

                        // Final Exam
                        if (/Final\\s*Exam/i.test(text)) {
                            const timeMatch = text.match(/(\\d{1,2}[:-]\\d{2}\\s*(pm|am|PM|AM))/);
                            results.push({
                                name: 'Final Exam',
                                type: 'exam',
                                date: currentDate || text,
                                time: timeMatch ? timeMatch[1] : null,
                                id: '270-final'
                            });
                        }
                    }
                }
            }

            // 3. Project cards with due dates
            //    Look for headings + due dates in cards/sections
            const headings = document.querySelectorAll('h2, h3, h4, [class*="card"] h2, [class*="card"] h3');
            headings.forEach(h => {
                const text = h.textContent.trim();
                const pm = text.match(/Project\\s*(\\d+)/i);
                if (pm) {
                    // Look for a "Due" date near this heading
                    let dueText = '';
                    let el = h.nextElementSibling || h.parentElement;
                    // Search siblings and parent for due date text
                    for (let i = 0; i < 5 && el; i++) {
                        const t = el.textContent || '';
                        const dm = t.match(/Due[:\\s]+(\\w+ \\d{1,2}(?:,?\\s*\\d{4})?)/i);
                        if (dm) { dueText = dm[1]; break; }
                        el = el.nextElementSibling;
                    }
                    // Also check parent container
                    if (!dueText) {
                        const parent = h.closest('div, section, article');
                        if (parent) {
                            const dm = parent.textContent.match(/Due[:\\s]+(\\w+ \\d{1,2}(?:,?\\s*\\d{4})?)/i);
                            if (dm) dueText = dm[1];
                        }
                    }
                    results.push({
                        name: text,
                        type: 'project',
                        date: dueText,
                        id: `270-p${pm[1]}`
                    });
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

        # Copy updated config.js
        shutil.copy2(CONFIG_PATH, os.path.join(tmp_dir, "config.js"))

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
            ["git", "add", "config.js"],
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

        # 4. Canvas planner API
        if not args.skip_canvas and driver:
            _step_header(4, "Canvas planner API")
            with Spinner("Fetching planner items…"):
                canvas_items = scrape_canvas_planner(driver)
            parsed = parse_canvas_items(canvas_items)
            all_new.extend(parsed)
            _ok(f"{len(canvas_items)} planner items → {len(parsed)} relevant assignments")
        else:
            _step_header(4, "Canvas planner")
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

    # 9. Write config.js
    _step_header(9, "Writing config.js")
    with Spinner("Saving…"):
        write_config(raw_text, merged, updated_ac)
    _ok(f"Saved → {CONFIG_PATH}")

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
