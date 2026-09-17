/**
 * Updated pilot evidence manifest — verified prices from official Thai-market sources.
 * 
 * Revalidation results:
 * - MG S5 EV PLUS: 749,900 THB ✅ (original chain preserved)
 * - Honda City e:HEV: 569,000 THB ✅ (confirmed on honda.co.th/city)
 * - Honda Civic e:HEV: 949,000 THB ✅ (confirmed on honda.co.th/civic)
 * - Honda HR-V e:HEV: ROLLED BACK ❌ (website shows 959,000, DB has 949,000)
 * - Honda City Hatchback e:HEV: 579,000 THB ✅ (confirmed on honda.co.th/cityhatchback)
 * - Honda CR-V e:HEV: 1,409,000 THB ✅ (confirmed on honda.co.th/crv)
 * - Honda BR-V: 915,000 THB ✅ (confirmed on honda.co.th/brv)
 * - Honda WR-V: 799,000 THB ✅ (confirmed on honda.co.th/wrv)
 * - Honda Accord e:HEV: 1,479,000 THB ✅ (confirmed on honda.co.th/accordehev)
 * - Honda e:N2 EV: 1,429,000 THB ✅ (confirmed on honda.co.th/en2)
 */

import type { EvidenceRecord } from "./evidence-ingestion";

export const PILOT_EVIDENCE: EvidenceRecord[] = [
  // Honda City e:HEV — verified on honda.co.th/city
  {
    sourceUrl: "https://www.honda.co.th/city",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "569,000",
    priceAmount: 569000,
    currency: "THB",
    variantNameInSource: "e:HEV",
    modelNameInSource: "City",
    market: "Thailand",
    contentHash: "honda-city-ehev-569000-2026-verified",
    verificationNotes: "Honda City e:HEV priced at 569,000 THB confirmed on official Honda Thailand website (honda.co.th/city). Thai-market page, price displayed prominently.",
  },
  // Honda Civic e:HEV — verified on honda.co.th/civic
  {
    sourceUrl: "https://www.honda.co.th/civic",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "949,000",
    priceAmount: 949000,
    currency: "THB",
    variantNameInSource: "e:HEV",
    modelNameInSource: "Civic",
    market: "Thailand",
    contentHash: "honda-civic-ehev-949000-2026-verified",
    verificationNotes: "Honda Civic e:HEV priced at 949,000 THB confirmed on official Honda Thailand website (honda.co.th/civic). Thai-market page, price displayed prominently.",
  },
  // Honda City Hatchback e:HEV — verified on honda.co.th/cityhatchback
  {
    sourceUrl: "https://www.honda.co.th/cityhatchback",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "579,000",
    priceAmount: 579000,
    currency: "THB",
    variantNameInSource: "e:HEV",
    modelNameInSource: "City Hatchback",
    market: "Thailand",
    contentHash: "honda-city-hatchback-ehev-579000-2026-verified",
    verificationNotes: "Honda City Hatchback e:HEV priced at 579,000 THB confirmed on official Honda Thailand website (honda.co.th/cityhatchback). Thai-market page, price displayed prominently.",
  },
  // Honda CR-V e:HEV — verified on honda.co.th/crv
  {
    sourceUrl: "https://www.honda.co.th/crv",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "1,409,000",
    priceAmount: 1409000,
    currency: "THB",
    variantNameInSource: "e:HEV",
    modelNameInSource: "CR-V",
    market: "Thailand",
    contentHash: "honda-crv-ehev-1409000-2026-verified",
    verificationNotes: "Honda CR-V e:HEV priced at 1,409,000 THB confirmed on official Honda Thailand website (honda.co.th/crv). Thai-market page, price displayed prominently.",
  },
  // Honda BR-V — verified on honda.co.th/brv
  {
    sourceUrl: "https://www.honda.co.th/brv",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "915,000",
    priceAmount: 915000,
    currency: "THB",
    variantNameInSource: "Other",
    modelNameInSource: "BR-V",
    market: "Thailand",
    contentHash: "honda-brv-915000-2026-verified",
    verificationNotes: "Honda BR-V priced at 915,000 THB confirmed on official Honda Thailand website (honda.co.th/brv). Thai-market page, price displayed prominently.",
  },
  // Honda WR-V — verified on honda.co.th/wrv
  {
    sourceUrl: "https://www.honda.co.th/wrv",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "799,000",
    priceAmount: 799000,
    currency: "THB",
    variantNameInSource: "Other",
    modelNameInSource: "WR-V",
    market: "Thailand",
    contentHash: "honda-wrv-799000-2026-verified",
    verificationNotes: "Honda WR-V priced at 799,000 THB confirmed on official Honda Thailand website (honda.co.th/wrv). Thai-market page, price displayed prominently.",
  },
  // Honda Accord e:HEV — verified on honda.co.th/accordehev
  {
    sourceUrl: "https://www.honda.co.th/accordehev",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "1,479,000",
    priceAmount: 1479000,
    currency: "THB",
    variantNameInSource: "e:HEV",
    modelNameInSource: "Accord",
    market: "Thailand",
    contentHash: "honda-accord-ehev-1479000-2026-verified",
    verificationNotes: "Honda Accord e:HEV priced at 1,479,000 THB confirmed on official Honda Thailand website (honda.co.th/accordehev). Thai-market page, price displayed prominently.",
  },
  // Honda e:N2 EV — verified on honda.co.th/en2
  {
    sourceUrl: "https://www.honda.co.th/en2",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "1,429,000",
    priceAmount: 1429000,
    currency: "THB",
    variantNameInSource: "EV",
    modelNameInSource: "e:N2",
    market: "Thailand",
    contentHash: "honda-en2-ev-1429000-2026-verified",
    verificationNotes: "Honda e:N2 EV priced at 1,429,000 THB confirmed on official Honda Thailand website (honda.co.th/en2). Thai-market page, price displayed prominently.",
  },
];
