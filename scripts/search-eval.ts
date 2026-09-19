import "dotenv/config";

type SearchCase = {
  query: string;
  /** Expected model slug in top result, or null if no result expected */
  expectSlug: string | null;
  label: string;
};

const CASES: SearchCase[] = [
  // Exact model
  { query: "Honda City", expectSlug: "honda-city", label: "exact model" },
  { query: "MG4", expectSlug: "mg4", label: "exact model (MG4)" },
  { query: "BYD Atto 3", expectSlug: "atto-3", label: "exact model (Atto 3)" },
  // Thai alias
  { query: "ฮอนด้า ซิตี้", expectSlug: "honda-city", label: "Thai alias (ฮอนด้า ซิตี้)" },
  { query: "เอ็มจี โฟร์", expectSlug: "mg4", label: "Thai alias (เอ็มจี โฟร์)" },
  { query: "โตโยต้า คัมรี", expectSlug: "toyota-camry", label: "Thai alias (โตโยต้า คัมรี)" },
  // Brand only
  { query: "Honda", expectSlug: "honda-city", label: "brand only (Honda)" },
  { query: "MG", expectSlug: "mg4", label: "brand only (MG)" },
  // Fuel type in query
  { query: "EV ราคา", expectSlug: null, label: "fuel type (EV)" },
  { query: "ไฮบริด Honda", expectSlug: "honda-city", label: "Thai fuel type (ไฮบริด)" },
  // Price
  { query: "รถไม่เกิน 800000", expectSlug: null, label: "price filter (ไม่เกิน 800000)" },
  { query: "ราคาถูกที่สุด", expectSlug: null, label: "cheapest" },
  // Body type intent
  { query: "SUV Honda", expectSlug: "honda-cr-v", label: "body type (SUV Honda)" },
  { query: "แฮทช์แบ็ก MG", expectSlug: "mg4", label: "Thai body type (แฮทช์แบ็ก MG)" },
  // Variant
  { query: "Honda City Hatchback", expectSlug: "honda-city-hb", label: "variant (City Hatchback)" },
  { query: "Civic Type R", expectSlug: "honda-civic-tr", label: "variant (Civic Type R)" },
  // Compare intent
  { query: "เปรียบเทียบ Honda City กับ MG4", expectSlug: null, label: "compare intent" },
  // Unknown
  { query: "Tesla Cybertruck", expectSlug: null, label: "unknown model" },
  { query: " Ferrari ", expectSlug: null, label: "unsupported brand" },
  // Partial match
  { query: "Accord", expectSlug: "honda-accord", label: "partial (Accord)" },
];

async function search(q: string): Promise<{ results: Array<{ slug: string }>; total: number }> {
  const params = new URLSearchParams({ q, limit: "5" });
  const res = await fetch(`http://localhost:3099/api/search?${params}`);
  return res.json();
}

async function main() {
  let pass = 0;
  let total = 0;

  for (const c of CASES) {
    total++;
    try {
      const data = await search(c.query);
      const topSlug = data.results?.[0]?.slug || null;
      const ok = c.expectSlug === null
        ? data.total === 0 || !topSlug  // no result expected
        : topSlug === c.expectSlug;      // specific result expected
      if (ok) pass++;
      console.log(`${ok ? "✓" : "✗"} [${c.label}] "${c.query}" → top=${topSlug} (expected ${c.expectSlug ?? "none"}) total=${data.total}`);
    } catch (e) {
      console.log(`✗ [${c.label}] "${c.query}" → ERROR: ${e}`);
    }
  }

  console.log(`\n=== Search evaluation: ${pass}/${total} ${pass === total ? "ALL PASS" : ""} ===`);
}

main().catch(console.error);
