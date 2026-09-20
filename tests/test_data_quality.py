#!/usr/bin/env python3
"""
Integration tests for data quality gates.
Tests cross-model contamination, quarantine, model dedup, and spec provenance.
"""
import sys
import os
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "thai-media-extractors"))
from importlib.util import spec_from_file_location, module_from_spec

# Load 9carthai parser
_spec = spec_from_file_location("p9c", os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "thai-media-extractors", "9carthai_parser.py"))
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)
parse_brand_page = _mod.parse_brand_page

# Load headlightmag extractor
_hl_spec = spec_from_file_location("hl", os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "thai-media-extractors", "headlightmag_extractor.py"))
_hl_mod = module_from_spec(_hl_spec)
_hl_spec.loader.exec_module(_hl_mod)
extract_prices_from_article = _hl_mod.extract_prices_from_article

PASS = 0
FAIL = 0

def assert_eq(name, actual, expected):
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}: expected {expected!r}, got {actual!r}")

def assert_true(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}: condition was false")

# ═══════════════════════════════════════════════════════════════════
# TEST 1: GR Corolla cross-model contamination
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 1: GR Corolla → Corolla Altis cross-model contamination ---")

# Simulate a BYD Seal roundup article that mentions Honda City, Civic, etc.
roundup_text = """
Toyota GR Corolla 2026 เปิดตัวราคา 4,199,000 บาท
สมรรถนะเครื่องยนต์ 268 แรงม้า แรงบิด 370 Nm
ระบบขับเคลื่อน 4 ล้อ GR-FOUR
Honda City 2026 ราคา 569,000 บาท รุ่น V
Honda Civic 2026 ราคา 999,000 บาท รุ่น e:HEV
MG MG4 2026 ราคา 799,000 บาท
BYD Dolphin 2026 ราคา 699,000 บาท รุ่น Dynamic
"""

# Extract as if this is a "GR Corolla" article
obs, rej = extract_prices_from_article(roundup_text, "GR Corolla", "toyota",
    "https://www.headlightmag.com/official-price-gr-corolla-2026/",
    "Toyota GR Corolla 2026 เปิดตัวอย่างเป็นทางการ")

# The GR Corolla article should NOT produce Honda/MG/BYD observations
obs_with_other_models = [o for o in obs if o.model not in ("GR Corolla", "__MODEL__")]
assert_eq("no cross-model prices from roundup", len(obs_with_other_models), 0)
assert_true("GR Corolla prices found", any(o.model == "GR Corolla" and o.obs_field == "price" for o in obs))

# Specs should be scoped to GR Corolla only
specs = [o for o in obs if o.obs_field in ("power_hp", "torque_nm", "battery_kwh", "range_km")]
for spec in specs:
    assert_eq(f"spec {spec.obs_field} attributed to GR Corolla", spec.model, "GR Corolla")

# ═══════════════════════════════════════════════════════════════════
# TEST 2: Single-model article (non-roundup) should extract normally
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 2: Single-model article extracts normally ---")

single_model_text = """
Honda City 2026 e:HEV RS ราคา 849,000 บาท
เครื่องยนต์ 1.5 ลิตร 109 แรงม้า แรงบิด 253 Nm
ระบบขับเคลื่อน front-wheel drive
"""

obs2, rej2 = extract_prices_from_article(single_model_text, "City", "honda",
    "https://www.headlightmag.com/honda-city-2026/",
    "Honda City 2026 e:HEV เปิดตัว")

city_prices = [o for o in obs2 if o.obs_field == "price" and o.model == "City"]
assert_true("City prices found", len(city_prices) > 0)
city_specs = [o for o in obs2 if o.obs_field in ("power_hp", "torque_nm")]
assert_true("City specs found", len(city_specs) > 0)
for spec in city_specs:
    assert_eq(f"spec {spec.obs_field} attributed to City", spec.model, "City")

# ═══════════════════════════════════════════════════════════════════
# TEST 3: BYD Seal article mentioning Honda specs (cross-model)
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 3: BYD Seal article with Honda mentions (cross-model) ---")

byd_seal_text = """
BYD Seal 2026 Dynamic RWD ราคา 1,599,000 บาท
แบตเตอรี่ 82.5 kWh ระยะทาง 520 km WLTP
กำลัง 313 hp แรงบิด 380 Nm

Honda City 2026 ราคา 569,000 บาท
Honda Civic 2026 ราคา 999,000 บาท
Honda HR-V 2026 ราคา 849,000 บาท
"""

obs3, rej3 = extract_prices_from_article(byd_seal_text, "Seal", "byd",
    "https://www.headlightmag.com/official-price-byd-seal-6-2026/",
    "BYD Seal 2026 ราคาอย่างเป็นทางการ")

# Seal prices should be found
seal_prices = [o for o in obs3 if o.obs_field == "price" and o.model == "Seal"]
assert_true("Seal prices found", len(seal_prices) > 0)

# Honda mentions should NOT produce observations (they're far from Seal context)
honda_obs = [o for o in obs3 if o.model in ("City", "Civic", "HR-V")]
assert_eq("no cross-model Honda observations", len(honda_obs), 0)

# ═══════════════════════════════════════════════════════════════════
# TEST 4: Model-range vs variant MSRP distinction
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 4: Model-range vs variant MSRP ---")

# 9CARTHAI parser needs HTML structure
range_html = "<html><body><h2>MG MG4 2026</h2><p>ราคาเริ่มต้น 599,000 - 799,000 บาท</p></body></html>"
obs4, rej4 = parse_brand_page(range_html, "mg", "https://www.9carthai.com/mg-price/")
model_ranges = [o for o in obs4 if o.scope == "MODEL" and o.obs_field == "price"]
assert_true("model-range found", len(model_ranges) >= 1)
if model_ranges:
    assert_eq("model-range not variant", model_ranges[0].variant, "__MODEL_RANGE__")
    assert_eq("model-range price_type", model_ranges[0].price_type, "LIST_PRICE")

# ═══════════════════════════════════════════════════════════════════
# TEST 5: Stale/current separation
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 5: Stale/current separation ---")

# The 9CARTHAI parser should always produce validFrom (current date)
stale_text = "ราคา Honda City 2026 รุ่น V 569,000 บาท"
obs5, rej5 = parse_brand_page(stale_text, "honda", "https://www.9carthai.com/honda-price/")
city_v = [o for o in obs5 if o.variant == "V" and o.obs_field == "price"]
if city_v:
    assert_true("validFrom is set", city_v[0].valid_from is not None)

# ═══════════════════════════════════════════════════════════════════
# TEST 6: Duplicate idempotency
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 6: Duplicate idempotency ---")

dup_text = "ราคา Honda City 2026 รุ่น V 569,000 บาท รุ่น EL 669,000 บาท"
obs6a, _ = parse_brand_page(dup_text, "honda", "https://www.9carthai.com/honda-price/")
obs6b, _ = parse_brand_page(dup_text, "honda", "https://www.9carthai.com/honda-price/")
assert_eq("idempotent: same count", len(obs6a), len(obs6b))

# Check content hashes match
hashes_a = sorted([o.content_hash for o in obs6a])
hashes_b = sorted([o.content_hash for o in obs6b])
assert_eq("idempotent: same hashes", hashes_a, hashes_b)

# ═══════════════════════════════════════════════════════════════════
# TEST 7: Cross-contamination rejection
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 7: Cross-contamination rejection ---")

# 9CARTHAI parser needs separate <h2> sections for each model
contam_html = """
<html><body>
<h2>Toyota Corolla Altis 2026</h2>
<p>รุ่น 1.8 Sport ราคา 909,000 บาท</p>
<p>รุ่น HEV ราคา 1,129,000 บาท</p>
<h2>Toyota GR Corolla 2026</h2>
<p>รุ่น GR ราคา 4,199,000 บาท</p>
</body></html>
"""
obs7, rej7 = parse_brand_page(contam_html, "toyota", "https://www.9carthai.com/toyota-price/")
# Corolla Altis prices should NOT include GR Corolla pricing
altis_prices = [o for o in obs7 if o.model == "Corolla Altis" and o.obs_field == "price"]
gr_prices = [o for o in obs7 if o.model == "GR Corolla" and o.obs_field == "price"]
assert_true("Corolla Altis has its own prices", len(altis_prices) > 0)
# GR Corolla should either be separate or rejected, not mixed into Corolla Altis
for p in altis_prices:
    assert_true(f"Corolla Altis price {p.raw_value} not GR-level", int(p.raw_value) < 3_000_000)

# ═══════════════════════════════════════════════════════════════════
# TEST 8: Secondary sources stay unverified
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 8: Secondary sources stay RESEARCH_UNVERIFIED ---")

hl_text = "Honda Civic 2026 ราคา 999,000 บาท รุ่น e:HEV"
obs8, _ = extract_prices_from_article(hl_text, "Civic", "honda",
    "https://www.headlightmag.com/honda-civic-2026/",
    "Honda Civic 2026")
for o in obs8:
    assert_eq(f"trust_state={o.obs_field}", o.trust_state, "RESEARCH_UNVERIFIED")
    assert_eq(f"source_class={o.obs_field}", o.source_class, "AUTO_MEDIA")

# ═══════════════════════════════════════════════════════════════════
# TEST 9: Nissan contamination regression
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 9: Nissan contamination regression ---")

# 9CARTHAI parser needs HTML structure
nissan_html = "<html><body><h2>Nissan Kicks 2026</h2><p>รุ่น V ราคา 749,000 บาท</p></body></html>"
obs9, _ = parse_brand_page(nissan_html, "nissan", "https://www.9carthai.com/nissan-price/")
kicks = [o for o in obs9 if "Kicks" in o.model and o.obs_field == "price"]
assert_true("Kicks prices found", len(kicks) > 0)
for k in kicks:
    assert_true(f"Kicks price in range", 500000 <= int(k.raw_value) <= 1000000)
    # Should NOT be attributed to any other model
    assert_eq("Kicks brand", k.brand, "nissan")

# ═══════════════════════════════════════════════════════════════════
# TEST 10: Spec provenance persistence
# ═══════════════════════════════════════════════════════════════════
print("\n--- Test 10: Spec provenance persistence ---")

spec_text = """
BYD Dolphin 2026 ราคา 699,000 บาท รุ่น Dynamic
แบตเตอรี่ 44.9 kWh ระยะทาง 340 km WLTP
กำลัง 95 hp แรงบิด 180 Nm
"""
obs10, _ = extract_prices_from_article(spec_text, "Dolphin", "byd",
    "https://www.headlightmag.com/byd-dolphin-2026/",
    "BYD Dolphin 2026")
specs10 = [o for o in obs10 if o.obs_field in ("power_hp", "torque_nm", "battery_kwh", "range_km")]
for s in specs10:
    assert_true(f"spec {s.obs_field} has source_url", s.source_url is not None)
    assert_true(f"spec {s.obs_field} has evidence_excerpt", len(s.evidence_excerpt) > 0)
    assert_true(f"spec {s.obs_field} has content_hash", len(s.content_hash) >= 8)
    assert_eq(f"spec {s.obs_field} source_class", s.source_class, "AUTO_MEDIA")
    assert_eq(f"spec {s.obs_field} trust_state", s.trust_state, "RESEARCH_UNVERIFIED")

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL == 0:
    print("All tests passed!")
else:
    print(f"FAILED: {FAIL} test(s) failed")
    sys.exit(1)
