#!/usr/bin/env python3
"""
Tests for thai-source-registry module.
"""
import sys
import os
import json
from importlib.util import spec_from_file_location, module_from_spec

_registry_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "scripts", "thai-source-registry.py"
)
_spec = spec_from_file_location("thai_source_registry", _registry_path)
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SourceRegistry = _mod.SourceRegistry
SourceEntry = _mod.SourceEntry

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


# --- Test 1: Registry loads with 4 sources ---
print("\n--- Test 1: Registry has 4 sources ---")
registry = SourceRegistry()
assert_eq("source count", registry.count(), 4)

# --- Test 2: All 4 domains present ---
print("\n--- Test 2: All domains present ---")
domains = set(registry.domains())
assert_eq("domains", domains, {
    "headlightmag.com", "autospinn.com",
    "autolifethailand.tv", "9carthai.com",
})

# --- Test 3: All sources are AUTOMOTIVE_MEDIA ---
print("\n--- Test 3: source_class = AUTOMOTIVE_MEDIA ---")
for s in registry.all():
    assert_eq(f"{s.domain} source_class", s.source_class, "AUTOMOTIVE_MEDIA")

# --- Test 4: All sources are RESEARCH_UNVERIFIED ---
print("\n--- Test 4: trust_state = RESEARCH_UNVERIFIED ---")
for s in registry.all():
    assert_eq(f"{s.domain} trust_state", s.trust_state, "RESEARCH_UNVERIFIED")

# --- Test 5: All sources are language TH ---
print("\n--- Test 5: language = TH ---")
for s in registry.all():
    assert_eq(f"{s.domain} language", s.language, "TH")

# --- Test 6: Parser status ---
print("\n--- Test 6: has_parser flags ---")
assert_true("headlightmag has parser", registry.has_parser("headlightmag.com"))
assert_true("9carthai has parser", registry.has_parser("9carthai.com"))
assert_true("autospinn no parser", not registry.has_parser("autospinn.com"))
assert_true("autolifethailand no parser", not registry.has_parser("autolifethailand.tv"))

# --- Test 7: by_parser_status ---
print("\n--- Test 7: by_parser_status ---")
with_parser = registry.by_parser_status(True)
without_parser = registry.by_parser_status(False)
assert_eq("with_parser count", len(with_parser), 2)
assert_eq("without_parser count", len(without_parser), 2)
parser_domains = set(s.domain for s in with_parser)
assert_eq("parser domains", parser_domains, {"headlightmag.com", "9carthai.com"})

# --- Test 8: Each source has required fields ---
print("\n--- Test 8: All required fields populated ---")
for s in registry.all():
    assert_true(f"{s.domain} has search_method", bool(s.search_method))
    assert_true(f"{s.domain} has content_hash_method", bool(s.content_hash_method))
    assert_true(f"{s.domain} has scope_requirements", len(s.scope_requirements) > 0)
    assert_true(f"{s.domain} has known_article_patterns", len(s.known_article_patterns) > 0)

# --- Test 9: validate() returns no errors ---
print("\n--- Test 9: validate() clean ---")
errors = registry.validate()
assert_eq("validation errors", errors, [])

# --- Test 10: JSON export round-trip ---
print("\n--- Test 10: JSON round-trip ---")
json_path = "/tmp/test-source-registry.json"
registry.to_json(json_path)
assert_true("JSON file exists", os.path.exists(json_path))
loaded = SourceRegistry.from_json(json_path)
assert_eq("loaded count", loaded.count(), 4)
for domain in registry.domains():
    orig = registry.get(domain)
    reloaded = loaded.get(domain)
    assert_true(f"{domain} survived round-trip", reloaded is not None)
    assert_eq(f"{domain} display_name", reloaded.display_name, orig.display_name)
    assert_eq(f"{domain} source_class", reloaded.source_class, orig.source_class)

# --- Test 11: SourceEntry.from_dict ---
print("\n--- Test 11: SourceEntry.from_dict ---")
d = {
    "domain": "test.com",
    "display_name": "Test",
    "source_class": "AUTOMOTIVE_MEDIA",
    "trust_state": "RESEARCH_UNVERIFIED",
    "language": "TH",
    "search_method": "test_method",
    "content_hash_method": "sha256_16",
    "scope_requirements": ["req1"],
    "known_article_patterns": ["pat1"],
    "has_parser": False,
    "notes": "test notes",
}
entry = SourceEntry.from_dict(d)
assert_eq("from_dict domain", entry.domain, "test.com")
assert_eq("from_dict scope_requirements", entry.scope_requirements, ["req1"])
assert_true("to_dict roundtrip", entry.to_dict()["domain"] == "test.com")

# --- Test 12: get() returns None for unknown domain ---
print("\n--- Test 12: get() unknown domain ---")
assert_true("unknown domain returns None", registry.get("nope.com") is None)

# --- Test 13: headlightmag specific patterns ---
print("\n--- Test 13: headlightmag patterns ---")
hl = registry.get("headlightmag.com")
assert_true("has thai price pattern",
            any("ราคา" in p for p in hl.known_article_patterns))
assert_true("has hp/torque pattern",
            any("แรงม้า" in p for p in hl.known_article_patterns))

# --- Test 14: 9carthai specific patterns ---
print("\n--- Test 14: 9carthai patterns ---")
tc = registry.get("9carthai.com")
assert_true("has รุ่น pattern",
            any("รุ่น" in p for p in tc.known_article_patterns))
assert_true("brand_price_page_crawl in search_method",
            "brand_price_page_crawl" in tc.search_method)

# --- Cleanup ---
os.unlink(json_path)

# --- Summary ---
print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
print("All tests passed!")
