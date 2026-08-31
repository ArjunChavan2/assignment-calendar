#!/usr/bin/env node
// ============================================================
// GOOGLE CALENDAR EXPORT
// ============================================================
// Turns APP_CONFIG.assignments in config.js into calendar events.
//
//   node gcal-export.js            → writes calendar.ics + gcal-events.json
//   node gcal-export.js --json     → prints the event list as JSON (for syncing)
//   node gcal-export.js --from 2026-01-01 --to 2026-05-01
//   node gcal-export.js --work-blocks     → also emit workPlan study blocks
//   node gcal-export.js --include-past    → also emit deadlines already passed
//
// By default only deadlines from today onward are emitted. config.js keeps the
// whole term's history, but a calendar feed should not backfill a finished term
// into someone's calendar every time they subscribe.
//
// calendar.ics is committed and served by GitHub Pages, so Google Calendar
// can subscribe to it by URL and pick up every scrape automatically.
// ============================================================

const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const TZID = 'America/Detroit';

// DST for 2026: EDT (UTC-4) from Mar 8 2:00 AM to Nov 1 2:00 AM, EST (UTC-5) otherwise.
// Matches the constants in scrape_assignments.py.
function utcOffset(dateStr) {
  const d = new Date(`${dateStr}T12:00:00Z`);
  const dstStart = new Date('2026-03-08T07:00:00Z');
  const dstEnd = new Date('2026-11-01T06:00:00Z');
  return d >= dstStart && d < dstEnd ? '-04:00' : '-05:00';
}

// Google Calendar colorIds chosen to match the recurring class events
// already on the School Schedule calendar.
const COURSE_COLOR = {
  eecs270: '4',   // Flamingo
  eecs370: '2',   // Sage
  eecs442: '9',   // Blueberry
  stats250: '5',  // Banana
  tc300: '3'      // Grape
};

const TYPE_LABEL = {
  project: 'Project',
  quiz: 'Quiz',
  exam: 'Exam',
  homework: 'Homework',
  prelab: 'Pre-lab',
  assignment: 'Assignment',
  ep: 'Engagement Point',
  lab: 'Lab',
  casestudy: 'Case Study',
  lecture: 'Lecture Prep'
};

// How long the calendar block should be, in minutes, by type.
const TYPE_DURATION = { exam: 120, lab: 60, lecture: 30 };
const DEFAULT_DURATION = 30;

function loadConfig() {
  const src = fs.readFileSync(path.join(ROOT, 'config.js'), 'utf8');
  const sandbox = {};
  new Function('global', src + '\nglobal.APP_CONFIG = APP_CONFIG;')(sandbox);
  return sandbox.APP_CONFIG;
}

function parseTime(t) {
  if (!t) return null;
  const m = String(t).trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!m) return null;
  let h = parseInt(m[1], 10);
  const min = parseInt(m[2], 10);
  const ap = m[3].toUpperCase();
  if (ap === 'PM' && h !== 12) h += 12;
  if (ap === 'AM' && h === 12) h = 0;
  return { h, min };
}

function addMinutes(dateStr, { h, min }, delta) {
  const d = new Date(Date.UTC(
    +dateStr.slice(0, 4), +dateStr.slice(5, 7) - 1, +dateStr.slice(8, 10), h, min
  ));
  d.setUTCMinutes(d.getUTCMinutes() + delta);
  const p = (n) => String(n).padStart(2, '0');
  return {
    date: `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`,
    time: `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:00`
  };
}

function nextDay(dateStr) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function buildDescription(a, cfg) {
  const lines = [];
  const label = TYPE_LABEL[a.type] || a.type;
  lines.push(`${cfg.courses[a.course]?.name || a.course} — ${label}`);
  if (a.points && a.points !== '-') lines.push(`Points: ${a.points}`);
  if (a.hours) lines.push(`Estimated work: ${a.hours}h`);
  if (a.specUrl) lines.push(`Spec: ${a.specUrl}`);
  const platformUrl = cfg.courses[a.course]?.platformUrl;
  if (platformUrl) lines.push(`Course site: ${platformUrl}`);
  if (Array.isArray(a.workPlan) && a.workPlan.length) {
    lines.push('', 'Work plan:');
    a.workPlan.forEach((w) => lines.push(`  ${w.date} (${w.hours}h) — ${w.task}`));
  }
  lines.push('', `Synced from assignment-calendar [${a.id}]`);
  return lines.join('\n');
}

function buildEvents(cfg, opts) {
  const done = new Set(cfg.autoCompleted || []);
  const events = [];

  for (const a of cfg.assignments) {
    if (!a.due) continue;
    if (opts.from && a.due < opts.from) continue;
    if (opts.to && a.due > opts.to) continue;
    if (!opts.includePast && !opts.from && a.due < opts.today) continue;

    const courseName = cfg.courses[a.course]?.name || a.course;
    const time = parseTime(a.time);
    const duration = TYPE_DURATION[a.type] || DEFAULT_DURATION;

    const ev = {
      uid: `assignment-${a.id}@assignment-calendar`,
      syncId: a.id,
      summary: `${courseName}: ${a.name}`,
      description: buildDescription(a, cfg),
      colorId: COURSE_COLOR[a.course],
      course: a.course,
      type: a.type,
      completed: done.has(a.id)
    };

    if (time) {
      // Block ends at the deadline so the deadline is the edge of the event.
      const start = addMinutes(a.due, time, -duration);
      ev.allDay = false;
      ev.start = `${start.date}T${start.time}${utcOffset(start.date)}`;
      const p = (n) => String(n).padStart(2, '0');
      ev.end = `${a.due}T${p(time.h)}:${p(time.min)}:00${utcOffset(a.due)}`;
      // Exams block time; everything else is a deadline marker.
      ev.availability = a.type === 'exam' ? 'AVAILABILITY_BUSY' : 'AVAILABILITY_FREE';
      ev.reminders = a.type === 'exam'
        ? [{ method: 'popup', minutes: 1440 }, { method: 'popup', minutes: 60 }]
        : [{ method: 'popup', minutes: 1440 }, { method: 'popup', minutes: 120 }];
    } else {
      ev.allDay = true;
      ev.start = a.due;
      ev.end = nextDay(a.due);
      ev.availability = 'AVAILABILITY_FREE';
      ev.reminders = [{ method: 'popup', minutes: 1440 }];
    }
    events.push(ev);

    if (opts.workBlocks && Array.isArray(a.workPlan)) {
      a.workPlan.forEach((w, i) => {
        if (opts.from && w.date < opts.from) return;
        if (opts.to && w.date > opts.to) return;
        if (!opts.includePast && !opts.from && w.date < opts.today) return;
        events.push({
          uid: `workplan-${a.id}-${i}@assignment-calendar`,
          syncId: `${a.id}#work${i}`,
          summary: `Work: ${courseName} ${a.name}`,
          description: `${w.task}\n\nPlanned: ${w.hours}h\n\nSynced from assignment-calendar [${a.id}]`,
          colorId: COURSE_COLOR[a.course],
          course: a.course,
          type: 'workblock',
          allDay: true,
          start: w.date,
          end: nextDay(w.date),
          availability: 'AVAILABILITY_FREE',
          reminders: [],
          completed: done.has(a.id)
        });
      });
    }
  }

  events.sort((x, y) => String(x.start).localeCompare(String(y.start)));
  return events;
}

// ---- ICS output ----

function icsEscape(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
}

function fold(line) {
  // RFC 5545: octet-based 75-char folding.
  const bytes = Buffer.from(line, 'utf8');
  if (bytes.length <= 75) return line;
  const out = [];
  let i = 0;
  while (i < bytes.length) {
    const take = out.length === 0 ? 75 : 74;
    let end = Math.min(i + take, bytes.length);
    // Don't split a multi-byte UTF-8 sequence.
    while (end > i && end < bytes.length && (bytes[end] & 0xc0) === 0x80) end--;
    out.push((out.length ? ' ' : '') + bytes.slice(i, end).toString('utf8'));
    i = end;
  }
  return out.join('\r\n');
}

const VTIMEZONE = [
  'BEGIN:VTIMEZONE',
  `TZID:${TZID}`,
  'X-LIC-LOCATION:America/Detroit',
  'BEGIN:DAYLIGHT',
  'TZOFFSETFROM:-0500',
  'TZOFFSETTO:-0400',
  'TZNAME:EDT',
  'DTSTART:19700308T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU',
  'END:DAYLIGHT',
  'BEGIN:STANDARD',
  'TZOFFSETFROM:-0400',
  'TZOFFSETTO:-0500',
  'TZNAME:EST',
  'DTSTART:19701101T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU',
  'END:STANDARD',
  'END:VTIMEZONE'
];

function toIcs(events, cfg) {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//assignment-calendar//gcal-export//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:${icsEscape(cfg.title || 'Assignments')}`,
    `X-WR-CALDESC:${icsEscape(cfg.subtitle || '')}`,
    `X-WR-TIMEZONE:${TZID}`,
    'REFRESH-INTERVAL;VALUE=DURATION:PT6H',
    'X-PUBLISHED-TTL:PT6H',
    ...VTIMEZONE
  ];

  for (const ev of events) {
    lines.push('BEGIN:VEVENT');
    lines.push(`UID:${ev.uid}`);
    lines.push(`DTSTAMP:${stamp}`);
    if (ev.allDay) {
      lines.push(`DTSTART;VALUE=DATE:${ev.start.replace(/-/g, '')}`);
      lines.push(`DTEND;VALUE=DATE:${ev.end.replace(/-/g, '')}`);
    } else {
      const strip = (s) => s.slice(0, 19).replace(/[-:]/g, '');
      lines.push(`DTSTART;TZID=${TZID}:${strip(ev.start)}`);
      lines.push(`DTEND;TZID=${TZID}:${strip(ev.end)}`);
    }
    lines.push(`SUMMARY:${icsEscape((ev.completed ? '✓ ' : '') + ev.summary)}`);
    lines.push(`DESCRIPTION:${icsEscape(ev.description)}`);
    lines.push(`TRANSP:${ev.availability === 'AVAILABILITY_BUSY' ? 'OPAQUE' : 'TRANSPARENT'}`);
    lines.push(`CATEGORIES:${icsEscape(ev.course)},${icsEscape(ev.type)}`);
    if (ev.completed) lines.push('STATUS:CONFIRMED');
    for (const r of ev.reminders || []) {
      lines.push('BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${icsEscape(ev.summary)}`,
        `TRIGGER:-PT${r.minutes}M`, 'END:VALARM');
    }
    lines.push('END:VEVENT');
  }

  lines.push('END:VCALENDAR');
  return lines.map(fold).join('\r\n') + '\r\n';
}

// ---- main ----

function main() {
  const argv = process.argv.slice(2);
  const arg = (name) => {
    const i = argv.indexOf(name);
    return i === -1 ? null : argv[i + 1];
  };
  const opts = {
    from: arg('--from'),
    to: arg('--to'),
    workBlocks: argv.includes('--work-blocks'),
    includePast: argv.includes('--include-past'),
    today: new Date().toISOString().slice(0, 10)
  };

  const cfg = loadConfig();
  const events = buildEvents(cfg, opts);

  if (argv.includes('--json')) {
    process.stdout.write(JSON.stringify(events, null, 2));
    return;
  }

  fs.writeFileSync(path.join(ROOT, 'calendar.ics'), toIcs(events, cfg));
  fs.writeFileSync(path.join(ROOT, 'gcal-events.json'), JSON.stringify(events, null, 2) + '\n');
  const byCourse = {};
  events.forEach((e) => { byCourse[e.course] = (byCourse[e.course] || 0) + 1; });
  const total = cfg.assignments.filter((a) => a.due).length;
  const skipped = total - events.filter((e) => e.type !== 'workblock').length;
  console.error(`Wrote calendar.ics and gcal-events.json — ${events.length} events`);
  if (skipped > 0 && !opts.includePast && !opts.from) {
    console.error(`  (${skipped} past deadlines skipped — use --include-past to keep them)`);
  }
  Object.entries(byCourse).sort().forEach(([c, n]) => console.error(`  ${c.padEnd(10)} ${n}`));
}

main();
