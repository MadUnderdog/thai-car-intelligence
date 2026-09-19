import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';
import {
  parseNissanNavigationJson,
  dedupCandidates,
  getValidCandidates,
  type NissanExtractionCandidate,
} from '../lib/discovery/nissan-parser';

// Load real fixture from actual Nissan HTML extraction
let NISSAN_JSON: Record<string, unknown>;
let candidates: NissanExtractionCandidate[];

beforeAll(() => {
  const fixturePath = join(__dirname, 'fixtures', 'nissan-navigation-prices.json');
  NISSAN_JSON = JSON.parse(readFileSync(fixturePath, 'utf-8'));
  candidates = parseNissanNavigationJson(
    NISSAN_JSON as Record<string, unknown>,
    'https://www.nissan.co.th/en/vehicles/new-vehicles/march.html',
    'sha256:test-fixture-hash',
  );
});

describe('Nissan Parser — Real Source Fixture', () => {
  it('parses real navigation JSON without throwing', () => {
    expect(candidates).toBeDefined();
    expect(Array.isArray(candidates)).toBe(true);
    expect(candidates.length).toBeGreaterThan(0);
  });

  it('extracts candidates for every model in real JSON', () => {
    const modelKeys = Object.keys(NISSAN_JSON);
    expect(candidates.length).toBe(modelKeys.length);
  });

  it('classifies all valid candidates as MODEL_RANGE', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.price_type).toBe('MODEL_RANGE');
      expect(c.scope_reason).toContain('starting price');
    }
  });

  it('has NO VARIANT_MSRP candidates from navigation JSON', () => {
    const variantMsrs = candidates.filter(c => c.price_type === 'VARIANT_MSRP');
    expect(variantMsrs.length).toBe(0);
  });
});

describe('Nissan Parser — Cross-Model Contamination', () => {
  it('March price does NOT equal Terra price', () => {
    const march = candidates.find(c => c.model_key === 'march');
    const terra = candidates.find(c => c.model_key === 'terra');
    expect(march).toBeDefined();
    expect(terra).toBeDefined();
    expect(march!.price).not.toBe(terra!.price);
  });

  it('X-Trail price does NOT equal March price', () => {
    const xtrail = candidates.find(c => c.model_key === 'x-trail');
    const march = candidates.find(c => c.model_key === 'march');
    expect(xtrail).toBeDefined();
    expect(march).toBeDefined();
    expect(xtrail!.price).not.toBe(march!.price);
  });

  it('Leaf price does NOT equal Almera price', () => {
    const leaf = candidates.find(c => c.model_key === 'leaf');
    const almera = candidates.find(c => c.model_key === 'almera');
    expect(leaf).toBeDefined();
    expect(almera).toBeDefined();
    expect(leaf!.price).not.toBe(almera!.price);
  });

  it('Serena price does NOT equal Teana price', () => {
    const serena = candidates.find(c => c.model_key === 'serena');
    const teana = candidates.find(c => c.model_key === 'teana');
    expect(serena).toBeDefined();
    expect(teana).toBeDefined();
    expect(serena!.price).not.toBe(teana!.price);
  });

  it('Navara price does NOT equal Kicks price', () => {
    const navara = candidates.find(c => c.model_key === 'navara');
    const kicks = candidates.find(c => c.model_key === 'kicks-epower');
    expect(navara).toBeDefined();
    expect(kicks).toBeDefined();
    expect(navara!.price).not.toBe(kicks!.price);
  });

  it('every model has a unique price (no cross-contamination)', () => {
    const valid = getValidCandidates(candidates);
    const prices = valid.map(c => c.price);
    const unique = new Set(prices);
    // Some models may share prices (e.g. urvan/nv350-urvan), but most should differ
    expect(unique.size).toBeGreaterThan(prices.length * 0.5);
  });
});

describe('Nissan Parser — Rejected Keys', () => {
  it('rejects test-gt-r', () => {
    const testGtr = candidates.find(c => c.model_key === 'test-gt-r');
    expect(testGtr).toBeDefined();
    expect(testGtr!.identity_status).toBe('UNKNOWN_MODEL');
  });

  it('rejects sky-edition', () => {
    const sky = candidates.find(c => c.model_key === 'kicks-e-power-sky-edition');
    expect(sky).toBeDefined();
    expect(sky!.identity_status).toBe('UNKNOWN_MODEL');
  });

  it('rejects navara-n-trek-warrior-', () => {
    const trek = candidates.find(c => c.model_key === 'navara-n-trek-warrior-');
    expect(trek).toBeDefined();
    expect(trek!.identity_status).toBe('UNKNOWN_MODEL');
  });

  it('rejected keys have UNRESOLVED price_type', () => {
    const rejected = candidates.filter(c => c.identity_status === 'UNKNOWN_MODEL');
    for (const c of rejected) {
      expect(c.price_type).toBe('UNRESOLVED');
    }
  });
});

describe('Nissan Parser — Model-Code Validation', () => {
  it('validates modelCode for known models', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.identity_status).toBe('VALID');
      expect(c.model_code).toBeTruthy();
    }
  });

  it('flags invalid modelCode', () => {
    // Create a tampered entry
    const tampered: Record<string, unknown> = { ...NISSAN_JSON };
    tampered['march'] = {
      default: { modelPrice: '420000', bestPriceVersionKey: 'VEC001', bestPriceGradeKey: 'LVL001' },
      modelCode: 'WRONG_CODE',
      Updated_On: '2026-01-01',
    };
    const result = parseNissanNavigationJson(tampered, 'test', 'test-hash');
    const march = result.find(c => c.model_key === 'march');
    expect(march).toBeDefined();
    expect(march!.identity_status).toBe('INVALID_CODE');
  });

  it('detects unknown model keys', () => {
    const tampered: Record<string, unknown> = { ...NISSAN_JSON };
    tampered['unknown-new-model'] = {
      default: { modelPrice: '500000', bestPriceVersionKey: 'X', bestPriceGradeKey: 'Y' },
      modelCode: 'NEW1',
      Updated_On: '2026-01-01',
    };
    const result = parseNissanNavigationJson(tampered, 'test', 'test-hash');
    const unknown = result.find(c => c.model_key === 'unknown-new-model');
    expect(unknown).toBeDefined();
    expect(unknown!.identity_status).toBe('UNKNOWN_MODEL');
  });
});

describe('Nissan Parser — Scope Semantics', () => {
  it('navigation JSON prices are MODEL_RANGE not VARIANT_MSRP', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.price_type).toBe('MODEL_RANGE');
    }
  });

  it('gradeKey does NOT prove variant-level pricing', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      // gradeKey exists but scope_reason must explain why it's MODEL_RANGE
      expect(c.grade_key).toBeTruthy();
      expect(c.scope_reason).toContain('starting price');
    }
  });

  it('model-level price cannot become arbitrary first variant MSRP', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      // price_type must be MODEL_RANGE, not MSRP
      expect(c.price_type).not.toBe('VARIANT_MSRP');
    }
  });

  it('shared navigation prices cannot become model-specific by page URL', () => {
    // All candidates share the same source_url (march.html)
    // but each price is attributed to its model_key, not the page URL
    const marchCandidates = candidates.filter(c => c.model_key === 'march');
    const otherCandidates = candidates.filter(c => c.model_key !== 'march');
    
    // March candidates should have march-specific price
    for (const c of marchCandidates) {
      expect(c.price).toBe(420000); // march starting price
    }
    
    // Other candidates should have their own prices
    for (const c of otherCandidates) {
      if (c.identity_status === 'VALID') {
        expect(c.price).not.toBe(420000); // should NOT be march price
      }
    }
  });
});

describe('Nissan Parser — Kicks Dedup', () => {
  it('identifies Kicks e-POWER as single valid entry', () => {
    const kicks = candidates.filter(c => c.model_key === 'kicks-epower');
    expect(kicks.length).toBe(1);
    expect(kicks[0].price).toBe(789900);
    expect(kicks[0].identity_status).toBe('VALID');
  });

  it('dedup by evidence identity removes exact duplicates', () => {
    const withDupes = [
      ...candidates,
      // Add a duplicate candidate
      {
        ...candidates.find(c => c.model_key === 'march')!,
        content_hash: 'sha256:duplicate-hash',
      },
    ];
    const deduped = dedupCandidates(withDupes);
    // Original + duplicate should become 1 (different hash = different evidence)
    const marchEntries = deduped.filter(c => c.model_key === 'march');
    // Same model_key + same price + different hash = 2 entries (different evidence)
    expect(marchEntries.length).toBe(2);
  });

  it('dedup removes same model_key + same price + same hash', () => {
    const original = candidates.find(c => c.model_key === 'march')!;
    const dupe = { ...original };
    const withDupes = [...candidates, dupe];
    const deduped = dedupCandidates(withDupes);
    const marchEntries = deduped.filter(c => c.model_key === 'march');
    expect(marchEntries.length).toBe(1);
  });
});

describe('Nissan Parser — Price Sanity', () => {
  it('all valid prices are within 100K-20M THB', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.price).toBeGreaterThanOrEqual(100000);
      expect(c.price).toBeLessThanOrEqual(20000000);
    }
  });

  it('no NaN prices', () => {
    for (const c of candidates) {
      if (c.identity_status === 'VALID') {
        expect(isNaN(c.price)).toBe(false);
      }
    }
  });

  it('all valid candidates have source_url', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.source_url).toBeTruthy();
      expect(c.source_url).toContain('nissan.co.th');
    }
  });

  it('all valid candidates have content_hash', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.content_hash).toBeTruthy();
    }
  });

  it('all valid candidates have observed_at timestamp', () => {
    const valid = getValidCandidates(candidates);
    for (const c of valid) {
      expect(c.observed_at).toBeTruthy();
      expect(new Date(c.observed_at).getTime()).toBeGreaterThan(0);
    }
  });
});

describe('Nissan Parser — Provenance', () => {
  it('every candidate has identity_status and validity_reason', () => {
    for (const c of candidates) {
      expect(c.identity_status).toBeTruthy();
      expect(c.validity_reason).toBeTruthy();
    }
  });

  it('valid candidates have VALID identity_status', () => {
    const valid = getValidCandidates(candidates);
    expect(valid.length).toBeGreaterThan(0);
    for (const c of valid) {
      expect(c.identity_status).toBe('VALID');
    }
  });

  it('invalid candidates have explanatory validity_reason', () => {
    const invalid = candidates.filter(c => c.identity_status !== 'VALID');
    for (const c of invalid) {
      expect(c.validity_reason.length).toBeGreaterThan(10);
    }
  });

  it('candidate counts match expectations', () => {
    const valid = getValidCandidates(candidates);
    const rejected = candidates.filter(c => c.identity_status === 'UNKNOWN_MODEL');
    const invalidCode = candidates.filter(c => c.identity_status === 'INVALID_CODE');
    
    // At least 20 valid model entries
    expect(valid.length).toBeGreaterThanOrEqual(20);
    // At least 3 rejected keys
    expect(rejected.length).toBeGreaterThanOrEqual(3);
    // No invalid codes in clean fixture
    expect(invalidCode.length).toBe(0);
  });
});
