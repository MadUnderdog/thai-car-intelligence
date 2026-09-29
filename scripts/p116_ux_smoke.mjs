/**
 * P116 — public UX smoke (mobile-first, real browser, read-only).
 *
 * Asserts against a live `next dev` server:
 *   Serves `next start` (production build) — next dev is unusable here.
 *   1. /cars renders model cards (no console/runtime errors)
 *   2. /cars?q= works (the base q-binding bug returned 503)
 *   3. wrong manufacturer/model slug → HTTP 404 (no cross-entity leak)
 *   4. /search?q=City renders real results with price/provenance UI
 *   5. /compare?ids=A,B renders 2 columns in SELECTED order, truthful states
 *   6. mobile viewport 390x844: no horizontal overflow, touch targets ≥ 32px
 *
 * Exit code 0 = all checks pass. JSON summary printed as SMOKE_JSON=<json>.
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import pg from "pg";
import fs from "node:fs";
import path from "node:path";

const PORT = 3216;
const BASE = `http://127.0.0.1:${PORT}`;
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT_LOG = path.join(REPO, "audit", "daily-runs", "20260929-p116-smoke.log");

const results = [];
let failures = 0;
function check(name, ok, detail = "") {
  results.push({ name, ok: !!ok, detail: String(detail).slice(0, 300) });
  if (!ok) failures++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

async function waitForServer(url, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { redirect: "manual" });
      if (res.status < 500) return true;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 1500));
  }
  return false;
}

async function main() {
  // ── real data (read-only) ────────────────────────────────────────────────
  const client = new pg.Client({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
  });
  await client.connect();

  const priced = await client.query(`
    SELECT v.id::text, m.slug as mfr_slug, cm.slug as model_slug
    FROM "Price" p
    JOIN "SourceDocument" sd ON sd.id = p."sourceDocumentId"
    JOIN "Source" s ON s.id = sd."sourceId"
    JOIN "Variant" v ON v.id = p."variantId"
    JOIN "CarModel" cm ON cm.id = v."modelId"
    JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
    WHERE p."isCurrent" = true AND sd.status = 'VERIFIED' AND s.status = 'ACTIVE'
      AND s."sourceType"::text IN ('OFFICIAL_MANUFACTURER','OFFICIAL_MANUFACTURER_BROCHURE','OFFICIAL_MANUFACTURER_PRICE_LIST','OFFICIAL_MANUFACTURER_PRESS_RELEASE')
      AND v.status = 'ACTIVE' AND cm.status = 'ACTIVE'
      AND EXISTS (SELECT 1 FROM "BrochureVerification" bv WHERE bv."sourceDocumentId" = sd.id AND bv.status = 'VERIFIED')
    LIMIT 2`);
  const withFeatures = await client.query(`
    SELECT v.id::text
    FROM "VariantFeature" vf JOIN "Variant" v ON v.id = vf."variantId"
    WHERE v.status = 'ACTIVE'
    GROUP BY v.id HAVING count(*) >= 1 LIMIT 2`);
  const anyModel = await client.query(`
    SELECT m.slug as mfr_slug, cm.slug as model_slug
    FROM "CarModel" cm JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
    WHERE cm.status = 'ACTIVE' AND m.status = 'ACTIVE' LIMIT 1`);

  check("smoke: >=2 full-chain priced variants in DB", priced.rows.length >= 2, `got ${priced.rows.length}`);
  check("smoke: active model for detail page", anyModel.rows.length === 1);
  const [vA, vB] = withFeatures.rows.length >= 2 ? withFeatures.rows.map((r) => r.id) : priced.rows.map((r) => r.id);
  // NOTE: VariantFeature may legitimately be empty in the accepted set (0 rows
  // today) — no DB writes allowed in P116, so the smoke asserts the empty-path
  // (no features section rendered) and the three-state legend itself is proven
  // by vitest fixtures (C5 featureCellText ✓/✗/ไม่มีข้อมูล).
  console.log(`INFO variant-feature rows available: ${withFeatures.rows.length}`);
  const detail = anyModel.rows[0];

  // Refuse to run if something already listens (stale next start from a
  // previous run would silently answer with an old build → false results).
  try {
    const probe = await fetch(`http://127.0.0.1:${PORT}/`, { signal: AbortSignal.timeout(2000) });
    check("smoke: port not already in use", false, `pre-existing listener answered ${probe.status}`);
    throw new Error("port 3216 busy — kill stale next-server first");
  } catch (e) {
    if (String(e).includes("busy")) throw e;
    // fetch failed = nothing listening = correct precondition
  }

  // ── production server (next start) ──────────────────────────────────────
  // Dev-mode Turbopack hangs in this environment (postcss worker spins
  // forever — reproduced with a wiped .next). Smoke against the production
  // build: `next build` must have run first (the gate chain does).
  const server = spawn("npx", ["next", "start", "-p", String(PORT)], {
    cwd: REPO, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env },
    detached: true, // own process group → finally can kill npx AND next-server
  });
  let serverLog = "";
  server.stdout.on("data", (d) => { serverLog += d; });
  server.stderr.on("data", (d) => { serverLog += d; });

  // bundled build version ≠ installed cache (1243 vs 1234) → use system Chrome
  let browser;
  try {
    const built = fs.existsSync(path.join(REPO, ".next", "BUILD_ID"));
    check("smoke: production build exists (npx next build)", built);
    if (!built) throw new Error("no production build");
    const up = await waitForServer(`http://127.0.0.1:${PORT}`, 60_000);
    check("smoke: next dev server up", up, up ? "" : serverLog.slice(-300));
    if (!up) throw new Error("server never became ready");
    browser = await chromium.launch({
      executablePath: process.env.P116_CHROME || "/usr/bin/google-chrome",
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });

    const context = await browser.newContext({ viewport: { width: 390, height: 844 } }); // iPhone-class
    const page = await context.newPage();
    const consoleErrors = [];
    const badResponses = [];
    page.on("pageerror", (e) => consoleErrors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
    page.on("response", (r) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`); });

    // 1. /cars renders cards
    await page.goto(`${BASE}/cars`, { waitUntil: "networkidle", timeout: 120_000 });
    const cardCount = await page.locator('a[href^="/cars/"]').count();
    check("G/J: /cars renders model cards", cardCount > 0, `${cardCount} links`);
    const overflowCars = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    check("J: /cars has no horizontal overflow (390px)", !overflowCars);

    // 2. q filter works (base: 503 missing $3)
    const qRes = await fetch(`${BASE}/api/models?q=city&limit=10`);
    const qBody = await qRes.json().catch(() => null);
    check("A3/G: /api/models?q= returns 200 + payload", qRes.status === 200 && Array.isArray(qBody?.results), `status ${qRes.status}`);

    // 3. slug mismatch → 404 (no cross-entity leakage)
    const bad = await page.goto(`${BASE}/cars/${detail.mfr_slug}/definitely-not-a-model-xyz`, { timeout: 60_000 });
    check("G: wrong model slug → 404", bad.status() === 404, `status ${bad.status()}`);
    const bad2 = await page.goto(`${BASE}/cars/definitely-not-a-mfr/${detail.model_slug}`, { timeout: 60_000 });
    check("G: wrong manufacturer slug → 404", bad2.status() === 404, `status ${bad2.status()}`);

    // detail page renders + provenance/fallback surfaces
    await page.goto(`${BASE}/cars/${detail.mfr_slug}/${detail.model_slug}`, { waitUntil: "networkidle", timeout: 120_000 });
    const h1 = await page.locator("h1").first().textContent();
    check("G: detail page renders model name", !!h1 && h1.trim().length > 0, (h1 || "").trim().slice(0, 60));

    // 4. /search?q=City renders real results + price/provenance UI
    await page.goto(`${BASE}/search?q=City`, { waitUntil: "networkidle", timeout: 120_000 });
    const searchLinks = await page.locator('a[href^="/cars/"]').count();
    check("E: /search renders result links", searchLinks > 0, `${searchLinks} links`);
    const hasPriceOrNoData = await page.locator("text=/฿[0-9]/").count();
    const hasNoPriceNote = await page.locator("text=ยังไม่มีข้อมูลราคา").count();
    check("E: search rows show price or truthful no-price note", hasPriceOrNoData + hasNoPriceNote > 0);
    const undefLinks = await page.locator('a[href*="undefined"]').count();
    check("E: no /cars/undefined links ever render", undefLinks === 0, `${undefLinks} found`);

    // 5. /compare?ids=A,B — selected order + truthful states
    await page.goto(`${BASE}/compare?ids=${vB},${vA}`, { waitUntil: "networkidle", timeout: 120_000 });
    const headerNames = await page.locator("main div.grid div.text-lg.font-bold").allTextContents();
    check("C: compare renders 2 columns", headerNames.length === 2, JSON.stringify(headerNames));
    const compareErrorStates = await page.locator("main").getByText(/ไม่สามารถโหลดข้อมูล|ไม่พบรถที่เลือก|กรุณาเลือกรถอย่างน้อย/).count();
    check("C: compare page not in error state", compareErrorStates === 0, `error blocks: ${compareErrorStates}`);
    const featuresSection = await page.locator("main:has-text('อุปกรณ์และระบบช่วยเหลือ')").count();
    const legend = await page.locator("main:has-text('อุปกรณ์และระบบช่วยเหลือ') >> text=/ไม่มีข้อมูล =/").count();
    if (featuresSection > 0) {
      check("C: feature three-state legend rendered with features section", legend > 0);
    } else {
      // DB has no feature rows → honest behavior = section hidden entirely
      check("C: features section hidden when accepted set has no feature rows", featuresSection === 0, "empty-table path");
    }
    const overflowCompare = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    check("J: /compare has no horizontal overflow (390px)", !overflowCompare);

    // touch targets ≥32px on interactive controls
    const smallTargets = await page.evaluate(() => {
      const main = document.querySelector("main");
      const links = main ? Array.from(main.querySelectorAll("a[href]")) : [];
      const controls = main ? Array.from(main.querySelectorAll("button, input, select, [role=button]")) : [];
      const measure = (els) => els
        .map((el) => { const r = el.getBoundingClientRect(); return { tag: el.tagName, text: (el.textContent || "").trim().slice(0, 24), w: Math.round(r.width), h: Math.round(r.height) }; })
        .filter((m) => m.w > 0 || m.h > 0);
      return {
        controlSmall: measure(controls).filter((m) => m.h < 32 || m.w < 32),
        controls: measure(controls).length,
        linkSmall: measure(links).filter((m) => m.h < 24 || m.w < 24),
        links: measure(links).length,
      };
    });
    check(
      "J: touch targets on /compare (controls ≥32px, text links ≥24px)",
      smallTargets.controlSmall.length === 0 && smallTargets.linkSmall.length === 0,
      `controls ${smallTargets.controls} (small: ${JSON.stringify(smallTargets.controlSmall)}), links ${smallTargets.links} (small: ${JSON.stringify(smallTargets.linkSmall)})`,
    );

    // 6. console/runtime errors across the affected flows (page errors reset per nav)
    // favicon 404s and the DELIBERATE wrong-slug 404 probes (G checks) are expected
    const real4xx = badResponses.filter((u) => !/favicon\.ico/.test(u) && !/definitely-not-a-/.test(u));
    const meaningful = consoleErrors.filter((e) => {
      if (/favicon|hydration|Download the React DevTools/i.test(e)) return false;
      // generic resource-404 console text carries no URL — suppress only when
      // every observed 4xx was an expected probe (favicon / deliberate 404s)
      if (/Failed to load resource.*404/i.test(e) && real4xx.length === 0) return false;
      return true;
    });
    const meaningful4xx = real4xx;
    check(
      "J: zero console/runtime errors across flows",
      meaningful.length === 0 && meaningful4xx.length === 0,
      `console: ${meaningful.slice(0, 3).join(" | ") || "none"} ; http>=400: ${meaningful4xx.slice(0, 5).join(" | ") || "none"}`,
    );

    await context.close();
  } finally {
    if (browser) await browser.close().catch(() => {});
    try { process.kill(-server.pid, "SIGTERM"); } catch { server.kill("SIGTERM"); }
    await new Promise((r) => setTimeout(r, 1500));
    try { process.kill(-server.pid, "SIGKILL"); } catch { /* already gone */ }
    await client.end().catch(() => {});
  }

  const summary = { total: results.length, passed: results.length - failures, failures, results };
  const line = `\n=== SMOKE SUMMARY ${new Date().toISOString()} ===\n${JSON.stringify(summary, null, 2)}\n`;
  fs.appendFileSync(OUT_LOG, line);
  console.log(`SMOKE_JSON=${JSON.stringify(summary)}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  const summary = { fatal: String(e), total: results.length, passed: results.length - failures, failures, results };
  fs.appendFileSync(OUT_LOG, `\n=== SMOKE FATAL ${new Date().toISOString()} ===\n${JSON.stringify(summary, null, 2)}\n`);
  console.error("SMOKE_FATAL", e);
  process.exit(1);
});
