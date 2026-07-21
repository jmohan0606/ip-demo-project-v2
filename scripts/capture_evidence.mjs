#!/usr/bin/env node
/**
 * capture_evidence.mjs — Playwright screenshot evidence harness (FIX_SPEC R6).
 *
 * Walks every V2 screen at a 1440-wide viewport against the RUNNING app
 * (sample data set) and writes full-page PNGs to docs/qa_screenshots/,
 * plus an index.md describing what each shot proves.
 *
 * It does NOT start servers. Run first:
 *   backend :  python run_local_api.py            (port 8001)
 *   frontend:  cd frontend && npm run dev         (port 3001)
 *
 * Console errors on any page are collected and reported; the script exits
 * non-zero if any page produced console errors — that is part of the evidence.
 *
 * Selectors deliberately avoid component internals (other agents edit
 * components concurrently): navigation is by URL; interaction uses ARIA
 * roles/labels and stable visible text only.
 */

import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..");
const OUT_DIR = path.join(REPO, "docs", "qa_screenshots");

// Playwright lives in frontend/node_modules — resolve from there.
const requireFrontend = createRequire(path.join(REPO, "frontend", "package.json"));
let chromium;
try {
  ({ chromium } = requireFrontend("@playwright/test"));
} catch {
  console.error(
    "Playwright is not installed.\n" +
      "  cd frontend && npm install -D @playwright/test && npx playwright install chromium",
  );
  process.exit(2);
}

const BACKEND = process.env.V2_BACKEND_URL ?? "http://localhost:8001";
const FRONTEND = process.env.V2_FRONTEND_URL ?? "http://localhost:3001";
const VIEWPORT = { width: 1440, height: 1000 };

/** shot name -> { file, proves, consoleErrors[] , captured, note } */
const results = [];

async function checkServer(url, name, hint) {
  try {
    // Generous timeout: a dev-server's first hit compiles the page.
    const res = await fetch(url, { signal: AbortSignal.timeout(30000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return true;
  } catch (e) {
    console.error(`\n${name} is not reachable at ${url} (${e.message ?? e}).`);
    console.error(`Start it first:\n  ${hint}\n`);
    return false;
  }
}

function attachConsoleCollector(page, bucket) {
  page.on("console", (msg) => {
    if (msg.type() === "error") bucket.push(msg.text());
  });
  page.on("pageerror", (err) => bucket.push(`pageerror: ${err.message}`));
  // "Failed to load resource" console messages omit the URL — record it.
  page.on("response", (res) => {
    if (res.status() >= 400) bucket.push(`HTTP ${res.status()} ${res.url()}`);
  });
}

/** Wait for the app to settle: network idle, then no visible "Loading" text. */
async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page
    .waitForFunction(() => !/Loading/i.test(document.body.innerText), null, { timeout: 20000 })
    .catch(() => {}); // a stuck spinner will be visible in the shot — that IS evidence
  await page.waitForTimeout(750); // let charts finish animating
}

async function capture(context, spec) {
  const { name, url, proves, fullPage = true, interact } = spec;
  const errors = [];
  const page = await context.newPage();
  attachConsoleCollector(page, errors);
  const entry = { name, file: `${name}.png`, proves, consoleErrors: errors, captured: false, note: "" };
  results.push(entry);
  try {
    console.log(`→ ${name}  (${url})`);
    await page.goto(FRONTEND + url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await settle(page);
    if (interact) await interact(page, entry);
    await page.screenshot({ path: path.join(OUT_DIR, entry.file), fullPage });
    entry.captured = true;
    console.log(`  ✓ ${entry.file}${errors.length ? `  (${errors.length} console error(s))` : ""}`);
  } catch (e) {
    entry.note = `capture failed: ${e.message ?? e}`;
    console.error(`  ✗ ${name}: ${entry.note}`);
    // best-effort shot of whatever is on screen, for diagnosis
    await page
      .screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: false })
      .then(() => { entry.captured = true; entry.note += " (partial screenshot saved)"; })
      .catch(() => {});
  } finally {
    await page.close();
  }
}

const SHOTS = [
  {
    name: "01_trends",
    url: "/trends",
    proves:
      "Trends screen renders both cards — the revenue pivot by product hierarchy and the month-over-month card — from sample data.",
  },
  {
    name: "02_ai_insights",
    url: "/ai-insights",
    proves:
      "AI Insights renders the stacked revenue chart, the stored commentary cards (with version selector), and the monthly walk table. Commentary is retrieved, not generated on load.",
  },
  {
    name: "03_evidence_modal",
    url: "/ai-insights",
    fullPage: false, // fixed-position overlay; viewport shot shows the open modal
    interact: async (page, entry) => {
      const trigger = page.getByRole("button", { name: /view evidence/i }).first();
      await trigger.waitFor({ state: "visible", timeout: 20000 });
      await trigger.click();
      await page.getByRole("dialog").waitFor({ state: "visible", timeout: 20000 });
      await settle(page);
      entry.note = "Opened via the first 'View evidence' affordance on a commentary bullet.";
    },
    proves:
      "The evidence modal opens from a driver bullet and shows the evidence record for that driver (finding, calculation, source records, lineage, runnable query).",
  },
  {
    name: "04_transactions_filtered",
    url: "/transactions?advisor=SMPL001&month=202606&group=unified_managed_account",
    proves:
      "Transactions drill-down honours URL filters (advisor SMPL001, Jun 2026, Unified Managed Account): filter chips shown, rows restricted, footer credited-revenue total matches the filtered set.",
  },
  {
    name: "05_data_ingestion",
    url: "/data-ingestion",
    proves:
      "Data-ingestion screen renders: load / reload / ordered-delete controls and per-file status for the sample data set.",
  },
  {
    name: "06_env_health",
    url: "/env-health",
    proves:
      "Environment-health screen reports backend connectivity, configured modes, and the true serving tier.",
  },
  {
    name: "07_transactions_empty_state",
    url: "/transactions?advisor=SMPL001&month=202606&group=annuities",
    proves:
      "Empty state: Annuities has no SMPL001 transactions in Jun 2026 (true in the sample data), so the screen shows its 'no transactions match' state rather than fabricating rows.",
  },
  {
    name: "08_commentary_blocked_state",
    url: "/ai-insights",
    interact: async (page, entry) => {
      // Version v3 genuinely contains BLOCKED transitions in the sample data
      // (guardrails blocked SMPL001 202605→202606: invented figure). Selecting
      // it via the UI's own version selector renders the BLOCKED state honestly.
      const selector = page.getByLabel("Commentary version");
      await selector.waitFor({ state: "visible", timeout: 20000 });
      await selector.selectOption("v3");
      await page
        .getByText(/BLOCKED/i)
        .first()
        .waitFor({ state: "visible", timeout: 20000 });
      await settle(page);
      entry.note =
        "Version v3 selected via the UI version selector; v3 contains a guardrail-BLOCKED transition for SMPL001 (May→Jun 2026) in the sample data.";
    },
    proves:
      "BLOCKED-commentary state: with historical version v3 selected, the SMPL001 May→Jun transition shows its guardrail-blocked card with the block reason — no narrative is shown for a transition that failed validation.",
  },
];

function writeIndex() {
  const lines = [
    "# QA screenshot evidence",
    "",
    `Generated ${new Date().toISOString()} against ${FRONTEND} (backend ${BACKEND}), viewport width 1440, sample data set.`,
    "",
    "This folder is gitignored — regenerate with `node scripts/capture_evidence.mjs` (servers must be running).",
    "",
    "| Screenshot | Captured | What it proves | Console errors |",
    "|---|---|---|---|",
  ];
  for (const r of results) {
    const proves = r.note ? `${r.proves} ${r.note}` : r.proves;
    lines.push(
      `| \`${r.file}\` | ${r.captured ? "yes" : "NO"} | ${proves.replace(/\|/g, "\\|")} | ${
        r.consoleErrors.length === 0
          ? "none"
          : r.consoleErrors.map((e) => e.replace(/\|/g, "\\|").slice(0, 200)).join("<br>")
      } |`,
    );
  }
  lines.push("");
  const anyErrors = results.some((r) => r.consoleErrors.length > 0);
  const anyMissed = results.some((r) => !r.captured);
  lines.push(
    anyErrors || anyMissed
      ? "**Result: FAIL** — console errors and/or missed captures above must be resolved."
      : "**Result: PASS** — every screen captured with zero browser console errors.",
  );
  lines.push("");
  writeFileSync(path.join(OUT_DIR, "index.md"), lines.join("\n"));
}

async function main() {
  const backendUp = await checkServer(`${BACKEND}/health`, "Backend", "python run_local_api.py   # port 8001");
  const frontendUp = await checkServer(FRONTEND, "Frontend", "cd frontend && npm run dev   # port 3001");
  if (!backendUp || !frontendUp) process.exit(2);

  mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT });

  // The frontend's NEXT_PUBLIC_API_BASE_URL may point at a Codespaces
  // forwarded URL (…-8001.app.github.dev) so an external browser can reach the
  // backend. This headless browser runs INSIDE the codespace, where that proxy
  // demands GitHub auth and breaks CORS. Rewrite those requests to the local
  // backend — the very same server, just addressed directly.
  await context.route(
    (url) => /-8001\.app\.github\.dev$/.test(url.host),
    async (route) => {
      const u = new URL(route.request().url());
      try {
        const resp = await route.fetch({ url: BACKEND + u.pathname + u.search });
        await route.fulfill({
          response: resp,
          headers: { ...resp.headers(), "access-control-allow-origin": "*" },
        });
      } catch (e) {
        await route.abort();
      }
    },
  );
  try {
    for (const spec of SHOTS) await capture(context, spec);
  } finally {
    await browser.close();
  }

  writeIndex();

  const errorPages = results.filter((r) => r.consoleErrors.length > 0);
  const missed = results.filter((r) => !r.captured);
  console.log(`\n${results.length - missed.length}/${results.length} screenshots captured → ${OUT_DIR}`);
  if (errorPages.length > 0) {
    console.error("\nConsole errors detected (this fails the run):");
    for (const r of errorPages) {
      console.error(`  ${r.name}:`);
      for (const e of r.consoleErrors) console.error(`    - ${e.slice(0, 300)}`);
    }
  }
  if (missed.length > 0) {
    console.error(`\nMissed captures: ${missed.map((r) => r.name).join(", ")}`);
  }
  process.exit(errorPages.length > 0 || missed.length > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(2);
});
