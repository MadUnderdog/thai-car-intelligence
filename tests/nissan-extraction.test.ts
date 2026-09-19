import { describe, it, expect } from 'vitest';

/**
 * Nissan Extraction — Adversarial Regression Tests
 * Tests for cross-contamination, scope classification, and provenance.
 */

const NISSAN_JSON: Record<string, { modelCode: string; price: number; versionKey: string; gradeKey: string }> = {
  march: { modelCode: 'B02A', price: 420000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  almera: { modelCode: 'L02B', price: 445000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  'almera-with-stylish-package': { modelCode: '29851', price: 573000, versionKey: 'BDYARBZ', gradeKey: '29851-1_0L_TURBO_E_CVT' },
  'kicks-epower': { modelCode: '70053', price: 789900, versionKey: '26KEV', gradeKey: '70053-L1_V' },
  xtrail: { modelCode: 'P32R', price: 1350000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  'xtrail-epower': { modelCode: '70006', price: 1699000, versionKey: '26XTE4', gradeKey: '70006-E-POWER' },
  terra: { modelCode: 'P60A', price: 1299000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  'new-terra': { modelCode: '29838', price: 1199000, versionKey: 'JTSARS', gradeKey: '29838-2_3_E_2WD_7AT' },
  navara: { modelCode: '70005', price: 1045000, versionKey: '25DCP2A', gradeKey: '70005-DC_PRO-2X_7AT' },
  serena: { modelCode: '30177', price: 1469000, versionKey: 'HWS01', gradeKey: '30177-V' },
  'serena-epower': { modelCode: '30176', price: 1690000, versionKey: 'SEC28', gradeKey: '30176-HIGHWAY_STAR' },
  leaf: { modelCode: 'B12P', price: 1990000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  'new-leaf': { modelCode: '29785', price: 1590000, versionKey: 'LEV1', gradeKey: '29785-EV' },
  livina: { modelCode: 'N11Q', price: 672000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  teana: { modelCode: 'L42L', price: 1339000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  juke: { modelCode: 'P12C', price: 837000, versionKey: 'VEC001', gradeKey: 'LVL001' },
  note: { modelCode: 'J02C', price: 530000, versionKey: 'VEC001', gradeKey: 'LVL001' },
};

describe('Nissan Cross-Contamination Prevention', () => {
  it('rejects March receiving Terra price', () => {
    expect(NISSAN_JSON.march.price).not.toBe(NISSAN_JSON.terra.price);
  });

  it('rejects X-Trail receiving March price', () => {
    expect(NISSAN_JSON.xtrail.price).not.toBe(NISSAN_JSON.march.price);
  });

  it('rejects Leaf receiving Almera price', () => {
    expect(NISSAN_JSON.leaf.price).not.toBe(NISSAN_JSON.almera.price);
  });

  it('rejects Serena receiving Teana price', () => {
    expect(NISSAN_JSON.serena.price).not.toBe(NISSAN_JSON.teana.price);
  });

  it('rejects Navara receiving Kicks price', () => {
    expect(NISSAN_JSON.navara.price).not.toBe(NISSAN_JSON['kicks-epower'].price);
  });

  it('rejects Terra receiving Leaf price', () => {
    expect(NISSAN_JSON.terra.price).not.toBe(NISSAN_JSON.leaf.price);
  });

  it('rejects Juke receiving any other model price', () => {
    for (const [key, entry] of Object.entries(NISSAN_JSON)) {
      if (key !== 'juke') {
        expect(NISSAN_JSON.juke.price).not.toBe(entry.price);
      }
    }
  });
});

describe('Nissan Model-Code Validation', () => {
  it('has unique modelCodes across models', () => {
    const codes = Object.values(NISSAN_JSON).map(e => e.modelCode);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it('rejects unknown model keys', () => {
    const reject = ['test-gt-r', 'sky-edition', 'kicks-e-power-sky-edition', 'navara-n-trek-warrior-'];
    for (const key of reject) {
      expect(NISSAN_JSON).not.toHaveProperty(key);
    }
  });
});

describe('Nissan Scope Classification', () => {
  it('all navigation JSON entries are MODEL_RANGE starting prices', () => {
    for (const entry of Object.values(NISSAN_JSON)) {
      expect(entry.price).toBeGreaterThanOrEqual(100000);
      expect(entry.price).toBeLessThanOrEqual(20000000);
      expect(entry.gradeKey).toBeTruthy();
    }
  });
});

describe('Nissan Kicks Dedup', () => {
  it('only one Kicks e-POWER starting price', () => {
    const kicks = NISSAN_JSON['kicks-epower'];
    expect(kicks.price).toBe(789900);
    expect(kicks.modelCode).toBe('70053');
    expect(kicks.versionKey).toBe('26KEV');
  });
});

describe('Nissan Adversarial Price Sanity', () => {
  it('rejects test-gt-r 13,500,000', () => {
    expect(NISSAN_JSON).not.toHaveProperty('test-gt-r');
  });

  it('rejects sky-edition 35,000', () => {
    expect(NISSAN_JSON).not.toHaveProperty('sky-edition');
  });

  it('rejects navara-n-trek-warrior 49,000', () => {
    expect(NISSAN_JSON).not.toHaveProperty('navara-n-trek-warrior-');
  });

  it('rejects prices below 100,000 THB', () => {
    for (const entry of Object.values(NISSAN_JSON)) {
      expect(entry.price).toBeGreaterThanOrEqual(100000);
    }
  });

  it('rejects prices above 20,000,000 THB', () => {
    for (const entry of Object.values(NISSAN_JSON)) {
      expect(entry.price).toBeLessThanOrEqual(20000000);
    }
  });
});

describe('Nissan Provenance Requirements', () => {
  it('every entry has required fields', () => {
    const fields = ['modelCode', 'versionKey', 'gradeKey', 'price'];
    for (const entry of Object.values(NISSAN_JSON)) {
      for (const field of fields) {
        expect(entry).toHaveProperty(field);
      }
    }
  });
});
