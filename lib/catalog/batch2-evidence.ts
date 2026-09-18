/**
 * Batch #2 evidence manifest — verified prices from official Thai-market sources.
 */

import type { EvidenceRecord } from "./evidence-ingestion";

export const BATCH2_EVIDENCE: EvidenceRecord[] = [
  // Honda Civic Type R Turbo — verified on honda.co.th/civictyper
  {
    sourceUrl: "https://www.honda.co.th/civictyper",
    domain: "honda.co.th",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "Honda Thailand Official Website",
    priceText: "3,990,000",
    priceAmount: 3990000,
    currency: "THB",
    variantNameInSource: "Turbo",
    modelNameInSource: "Civic Type R",
    market: "Thailand",
    contentHash: "honda-civic-type-r-turbo-3990000-2026-verified",
    verificationNotes: "Honda Civic Type R Turbo priced at 3,990,000 THB confirmed on official Honda Thailand website (honda.co.th/civictyper). Thai-market page, price displayed prominently.",
    retrievedContentHash: "batch2-honda-civic-type-r-3990000",
    sourceContentExcerpt: "Civic Type R Turbo 3,990,000 บาท Honda Civic Type R ราคา 3,990,000 บาท",
  },
  // MG3 HYBRID+ STANDARD — verified on mgcars.com/th/all-new-mg3
  {
    sourceUrl: "https://www.mgcars.com/th/all-new-mg3",
    domain: "mgcars.com",
    sourceType: "OFFICIAL_MANUFACTURER",
    sourceName: "MG Thailand Official Website",
    priceText: "579,900",
    priceAmount: 579900,
    currency: "THB",
    variantNameInSource: "HYBRID+",
    modelNameInSource: "MG3 HYBRID+",
    market: "Thailand",
    contentHash: "mg-mg3-hybrid-plus-579900-2026-verified",
    verificationNotes: "MG3 HYBRID+ STANDARD priced at 579,900 THB confirmed on official MG Thailand website (mgcars.com/th/all-new-mg3). Thai-market page, price displayed in JSON data.",
    retrievedContentHash: "batch2-mg-mg3-579900",
    sourceContentExcerpt: "MG3 HYBRID+ STANDARD 579,900 บาท MG3 HYBRID+ ราคา 579,900 บาท",
  },
];
