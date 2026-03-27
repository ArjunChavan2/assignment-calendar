/**
 * Assignment Data Module
 * Handles fetching and managing assignment data from GitHub Pages
 * Separated from game logic to enable modularization and independent testing
 */

const GITHUB_PAGES_URL = 'https://arjunchavan2.github.io/assignment-calendar/config.js';
const DONE_MAP_KEY = 'classroom-done-map';

let assignmentsCache = [];
let coursesCache = {};
let doneMapCache = JSON.parse(localStorage.getItem(DONE_MAP_KEY) || '{}');

/**
 * Save done map to localStorage
 */
function saveDoneMap() {
  localStorage.setItem(DONE_MAP_KEY, JSON.stringify(doneMapCache));
}

/**
 * Fetch assignments from GitHub Pages and parse config.js
 * @returns {Promise<boolean>} - true if successful, false otherwise
 */
export async function fetchAssignments() {
  try {
    const resp = await fetch(GITHUB_PAGES_URL, {
      cache: 'no-store'
    });
    let text = await resp.text();

    // Replace const with var to allow reassignment in function scope
    text = text.replace(/const\s+APP_CONFIG\s*=/g, 'var APP_CONFIG =');

    // Create isolated scope to parse config
    const cfg = new Function(`
      ${text}
      return APP_CONFIG;
    `)();

    coursesCache = cfg.courses || {};
    assignmentsCache = cfg.assignments || [];

    // Mark auto-completed assignments from site data
    const ac = new Set(cfg.autoCompleted || []);
    assignmentsCache.forEach(a => {
      if (ac.has(a.id) || doneMapCache[a.id]) a._done = true;
    });

    console.log(`Loaded ${assignmentsCache.length} assignments across ${Object.keys(coursesCache).length} courses`);
    return true;
  } catch (e) {
    console.error('Failed to fetch assignments:', e);
    return false;
  }
}

/**
 * Get current assignments list
 * @returns {Array} - Array of assignment objects
 */
export function getAssignments() {
  return assignmentsCache;
}

/**
 * Get current courses map
 * @returns {Object} - Map of course IDs to course objects
 */
export function getCourses() {
  return coursesCache;
}

/**
 * Toggle assignment completion status
 * @param {string} id - Assignment ID
 */
export function markDone(id) {
  if (doneMapCache[id]) {
    delete doneMapCache[id];
  } else {
    doneMapCache[id] = true;
  }
  saveDoneMap();

  // Update assignment in cache if it exists
  const assignment = assignmentsCache.find(a => a.id === id);
  if (assignment) {
    assignment._done = doneMapCache[id] ? true : false;
  }
}

/**
 * Get the done map (for debugging/inspection)
 * @returns {Object} - Current done map state
 */
export function getDoneMap() {
  return { ...doneMapCache };
}

/**
 * Check if assignment is marked done
 * @param {string} id - Assignment ID
 * @returns {boolean} - true if marked done
 */
export function isDone(id) {
  return !!doneMapCache[id];
}

/**
 * Get assignment by ID
 * @param {string} id - Assignment ID
 * @returns {Object|null} - Assignment object or null
 */
export function getAssignmentById(id) {
  return assignmentsCache.find(a => a.id === id) || null;
}

/**
 * Get assignments for a specific course
 * @param {string} courseId - Course ID
 * @returns {Array} - Assignments for the course
 */
export function getAssignmentsByCourse(courseId) {
  return assignmentsCache.filter(a => a.course === courseId);
}

/**
 * Initialize - fetch assignments on module load
 * Note: This will run once when the module is imported
 */
await fetchAssignments();
