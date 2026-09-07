// ============================================================
// ASSIGNMENT CALENDAR — USER CONFIGURATION
// ============================================================
// Edit this file to customize the calendar for your courses.
// A friend can copy index.html + config.js, edit this file,
// and deploy their own version with their own Firebase.
// ============================================================

const APP_CONFIG = {

  // ---- Display Settings ----
  title: "Arjun's Assignment Calendar",
  subtitle: "EECS 367 · EECS 373 · EECS 445 · CLCIV 371 — Fall 2026",

  // When the assignment data was last scraped (shown in footer — auto-updated by scrape task)
  scrapeDate: "September 6, 2026",

  // ---- Firebase (each user needs their own project) ----
  // 1. Go to console.firebase.google.com
  // 2. Create a project → Add a web app → Copy config here
  // 3. Enable Realtime Database (test mode is fine for personal use)
  firebase: {
    apiKey: "AIzaSyCUzvAHBOMLRtrrl5uTIMe6f9sGkubTtWY",
    authDomain: "arjun-calendar-6eefc.firebaseapp.com",
    databaseURL: "https://arjun-calendar-6eefc-default-rtdb.firebaseio.com",
    projectId: "arjun-calendar-6eefc",
    storageBucket: "arjun-calendar-6eefc.firebasestorage.app",
    messagingSenderId: "889449529154",
    appId: "1:889449529154:web:30c71c415b277d31d992db"
  },

  // ---- Courses ----
  // Each key is a course ID used in assignments below.
  // Colors are CSS hex values for light and dark themes.
  // Colors mirror the Google Calendar colorIds used for the class events:
  // 367 Sage · 373 Flamingo · 445 Blueberry · CLCIV 371 Grape
  courses: {
    eecs367: {
      name: "EECS 367",
      color: "#16a34a", bg: "#dcfce7",
      darkColor: "#4ade80", darkBg: "#14532d",
      platform: "autorob.org",
      platformUrl: "https://autorob.org/"
    },
    eecs373: {
      name: "EECS 373",
      color: "#e11d48", bg: "#ffe4e6",
      darkColor: "#fb7185", darkBg: "#4c0519",
      platform: "eecs373",
      platformUrl: "https://www.eecs.umich.edu/courses/eecs373/index.html"
    },
    eecs445: {
      name: "EECS 445",
      color: "#2563eb", bg: "#dbeafe",
      darkColor: "#60a5fa", darkBg: "#1e3a5f",
      platform: "gradescope",
      platformUrl: "https://www.gradescope.com/"
    },
    clciv371: {
      name: "CLCIV 371",
      color: "#7c3aed", bg: "#ede9fe",
      darkColor: "#a78bfa", darkBg: "#2e1f5e",
      platform: "canvas",
      platformUrl: "https://umich.instructure.com/"
    }
  },

  // ---- Assignments ----
  // Each assignment needs: id, name, course (must match a key above),
  // due (YYYY-MM-DD), time (string or null), type, points, hours
  // Populated by scrape_assignments.py — empty until the first Fall 2026 scrape.
  assignments: [
  ],

  autoCompleted: [
  ]
};
