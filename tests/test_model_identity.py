#!/usr/bin/env python3
"""
Unit tests for model_identity.py — the shared model identity resolver.

Uses the report file (no live DB needed for most tests).
"""
import json
import os
import sys
import unittest

# Add scripts dir to path
SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts", "thai-media-extractors")
sys.path.insert(0, os.path.abspath(SCRIPT_DIR))

from model_identity import ModelIdentityResolver, ModelEntry, AliasEntry


class TestNormalize(unittest.TestCase):
    """Test the _normalize static method."""

    def test_basic_lowercase(self):
        self.assertEqual(ModelIdentityResolver._normalize("Camry"), "camry")

    def test_whitespace_collapse(self):
        self.assertEqual(ModelIdentityResolver._normalize("  hello   world  "), "hello world")

    def test_thai_passthrough(self):
        self.assertEqual(ModelIdentityResolver._normalize("แคมรี่"), "แคมรี่")

    def test_empty(self):
        self.assertEqual(ModelIdentityResolver._normalize(""), "")

    def test_none_like(self):
        self.assertEqual(ModelIdentityResolver._normalize("  "), "")


class TestStripPrefixes(unittest.TestCase):
    """Test common prefix stripping."""

    def test_new_prefix(self):
        self.assertEqual(
            ModelIdentityResolver._strip_prefixes("new camry"), "camry"
        )

    def test_all_new_prefix(self):
        self.assertEqual(
            ModelIdentityResolver._strip_prefixes("all-new corolla cross"), "corolla cross"
        )

    def test_the_prefix(self):
        self.assertEqual(
            ModelIdentityResolver._strip_prefixes("the new civic"), "civic"
        )

    def test_no_prefix(self):
        self.assertEqual(
            ModelIdentityResolver._strip_prefixes("fortuner"), "fortuner"
        )


class TestWholeWord(unittest.TestCase):
    """Test whole-word matching."""

    def test_exact_whole_word(self):
        self.assertTrue(
            ModelIdentityResolver._is_whole_word("camry", "toyota camry hev")
        )

    def test_not_substring(self):
        self.assertFalse(
            ModelIdentityResolver._is_whole_word("amry", "toyota camry")
        )

    def test_start_of_text(self):
        self.assertTrue(
            ModelIdentityResolver._is_whole_word("camry", "camry hev premium")
        )

    def test_end_of_text(self):
        self.assertTrue(
            ModelIdentityResolver._is_whole_word("hev", "camry hev")
        )


class TestLoadFromReport(unittest.TestCase):
    """Test loading from the exported identity-report.json."""

    @classmethod
    def setUpClass(cls):
        cls.resolver = ModelIdentityResolver()
        cls.resolver.load(use_db=False)

    def test_models_loaded(self):
        self.assertGreater(len(self.resolver.models), 100)

    def test_aliases_built(self):
        self.assertGreater(len(self.resolver.alias_index), 500)

    def test_brand_index_populated(self):
        self.assertIn("toyota", self.resolver.brand_models)
        self.assertIn("bmw", self.resolver.brand_models)
        self.assertIn("byd", self.resolver.brand_models)

    def test_slug_to_model(self):
        m = self.resolver.get_model_by_slug("toyota-camry")
        self.assertIsNotNone(m)
        self.assertEqual(m.model_en, "Camry")

    def test_get_models_by_brand(self):
        models = self.resolver.get_models_by_brand("BMW")
        self.assertGreater(len(models), 0)
        self.assertTrue(all(m.brand_en == "BMW" for m in models))


class TestResolveExact(unittest.TestCase):
    """Test exact alias resolution."""

    @classmethod
    def setUpClass(cls):
        cls.r = ModelIdentityResolver()
        cls.r.load(use_db=False)

    def test_english_exact(self):
        b, m, c, a = self.r.resolve("Toyota", "Camry")
        self.assertEqual(b, "Toyota")
        self.assertEqual(m, "Camry")
        self.assertGreater(c, 0.9)

    def test_thai_exact(self):
        b, m, c, a = self.r.resolve("Toyota", "แคมรี่")
        self.assertEqual(b, "Toyota")
        self.assertEqual(m, "Camry")
        self.assertGreater(c, 0.9)

    def test_slug_exact(self):
        b, m, c, a = self.r.resolve("Honda", "honda-cr-v")
        self.assertEqual(b, "Honda")
        self.assertEqual(m, "CR-V")

    def test_brand_prefixed_exact(self):
        b, m, c, a = self.r.resolve("Toyota", "Toyota Camry")
        self.assertEqual(b, "Toyota")
        self.assertEqual(m, "Camry")

    def test_bmw_series(self):
        b, m, c, a = self.r.resolve("BMW", "3 Series")
        self.assertEqual(b, "BMW")
        self.assertEqual(m, "3 Series")

    def test_tesla_model_y(self):
        b, m, c, a = self.r.resolve("Tesla", "Model Y")
        self.assertEqual(b, "Tesla")
        self.assertEqual(m, "Model Y")

    def test_byd_atto3(self):
        b, m, c, a = self.r.resolve("BYD", "ATTO 3")
        self.assertEqual(b, "BYD")
        self.assertEqual(m, "ATTO 3")


class TestResolveWithHint(unittest.TestCase):
    """Test resolution with brand hint."""

    @classmethod
    def setUpClass(cls):
        cls.r = ModelIdentityResolver()
        cls.r.load(use_db=False)

    def test_brand_hint_improves(self):
        """Brand hint should resolve correctly even for short names."""
        b, m, c, a = self.r.resolve("Toyota", "Fortuner")
        self.assertEqual(b, "Toyota")
        self.assertEqual(m, "Fortuner")

    def test_no_hint_still_resolves(self):
        b, m, c, a = self.r.resolve(None, "Fortuner")
        self.assertEqual(b, "Toyota")
        self.assertEqual(m, "Fortuner")

    def test_thai_brand_hint(self):
        b, m, c, a = self.r.resolve("โตโยต้า", "Fortuner")
        self.assertEqual(b, "Toyota")
        self.assertEqual(m, "Fortuner")


class TestResolveLongestMatch(unittest.TestCase):
    """Test that longest alias wins."""

    @classmethod
    def setUpClass(cls):
        cls.r = ModelIdentityResolver()
        cls.r.load(use_db=False)

    def test_corolla_cross_over_corolla(self):
        """'Corolla Cross' should resolve to Corolla Cross, not Corolla Altis."""
        b, m, c, a = self.r.resolve("Toyota", "Corolla Cross")
        self.assertEqual(m, "Corolla Cross")

    def test_haval_h6_over_haval(self):
        b, m, c, a = self.r.resolve("GWM", "Haval H6")
        self.assertEqual(m, "Haval H6")

    def test_xpander_cross_over_xpander(self):
        b, m, c, a = self.r.resolve("Mitsubishi", "Xpander Cross")
        self.assertEqual(m, "Xpander Cross")


class TestResolveFailClosed(unittest.TestCase):
    """Test that unknown inputs fail closed."""

    @classmethod
    def setUpClass(cls):
        cls.r = ModelIdentityResolver()
        cls.r.load(use_db=False)

    def test_unknown_text_returns_empty(self):
        b, m, c, a = self.r.resolve("Toyota", "xyzzy12345")
        self.assertEqual(b, "")
        self.assertEqual(m, "")
        self.assertEqual(c, 0.0)

    def test_empty_text_returns_empty(self):
        b, m, c, a = self.r.resolve("Toyota", "")
        self.assertEqual(b, "")
        self.assertEqual(m, "")

    def test_pure_noise_returns_empty(self):
        b, m, c, a = self.r.resolve(None, "the quick brown fox")
        self.assertEqual(b, "")


class TestCrossBrandCollisions(unittest.TestCase):
    """Test cross-brand collision detection."""

    @classmethod
    def setUpClass(cls):
        cls.r = ModelIdentityResolver()
        cls.r.load(use_db=False)

    def test_model3_no_hint_is_ambiguous(self):
        """'Model 3' without brand hint could be Tesla (Model 3)."""
        b, m, c, a = self.r.resolve(None, "Model 3")
        # Should resolve to Tesla with high confidence since Tesla Model 3 is unique
        if a:
            self.assertEqual(b, "")
        else:
            self.assertEqual(b, "Tesla")

    def test_m6_resolves_to_byd(self):
        b, m, c, a = self.r.resolve(None, "M6")
        # M6 is BYD M6, should resolve
        self.assertEqual(m, "M6")


class TestTrimPatterns(unittest.TestCase):
    """Test trim suffix handling."""

    @classmethod
    def setUpClass(cls):
        cls.r = ModelIdentityResolver()
        cls.r.load(use_db=False)

    def test_hilux_revo_alias(self):
        """'Hilux Revo' should map to Hilux via manual alias."""
        b, m, c, a = self.r.resolve("Toyota", "Hilux Revo")
        self.assertEqual(m, "Hilux")

    def test_kicks_e_power(self):
        """'Kicks e-Power' should resolve to Kicks."""
        b, m, c, a = self.r.resolve("Nissan", "Kicks e-Power")
        self.assertEqual(m, "Kicks")


class TestExportReport(unittest.TestCase):
    """Test report export."""

    def test_export_creates_file(self):
        import tempfile
        r = ModelIdentityResolver()
        r.load(use_db=False)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            report = r.export_report(path)
            self.assertIn("models", report)
            self.assertIn("total_models", report)
            self.assertIn("total_aliases", report)
            self.assertIn("brands_covered", report)
            self.assertGreater(report["total_models"], 100)
            self.assertGreater(report["total_aliases"], 500)
            self.assertGreater(report["brands_covered"], 20)
            # Verify file exists and is valid JSON
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded["total_models"], report["total_models"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
