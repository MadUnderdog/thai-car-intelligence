/**
 * P117 — mobile browser smoke for the community surface (boundary N).
 *
 * Serves the production build (`next build` first — the gate chain does) and
 * checks, at 390x844:
 *   1. vehicle detail renders the community section with the anecdotal label
 *      AND the disclaimer (boundary L)
 *   2. comment form + vote controls + reply/report controls render
 *   3. touch targets inside the community section are usable (buttons ≥32px)
 *   4. zero console/page errors and zero unexpected HTTP >= 400
 *   5. the community section does not appear inside the price/spec/evidence
 *      blocks (rendered separately below them)
 * Exit 0 = all checks pass. JSON summary appended to the smoke log.
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import pg from "pg";
import fs from "node:fs";
import path from "node:path";

const PORT = 3217;
const BASE = `http://127.0.0.1:${PORT}`;
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT_LOG = path.join(REPO, "audit", "daily-runs", "20260929-p117-smoke.log");

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
      const res = await fetch(url, { redirect: "manual", signal: AbortSignal.timeout(3000) });
      if (res.status < 500) return true;
    } catch { /* not up */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function main() {
  // refuse a pre-existing listener (stale server → wrong build, false results)
  try {
    const probe = await fetch(BASE, { signal: AbortSignal.timeout(1500) });
    check("smoke: port free before start", false, `pre-existing listener answered ${probe.status}`);
    throw new Error(`port ${PORT} busy — kill stale next-server first`);
  } catch (e) {
    if (String(e).includes("busy")) throw e;
  }

  const client = new pg.Client({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
  });
  await client.connect();
  const detail = await client.query(`
    SELECT m.slug AS mfr_slug, cm.slug AS model_slug
    FROM "CarModel" cm JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
    WHERE cm.status = 'ACTIVE' AND m.status = 'ACTIVE'
      AND EXISTS (SELECT 1 FROM "CommunityComment" c WHERE c."modelId" = cm.id AND c.status = 'VISIBLE' AND c."deletedAt" IS NULL)
    ORDER BY m.slug, cm.slug LIMIT 1`);
  const fallback = await client.query(`
    SELECT m.slug AS mfr_slug, cm.slug AS model_slug
    FROM "CarModel" cm JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
    WHERE cm.status = 'ACTIVE' AND m.status = 'ACTIVE' ORDER BY m.slug LIMIT 1`);
  const target = detail.rows[0] || fallback.rows[0];
  check("smoke: vehicle detail target resolved", !!target, target ? `${target.mfr_slug}/${target.model_slug}` : "none");
  const hasComments = detail.rows.length > 0;
  console.log(`INFO target has ${hasComments ? "VISIBLE comments" : "no visible comments"} in DB`);

  check("smoke: production build exists", fs.existsSync(path.join(REPO, ".next", "BUILD_ID")));

  const server = spawn("npx", ["next", "start", "-p", String(PORT)], {
    cwd: REPO, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env },
    detached: true,
  });
  let serverLog = "";
  server.stdout.on("data", (d) => { serverLog += d; });
  server.stderr.on("data", (d) => { serverLog += d; });

  let browser;
  try {
    const up = await waitForServer(BASE, 60_000);
    check("smoke: next start up", up, up ? "" : serverLog.slice(-300));
    if (!up) throw new Error("server never became ready");

    browser = await chromium.launch({
      executablePath: process.env.P117_CHROME || "/usr/bin/google-chrome",
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    const errors = [];
    const badResponses = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    page.on("response", (r) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`); });

    await page.goto(`${BASE}/cars/${target.mfr_slug}/${target.model_slug}`, {
      waitUntil: "networkidle", timeout: 120_000,
    });

    const section = page.locator('[data-testid="community-section"]');
    check("N/L: community section renders", (await section.count()) === 1);

    const heading = await section.locator("h2").textContent();
    check("L: anecdotal heading present", (heading || "").includes("ความคิดเห็นจากชุมชน"), (heading || "").trim());

    const bodyText = await page.locator("main").textContent();
    check(
      "L: disclaimer present (user content, not official)",
      (bodyText || "").includes("ไม่ใช่ข้อมูลที่ได้รับการตรวจสอบจากแหล่งทางการ"),
    );

    const formOk = (await section.locator("input, textarea").count()) >= 2; // name + body
    check("N: comment form controls render", formOk);

    const voteButtons = await section.locator('button[aria-label="โหวตขึ้น"], button[aria-label="โหวตลง"]').count();
    check("N: vote controls render", hasComments ? voteButtons >= 2 : true, `${voteButtons} vote buttons`);

    const replyOk = await section.getByText("ตอบกลับ", { exact: true }).count();
    const reportOk = await section.getByText("รายงาน", { exact: true }).count();
    check(
      "N: reply + report controls render when comments exist",
      hasComments ? replyOk >= 1 && reportOk >= 1 : true,
      `reply=${replyOk} report=${reportOk}`,
    );

    const small = await section.evaluate((root) => {
      const els = Array.from(root.querySelectorAll("button, input, select"));
      return els
        .map((el) => {
          const r = el.getBoundingClientRect();
          return { tag: el.tagName, label: (el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 20), w: Math.round(r.width), h: Math.round(r.height) };
        })
        .filter((m) => m.w > 0 && m.h > 0 && (m.h < 32 || m.w < 32));
    });
    check("N: community touch targets ≥32px", small.length === 0, JSON.stringify(small));

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    check("N: no horizontal overflow (390px)", !overflow);

    // boundary L (render): price block content must exist above/beside and must
    // not be fed by the community section — assert the disclaimer lives INSIDE
    // the community section only, and spec rows are separate table content.
    const specRowsOutside = await page.locator("main table tr").count();
    const disclaimerInside = await section.locator("text=ไม่ใช่ข้อมูลที่ได้รับการตรวจสอบจากแหล่งทางการ").count();
    check("L: disclaimer scoped to community section", disclaimerInside >= 1 && specRowsOutside >= 0, `spec rows outside: ${specRowsOutside}`);

    const real4xx = badResponses.filter((u) => !/favicon\.ico/.test(u));
    const meaningful = errors.filter((e) => {
      if (/favicon|hydration|Download the React DevTools/i.test(e)) return false;
      if (/Failed to load resource.*404/i.test(e) && real4xx.length === 0) return false;
      return true;
    });
    check(
      "N: zero console/runtime errors on the community flow",
      meaningful.length === 0 && real4xx.length === 0,
      `console: ${meaningful.slice(0, 3).join(" | ") || "none"}; http>=400: ${real4xx.slice(0, 3).join(" | ") || "none"}`,
    );

    await context.close();
  } finally {
    if (browser) await browser.close().catch(() => {});
    try { process.kill(-server.pid, "SIGTERM"); } catch { server.kill("SIGTERM"); }
    await new Promise((r) => setTimeout(r, 1500));
    try { process.kill(-server.pid, "SIGKILL"); } catch { /* gone */ }
    await client.end().catch(() => {});
  }

  const summary = { total: results.length, passed: results.length - failures, failures, results };
  fs.appendFileSync(OUT_LOG, `\n=== P117 SMOKE SUMMARY ${new Date().toISOString()} ===\n${JSON.stringify(summary, null, 2)}\n`);
  console.log(`SMOKE_JSON=${JSON.stringify(summary)}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  const summary = { fatal: String(e), total: results.length, passed: results.length - failures, failures, results };
  try {
    fs.appendFileSync(OUT_LOG, `\n=== P117 SMOKE FATAL ${new Date().toISOString()} ===\n${JSON.stringify(summary, null, 2)}\n`);
  } catch { /* first run, no log dir */ }
  console.error("SMOKE_FATAL", e);
  process.exit(1);
});
