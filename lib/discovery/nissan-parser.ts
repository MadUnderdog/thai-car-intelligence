/**
 * Nissan Navigation Price JSON Parser
 * 
 * Parses the embedded JSON from nissan.co.th HTML pages.
 * The JSON contains ALL models in a single object keyed by URL slug.
 * Each model entry has a starting price, not grade-level pricing.
 * 
 * CRITICAL RULES:
 * 1. Each price belongs to its model key, NOT the page URL
 * 2. The JSON provides MODEL_RANGE starting prices, not variant MSRPs
 * 3. gradeKey/versionKey exist but do NOT prove variant-level pricing
 * 4. Unknown model keys must be flagged, not silently skipped
 * 5. Duplicate evidence from same source must be deduped by evidence identity
 */

export type NissanModelEntry = {
  default?: {
    priceDisclaimer: string;
    modelPrice: string;
    bestPriceVersionKey: string;
    bestPriceGradeKey: string;
  };
  'Retail'?: {
    priceDisclaimer: string;
    modelPrice: string;
    bestPriceVersionKey: string;
    bestPriceGradeKey: string;
  };
  'Retail with VAT'?: {
    priceDisclaimer: string;
    modelPrice: string;
    bestPriceVersionKey: string;
    bestPriceGradeKey: string;
  };
  Updated_On?: string;
  modelCode?: string;
  [key: string]: unknown;
};

export type NissanExtractionCandidate = {
  model_key: string;
  model_code: string;
  version_key: string;
  grade_key: string;
  price: number;
  price_type: 'MODEL_RANGE' | 'VARIANT_MSRP' | 'UNRESOLVED';
  scope_reason: string;
  tier: string;
  updated: string;
  source_url: string;
  content_hash: string;
  observed_at: string;
  identity_status: 'VALID' | 'UNKNOWN_MODEL' | 'INVALID_CODE' | 'NO_PRICE' | 'INVALID_PRICE';
  validity_reason: string;
};

// Known Nissan model codes (derived from source, not invented)
const KNOWN_NISSAN_CODES: Record<string, string> = {
  march: 'B02A',
  almera: 'L02B',
  'almera-with-stylish-package': '29851',
  'new-almera': '29851',
  'new-almera-22my': '29545',
  'kicks-epower': '70053',
  'kicks-e-power-with-stylish-package': '29843',
  'new-kicks': '29843',
  xtrail: 'P32R',
  'xtrail-epower': '70006',
  terra: 'P60A',
  'new-terra': '29838',
  'nissan-terra-mc': '29464',
  navara: '70005',
  'navara-single-cab': '70002',
  'new-navara-single-cab': '29637',
  'navara-king-cab': '70003',
  'new-navara-king-cab': '29624',
  'navara-calibre': '70004',
  'navara-calibre-my21': 'NACALI',
  'new-navara-calibre': '29621',
  'new-navara-pro-4x-and-pro-2x': '29643',
  'navara-pro-4x-and-pro-2x': '70005',
  serena: '30177',
  'serena-epower': '30176',
  leaf: 'B12P',
  'new-leaf': '29785',
  livina: 'N11Q',
  juke: 'P12C',
  note: 'J02C',
  teana: 'L42L',
  'nv350-urvan': 'X81C',
  urvan: 'X81C',
  pulsar: 'B12D',
  sylphy: 'L12F',
};

// Keys that must be rejected (test data, special editions, etc.)
const REJECT_KEYS = new Set([
  'test-gt-r',
  'sky-edition',
  'kicks-e-power-sky-edition',
  'navara-n-trek-warrior-',
]);

/**
 * Parse the Nissan navigation JSON and extract candidates.
 * Returns ALL entries including unknown/rejected ones for audit.
 */
export function parseNissanNavigationJson(
  jsonData: Record<string, unknown>,
  sourceUrl: string,
  contentHash: string,
): NissanExtractionCandidate[] {
  const candidates: NissanExtractionCandidate[] = [];
  const observedAt = new Date().toISOString();

  for (const [modelKey, rawModelData] of Object.entries(jsonData)) {
    const modelData = rawModelData as NissanModelEntry;
    // Find the first pricing tier
    let priceData: { modelPrice: string; bestPriceVersionKey: string; bestPriceGradeKey: string } | null = null;
    let tierName = '';

    for (const [tier, tierData] of Object.entries(modelData)) {
      if (
        typeof tierData === 'object' &&
        tierData !== null &&
        'modelPrice' in tierData &&
        'bestPriceVersionKey' in tierData &&
        'bestPriceGradeKey' in tierData
      ) {
        priceData = tierData as { modelPrice: string; bestPriceVersionKey: string; bestPriceGradeKey: string };
        tierName = tier;
        break;
      }
    }

    const modelCode = modelData.modelCode || '';
    const updated = modelData.Updated_On || '';

    if (!priceData || !priceData.modelPrice) {
      candidates.push({
        model_key: modelKey,
        model_code: modelCode,
        version_key: '',
        grade_key: '',
        price: 0,
        price_type: 'UNRESOLVED',
        scope_reason: 'No price data found',
        tier: tierName,
        updated,
        source_url: sourceUrl,
        content_hash: contentHash,
        observed_at: observedAt,
        identity_status: 'NO_PRICE',
        validity_reason: 'Entry has no modelPrice field',
      });
      continue;
    }

    const price = parseInt(priceData.modelPrice, 10);
    const versionKey = priceData.bestPriceVersionKey;
    const gradeKey = priceData.bestPriceGradeKey;

    // Check if rejected key FIRST (before price validation)
    if (REJECT_KEYS.has(modelKey)) {
      candidates.push({
        model_key: modelKey,
        model_code: modelCode,
        version_key: versionKey,
        grade_key: gradeKey,
        price,
        price_type: 'UNRESOLVED',
        scope_reason: 'Rejected key (test/special data)',
        tier: tierName,
        updated,
        source_url: sourceUrl,
        content_hash: contentHash,
        observed_at: observedAt,
        identity_status: 'UNKNOWN_MODEL',
        validity_reason: `Model key '${modelKey}' is in reject list`,
      });
      continue;
    }

    // Validate price range
    if (isNaN(price) || price < 100000 || price > 20000000) {
      candidates.push({
        model_key: modelKey,
        model_code: modelCode,
        version_key: versionKey,
        grade_key: gradeKey,
        price,
        price_type: 'UNRESOLVED',
        scope_reason: `Price ${price} outside valid range`,
        tier: tierName,
        updated,
        source_url: sourceUrl,
        content_hash: contentHash,
        observed_at: observedAt,
        identity_status: 'INVALID_PRICE',
        validity_reason: `Price ${price} is outside 100K-20M THB range`,
      });
      continue;
    }

    // Check if known model
    const expectedCode = KNOWN_NISSAN_CODES[modelKey];
    if (!expectedCode) {
      candidates.push({
        model_key: modelKey,
        model_code: modelCode,
        version_key: versionKey,
        grade_key: gradeKey,
        price,
        price_type: 'UNRESOLVED',
        scope_reason: 'Unknown model key',
        tier: tierName,
        updated,
        source_url: sourceUrl,
        content_hash: contentHash,
        observed_at: observedAt,
        identity_status: 'UNKNOWN_MODEL',
        validity_reason: `Model key '${modelKey}' not in known model registry`,
      });
      continue;
    }

    // Validate modelCode
    if (modelCode !== expectedCode) {
      candidates.push({
        model_key: modelKey,
        model_code: modelCode,
        version_key: versionKey,
        grade_key: gradeKey,
        price,
        price_type: 'UNRESOLVED',
        scope_reason: `modelCode mismatch: got '${modelCode}', expected '${expectedCode}'`,
        tier: tierName,
        updated,
        source_url: sourceUrl,
        content_hash: contentHash,
        observed_at: observedAt,
        identity_status: 'INVALID_CODE',
        validity_reason: `modelCode '${modelCode}' does not match expected '${expectedCode}' for key '${modelKey}'`,
      });
      continue;
    }

    // Valid entry — classify scope
    // CRITICAL: gradeKey exists but does NOT prove variant-level pricing
    // The navigation JSON only provides starting prices per model
    // Grade-level pricing requires model-specific page data
    candidates.push({
      model_key: modelKey,
      model_code: modelCode,
      version_key: versionKey,
      grade_key: gradeKey,
      price,
      price_type: 'MODEL_RANGE',
      scope_reason: 'Navigation JSON provides model-level starting price only; gradeKey identifies best-value grade but does not prove variant MSRP',
      tier: tierName,
      updated,
      source_url: sourceUrl,
      content_hash: contentHash,
      observed_at: observedAt,
      identity_status: 'VALID',
      validity_reason: `modelCode matches expected '${expectedCode}'; price is starting price for model`,
    });
  }

  return candidates;
}

/**
 * Dedup candidates by evidence identity.
 * Two candidates are duplicates if they have same model_key + price + content_hash.
 */
export function dedupCandidates(candidates: NissanExtractionCandidate[]): NissanExtractionCandidate[] {
  const seen = new Map<string, NissanExtractionCandidate>();
  
  for (const c of candidates) {
    const key = `${c.model_key}|${c.price}|${c.content_hash}`;
    if (!seen.has(key)) {
      seen.set(key, c);
    }
  }
  
  return Array.from(seen.values());
}

/**
 * Get valid candidates only (identity_status === 'VALID').
 */
export function getValidCandidates(candidates: NissanExtractionCandidate[]): NissanExtractionCandidate[] {
  return candidates.filter(c => c.identity_status === 'VALID');
}
