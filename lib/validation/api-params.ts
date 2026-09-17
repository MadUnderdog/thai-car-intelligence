/** Shared validation constants for public API routes. */

export const VALID_FUEL_TYPES = ["BEV", "HEV", "ICE", "PHEV"] as const;
export type FuelType = (typeof VALID_FUEL_TYPES)[number];

export const DEFAULT_PAGE_SIZE = 24;
export const MAX_PAGE_SIZE = 100;
export const MAX_QUERY_LENGTH = 120;

/** Validate fuelType against known values. Returns undefined if not provided or invalid. */
export function validateFuelType(value: string | null): FuelType | undefined {
  if (!value) return undefined;
  const upper = value.toUpperCase();
  return (VALID_FUEL_TYPES as readonly string[]).includes(upper) ? (upper as FuelType) : undefined;
}

/** Validate a UUID v4 format (loose — checks dash-separated hex groups). */
export function isValidUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

/** Validate and parse limit parameter. Returns undefined if not provided, null if invalid. */
export function validateLimit(raw: string | null, defaultValue?: number): number | null {
  if (!raw) return defaultValue ?? null;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1 || n > MAX_PAGE_SIZE) return null;
  return Math.floor(n);
}

/** Validate and parse page parameter. Returns undefined if not provided, null if invalid. */
export function validatePage(raw: string | null, defaultValue?: number): number | null {
  if (!raw) return defaultValue ?? null;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return null;
  return Math.floor(n);
}

/** Validate and parse maxPrice parameter. Returns undefined if not provided, null if invalid. */
export function validateMaxPrice(raw: string | null): number | null {
  if (!raw) return undefined as unknown as null;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) return null;
  return n;
}
