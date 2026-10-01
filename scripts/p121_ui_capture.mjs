/**
 * P121 — real browser capture + UI gate against localhost:3099 (read-only).
 *
 * Spawns the production build on port 3099 (refuses if the port is busy),
 * then for each route × viewport (desktop 1440x900, mobile 390x844):
 *   - waits for network settling, captures full-page JPEG + viewport PNG,
 *   - records HTTP status, console/page errors, failed requests,
 *   - checks: broken images, horizontal overflow, blank/hydration, small
 *     touch targets (mobile), price presence, provenance link (detail),
 *   - exercises real interactions (search typing, compare selection + diff
 *     toggle, compare handoff) — not just URL loads.
 *
 * Outputs: audit/ui-captures/<RUN_ID>/screenshots/*, manifest.json (+ md).
 * Exit 0 = capture completed (defects are recorded in the manifest, not hidden).
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import net from "node:net";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const PORT = 3099;
const BASE = `http://127.0.0.1:${PORT}`;
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RUN_ID = process.env.P121_RUN_ID || "p121-20260930-baseline";
const OUT = path.join(REPO, "audit", "ui-captures", RUN_ID);
const SHOTS = path.join(OUT, "screenshots");
const LOG = path.join(REPO, "audit", "daily-runs", "20260930-p121-capture.log");

// real data (read-only queries captured from the live DB):
//  - gr-86: honest mostly-unavailable state (bv price gate + thin specs)
//  - yaris-ativ: spec-rich detail (2503 ACTIVE spec rows, price unavailable)
//  - city-hatchback: bv-verified official price present
//  - compare price pair: two variants with verified official prices
//  - compare specs pair: two variants with 1940/746 ACTIVE spec rows
const DETAIL_ROUTE = "/cars/toyota/gr-86";
const DETAIL_SPECS_ROUTE = "/cars/mg/mg-s5";
const DETAIL_PRICE_ROUTE = "/cars/honda/city-hatchback";
const COMPARE_PRICE_IDS =
  "40043ccc-7624-4d68-942a-79ba447bfa26,054138f7-37f7-45be-8089-8ff99e1c6c22";
const COMPARE_SPEC_IDS =
  "cbe7ceca-7bfd-4bf9-aa08-d47c7cf6872b,d696cff5-937a-411e-96be-9598c92044e0";

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];

const PAGES = [
  { name: "home", route: "/", expect: { price: true, stats: true } },
  { name: "cars", route: "/cars", expect: { price: true, cards: true } },
  { name: "detail-gr86", route: DETAIL_ROUTE, expect: { price: false } },
  { name: "detail-mg-s5", route: DETAIL_SPECS_ROUTE, expect: { price: true, specs: true } },
  { name: "detail-city", route: DETAIL_PRICE_ROUTE, expect: { price: true, provenance: true } },
  { name: "search", route: "/search", expect: { price: false } },
  { name: "search-empty-state", route: "/search?q=GR%2086", expect: { price: false } },
  { name: "compare-price", route: `/compare?ids=${COMPARE_PRICE_IDS}`, expect: { price: true } },
  { name: "compare-specs", route: `/compare?ids=${COMPARE_SPEC_IDS}`, expect: { price: false } },
  { name: "ai-ask", route: "/ai-ask", expect: {} },
];

const logLines = [];
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  logLines.push(line);
  console.log(msg);
}

async function waitForServer(url, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { redirect: "manual" });
      if (res.status < 500) return true;
    } catch { /* not up */ }
    await new Promise((r) => setTimeout(r, 1500));
  }
  return false;
}

function portBusy() {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.once("connect", () => { socket.destroy(); resolve(true); });
    socket.once("error", () => resolve(false));
    socket.setTimeout(1500, () => { socket.destroy(); resolve(false); });
    socket.connect(PORT, "127.0.0.1");
  });
}

async function collectPageProbe(page) {
  return await page.evaluate(() => {
    const doc = document.documentElement;
    const overflowEls = [];
    if (doc.scrollWidth > window.innerWidth + 2) {
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.right > window.innerWidth + 2 && r.width > 8) {
          overflowEls.push(
            `${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(/\s+/).slice(0, 2).join(".") : ""}`
          );
          if (overflowEls.length >= 5) break;
        }
      }
    }
    const brokenImages = [...document.images]
      .filter((i) => !i.complete || i.naturalWidth === 0)
      .map((i) => i.currentSrc || i.src).slice(0, 10);
    const smallTargets = [];
    const mobile = window.innerWidth <= 480;
    if (mobile) {
      for (const el of document.querySelectorAll("a, button, input[type=checkbox], input[type=submit], [role=button]")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        // sr-only / visually-hidden controls are NOT tap targets — their
        // styled label is (checked separately with min-h-[32px])
        if (el.classList.contains("sr-only") || (r.width < 4 && r.height < 4)) continue;
        if (r.height < 32) {
          smallTargets.push(
            `${el.tagName.toLowerCase()}"${(el.textContent || "").trim().slice(0, 24)}" h=${Math.round(r.height)}`
          );
          if (smallTargets.length >= 8) break;
        }
      }
    }
    const text = (document.body.innerText || "").trim();
    return {
      scrollWidth: doc.scrollWidth,
      innerWidth: window.innerWidth,
      overflow: overflowEls,
      brokenImages,
      smallTargets,
      textLength: text.length,
      textSample: text.slice(0, 120),
      priceCount: (text.match(/[0-9]{1,3}(,[0-9]{3}){1,2}\s*บาท|฿\s*[0-9]/g) || []).length,
      externalLinks: [...document.querySelectorAll('a[href^="http"]')]
        .map((a) => a.href).filter((h) => !h.includes("127.0.0.1")).slice(0, 5),
      hasThai: /[ก-๙]/.test(text),
    };
  });
}

function classifyConsole(msgs) {
  const hydration = msgs.filter((m) => /hydrat|did not match/i.test(m));
  return { hydration, other: msgs.filter((m) => !/hydrat|did not match/i.test(m)) };
}

async function main() {
  fs.mkdirSync(SHOTS, { recursive: true });
  const gitSha = (await import("node:child_process"))
    .execSync("git rev-parse HEAD", { cwd: REPO }).toString().trim();
  const buildId = fs.readFileSync(path.join(REPO, ".next", "BUILD_ID"), "utf8").trim();

  // ── server ────────────────────────────────────────────────────────────────
  let server = null;
  const busy = await portBusy();
  if (!busy) {
    log(`spawning next start -p ${PORT}`);
    server = spawn("npx", ["next", "start", "-p", String(PORT)], {
      cwd: REPO,
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
      env: { ...process.env },
    });
    let serverLog = "";
    server.stdout.on("data", (d) => (serverLog += d));
    server.stderr.on("data", (d) => (serverLog += d));
    server.unref();
    const up = await waitForServer(`${BASE}/`, 90_000);
    if (!up) {
      log("SERVER NOT READY: " + serverLog.slice(-500));
      process.exit(2);
    }
  } else {
    const up = await waitForServer(`${BASE}/`, 15_000);
    if (!up) { log("port busy but server not answering"); process.exit(2); }
    log("port 3099 already serving (using it as requested)");
  }
  log(`server ready at ${BASE} (build ${buildId})`);

  const browser = await chromium.launch({
    executablePath: process.env.P121_CHROME || "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  const manifest = {
    schema: "p121_ui_capture_manifest/v1",
    run_id: RUN_ID,
    git_sha: gitSha,
    build_id: buildId,
    base: BASE,
    captured_at: new Date().toISOString(),
    viewports: VIEWPORTS,
    pages: [],
    interactions: [],
    summary: {},
  };
  const defects = [];

  function recordDefect(sev, where, what) {
    defects.push({ severity: sev, where, what });
    log(`DEFECT[${sev}] ${where}: ${what}`);
  }

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    for (const spec of PAGES) {
      const consoleMsgs = [];
      const pageErrors = [];
      const failedRequests = [];
      const badResponses = [];
      const onConsole = (m) => { if (m.type() === "error") consoleMsgs.push(m.text()); };
      const onErr = (e) => pageErrors.push(String(e));
      const onReqFail = (r) => failedRequests.push(`${r.failure()?.errorText} ${r.url()}`);
      const onResp = (r) => {
        if (r.status() >= 400 && !r.url().includes("favicon")) {
          badResponses.push(`${r.status()} ${r.url()}`);
        }
      };
      page.on("console", onConsole);
      page.on("pageerror", onErr);
      page.on("requestfailed", onReqFail);
      page.on("response", onResp);

      const entry = {
        route: spec.route,
        name: spec.name,
        viewport: vp.name,
        screenshots: [],
        console_errors: [],
        page_errors: [],
        failed_requests: [],
        bad_responses: [],
        checks: {},
        interactions: [],
      };
      try {
        const resp = await page.goto(`${BASE}${spec.route}`, {
          waitUntil: "networkidle",
          timeout: 60_000,
        });
        await page.waitForTimeout(600);
        entry.http_status = resp ? resp.status() : null;

        const full = path.join(SHOTS, `${spec.name}-${vp.name}-full.jpg`);
        await page.screenshot({ path: full, fullPage: true, type: "jpeg", quality: 75 });
        entry.screenshots.push(path.relative(REPO, full));

        const probe = await collectPageProbe(page);
        const cls = classifyConsole([...consoleMsgs, ...pageErrors]);
        entry.console_errors = cls.other;
        entry.page_errors = pageErrors;
        entry.failed_requests = failedRequests;
        entry.bad_responses = badResponses;
        entry.probe = {
          text_length: probe.textLength,
          scroll_width: probe.scrollWidth,
          inner_width: probe.innerWidth,
          overflow_elements: probe.overflow,
          broken_images: probe.brokenImages,
          small_touch_targets: probe.smallTargets,
          price_matches: probe.priceCount,
          external_links: probe.externalLinks,
          has_thai: probe.hasThai,
        };

        // checks
        entry.checks.rendered = probe.textLength > 100;
        entry.checks.no_console_errors = cls.other.length === 0 && pageErrors.length === 0;
        entry.checks.no_hydration_errors = cls.hydration.length === 0;
        entry.checks.no_broken_images = probe.brokenImages.length === 0;
        // Next.js RSC prefetches get aborted on navigation/close (net::ERR_ABORTED
        // on ?_rsc=) — capture noise, not page failures. Real failures stay.
        const realFailures = failedRequests.filter(
          (f) => !(f.includes("ERR_ABORTED") && f.includes("_rsc="))
        );
        entry.real_failed_requests = realFailures;
        entry.checks.no_bad_responses = badResponses.length === 0 && realFailures.length === 0;
        entry.checks.http_ok = entry.http_status === 200;
        entry.checks.no_overflow_mobile =
          vp.name !== "mobile" || probe.overflow.length === 0;
        entry.checks.touch_targets_ok =
          vp.name !== "mobile" || probe.smallTargets.length === 0;
        if (spec.expect.price) {
          entry.checks.price_present = probe.priceCount > 0;
        }
        if (spec.expect.provenance) {
          entry.checks.provenance_link_present = probe.externalLinks.length > 0;
        }
        if (spec.expect.stats) {
          const stats = await page.evaluate(() => {
            const el = document.querySelector('[data-testid="home-stats"]');
            if (!el) return null;
            return (el.innerText || "")
              .split("\n")
              .map((s) => parseInt(s.replace(/[^0-9]/g, ""), 10))
              .filter((n) => !Number.isNaN(n));
          });
          entry.stats_values = stats;
          entry.checks.stats_present_nonzero =
            !!stats && stats.length >= 4 && stats.every((n) => n > 0);
        }
        if (spec.expect.specs) {
          const specValues = await page.evaluate(() => {
            const text = document.body.innerText || "";
            const heading = /สเปคหลัก/.test(text);
            const labels = (text.match(/กำลังสูงสุด|แรงบิด|ความจุแบตเตอรี่|ยาวxกว้างxสูง/g) || []).length;
            const placeholders = (text.match(/ยังไม่มีข้อมูลยืนยัน/g) || []).length;
            // typed-spec values that MUST be visible (mg4/mg-s5 real rows)
            const values = (text.match(/\b(125|130|250|280|4287|4325|61[.]1)\b/g) || []).length;
            return { heading, labels, placeholders, values };
          });
          entry.spec_probe = specValues;
          entry.checks.specs_rendered =
            specValues.heading && specValues.labels >= 4 && specValues.values >= 4;
        }

        for (const [k, ok] of Object.entries(entry.checks)) {
          if (!ok) recordDefect("functional", `${spec.route} @${vp.name}`, `check failed: ${k}`);
        }
        if (probe.brokenImages.length) {
          recordDefect("functional", `${spec.route} @${vp.name}`,
            `broken images: ${probe.brokenImages.slice(0, 3).join(", ")}`);
        }
        if (probe.overflow.length) {
          recordDefect("functional", `${spec.route} @${vp.name}`,
            `horizontal overflow: ${probe.overflow.join(", ")}`);
        }
        if (probe.smallTargets.length) {
          recordDefect("functional", `${spec.route} @${vp.name}`,
            `touch targets <32px: ${probe.smallTargets.slice(0, 4).join(" | ")}`);
        }
        if (cls.hydration.length) {
          recordDefect("functional", `${spec.route} @${vp.name}`,
            `hydration: ${cls.hydration[0].slice(0, 160)}`);
        }
        if (cls.other.length) {
          recordDefect("functional", `${spec.route} @${vp.name}`,
            `console: ${cls.other[0].slice(0, 160)}`);
        }

        // ── interactions ──────────────────────────────────────────────────
        if (spec.name === "search") {
          const input = page.locator('input[type="search"], input[type="text"]').first();
          if (await input.count()) {
            // real query against verified-price data (Honda City exists with
            // official price + full text) — assert RESULTS, not mere mention
            await input.fill("City");
            await input.press("Enter");
            await page.waitForLoadState("networkidle").catch(() => {});
            await page.waitForTimeout(800);
            const shot = path.join(SHOTS, `search-interaction-${vp.name}.png`);
            await page.screenshot({ path: shot });
            entry.screenshots.push(path.relative(REPO, shot));
            const probe2 = await collectPageProbe(page);
            const bodyText = await page.evaluate(() => document.body.innerText);
            const mentionsCity = /City/i.test(bodyText);
            const ok = mentionsCity && probe2.priceCount > 0;
            entry.interactions.push({
              action: "type 'City' + Enter",
              ok,
              detail: `mentions=${mentionsCity} price_matches=${probe2.priceCount}`,
            });
            if (!ok) recordDefect("functional", `/search @${vp.name}`, "City search returned no priced results");
          } else {
            entry.interactions.push({ action: "search input", ok: false, detail: "no input found" });
            recordDefect("functional", `/search @${vp.name}`, "search input missing");
          }
        }

        if (spec.name === "cars" && vp.name === "mobile") {
          // real compare control: per-card toggle buttons with aria-pressed
          const toggles = page.locator('button[aria-pressed]');
          const n = await toggles.count();
          let selected = 0;
          for (let i = 0; i < Math.min(n, 6) && selected < 2; i++) {
            const b = toggles.nth(i);
            if (await b.isVisible().catch(() => false)) {
              await b.click({ force: true }).catch(() => {});
              await page.waitForTimeout(150);
              if ((await b.getAttribute("aria-pressed")) === "true") selected++;
            }
          }
          await page.waitForTimeout(400);
          const shot = path.join(SHOTS, `cars-compare-selection-${vp.name}.png`);
          await page.screenshot({ path: shot });
          entry.screenshots.push(path.relative(REPO, shot));
          const bodyText = await page.evaluate(() => document.body.innerText);
          const bar = /เลือกแล้ว\s+2\/4/.test(bodyText);
          const compareHref = await page
            .locator('a[href*="/compare?ids="]')
            .first().getAttribute("href").catch(() => null);
          const ok = selected === 2 && bar && !!compareHref && /ids=.*,/.test(compareHref || "");
          entry.interactions.push({
            action: `toggle ${selected} compare buttons (aria-pressed)`,
            ok,
            detail: `selection_bar=${bar} href=${compareHref}`,
          });
          if (!ok) {
            recordDefect("functional", "/cars @mobile",
              `compare handoff: selected=${selected} bar=${bar} href=${compareHref}`);
          }
        }

        if (spec.name.startsWith("compare")) {
          const shot = path.join(SHOTS, `${spec.name}-${vp.name}-viewport.png`);
          await page.screenshot({ path: shot });
          entry.screenshots.push(path.relative(REPO, shot));
          // difference filter / toggle if present
          const diff = page.locator('input[type="checkbox"], button').filter({ hasText: /difference|ต่าง|違い/i }).first();
          const diffCount = await page.locator('input[type="checkbox"]').count();
          if (diffCount > 0) {
            const before = await page.locator("#comparison-rows tr:visible").count();
            const diffRows = await page.locator('#comparison-rows tr[data-different="true"]').count();
            const b = page.locator('input[type="checkbox"]').first();
            await b.click({ force: true }).catch(() => {});
            await page.waitForTimeout(400);
            const after = await page.locator("#comparison-rows tr:visible").count();
            const shot2 = path.join(SHOTS, `${spec.name}-${vp.name}-toggled.png`);
            await page.screenshot({ path: shot2 });
            entry.screenshots.push(path.relative(REPO, shot2));
            // correctness: after the toggle NO identical (data-different=false)
            // row may stay visible — narrowing count is informational only
            const identicalVisible = await page
              .locator('#comparison-rows tr[data-different="false"]:visible')
              .count();
            const checked = await b.isChecked().catch(() => false);
            const ok = diffCount > 0 && checked && identicalVisible === 0;
            entry.interactions.push({
              action: "toggle difference-only filter",
              ok,
              detail: `rows ${before} -> ${after}, different_rows=${diffRows}, identical_visible_after=${identicalVisible}, checked=${checked}`,
            });
            if (!ok) recordDefect("functional", `${spec.route} @${vp.name}`,
              `difference filter state: identical_visible_after=${identicalVisible} checked=${checked}`);
            // restore full view for the record
            await b.click({ force: true }).catch(() => {});
            await page.waitForTimeout(300);
          } else {
            entry.interactions.push({ action: "toggle compare filter", ok: false, detail: "no filter control present" });
            recordDefect("functional", `${spec.route} @${vp.name}`, "difference filter control missing");
          }
        }

        if (spec.name === "ai-ask") {
          const hasInput = (await page.locator("textarea, input[type=text]").count()) > 0;
          const bodyText = await page.evaluate(() => document.body.innerText);
          const loginWall = /login|sign in|เข้าสู่ระบบ|auth/i.test(bodyText);
          entry.checks.ai_reachable_state_recorded = hasInput || loginWall || bodyText.length > 60;
          entry.ai_state = hasInput ? "input_ready" : loginWall ? "login_wall" : "other";
          entry.interactions.push({
            action: "record ai-ask availability (no AI request sent)",
            ok: entry.checks.ai_reachable_state_recorded,
            detail: entry.ai_state,
          });
        }
      } catch (err) {
        entry.error = String(err).slice(0, 400);
        recordDefect("blocker", `${spec.route} @${vp.name}`, entry.error);
      } finally {
        page.off("console", onConsole);
        page.off("pageerror", onErr);
        page.off("requestfailed", onReqFail);
        page.off("response", onResp);
        manifest.pages.push(entry);
      }
    }
    await context.close();
  }

  await browser.close();

  const totals = {
    pages: manifest.pages.length,
    pages_with_any_failed_check: manifest.pages.filter((p) =>
      Object.values(p.checks || {}).some((v) => v === false)).length,
    console_error_pages: manifest.pages.filter((p) => p.console_errors.length || p.page_errors.length).length,
    screenshots: manifest.pages.reduce((n, p) => n + p.screenshots.length, 0),
    defects: defects.length,
    by_severity: defects.reduce((m, d) => ((m[d.severity] = (m[d.severity] || 0) + 1), m), {}),
  };
  manifest.summary = totals;
  manifest.defects = defects;
  fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2));
  fs.writeFileSync(LOG, logLines.join("\n") + "\n");

  console.log("MANIFEST_JSON=" + path.join(OUT, "manifest.json"));
  console.log(JSON.stringify(totals));

  if (server) {
    try {
      process.kill(-server.pid, "SIGTERM");
    } catch { /* group already gone */ }
  }
  process.exit(0);
}

main().catch((e) => {
  console.error("FATAL", e);
  fs.writeFileSync(LOG, logLines.join("\n") + "\nFATAL " + String(e) + "\n");
  process.exit(1);
});
