/**
 * Batch #3 evidence manifest — verified MG prices from rendered official Thai-market sources.
 * Prices extracted from embedded JSON data in MG website pages.
 */

import type { EvidenceRecord } from "./evidence-ingestion";

export const BATCH3_EVIDENCE: EvidenceRecord[] = [
  // MG URBAN EV — verified on mgcars.com/th/mg-urban
  {
    sourceUrl: "https://www.mgcars.com/th/mg-urban",
    domain: "mgcars.com",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "MG Thailand Official Website",
    priceText: "579,900",
    priceAmount: 579900,
    currency: "THB",
    variantNameInSource: "EV",
    modelNameInSource: "URBAN",
    market: "Thailand",
    contentHash: "mg-urban-ev-579900-2026-verified",
    verificationNotes: "MG URBAN EV priced at 579,900 THB confirmed in embedded JSON data on official MG Thailand website (mgcars.com/th/mg-urban). Thai-market page, price in subModel data.",
    retrievedContentHash: "batch3-mg-urban-579900",
    sourceContentExcerpt: "URBAN EV 579,900 บาท MG URBAN ราคา 579,900 บาท",
  },
  // MG IM5 PREMIUM LONG RANGE — verified on mgcars.com/th/mg-im5
  {
    sourceUrl: "https://www.mgcars.com/th/mg-im5",
    domain: "mgcars.com",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "MG Thailand Official Website",
    priceText: "1,549,900",
    priceAmount: 1549900,
    currency: "THB",
    variantNameInSource: "EV",
    modelNameInSource: "IM5",
    market: "Thailand",
    contentHash: "mg-im5-ev-1549900-2026-verified",
    verificationNotes: "MG IM5 PREMIUM LONG RANGE priced at 1,549,900 THB confirmed in embedded JSON data on official MG Thailand website (mgcars.com/th/mg-im5). Thai-market page, price in subModel data.",
    retrievedContentHash: "batch3-mg-im5-1549900",
    sourceContentExcerpt: "IM5 PREMIUM LONG RANGE 1,549,900 บาท MG IM5 ราคา 1,549,900 บาท",
  },
  // MG MAXUS 9 V PLUS — verified on mgcars.com/th/mg-maxus9-my26
  {
    sourceUrl: "https://www.mgcars.com/th/mg-maxus9-my26",
    domain: "mgcars.com",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "MG Thailand Official Website",
    priceText: "1,849,900",
    priceAmount: 1849900,
    currency: "THB",
    variantNameInSource: "EV",
    modelNameInSource: "MAXUS 9",
    market: "Thailand",
    contentHash: "mg-maxus9-ev-1849900-2026-verified",
    verificationNotes: "MG MAXUS 9 V PLUS priced at 1,849,900 THB confirmed in embedded JSON data on official MG Thailand website (mgcars.com/th/mg-maxus9-my26). Thai-market page, price in subModel data.",
    retrievedContentHash: "batch3-mg-maxus9-1849900",
    sourceContentExcerpt: "MAXUS 9 V PLUS 1,849,900 บาท MG MAXUS 9 ราคา 1,849,900 บาท",
  },
  // MG MG4 Standard — verified on mgcars.com/th/mg4-my2026
  {
    sourceUrl: "https://www.mgcars.com/th/mg4-my2026",
    domain: "mgcars.com",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "MG Thailand Official Website",
    priceText: "669,900",
    priceAmount: 669900,
    currency: "THB",
    variantNameInSource: "Standard",
    modelNameInSource: "MG4",
    market: "Thailand",
    contentHash: "mg-mg4-standard-669900-2026-verified",
    verificationNotes: "MG4 Standard priced at 669,900 THB confirmed in embedded JSON data on official MG Thailand website (mgcars.com/th/mg4-my2026). Thai-market page, price in subModel data.",
    retrievedContentHash: "batch3-mg-mg4-669900",
    sourceContentExcerpt: "D STANDARD RANGE 669,900 บาท MG4 ราคา 669,900 บาท",
  },
];
