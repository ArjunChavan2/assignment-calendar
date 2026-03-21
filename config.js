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
  subtitle: "EECS 270 · EECS 370 · EECS 442 · STATS 250 · TCHNCLCM 300 — Winter 2026",

  // When the assignment data was last scraped (shown in footer — auto-updated by scrape task)
  scrapeDate: "March 21, 2026",

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
  courses: {
    eecs270: {
      name: "EECS 270",
      color: "#2563eb", bg: "#dbeafe",
      darkColor: "#60a5fa", darkBg: "#1e3a5f",
      platform: "eecs270.org",
      platformUrl: "https://www.eecs270.org/"
    },
    eecs370: {
      name: "EECS 370",
      color: "#db2777", bg: "#fce7f3",
      darkColor: "#f9a8d4", darkBg: "#500724",
      platform: "eecs370.github.io",
      platformUrl: "https://eecs370.github.io/"
    },
    eecs442: {
      name: "EECS 442",
      color: "#7c3aed", bg: "#ede9fe",
      darkColor: "#a78bfa", darkBg: "#2e1f5e",
      platform: "gradescope",
      platformUrl: "https://www.gradescope.com/"
    },
    stats250: {
      name: "STATS 250",
      color: "#ea580c", bg: "#fff7ed",
      darkColor: "#fb923c", darkBg: "#431a04",
      platform: "gradescope",
      platformUrl: "https://www.gradescope.com/"
    },
    tc300: {
      name: "TC 300",
      color: "#0d9488", bg: "#ccfbf1",
      darkColor: "#2dd4bf", darkBg: "#0f3d38",
      platform: "canvas",
      platformUrl: "https://umich.instructure.com/"
    }
  },

  // ---- Assignments ----
  // Each assignment needs: id, name, course (must match a key above),
  // due (YYYY-MM-DD), time (string or null), type, points, hours
  assignments: [
    {
      id: "270-p1",
      name: "Project 1: Selector",
      course: "eecs270",
      due: "2026-01-20",
      time: "11:59 PM",
      type: "project",
      points: "50",
      hours: 6,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-1-selector"
    },
    {
      id: "270-p1-signoff",
      name: "Project 1 Signoff",
      course: "eecs270",
      due: "2026-01-23",
      time: "11:59 PM",
      type: "project",
      points: "3",
      hours: 0.5
    },
    {
      id: "270-p2a",
      name: "Project 2A: Robot Control (Autograde)",
      course: "eecs270",
      due: "2026-02-06",
      time: "11:59 PM",
      type: "project",
      points: "25",
      hours: 5,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-2-robot-control"
    },
    {
      id: "270-p2b",
      name: "Project 2B: Robot Control (Autograde)",
      course: "eecs270",
      due: "2026-02-06",
      time: "11:59 PM",
      type: "project",
      points: "57",
      hours: 7,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-2-robot-control"
    },
    {
      id: "270-p2a-signoff",
      name: "Project 2A Signoff",
      course: "eecs270",
      due: "2026-02-20",
      time: "11:59 PM",
      type: "project",
      points: "3",
      hours: 0.5
    },
    {
      id: "270-p2b-signoff",
      name: "Project 2B Signoff",
      course: "eecs270",
      due: "2026-02-20",
      time: "11:59 PM",
      type: "project",
      points: "5",
      hours: 0.5
    },
    {
      id: "270-p3-auto",
      name: "Project 3: Combinational Calculator",
      course: "eecs270",
      due: "2026-02-24",
      time: "11:59 PM",
      type: "project",
      points: "109",
      hours: 10,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-3-combinational-calculator"
    },
    {
      id: "270-p3-signoff",
      name: "Project 3 Signoff",
      course: "eecs270",
      due: "2026-03-02",
      time: "11:59 PM",
      type: "project",
      points: "5",
      hours: 0.5
    },
    {
      id: "270-p4",
      name: "Project 4: Timing and Delay",
      course: "eecs270",
      due: "2026-02-27",
      time: "11:59 PM",
      type: "project",
      points: "40",
      hours: 6,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-4-timing-and-delay"
    },
    {
      id: "270-p5",
      name: "Project 5: Up-Down Counter",
      course: "eecs270",
      due: "2026-03-11",
      time: "11:59 PM",
      type: "project",
      points: "-",
      hours: 8,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-5-up-down-counter"
    },
    {
      id: "270-p6",
      name: "Project 6: Traffic Light Controller",
      course: "eecs270",
      due: "2026-04-01",
      time: "11:59 PM",
      type: "project",
      points: "-",
      hours: 10,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-6-traffic-light-controller"
    },
    {
      id: "270-p7",
      name: "Project 7: Sequential Calculator",
      course: "eecs270",
      due: "2026-04-20",
      time: "11:59 PM",
      type: "project",
      points: "-",
      hours: 12,
      specUrl: "https://umich.instructure.com/courses/815882/pages/project-7-sequential-calculator"
    },
    {
      id: "270-p3",
      name: "Project 3 Autograde",
      course: "eecs270",
      due: "2026-02-24",
      time: "11:59 PM",
      type: "project",
      points: "109",
      hours: 8
    },
    {
      id: "270-q1",
      name: "Quiz 1 (Switching Func.)",
      course: "eecs270",
      due: "2026-01-13",
      time: "11:59 PM",
      type: "quiz",
      points: "23",
      hours: 1.5
    },
    {
      id: "270-q2",
      name: "Quiz 2 (Boolean Algebra)",
      course: "eecs270",
      due: "2026-01-15",
      time: "11:59 PM",
      type: "quiz",
      points: "21",
      hours: 1.5
    },
    {
      id: "270-q3",
      name: "Quiz 3 (Pos. Binary Nums)",
      course: "eecs270",
      due: "2026-01-22",
      time: "11:59 PM",
      type: "quiz",
      points: "20",
      hours: 1.5
    },
    {
      id: "270-q4",
      name: "Quiz 4 (Binary Arith.)",
      course: "eecs270",
      due: "2026-01-29",
      time: "11:59 PM",
      type: "quiz",
      points: "29",
      hours: 1.5
    },
    {
      id: "270-q5",
      name: "Quiz 5 (Combo. Blocks)",
      course: "eecs270",
      due: "2026-02-05",
      time: "11:59 PM",
      type: "quiz",
      points: "22",
      hours: 1.5
    },
    {
      id: "270-q6",
      name: "Quiz 6 (2-Level Logic)",
      course: "eecs270",
      due: "2026-02-12",
      time: "11:59 PM",
      type: "quiz",
      points: "21",
      hours: 1.5
    },
    {
      id: "270-q7",
      name: "Quiz 7 (Timing & Delay)",
      course: "eecs270",
      due: "2026-02-19",
      time: "11:59 PM",
      type: "quiz",
      points: "20",
      hours: 1.5
    },
    {
      id: "270-q8",
      name: "Quiz 8 (Latches/FFs)",
      course: "eecs270",
      due: "2026-02-24",
      time: "11:59 PM",
      type: "quiz",
      points: "25",
      hours: 1.5
    },
    {
      id: "270-q9",
      name: "Quiz 9 (Seq. Analysis)",
      course: "eecs270",
      due: "2026-02-25",
      time: "11:59 PM",
      type: "quiz",
      points: "17",
      hours: 1.5
    },
    {
      id: "270-q10",
      name: "Quiz 10 (Seq. Design)",
      course: "eecs270",
      due: "2026-02-27",
      time: "11:59 PM",
      type: "quiz",
      points: "18",
      hours: 1.5
    },
    {
      id: "270-q11",
      name: "Quiz 11 (Seq. Design Examples)",
      course: "eecs270",
      due: "2026-03-10",
      time: "11:59 PM",
      type: "quiz",
      points: "23",
      hours: 1.5
    },
    {
      id: "270-q12",
      name: "Quiz 12 (Sequential Blocks)",
      course: "eecs270",
      due: "2026-03-12",
      time: "11:59 PM",
      type: "quiz",
      points: "21",
      hours: 1.5
    },
    {
      id: "270-q14",
      name: "Quiz 14 (RTL Design)",
      course: "eecs270",
      due: "2026-03-27",
      time: "11:59 PM",
      type: "quiz",
      points: "20",
      hours: 1.5
    },
    {
      id: "270-q15",
      name: "Quiz 15 (Seq. Timing Analysis)",
      course: "eecs270",
      due: "2026-04-03",
      time: "11:59 PM",
      type: "quiz",
      points: "20",
      hours: 1.5
    },
    {
      id: "270-q16",
      name: "Quiz 16 (Seq. Multiplication)",
      course: "eecs270",
      due: "2026-04-14",
      time: "11:59 PM",
      type: "quiz",
      points: "16",
      hours: 1.5
    },
    {
      id: "270-q17",
      name: "Quiz 17 (Carry-Lookahead Adders)",
      course: "eecs270",
      due: "2026-04-16",
      time: "11:59 PM",
      type: "quiz",
      points: "22",
      hours: 1.5
    },
    {
      id: "270-q18",
      name: "Quiz 18 (State Minimization)",
      course: "eecs270",
      due: "2026-04-16",
      time: "11:59 PM",
      type: "quiz",
      points: "20",
      hours: 1.5
    },
    {
      id: "270-q13",
      name: "Quiz 13 (RTL Design)",
      course: "eecs270",
      due: "2026-03-19",
      time: "11:59 PM",
      type: "quiz",
      points: "20",
      hours: 1.5
    },
    {
      id: "270-exam1",
      name: "Exam 1",
      course: "eecs270",
      due: "2026-02-05",
      time: "3:35 PM",
      type: "exam",
      points: "100",
      hours: 12
    },
    {
      id: "270-exam2",
      name: "Exam 2",
      course: "eecs270",
      due: "2026-03-12",
      time: "5:02 PM",
      type: "exam",
      points: "100",
      hours: 12
    },
    {
      id: "270-final",
      name: "Final Exam",
      course: "eecs270",
      due: "2026-04-27",
      time: null,
      type: "exam",
      points: "100",
      hours: 15
    },
    {
      id: "370-p1a",
      name: "Project 1a: Assembler",
      course: "eecs370",
      due: "2026-01-29",
      time: "11:55 PM",
      type: "project",
      points: "40",
      hours: 8,
      specUrl: "https://eecs370.github.io/project_1_spec"
    },
    {
      id: "370-p1m",
      name: "Project 1m: Multiplication",
      course: "eecs370",
      due: "2026-02-05",
      time: "11:55 PM",
      type: "project",
      points: "20",
      hours: 4,
      specUrl: "https://eecs370.github.io/project_1_spec"
    },
    {
      id: "370-p1s",
      name: "Project 1s: Simulator",
      course: "eecs370",
      due: "2026-02-05",
      time: "11:55 PM",
      type: "project",
      points: "40",
      hours: 8,
      specUrl: "https://eecs370.github.io/project_1_spec"
    },
    {
      id: "370-p2a",
      name: "Project 2a: Assembler",
      course: "eecs370",
      due: "2026-02-19",
      time: "11:55 PM",
      type: "project",
      points: "35",
      hours: 8,
      specUrl: "https://eecs370.github.io/project_2_spec"
    },
    {
      id: "370-p2l",
      name: "Project 2l: Linker",
      course: "eecs370",
      due: "2026-03-19",
      time: "11:55 PM",
      type: "project",
      points: "45",
      hours: 10,
      specUrl: "https://eecs370.github.io/project_2_spec"
    },
    {
      id: "370-p2r",
      name: "Project 2r: Relocation",
      course: "eecs370",
      due: "2026-03-19",
      time: "11:55 PM",
      type: "project",
      points: "20",
      hours: 5,
      specUrl: "https://eecs370.github.io/project_2_spec"
    },
    {
      id: "370-p3-cp",
      name: "Project 3 Checkpoint",
      course: "eecs370",
      due: "2026-03-26",
      time: "11:55 PM",
      type: "project",
      points: "5",
      hours: 3
    },
    {
      id: "370-p3",
      name: "Project 3",
      course: "eecs370",
      due: "2026-03-26",
      time: "11:55 PM",
      type: "project",
      points: "95",
      hours: 15
    },
    {
      id: "370-p4",
      name: "Project 4",
      course: "eecs370",
      due: "2026-04-16",
      time: "11:55 PM",
      type: "project",
      points: "100",
      hours: 15
    },
    {
      id: "370-hw1",
      name: "Homework 1",
      course: "eecs370",
      due: "2026-02-02",
      time: "11:55 PM",
      type: "homework",
      points: "100",
      hours: 6,
      specUrl: "https://eecs370.github.io/homework/index.html"
    },
    {
      id: "370-hw2",
      name: "Homework 2",
      course: "eecs370",
      due: "2026-02-23",
      time: "11:55 PM",
      type: "homework",
      points: "100",
      hours: 6,
      specUrl: "https://eecs370.github.io/homework/index.html"
    },
    {
      id: "370-hw3",
      name: "Homework 3",
      course: "eecs370",
      due: "2026-03-23",
      time: "11:55 PM",
      type: "homework",
      points: "100",
      hours: 6,
      specUrl: "https://eecs370.github.io/homework/index.html"
    },
    {
      id: "370-hw4",
      name: "Homework 4",
      course: "eecs370",
      due: "2026-04-20",
      time: "11:55 PM",
      type: "homework",
      points: "100",
      hours: 6,
      specUrl: "https://eecs370.github.io/homework/index.html"
    },
    {
      id: "370-pl2",
      name: "Pre-Lab 2",
      course: "eecs370",
      due: "2026-01-22",
      time: "11:55 PM",
      type: "prelab",
      points: "7",
      hours: 1
    },
    {
      id: "370-pl3",
      name: "Pre-Lab 3",
      course: "eecs370",
      due: "2026-01-29",
      time: "11:55 PM",
      type: "prelab",
      points: "6",
      hours: 1
    },
    {
      id: "370-pl4",
      name: "Pre-Lab 4",
      course: "eecs370",
      due: "2026-02-05",
      time: "11:55 PM",
      type: "prelab",
      points: "4",
      hours: 1
    },
    {
      id: "370-pl5",
      name: "Pre-Lab 5",
      course: "eecs370",
      due: "2026-02-12",
      time: "11:55 PM",
      type: "prelab",
      points: "4",
      hours: 1
    },
    {
      id: "370-pl6",
      name: "Pre-Lab 6",
      course: "eecs370",
      due: "2026-02-19",
      time: "11:55 PM",
      type: "prelab",
      points: "5",
      hours: 1
    },
    {
      id: "370-pl8",
      name: "Pre-Lab 8",
      course: "eecs370",
      due: "2026-03-19",
      time: "11:55 PM",
      type: "prelab",
      points: "5",
      hours: 1
    },
    {
      id: "370-pl9",
      name: "Pre-Lab 9",
      course: "eecs370",
      due: "2026-03-26",
      time: "11:55 PM",
      type: "prelab",
      points: "5",
      hours: 1
    },
    {
      id: "370-midterm",
      name: "Midterm Exam",
      course: "eecs370",
      due: "2026-02-24",
      time: "11:42 AM",
      type: "exam",
      points: "100",
      hours: 12
    },
    {
      id: "370-final",
      name: "Final Exam",
      course: "eecs370",
      due: "2026-04-23",
      time: "10:30 AM",
      type: "exam",
      points: "100",
      hours: 15
    },
    {
      id: "370-lectures-at-12pm-and",
      name: "Lectures at 12pm and 3pm cancelled for 1/27",
      course: "eecs370",
      due: "2026-01-27",
      time: "10:44 AM",
      type: "assignment",
      points: "—",
      hours: 1
    },
    {
      id: "442-hw1",
      name: "HW1: Faces",
      course: "eecs442",
      due: "2026-01-29",
      time: "5:29 PM",
      type: "homework",
      points: "120",
      hours: 10
    },
    {
      id: "442-hw2",
      name: "HW2: Filtering",
      course: "eecs442",
      due: "2026-02-05",
      time: "5:30 PM",
      type: "homework",
      points: "120",
      hours: 10
    },
    {
      id: "442-hw3",
      name: "HW3: Frequency",
      course: "eecs442",
      due: "2026-02-19",
      time: "5:29 PM",
      type: "homework",
      points: "120",
      hours: 10
    },
    {
      id: "442-hw4",
      name: "HW4: Recognition",
      course: "eecs442",
      due: "2026-03-26",
      time: "11:59 PM",
      type: "homework",
      points: "120",
      hours: 10
    },
    {
      id: "442-q1",
      name: "Quiz 1 (02/02)",
      course: "eecs442",
      due: "2026-02-02",
      time: null,
      type: "quiz",
      points: "—",
      hours: 0.5
    },
    {
      id: "442-q2",
      name: "Quiz 2 (02/04)",
      course: "eecs442",
      due: "2026-02-04",
      time: null,
      type: "quiz",
      points: "—",
      hours: 0.5
    },
    {
      id: "442-q3",
      name: "Quiz 3 (02/09)",
      course: "eecs442",
      due: "2026-02-09",
      time: "11:33 AM",
      type: "quiz",
      points: "5",
      hours: 0.5
    },
    {
      id: "442-q4",
      name: "Quiz 4 (02/11)",
      course: "eecs442",
      due: "2026-02-11",
      time: "11:46 AM",
      type: "quiz",
      points: "4",
      hours: 0.5
    },
    {
      id: "442-q5",
      name: "Quiz 5 (02/16)",
      course: "eecs442",
      due: "2026-02-16",
      time: "11:43 AM",
      type: "quiz",
      points: "2",
      hours: 0.5
    },
    {
      id: "442-q6",
      name: "Quiz 6 (02/18)",
      course: "eecs442",
      due: "2026-02-18",
      time: "11:49 AM",
      type: "quiz",
      points: "5",
      hours: 0.5
    },
    {
      id: "442-q7",
      name: "Quiz 7 (03/09)",
      course: "eecs442",
      due: "2026-03-09",
      time: "11:53 AM",
      type: "quiz",
      points: "5",
      hours: 0.5
    },
    {
      id: "442-q8",
      name: "Quiz 8 (03/11)",
      course: "eecs442",
      due: "2026-03-11",
      time: "11:55 AM",
      type: "quiz",
      points: "5",
      hours: 0.5
    },
    {
      id: "442-q9",
      name: "Quiz 9 (03/16)",
      course: "eecs442",
      due: "2026-03-16",
      time: "11:39 AM",
      type: "quiz",
      points: "5",
      hours: 0.5
    },
    {
      id: "442-q10",
      name: "Quiz 10 (03/18)",
      course: "eecs442",
      due: "2026-03-18",
      time: "11:39 AM",
      type: "quiz",
      points: "5",
      hours: 0.5
    },
    {
      id: "442-midterm",
      name: "Midterm Evaluation",
      course: "eecs442",
      due: "2026-03-14",
      time: "11:59 PM",
      type: "exam",
      points: "—",
      hours: 12
    },
    {
      id: "s250-ep01",
      name: "EP 01",
      course: "stats250",
      due: "2026-01-23",
      time: "1:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep02",
      name: "EP 02",
      course: "stats250",
      due: "2026-01-30",
      time: "1:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep03",
      name: "EP 03",
      course: "stats250",
      due: "2026-02-06",
      time: "2:30 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep04",
      name: "EP 04",
      course: "stats250",
      due: "2026-02-21",
      time: "2:30 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep05",
      name: "EP 05",
      course: "stats250",
      due: "2026-02-27",
      time: "8:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep06",
      name: "EP 06",
      course: "stats250",
      due: "2026-03-16",
      time: "8:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep07",
      name: "EP 07",
      course: "stats250",
      due: "2026-03-27",
      time: "8:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep08",
      name: "EP 08",
      course: "stats250",
      due: "2026-04-03",
      time: "8:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep09",
      name: "EP 09",
      course: "stats250",
      due: "2026-04-10",
      time: "8:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-ep10",
      name: "EP 10",
      course: "stats250",
      due: "2026-04-17",
      time: "8:00 PM",
      type: "ep",
      points: "40",
      hours: 2
    },
    {
      id: "s250-lab1",
      name: "Lab 1",
      course: "stats250",
      due: "2026-01-23",
      time: "8:00 AM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-lab2",
      name: "Lab 2",
      course: "stats250",
      due: "2026-01-30",
      time: "1:00 PM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-lab3",
      name: "Lab 3",
      course: "stats250",
      due: "2026-02-06",
      time: "1:00 PM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-lab4",
      name: "Lab 4",
      course: "stats250",
      due: "2026-02-27",
      time: "8:00 PM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-lab5",
      name: "Lab 5",
      course: "stats250",
      due: "2026-03-13",
      time: "8:00 PM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-lab6",
      name: "Lab 6",
      course: "stats250",
      due: "2026-03-27",
      time: "8:00 PM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-lab7",
      name: "Lab 7",
      course: "stats250",
      due: "2026-04-03",
      time: "8:00 PM",
      type: "lab",
      points: "20",
      hours: 1.5
    },
    {
      id: "s250-cs1",
      name: "Case Study 1",
      course: "stats250",
      due: "2026-02-21",
      time: "8:00 PM",
      type: "casestudy",
      points: "40",
      hours: 3
    },
    {
      id: "s250-cs2",
      name: "Case Study 2",
      course: "stats250",
      due: "2026-03-23",
      time: "8:00 PM",
      type: "casestudy",
      points: "40",
      hours: 3
    },
    {
      id: "s250-cs3",
      name: "Case Study 3",
      course: "stats250",
      due: "2026-04-11",
      time: "8:00 PM",
      type: "casestudy",
      points: "40",
      hours: 3
    },
    {
      id: "s250-exam1",
      name: "Exam 1",
      course: "stats250",
      due: "2026-02-11",
      time: "6:00 PM",
      type: "exam",
      points: "75",
      hours: 8
    },
    {
      id: "s250-exam2",
      name: "Exam 2",
      course: "stats250",
      due: "2026-03-19",
      time: "6:00 PM",
      type: "exam",
      points: "75",
      hours: 8
    },
    {
      id: "s250-exam3",
      name: "Exam 3",
      course: "stats250",
      due: "2026-04-23",
      time: "7:30 PM",
      type: "exam",
      points: "75",
      hours: 8
    },
    {
      id: "s250-l04pw",
      name: "Lecture 04 PW",
      course: "stats250",
      due: "2026-01-26",
      time: "8:00 AM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l04gw",
      name: "Lecture 04 GW",
      course: "stats250",
      due: "2026-01-26",
      time: "3:20 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l05pw",
      name: "Lecture 05 PW",
      course: "stats250",
      due: "2026-01-28",
      time: "4:00 PM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l05gw",
      name: "Lecture 05 GW",
      course: "stats250",
      due: "2026-01-28",
      time: "3:20 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l06pw",
      name: "Lecture 06 PW",
      course: "stats250",
      due: "2026-02-02",
      time: "8:00 AM",
      type: "lecture",
      points: "—",
      hours: 0.5
    },
    {
      id: "s250-l06gw",
      name: "Lecture 06 GW",
      course: "stats250",
      due: "2026-02-02",
      time: "3:20 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l07pw",
      name: "Lecture 07 PW",
      course: "stats250",
      due: "2026-02-04",
      time: "4:00 PM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l07gw",
      name: "Lecture 07 GW",
      course: "stats250",
      due: "2026-02-04",
      time: "3:20 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l08pw",
      name: "Lecture 08 PW",
      course: "stats250",
      due: "2026-02-17",
      time: "8:00 AM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l08gw",
      name: "Lecture 08 GW",
      course: "stats250",
      due: "2026-02-16",
      time: "3:20 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l09pw",
      name: "Lecture 09 PW",
      course: "stats250",
      due: "2026-02-18",
      time: "4:00 PM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l09gw",
      name: "Lecture 09 GW",
      course: "stats250",
      due: "2026-02-18",
      time: "3:20 PM",
      type: "lecture",
      points: "—",
      hours: 0.5
    },
    {
      id: "s250-l10pw",
      name: "Lecture 10 PW",
      course: "stats250",
      due: "2026-02-23",
      time: "8:00 AM",
      type: "lecture",
      points: "—",
      hours: 0.5
    },
    {
      id: "s250-l10gw",
      name: "Lecture 10 GW",
      course: "stats250",
      due: "2026-02-23",
      time: "3:20 PM",
      type: "lecture",
      points: "—",
      hours: 0.5
    },
    {
      id: "s250-l11pw",
      name: "Lecture 11 PW",
      course: "stats250",
      due: "2026-02-25",
      time: "8:00 AM",
      type: "lecture",
      points: "—",
      hours: 0.5
    },
    {
      id: "s250-l11gw",
      name: "Lecture 11 GW",
      course: "stats250",
      due: "2026-02-25",
      time: "3:20 PM",
      type: "lecture",
      points: "—",
      hours: 0.5
    },
    {
      id: "s250-l12pw",
      name: "Lecture 12 PW",
      course: "stats250",
      due: "2026-03-09",
      time: "2:30 PM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l12gw",
      name: "Lecture 12 GW",
      course: "stats250",
      due: "2026-03-09",
      time: "4:00 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l13pw",
      name: "Lecture 13 PW",
      course: "stats250",
      due: "2026-03-11",
      time: "2:30 PM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l13gw",
      name: "Lecture 13 GW",
      course: "stats250",
      due: "2026-03-11",
      time: "4:00 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "s250-l14pw",
      name: "Lecture 14 PW",
      course: "stats250",
      due: "2026-03-16",
      time: "2:30 PM",
      type: "lecture",
      points: "10",
      hours: 0.5
    },
    {
      id: "s250-l14gw",
      name: "Lecture 14 GW",
      course: "stats250",
      due: "2026-03-16",
      time: "4:00 PM",
      type: "lecture",
      points: "20",
      hours: 0.5
    },
    {
      id: "tc-survey",
      name: "Pre-Course Survey",
      course: "tc300",
      due: "2026-01-16",
      time: "11:59 PM",
      type: "assignment",
      points: "1",
      hours: 0.25
    },
    {
      id: "tc-syllabus",
      name: "Syllabus Agreement",
      course: "tc300",
      due: "2026-01-16",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 0.25
    },
    {
      id: "tc-w2",
      name: "Week 2 - Evidence Language Activity",
      course: "tc300",
      due: "2026-01-15",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-w3",
      name: "Week 3 - Cover Letter Group",
      course: "tc300",
      due: "2026-01-22",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-resume-draft",
      name: "Resume Draft",
      course: "tc300",
      due: "2026-01-23",
      time: "11:59 PM",
      type: "assignment",
      points: "10",
      hours: 3
    },
    {
      id: "tc-cover-draft",
      name: "Cover Letter Draft",
      course: "tc300",
      due: "2026-01-23",
      time: "11:59 PM",
      type: "assignment",
      points: "10",
      hours: 3
    },
    {
      id: "tc-annotated-job",
      name: "Annotated Job Ad",
      course: "tc300",
      due: "2026-01-23",
      time: "11:59 PM",
      type: "assignment",
      points: "10",
      hours: 2
    },
    {
      id: "tc-w4",
      name: "Week 4 - STAR Method",
      course: "tc300",
      due: "2026-01-29",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-w5",
      name: "Week 5 - Revision Group",
      course: "tc300",
      due: "2026-02-05",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-revised-resume",
      name: "Revised Resume",
      course: "tc300",
      due: "2026-02-06",
      time: "11:59 PM",
      type: "assignment",
      points: "20",
      hours: 4
    },
    {
      id: "tc-revised-cover",
      name: "Revised Cover Letter",
      course: "tc300",
      due: "2026-02-06",
      time: "11:59 PM",
      type: "assignment",
      points: "20",
      hours: 4
    },
    {
      id: "tc-portfolio-reflect",
      name: "Career Portfolio Reflection",
      course: "tc300",
      due: "2026-02-06",
      time: "11:59 PM",
      type: "assignment",
      points: "30",
      hours: 3
    },
    {
      id: "tc-w6",
      name: "Week 6 - Structure & Org",
      course: "tc300",
      due: "2026-02-12",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-topic-proposal",
      name: "Written Report Topic Proposal",
      course: "tc300",
      due: "2026-02-13",
      time: "11:59 PM",
      type: "assignment",
      points: "10",
      hours: 2
    },
    {
      id: "tc-w7",
      name: "Week 7 - Reading Articles Group",
      course: "tc300",
      due: "2026-02-19",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-w8-dataviz",
      name: "Week 8 - Data Visualization",
      course: "tc300",
      due: "2026-02-26",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-report-outline",
      name: "Written Report Outline",
      course: "tc300",
      due: "2026-02-27",
      time: "11:59 PM",
      type: "assignment",
      points: "20",
      hours: 3
    },
    {
      id: "tc-w10-presentation",
      name: "Week 10 - Presentation Delivery",
      course: "tc300",
      due: "2026-03-12",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-w11-peer-review",
      name: "Week 11 - Written Report Peer Review Worksheet",
      course: "tc300",
      due: "2026-03-19",
      time: "11:59 PM",
      type: "assignment",
      points: "2",
      hours: 1
    },
    {
      id: "tc-report-draft",
      name: "Written Report Draft",
      course: "tc300",
      due: "2026-03-20",
      time: "11:59 PM",
      type: "assignment",
      points: "30",
      hours: 8
    },
    {
      id: "tc-oral-proposal",
      name: "Oral Report Topic Proposal",
      course: "tc300",
      due: "2026-03-20",
      time: "11:59 PM",
      type: "assignment",
      points: "10",
      hours: 2
    },
    {
      id: "tc-final-report",
      name: "Final Written Report",
      course: "tc300",
      due: "2026-04-03",
      time: "11:59 PM",
      type: "assignment",
      points: "75",
      hours: 10
    },
    {
      id: "tc-oral-slides",
      name: "Oral Presentation Draft Slides",
      course: "tc300",
      due: "2026-04-02",
      time: "11:30 AM",
      type: "assignment",
      points: "10",
      hours: 3
    },
    {
      id: "tc-ec-originpro",
      name: "EC: OriginPro Familiarizing",
      course: "tc300",
      due: "2026-04-24",
      time: "11:59 PM",
      type: "assignment",
      points: "EC",
      hours: 2
    }
  ],

  // ---- Auto-Completed ----
  // Assignment IDs to auto-mark as done on first visit.
  // Remove or edit these for your own courses.
  autoCompleted: [
    "270-q1",
    "270-q2",
    "270-q3",
    "270-q4",
    "270-q5",
    "270-q6",
    "270-q7",
    "270-q8",
    "270-q9",
    "270-q10",
    "270-p1",
    "270-p1-signoff",
    "270-p2a",
    "270-p2b",
    "270-p2a-signoff",
    "270-p2b-signoff",
    "270-p3-auto",
    "270-p3-signoff",
    "270-p4",
    "270-p5",
    "270-exam1",
    "270-q11",
    "270-q12",
    "370-p1a",
    "370-p1m",
    "370-p1s",
    "370-p2a",
    "370-hw1",
    "370-hw2",
    "370-pl2",
    "370-pl3",
    "370-pl4",
    "370-pl5",
    "370-pl6",
    "370-pl8",
    "370-midterm",
    "442-hw1",
    "442-hw2",
    "442-hw3",
    "442-q3",
    "442-q4",
    "442-q5",
    "442-q6",
    "442-q7",
    "442-midterm",
    "s250-ep01",
    "s250-ep02",
    "s250-ep03",
    "s250-ep04",
    "s250-ep06",
    "s250-lab1",
    "s250-lab2",
    "s250-lab3",
    "s250-lab4",
    "s250-lab5",
    "s250-cs1",
    "s250-exam1",
    "s250-l04pw",
    "s250-l04gw",
    "s250-l05pw",
    "s250-l05gw",
    "s250-l06gw",
    "s250-l07pw",
    "s250-l07gw",
    "s250-l08pw",
    "s250-l08gw",
    "s250-l09pw",
    "s250-l11gw",
    "s250-l12pw",
    "s250-l12gw",
    "s250-l13pw",
    "s250-l13gw",
    "s250-l14pw",
    "tc-survey",
    "tc-syllabus",
    "tc-w2",
    "tc-w3",
    "tc-resume-draft",
    "tc-cover-draft",
    "tc-annotated-job",
    "tc-w4",
    "tc-w5",
    "tc-revised-resume",
    "tc-revised-cover",
    "tc-portfolio-reflect",
    "tc-w6",
    "tc-topic-proposal",
    "tc-w7",
    "tc-w8-dataviz",
    "tc-report-outline",
    "tc-w10-presentation",
    // Auto-added 2026-03-20: past assignments (due before 2026-03-18) not previously marked
    "270-p3",
    "270-exam2",
    "370-lectures-at-12pm-and",
    "442-q1",
    "442-q2",
    "442-q8",
    "442-q9",
    "s250-ep05",
    "s250-l06pw",
    "s250-l09gw",
    "s250-l10pw",
    "s250-l10gw",
    "s250-l11pw",
    "s250-l14gw",
    // Auto-added 2026-03-21: past assignments (due before 2026-03-19) not previously marked
    "442-q10"
  ]
};
