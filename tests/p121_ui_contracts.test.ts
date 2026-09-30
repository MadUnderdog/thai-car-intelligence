/**
 * P121 — UI surface source contracts (red/green pins for evidenced defects).
 *
 * Red-before: written against HEAD 8fda850 BEFORE any implementation change.
 * These pin the concrete defects found by the real-browser baseline capture
 * (audit/ui-captures/p121-20260930-baseline/):
 *   F1  touch targets < 32px on mobile: header nav, footer nav, breadcrumb
 *       links, detail sidebar action links (Button size sm → h=24), search
 *       filter button (h=20) — WCAG tap-target minimum from the wave brief
 *   F2  dead control: detail sidebar "🔖 บันทึก" button has NO handler
 *   F3  misleading breadcrumb aria-label in Chinese (面包屑导航)
 *   F4  homepage "รถยนต์ทั้งหมด" grid actually shows 12 A→Z models (mostly
 *       price-less) — label over-claims; fetch ignores sortBy so cards show
 *       "ไม่มีข้อมูลราคา"
 *   F5  footer link label "รถยนต์ทั้งหมด" points at a verified-price-scoped
 *       listing (18 variants), not "all"
 *
 * This file reads the component sources as text (no DOM): the live
 * end-to-end verification of the SAME defects is the Playwright capture
 * gate (touch_targets_ok / stats / price checks in the capture manifest).
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "..");
const read = (rel: string) => fs.readFileSync(path.join(ROOT, rel), "utf8");

describe("P121 UI surface source contracts", () => {
  it("F1a: Header desktop + mobile nav links carry a 32px minimum height", () => {
    const src = read("src/components/Header.tsx");
    const navLink = src.match(/className="([^"]*)"[^>]*>\s*\{link\.label\}/g) || [];
    expect(navLink.length).toBeGreaterThanOrEqual(1);
    for (const tag of navLink) {
      expect(tag).toContain("min-h-[32px]");
    }
  });

  it("F1b: Footer quick links carry a 32px minimum height", () => {
    const src = read("src/components/Footer.tsx");
    const quickLinks = src.match(/<Link href="\/[^"]*"[^>]*>/g) || [];
    expect(quickLinks.length).toBeGreaterThanOrEqual(3);
    for (const tag of quickLinks) {
      expect(tag).toContain("min-h-[32px]");
    }
  });

  it("F1c: Breadcrumb links carry a 32px minimum height", () => {
    const src = read("src/components/Breadcrumbs.tsx");
    const anchors = src.match(/<a href=[^>]*>/g) || [];
    expect(anchors.length).toBeGreaterThanOrEqual(1);
    for (const a of anchors) {
      expect(a).toContain("min-h-[32px]");
    }
  });

  it("F1d: Button base (all sizes incl. sm) carries a 32px minimum height", () => {
    const src = read("src/components/ui/Button.tsx");
    expect(src).toContain("min-h-[32px]");
  });

  it("F1e: search filter + clear buttons carry a 32px minimum height", () => {
    const src = read("src/app/search/SearchClient.tsx");
    const filterBtn = src.match(/<button onClick=\{\(\) => setShowFilters[^>]*>/);
    expect(filterBtn, "filter toggle button present").toBeTruthy();
    expect(filterBtn![0]).toContain("min-h-[32px]");
    const clearBtn = src.match(/<button onClick=\{clearFilters\}[^>]*>/);
    expect(clearBtn, "clear filters button present").toBeTruthy();
    expect(clearBtn![0]).toContain("min-h-[32px]");
  });

  it("F1f: homepage ViewAll links carry a 32px minimum height (all three)", () => {
    const src = read("src/app/page.tsx");
    const segments = src.split("<Link").filter((s) => s.includes("ดูทั้งหมด"));
    expect(segments.length).toBeGreaterThanOrEqual(3);
    for (const seg of segments) {
      expect(seg).toContain("min-h-[32px]");
    }
  });

  it("F2: detail sidebar has no dead 'บันทึก' button", () => {
    const src = read("src/app/cars/[manufacturer]/[model]/VehicleDetailClient.tsx");
    expect(src).not.toContain("บันทึก");
    // the two remaining primary actions stay real links
    expect(src).toContain("เปรียบเทียบรุ่นนี้");
    expect(src).toContain("ถาม AI");
  });

  it("F1g: detail custom breadcrumb + sidebar action links ≥32px", () => {
    const src = read("src/app/cars/[manufacturer]/[model]/VehicleDetailClient.tsx");
    const crumb = src.match(/<Link href="\/cars"[^>]*>/);
    expect(crumb, "detail breadcrumb link present").toBeTruthy();
    expect(crumb![0]).toContain("min-h-[32px]");
    const compareCta = src.match(/<Link href=\{`\/compare\?ids=[^>]*>/);
    expect(compareCta, "sidebar compare link present").toBeTruthy();
    expect(compareCta![0]).toContain("min-h-[32px]");
    const aiCta = src.match(/<Link href="\/ai-ask"[^>]*>/);
    expect(aiCta, "sidebar AI link present").toBeTruthy();
    expect(aiCta![0]).toContain("min-h-[32px]");
  });

  it("F3: breadcrumb nav aria-label is Thai, not a copy-paste artifact", () => {
    const src = read("src/components/Breadcrumbs.tsx");
    expect(src).not.toContain("面包屑");
    expect(src).toContain('aria-label="เส้นทางนำทาง"');
  });

  it("F4: homepage verified-price section label + price-sorted fetch", () => {
    const src = read("src/app/page.tsx");
    expect(src).toContain("sortBy=price_asc");
    expect(src).toContain("รถยนต์ที่มีราคาตรวจสอบแล้ว");
    // the old over-claiming heading must be gone
    expect(src).not.toMatch(/<h2[^>]*>\s*รถยนต์ทั้งหมด\s*<\/h2>/);
    // stats come from the API stats object; zero-fallbacks removed
    expect(src).toContain("stats.totalActiveVariants");
    expect(src).not.toContain("totalVariants || 0");
    expect(src).not.toContain("evCount || 0");
  });

  it("F8: compare hides spec groups where no vehicle has any value", () => {
    const cc = read("src/app/compare/CompareClient.tsx");
    expect(cc).toContain("hasAnyValue");
    expect(cc).toContain("if (!hasAnyValue) return null;");
  });

  it("F7: compare difference filter is wired (id + row flags + import)", () => {
    const cc = read("src/app/compare/CompareClient.tsx");
    expect(cc).toContain('import DifferenceFilter from "./DifferenceFilter"');
    expect(cc).toContain('id="comparison-rows"');
    expect(cc).toContain('data-different=');
    const df = read("src/app/compare/DifferenceFilter.tsx");
    expect(df).toContain("min-h-[32px]");
  });

  it("F6: detail renders the verified price source as a reachable link", () => {
    const src = read("src/app/cars/[manufacturer]/[model]/VehicleDetailClient.tsx");
    expect(src).toContain('data-testid="price-source-link"');
    expect(src).toContain("href={primary.priceSource.url}");
    expect(src).toContain('rel="noopener noreferrer"');
  });

  it("F5: footer no longer claims the verified-price listing is 'ทั้งหมด'", () => {
    const src = read("src/components/Footer.tsx");
    expect(src).not.toContain("รถยนต์ทั้งหมด");
  });
});
