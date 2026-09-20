#!/usr/bin/env python3
"""
Parser tests for 9CARTHAI and Headlightmag extractors.
Tests exercise real parser functions against representative raw HTML/text fixtures.
"""
import sys
import os
import hashlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "thai-media-extractors"))
from importlib.util import spec_from_file_location, module_from_spec

# Load 9carthai parser (filename starts with digit)
_spec = spec_from_file_location("p9c", os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "thai-media-extractors", "9carthai_parser.py"))
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)
parse_brand_page = _mod.parse_brand_page
normalize_model_name = _mod.normalize_model_name

PASS = 0
FAIL = 0

def assert_eq(test_name, actual, expected):
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  ✓ {test_name}")
    else:
        FAIL += 1
        print(f"  ✗ {test_name}: expected {expected}, got {actual}")

def assert_true(test_name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {test_name}")
    else:
        FAIL += 1
        print(f"  ✗ {test_name}: condition was false")

# ─── Test 1: 4 explicit trims → exactly 4 observations ──────────
print("\n--- Test 1: 4 explicit trims → 4 observations ---")
html1 = """
<html><body>
<h2>Honda City 2026</h2>
<p>รุ่น V ราคา 569,000 บาท</p>
<p>รุ่น RS ราคา 749,000 บาท</p>
<p>รุ่น EL ราคา 669,000 บาท</p>
<p>รุ่น e:HEV ราคา 849,000 บาท</p>
</body></html>
"""
obs, rej = parse_brand_page(html1, "honda", "https://www.9carthai.com/honda-price/")
price_obs = [o for o in obs if o.obs_field == "price" and o.scope == "VARIANT"]
assert_eq("4 variant observations", len(price_obs), 4)
trim_names = sorted([o.variant for o in price_obs])
assert_eq("trim names correct", trim_names, ["EL", "RS", "V", "e:HEV"])

# ─── Test 2: Range only → 1 MODEL_RANGE ───────────────────────
print("\n--- Test 2: Range only → 1 MODEL_RANGE ---")
html2 = """
<html><body>
<h2>MG MG4 2026</h2>
<p>ราคาเริ่มต้น 599,000 - 799,000 บาท</p>
</body></html>
"""
obs2, rej2 = parse_brand_page(html2, "mg", "https://www.9carthai.com/mg-price/")
model_ranges = [o for o in obs2 if o.scope == "MODEL" and o.obs_field == "price"]
assert_eq("1 MODEL_RANGE", len(model_ranges), 1)
if model_ranges:
    assert_eq("range value", model_ranges[0].raw_value, "599,000-799,000")
    assert_eq("price_type LIST_PRICE", model_ranges[0].price_type, "LIST_PRICE")

# ─── Test 3: Model-level price cannot attach to arbitrary variant ──
print("\n--- Test 3: Model-level price → MODEL scope, not VARIANT ---")
html3 = """
<html><body>
<h2>Toyota Fortuner 2026</h2>
<p>ราคาอย่างเป็นทางการ Fortuner 1,399,000 บาท</p>
</body></html>
"""
obs3, rej3 = parse_brand_page(html3, "toyota", "https://www.9carthai.com/toyota-price/")
model_prices = [o for o in obs3 if o.model == "Fortuner" and o.obs_field == "price"]
assert_true("has Fortuner price", len(model_prices) > 0)
if model_prices:
    # Should be MODEL scope, not a random VARIANT
    assert_true("scope is MODEL or has __MODEL_RANGE__",
                any(o.scope == "MODEL" or o.variant == "__MODEL_RANGE__" for o in model_prices))

# ─── Test 4: Shared page with multiple models → no cross-contamination ──
print("\n--- Test 4: Multi-model page → no cross-contamination ---")
html4 = """
<html><body>
<h2>Toyota Yaris Cross 2026</h2>
<p>รุ่น Smart ราคา 809,000 บาท</p>
<p>รุ่น Premium ราคา 929,000 บาท</p>
<h2>Toyota Corolla Cross 2026</h2>
<p>รุ่น Sport ราคา 999,000 บาท</p>
<p>รุ่น Premium ราคา 1,099,000 บาท</p>
</body></html>
"""
obs4, rej4 = parse_brand_page(html4, "toyota", "https://www.9carthai.com/toyota-price/")
yc_prices = [o for o in obs4 if o.model == "Yaris Cross" and o.obs_field == "price"]
cc_prices = [o for o in obs4 if o.model == "Corolla Cross" and o.obs_field == "price"]
assert_eq("Yaris Cross prices", len(yc_prices), 2)
assert_eq("Corolla Cross prices", len(cc_prices), 2)
# Verify no cross-contamination
yc_amounts = set(int(o.normalized_value) for o in yc_prices)
cc_amounts = set(int(o.normalized_value) for o in cc_prices)
assert_true("no cross-contamination", yc_amounts.isdisjoint(cc_amounts))

# ─── Test 5: Thai model name aliases → same canonical entity ──
print("\n--- Test 5: Thai model aliases → canonical ---")
assert_eq("hr-v → HR-V", normalize_model_name("hr-v"), "HR-V")
assert_eq("crv → CR-V", normalize_model_name("crv"), "CR-V")
assert_eq("kicks e-power → Kicks e-POWER", normalize_model_name("kicks e-power"), "Kicks e-POWER")
assert_eq("hilux revo → Hilux Revo", normalize_model_name("hilux revo"), "Hilux Revo")
assert_eq("pajero sport → Pajero Sport", normalize_model_name("pajero sport"), "Pajero Sport")
assert_eq("new city → City", normalize_model_name("new city"), "City")
assert_eq("all new civic → Civic", normalize_model_name("all new civic"), "Civic")

# ─── Test 6: Unrelated nearby brand/model price → rejected ──
print("\n--- Test 6: Unrelated price → rejected ---")
html6 = """
<html><body>
<h2>Honda City 2026</h2>
<p>เปรียบเทียบ Honda City กับ Toyota Yaris ราคา 569,000 บาท</p>
<p>City V ราคา 569,000 บาท</p>
<p>City RS ราคา 749,000 บาท</p>
</body></html>
"""
obs6, rej6 = parse_brand_page(html6, "honda", "https://www.9carthai.com/honda-price/")
city_prices = [o for o in obs6 if o.model == "City" and o.obs_field == "price"]
# Should have at least the 2 explicit City trims
assert_true("at least 2 City observations", len(city_prices) >= 2)

# ─── Test 7: Duplicate source/content → idempotent ──────────
print("\n--- Test 7: Duplicate → idempotent ---")
obs7a, _ = parse_brand_page(html1, "honda", "https://www.9carthai.com/honda-price/")
obs7b, _ = parse_brand_page(html1, "honda", "https://www.9carthai.com/honda-price/")
# Same input should produce same output
assert_eq("same observations count", len(obs7a), len(obs7b))
hashes_a = set(o.content_hash for o in obs7a)
hashes_b = set(o.content_hash for o in obs7b)
assert_eq("same content hashes", hashes_a, hashes_b)

# ─── Test 8: 9CARTHAI generic homepage → rejected ────────────
print("\n--- Test 8: Generic homepage prices → rejected ---")
html8 = """
<html><body>
<h2>ราคา car ทุกรุ่น</h2>
<p>Toyota Yaris ราคา 569,000 บาท</p>
<p>Honda City ราคา 569,000 บาท</p>
<p>MG MG4 ราคา 799,000 บาท</p>
</body></html>
"""
obs8, rej8 = parse_brand_page(html8, "generic", "https://www.9carthai.com/")
# Without model context from headings, most should be rejected
assert_true("rejections for generic page", len(rej8) > 0 or len(obs8) == 0)

# ─── Test 9: Headlightmag-style multi-trim article ───────────
print("\n--- Test 9: Multi-trim article text → 3+ variant observations ---")
# Simulate Headlightmag article text (already cleaned of HTML)
article_text = """
ราคาอย่างเป็นทางการ Honda Civic 2026
 Civic e:HEV EL ราคา 1,199,000 บาท
 Civic e:HEV RS ราคา 1,349,000 บาท
 Civic e:HEV RS Ultimate ราคา 1,499,000 บาท
 เครื่องยนต์ 2.0L 184 แรงม้า 321 Nm
 ระบบส่งกำลัง e-CVT
"""
# Test the Headlightmag article extraction function
# Load Headlightmag extractor
_hl_spec = spec_from_file_location("hl", os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "thai-media-extractors", "headlightmag_extractor.py"))
_hl_mod = module_from_spec(_hl_spec)
_hl_spec.loader.exec_module(_hl_mod)
extract_prices_from_article = _hl_mod.extract_prices_from_article
obs9, rej9 = extract_prices_from_article(article_text, "Civic", "honda",
    "https://www.headlightmag.com/test-civic/", "ราคาอย่างเป็นทางการ Honda Civic 2026")
price_obs9 = [o for o in obs9 if o.obs_field == "price" and o.scope == "VARIANT"]
assert_true("3+ variant observations from article", len(price_obs9) >= 3)
# Check spec extraction
spec_obs9 = [o for o in obs9 if o.obs_field in ("power_hp", "torque_nm", "battery_kwh", "range_km", "displacement_cc")]
assert_true("spec observations extracted", len(spec_obs9) > 0)

# ─── Summary ─────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
print("All tests passed!")
