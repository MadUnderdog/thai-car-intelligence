"""Tests for Thai alias catalog generation.

Tests cover:
- Catalog structure and completeness
- Brand alias coverage
- Model alias coverage
- Search query templates
- JSON export format
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the hyphenated script as a module via importlib
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "thai-alias-catalog.py"

spec = importlib.util.spec_from_file_location("thai_alias_catalog", SCRIPT_PATH)
assert spec is not None and spec.loader is not None, f"Cannot load {SCRIPT_PATH}"
mod = importlib.util.module_from_spec(spec)
sys.modules["thai_alias_catalog"] = mod
spec.loader.exec_module(mod)

THAI_BRAND_ALIASES = mod.THAI_BRAND_ALIASES
SEARCH_TEMPLATES = mod.SEARCH_TEMPLATES
build_brand_aliases = mod.build_brand_aliases
build_model_aliases = mod.build_model_aliases
generate_catalog = mod.generate_catalog
get_connection = mod.get_connection
export_catalog = mod.export_catalog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog():
    """Generate the catalog once for all tests in this module."""
    conn = get_connection()
    try:
        return generate_catalog(conn)
    finally:
        conn.close()


@pytest.fixture(scope="module")
def sample_brand(catalog):
    """Get a sample brand entry."""
    return catalog["brands"]["toyota"]


@pytest.fixture(scope="module")
def sample_model(catalog):
    """Get a sample model entry."""
    return catalog["models"]["hilux"]


# ---------------------------------------------------------------------------
# Catalog structure tests
# ---------------------------------------------------------------------------

class TestCatalogStructure:
    """Test the overall catalog JSON structure."""

    def test_has_version(self, catalog):
        assert "version" in catalog
        assert catalog["version"] == "1.0"

    def test_has_generated_by(self, catalog):
        assert "generated_by" in catalog
        assert "thai-alias-catalog" in catalog["generated_by"]

    def test_has_stats(self, catalog):
        assert "stats" in catalog
        stats = catalog["stats"]
        assert "brands_covered" in stats
        assert "models_covered" in stats
        assert "total_aliases" in stats
        assert "total_search_queries" in stats

    def test_has_brands_section(self, catalog):
        assert "brands" in catalog
        assert isinstance(catalog["brands"], dict)

    def test_has_models_section(self, catalog):
        assert "models" in catalog
        assert isinstance(catalog["models"], dict)


# ---------------------------------------------------------------------------
# Brand coverage tests
# ---------------------------------------------------------------------------

class TestBrandCoverage:
    """Test brand alias coverage."""

    def test_all_34_manufacturers_covered(self, catalog):
        assert catalog["stats"]["brands_covered"] == 34

    def test_toyota_brand_exists(self, catalog):
        assert "toyota" in catalog["brands"]

    def test_toyota_has_thai_name(self, catalog):
        toyota = catalog["brands"]["toyota"]
        assert toyota["nameTh"] == "โตโยต้า"

    def test_toyota_aliases_include_thai(self, catalog):
        toyota = catalog["brands"]["toyota"]
        assert "โตโยต้า" in toyota["aliases"]

    def test_bmw_has_multiple_aliases(self, catalog):
        bmw = catalog["brands"]["bmw"]
        aliases = bmw["aliases"]
        # Should have DB nameTh + hardcoded extras
        assert len(aliases) >= 3
        assert "บีเอ็มดับบลิว" in aliases  # from DB
        assert "บีเอ็มดับเบิลยู" in aliases  # from hardcoded
        assert "บีเอ็ม" in aliases  # from hardcoded

    def test_mercedes_has_benz_alias(self, catalog):
        mb = catalog["brands"]["mercedes-benz"]
        assert "เบนซ์" in mb["aliases"]

    def test_chery_has_both_spellings(self, catalog):
        chery = catalog["brands"]["chery"]
        assert "เชอรี" in chery["aliases"]
        assert "เชอรี่" in chery["aliases"]

    def test_all_brands_have_aliases(self, catalog):
        for slug, brand in catalog["brands"].items():
            assert len(brand["aliases"]) > 0, f"Brand {slug} has no aliases"

    def test_all_brands_have_required_fields(self, catalog):
        required = {"nameEn", "nameTh", "slug", "aliases"}
        for slug, brand in catalog["brands"].items():
            for field in required:
                assert field in brand, f"Brand {slug} missing field {field}"

    def test_known_thai_brands_have_aliases(self):
        """Verify the hardcoded alias map covers the required brands."""
        required_brands = [
            "Toyota", "Honda", "Nissan", "Mazda", "Mercedes-Benz", "BMW",
            "Volvo", "Tesla", "BYD", "MG", "GWM", "Chery", "Ford",
            "Hyundai", "Kia", "Mitsubishi", "Isuzu", "Suzuki", "Subaru",
            "Porsche", "MINI", "Lexus",
        ]
        for brand in required_brands:
            assert brand in THAI_BRAND_ALIASES, f"Missing hardcoded alias for {brand}"
            assert len(THAI_BRAND_ALIASES[brand]) > 0, f"Empty alias list for {brand}"


# ---------------------------------------------------------------------------
# Model coverage tests
# ---------------------------------------------------------------------------

class TestModelCoverage:
    """Test model alias coverage."""

    def test_all_157_models_covered(self, catalog):
        assert catalog["stats"]["models_covered"] == 157

    def test_hilux_model_exists(self, catalog):
        assert "toyota-hilux" in catalog["models"]

    def test_hilux_has_thai_name(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        assert hilux["nameTh"] == "ฮิลักซ์"

    def test_hilux_aliases(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        aliases = hilux["aliases"]
        assert "Hilux" in aliases
        assert "ฮิลักซ์" in aliases
        assert "toyota-hilux" in aliases

    def test_civic_model(self, catalog):
        civic = catalog["models"]["honda-civic"]
        assert civic["nameEn"] == "Civic"
        assert civic["brandEn"] == "Honda"
        assert civic["brandTh"] == "ฮอนด้า"

    def test_all_models_have_aliases(self, catalog):
        for slug, model in catalog["models"].items():
            # Some models have nameEn == nameTh == slug (e.g. "11", "EX5")
            # so they end up with just 1 unique alias
            assert len(model["aliases"]) >= 1, (
                f"Model {slug} has no aliases"
            )

    def test_all_models_have_brand_info(self, catalog):
        for slug, model in catalog["models"].items():
            assert "brandEn" in model
            assert "brandTh" in model
            assert "brandSlug" in model
            assert model["brandEn"]
            assert model["brandTh"]

    def test_all_models_have_required_fields(self, catalog):
        required = {
            "nameEn", "nameTh", "slug", "brandEn", "brandTh",
            "brandSlug", "aliases", "searchQueries",
        }
        for slug, model in catalog["models"].items():
            for field in required:
                assert field in model, f"Model {slug} missing field {field}"


# ---------------------------------------------------------------------------
# Search query template tests
# ---------------------------------------------------------------------------

class TestSearchQueries:
    """Test search query template generation."""

    def test_hilux_has_search_queries(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        assert len(queries) >= 6

    def test_queries_include_brand_thai(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        # Should have a query with โตโยต้า
        assert any("โตโยต้า" in q for q in queries)

    def test_queries_include_model_thai(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        # Should have a query with ฮิลักซ์
        assert any("ฮิลักซ์" in q for q in queries)

    def test_queries_include_price_keyword(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        assert any("ราคา" in q for q in queries)

    def test_queries_include_launch_keyword(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        assert any("เปิดตัว" in q for q in queries)

    def test_queries_include_spec_keyword(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        assert any("สเปก" in q for q in queries)

    def test_queries_include_variant_keyword(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        assert any("รุ่นย่อย" in q for q in queries)

    def test_queries_include_year(self, catalog):
        hilux = catalog["models"]["toyota-hilux"]
        queries = hilux["searchQueries"]
        assert any("2026" in q for q in queries)

    def test_no_duplicate_queries(self, catalog):
        for slug, model in catalog["models"].items():
            queries = model["searchQueries"]
            assert len(queries) == len(set(queries)), (
                f"Model {slug} has duplicate queries"
            )

    def test_all_models_have_queries(self, catalog):
        for slug, model in catalog["models"].items():
            assert len(model["searchQueries"]) >= 6, (
                f"Model {slug} has fewer than 6 queries"
            )


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Test JSON export functionality."""

    def test_catalog_is_json_serializable(self, catalog):
        # Should not raise
        json_str = json.dumps(catalog, ensure_ascii=False)
        assert len(json_str) > 0

    def test_export_writes_file(self, catalog, tmp_path):
        output = tmp_path / "test-catalog.json"
        export_catalog(catalog, output)
        assert output.exists()

    def test_exported_file_is_valid_json(self, catalog, tmp_path):
        output = tmp_path / "test-catalog.json"
        export_catalog(catalog, output)
        with open(output, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["stats"]["brands_covered"] == 34
        assert loaded["stats"]["models_covered"] == 157

    def test_export_preserves_thai_characters(self, catalog, tmp_path):
        output = tmp_path / "test-catalog.json"
        export_catalog(catalog, output)
        content = output.read_text(encoding="utf-8")
        assert "โตโยต้า" in content
        assert "ฮอนด้า" in content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and data quality."""

    def test_no_empty_brand_slugs(self, catalog):
        for slug in catalog["brands"]:
            assert slug, "Empty brand slug found"

    def test_no_empty_model_slugs(self, catalog):
        for slug in catalog["models"]:
            assert slug, "Empty model slug found"

    def test_no_duplicate_brand_aliases(self, catalog):
        for slug, brand in catalog["brands"].items():
            aliases = brand["aliases"]
            assert len(aliases) == len(set(aliases)), (
                f"Brand {slug} has duplicate aliases"
            )

    def test_no_duplicate_model_aliases(self, catalog):
        for slug, model in catalog["models"].items():
            aliases = model["aliases"]
            assert len(aliases) == len(set(aliases)), (
                f"Model {slug} has duplicate aliases"
            )

    def test_brand_aliases_are_strings(self, catalog):
        for slug, brand in catalog["brands"].items():
            for alias in brand["aliases"]:
                assert isinstance(alias, str), (
                    f"Brand {slug} has non-string alias: {alias}"
                )

    def test_model_aliases_are_strings(self, catalog):
        for slug, model in catalog["models"].items():
            for alias in model["aliases"]:
                assert isinstance(alias, str), (
                    f"Model {slug} has non-string alias: {alias}"
                )


# ---------------------------------------------------------------------------
# Import validation
# ---------------------------------------------------------------------------

class TestModuleImport:
    """Test that the module can be imported correctly."""

    def test_import_thai_alias_catalog(self):
        assert hasattr(mod, "THAI_BRAND_ALIASES")
        assert hasattr(mod, "SEARCH_TEMPLATES")
        assert hasattr(mod, "build_brand_aliases")
        assert hasattr(mod, "build_model_aliases")
        assert hasattr(mod, "generate_catalog")
        assert hasattr(mod, "get_connection")
        assert hasattr(mod, "export_catalog")

    def test_search_templates_count(self):
        assert len(SEARCH_TEMPLATES) == 8
