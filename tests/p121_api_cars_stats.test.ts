/**
 * P121 — live read-only contract: /api/cars must expose REAL platform stats.
 *
 * Red-before: written against HEAD 8fda850 BEFORE any implementation change.
 * The homepage stats block reads data.stats.totalVariants / evCount /
 * hevCount / totalManufacturers — fields the route did not return, so the
 * public UI rendered 18 / 0 / 0 / 0 (misleading "EV=0, brands=0" claims).
 *
 * Contract asserted here (no writes, real DB):
 *   A1  response.stats exists with all four fields (non-null integers)
 *   B1  stats equal an INDEPENDENTLY written reference query over ACTIVE rows
 *   C1  evCount + hevCount <= totalActiveVariants; every value > 0
 *   D1  pre-existing contract preserved: results[] + total still present
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import pg from "pg";
import { GET as getCars } from "../src/app/api/cars/route";

const client = new pg.Client({
  user: process.env.DB_USER || "hermes",
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "thai_car_intelligence",
});

const REFERENCE_STATS = `
  SELECT
    (SELECT count(*) FROM "Variant" WHERE status = 'ACTIVE')::int AS total_active_variants,
    (SELECT count(*) FROM "Variant"
      WHERE status = 'ACTIVE' AND "fuelType" IN ('BEV', 'EV'))::int AS ev_count,
    (SELECT count(*) FROM "Variant"
      WHERE status = 'ACTIVE' AND "fuelType" = 'HEV')::int AS hev_count,
    (SELECT count(*) FROM "Manufacturer" WHERE status = 'ACTIVE')::int AS manufacturers
`;

describe("P121 /api/cars stats contract (live, read-only)", () => {
  beforeAll(async () => {
    await client.connect();
  });
  afterAll(async () => {
    await client.end();
  });

  async function fetchCars(): Promise<any> {
    const res = await getCars(new Request("http://localhost/api/cars?limit=1"));
    expect(res.status).toBe(200);
    return res.json();
  }

  it("A1: response carries stats with all four integer fields", async () => {
    const body = await fetchCars();
    expect(body.stats).toBeDefined();
    for (const key of ["totalActiveVariants", "evCount", "hevCount", "totalManufacturers"]) {
      expect(typeof body.stats?.[key], `stats.${key} must be a number`).toBe("number");
      expect(Number.isInteger(body.stats[key]), `stats.${key} must be an integer`).toBe(true);
    }
  });

  it("B1: stats match an independent reference query over ACTIVE rows", async () => {
    const body = await fetchCars();
    const ref = (await client.query(REFERENCE_STATS)).rows[0];
    expect(body.stats?.totalActiveVariants).toBe(ref.total_active_variants);
    expect(body.stats?.evCount).toBe(ref.ev_count);
    expect(body.stats?.hevCount).toBe(ref.hev_count);
    expect(body.stats?.totalManufacturers).toBe(ref.manufacturers);
  });

  it("C1: values are non-zero and internally consistent", async () => {
    const body = await fetchCars();
    expect(body.stats?.totalActiveVariants).toBeGreaterThan(0);
    expect(body.stats?.evCount).toBeGreaterThan(0);
    expect(body.stats?.hevCount).toBeGreaterThan(0);
    expect(body.stats?.totalManufacturers).toBeGreaterThan(0);
    expect(body.stats.evCount + body.stats.hevCount).toBeLessThanOrEqual(
      body.stats.totalActiveVariants
    );
  });

  it("D1: pre-existing list contract preserved (results + total)", async () => {
    const body = await fetchCars();
    expect(Array.isArray(body.results)).toBe(true);
    expect(typeof body.total).toBe("number");
    expect(body.results.length).toBeGreaterThan(0);
  });
});
