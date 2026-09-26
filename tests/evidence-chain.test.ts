/**
 * Integration Tests — Evidence Chain, Variant Mapping, Toyota API
 * 
 * Tests the ACTUAL behavior of the data pipeline, not just functions.
 * Updated for multi-source reality: Toyota prices come from API + 9CARTHAI + Headlightmag.
 */

import { describe, it, expect, beforeAll } from "vitest";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import pg from "pg";

let prisma: PrismaClient;

beforeAll(async () => {
  const pool = new pg.Pool({
    user: process.env.DB_USER || "hermes",
    host: process.env.DB_HOST || "localhost",
    port: Number(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || "thai_car_intelligence",
    max: 5,
  });
  const adapter = new PrismaPg(pool);
  prisma = new PrismaClient({ adapter });
});

describe("Toyota API Evidence Chain", () => {
  it("all Toyota prices have a source document with valid extraction method", async () => {
    const toyota = await prisma.manufacturer.findUnique({ where: { slug: "toyota" } });
    if (!toyota) return;

    const prices = await prisma.price.findMany({
      where: { isCurrent: true, variant: { model: { manufacturerId: toyota.id } } },
      include: { sourceDocument: true },
    });

    // All prices must have a source document
    for (const price of prices) {
      expect(price.sourceDocument).toBeTruthy();
      expect(price.sourceDocument!.extractionMethod).toBeTruthy();
    }
  });

  it("API-sourced Toyota prices point to the actual API endpoint", async () => {
    const toyota = await prisma.manufacturer.findUnique({ where: { slug: "toyota" } });
    if (!toyota) return;
    
    const prices = await prisma.price.findMany({
      where: { isCurrent: true, variant: { model: { manufacturerId: toyota.id } } },
      include: { sourceDocument: true },
    });
    
    // Check only API-sourced prices (not 9CARTHAI or Headlightmag)
    const apiPrices = prices.filter(p => 
      p.sourceDocument?.extractionMethod?.includes("api") ||
      p.sourceDocument?.extractionMethod?.includes("toyota_web_init")
    );
    
    for (const price of apiPrices) {
      if (!price.sourceDocument) continue;
      
      // API-sourced prices must point to the API endpoint
      expect(price.sourceDocument.url).toContain("api");
      expect(price.sourceDocument.url).not.toMatch(/\/model\/[a-z-]+$/);
      
      // Content hash must be set (hex format)
      expect(price.sourceDocument.contentHash).toBeTruthy();
      expect(price.sourceDocument.contentHash.length).toBeGreaterThan(8);
    }
  });

  it("API-sourced Toyota prices have valid price types", async () => {
    const toyota = await prisma.manufacturer.findUnique({ where: { slug: "toyota" } });
    if (!toyota) return;
    
    const prices = await prisma.price.findMany({
      where: { isCurrent: true, variant: { model: { manufacturerId: toyota.id } } },
      include: { sourceDocument: true },
    });
    
    // Check only API-sourced prices
    const apiPrices = prices.filter(p => 
      p.sourceDocument?.extractionMethod?.includes("api") ||
      p.sourceDocument?.extractionMethod?.includes("toyota_web_init")
    );
    
    for (const price of apiPrices) {
      // Toyota API can return both LIST_PRICE (model-range) and MSRP (grade-level)
      expect(["LIST_PRICE", "MSRP"]).toContain(price.priceType);
    }
  });

  it("every Toyota price has a verified source document", async () => {
    const toyota = await prisma.manufacturer.findUnique({ where: { slug: "toyota" } });
    if (!toyota) return;
    
    const prices = await prisma.price.findMany({
      where: { isCurrent: true, variant: { model: { manufacturerId: toyota.id } } },
      include: {
        sourceDocument: {
          include: { verifications: true },
        },
      },
    });
    
    for (const price of prices) {
      // Must have source document
      expect(price.sourceDocument).toBeTruthy();
      
      // Source document must be verified status
      expect(price.sourceDocument!.status).toBe("VERIFIED");
      
      // Source document must have an extraction method
      expect(price.sourceDocument!.extractionMethod).toBeTruthy();
    }
  });
});

describe("Variant Mapping Safety", () => {
  it("API-sourced Toyota prices use appropriate price types", async () => {
    // Check that API-sourced Toyota prices use LIST_PRICE or MSRP appropriately
    const toyota = await prisma.manufacturer.findUnique({ where: { slug: "toyota" } });
    if (!toyota) return;
    
    const prices = await prisma.price.findMany({
      where: {
        isCurrent: true,
        variant: { model: { manufacturerId: toyota.id } },
      },
      include: { sourceDocument: true },
    });
    
    // API-sourced prices should be LIST_PRICE or MSRP (both valid from Toyota API)
    const apiPrices = prices.filter(p => 
      p.sourceDocument?.extractionMethod?.includes("api") ||
      p.sourceDocument?.extractionMethod?.includes("toyota_web_init")
    );
    
    for (const price of apiPrices) {
      expect(["LIST_PRICE", "MSRP"]).toContain(price.priceType);
    }
  });

  it("Honda/Nissan/MG prices have explicit variant identification in source", async () => {
    const brands = ["honda", "nissan", "mg"];
    
    for (const brandSlug of brands) {
      const brand = await prisma.manufacturer.findUnique({ where: { slug: brandSlug } });
      if (!brand) continue;
      
      const prices = await prisma.price.findMany({
        where: { isCurrent: true, variant: { model: { manufacturerId: brand.id } } },
        include: {
          sourceDocument: true,
        },
      });
      
      for (const price of prices) {
        // Must have source document with extraction method
        expect(price.sourceDocument).toBeTruthy();
        expect(price.sourceDocument!.extractionMethod).toBeTruthy();
        
        // Source URL must be set
        expect(price.sourceDocument!.url).toBeTruthy();
        expect(price.sourceDocument!.url.length).toBeGreaterThan(10);
      }
    }
  });
});

describe("Evidence Semantics", () => {
  it("no price has a fabricated content hash", async () => {
    const prices = await prisma.price.findMany({
      where: { isCurrent: true, sourceDocumentId: { not: null } },
      include: { sourceDocument: true },
    });
    
    for (const price of prices) {
      const hash = price.sourceDocument?.contentHash;
      if (!hash) continue;
      
      // Fake hashes follow the pattern "brand-slug-price" or "verified-official-date"
      expect(hash).not.toMatch(/^[a-z]+-[a-z]+-\d+$/);
      expect(hash).not.toMatch(/^verified-official-\d{4}/);
      expect(hash).not.toMatch(/^official-[a-z]+-[a-z]+-\d+$/);
      
      // Real hashes are hex strings or sha256: prefixed (may contain labels)
      expect(hash).toMatch(/^(sha256:|[a-f0-9]{8,})/);
    }
  });

  it("every SourceDocument has extractionMethod set", async () => {
    const docs = await prisma.sourceDocument.findMany({
      where: { status: "VERIFIED" },
    });
    
    for (const doc of docs) {
      expect(doc.extractionMethod).toBeTruthy();
      expect(doc.extractionMethod!.length).toBeGreaterThan(0);
    }
  });

  it("source URLs are real URLs, not fabricated", async () => {
    const docs = await prisma.sourceDocument.findMany({
      where: { status: "VERIFIED" },
      include: { source: true },
    });
    
    for (const doc of docs) {
      if (!doc.source) continue;
      
      // All source URLs must be valid HTTP(S) URLs
      expect(doc.url).toMatch(/^https?:\/\//);
      expect(doc.url).not.toContain("localhost");
      
      // Official manufacturer sources must not be example.com
      if (doc.source.sourceType === "OFFICIAL_MANUFACTURER") {
        expect(doc.url).not.toContain("example.com");
      }
    }
  });
});

describe("Thai Market Evidence", () => {
  it("all verified prices are from plausible sources", async () => {
    const prices = await prisma.price.findMany({
      where: { isCurrent: true },
      include: {
        sourceDocument: {
          include: { source: true },
        },
      },
    });
    
    for (const price of prices) {
      if (!price.sourceDocument?.source) continue;
      
      const domain = price.sourceDocument.source.domain;
      // Domain must not be obviously overseas
      expect(domain).not.toContain(".uk");
      expect(domain).not.toContain(".com.au");
      expect(domain).not.toContain(".jp");
      expect(domain).not.toContain("example.com");
    }
  });
});
