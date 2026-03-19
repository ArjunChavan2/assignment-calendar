#!/usr/bin/env node
// ============================================================
// Assignment Calendar — Local Scraper Server
// ============================================================
// Tiny HTTP server that runs scrape_assignments.py and
// validate-config.js when triggered from the calendar UI.
//
// Usage:
//   node run-scraper.js              # start on port 3847
//   node run-scraper.js --port 4000  # custom port
//
// The calendar's "Synced today" button sends a request to
// http://localhost:3847/scrape which triggers the pipeline.
// ============================================================

const http = require('http');
const { execFile } = require('child_process');
const path = require('path');

const PORT = (() => {
  const idx = process.argv.indexOf('--port');
  return idx !== -1 && process.argv[idx + 1] ? parseInt(process.argv[idx + 1], 10) : 3847;
})();

const DIR = __dirname;
const PYTHON = path.join(DIR, '.venv', 'bin', 'python3');
const SCRAPER = path.join(DIR, 'scrape_assignments.py');
const VALIDATOR = path.join(DIR, 'validate-config.js');

let running = false;

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };
}

function runCommand(cmd, args, label) {
  return new Promise((resolve, reject) => {
    console.log(`  → Running: ${label}`);
    const start = Date.now();
    const proc = execFile(cmd, args, {
      cwd: DIR,
      timeout: 10 * 60 * 1000, // 10 min max
      maxBuffer: 10 * 1024 * 1024,
    }, (err, stdout, stderr) => {
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      if (err) {
        console.log(`  ✗ ${label} failed (${elapsed}s)`);
        reject({ label, error: err.message, stdout, stderr, elapsed });
      } else {
        console.log(`  ✓ ${label} done (${elapsed}s)`);
        resolve({ label, stdout, stderr, elapsed });
      }
    });
  });
}

async function handleScrape(req, res) {
  if (running) {
    res.writeHead(409, corsHeaders());
    res.end(JSON.stringify({ success: false, error: 'A scrape is already running.' }));
    return;
  }

  running = true;
  const timestamp = new Date().toLocaleTimeString();
  console.log(`\n[${timestamp}] Scrape triggered`);

  try {
    // Step 1: Run scraper
    // Run without --headless so the browser window is visible if login is needed.
    // The browser profile persists auth cookies, so most runs won't need interaction.
    const scrapeResult = await runCommand(PYTHON, [SCRAPER, '--no-push'], 'scrape_assignments.py');

    // Step 2: Run validator
    let validationResult;
    try {
      validationResult = await runCommand('node', [VALIDATOR, '--fix'], 'validate-config.js --fix');
    } catch (valErr) {
      // Validator found unfixable errors — report but don't fail the whole pipeline
      validationResult = valErr;
    }

    res.writeHead(200, corsHeaders());
    res.end(JSON.stringify({
      success: true,
      scrape: {
        elapsed: scrapeResult.elapsed,
        output: scrapeResult.stdout.slice(-500), // last 500 chars
      },
      validation: {
        elapsed: validationResult.elapsed,
        output: (validationResult.stdout || '').slice(-500),
        warnings: (validationResult.stderr || '').slice(-300),
      },
    }));
    console.log(`  ✓ Pipeline complete\n`);

  } catch (err) {
    res.writeHead(500, corsHeaders());
    res.end(JSON.stringify({
      success: false,
      error: `${err.label} failed: ${err.error}`,
      output: (err.stdout || '').slice(-500),
      stderr: (err.stderr || '').slice(-300),
    }));
    console.log(`  ✗ Pipeline failed: ${err.error}\n`);

  } finally {
    running = false;
  }
}

const server = http.createServer((req, res) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders());
    res.end();
    return;
  }

  if (req.url === '/scrape' && (req.method === 'GET' || req.method === 'POST')) {
    handleScrape(req, res);
    return;
  }

  if (req.url === '/status') {
    res.writeHead(200, corsHeaders());
    res.end(JSON.stringify({ running, ok: true }));
    return;
  }

  res.writeHead(404, corsHeaders());
  res.end(JSON.stringify({ error: 'Not found. Use /scrape or /status' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`\n🔄 Assignment Scraper Server`);
  console.log(`   Listening on http://localhost:${PORT}`);
  console.log(`   Endpoints:`);
  console.log(`     GET /scrape  → run scraper + validator`);
  console.log(`     GET /status  → check if a scrape is running`);
  console.log(`\n   Press Ctrl+C to stop.\n`);
});
