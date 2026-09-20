#!/usr/bin/env python3
"""
Model Identity Resolver — shared component for all Thai media extractors.

Queries the live DB to build a complete identity catalog from CarModel + Manufacturer.
Generates aliases from: nameEn, nameTh, slug, known trim patterns, brand prefixes.
Implements resolve(brand_hint, text) -> (brand, model, confidence, ambiguity).

Usage:
    from model_identity import get_resolver
    r = get_resolver()
    brand, model, conf, ambig = r.resolve("Toyota", "Toyota Camry HEV")
"""
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# ---------------------------------------------------------------------------
# DB connection via docker exec (same pattern as db_integration.py)
# ---------------------------------------------------------------------------

def _psql(sql: str, fetch: bool = True) -> List[str]:
    """Execute SQL via docker exec psql, return pipe-delimited rows."""
    cmd = [
        "docker", "exec", "pgvector", "psql",
        "-U", "hermes", "-d", "thai_car_intelligence",
        "-t", "-A", "-F", "|", "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"psql error: {result.stderr[:500]}")
    if not fetch:
        return result.stdout.strip()
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    return lines


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ModelEntry:
    """Single car model with all its identity metadata."""
    model_id: str
    brand_en: str
    brand_th: str
    brand_slug: str
    model_en: str
    model_th: str
    slug: str
    segment: Optional[str] = None
    manufacturer_id: Optional[str] = None


@dataclass
class AliasEntry:
    """Maps a normalized alias string to its model entry and match quality."""
    alias: str              # lowercased, normalized
    model: ModelEntry
    source: str             # 'nameEn', 'nameTh', 'slug', 'trim_pattern', 'brand_prefix', 'manual'


# ---------------------------------------------------------------------------
# Known trim / suffix patterns to strip when building shorter aliases
# ---------------------------------------------------------------------------

# These suffixes are commonly appended to model names in Thai media and should
# be recognized as additional alias forms.
TRIM_SUFFIXES = [
    "hev", "hybrid", "hybrid+", "phev", "dm-i", "e:hev",
    "ev", "electric", "bev",
    "gr sport", "gr-sport",
    "sport", "premium", "performance", "standard", "comfort", "dynamic",
    "smart", "premium rwd", "performance awd", "extended",
    "pro", "plus", "max", "lite", "base",
    "single cab", "double cab", "king cab",
    "sport edition", "urban", "premium s",
    "4wd", "2wd", "awd", "rwd", "fwd",
]

# Brand name patterns that can prefix model names in mixed-language text
# (e.g. "Toyota Camry" or "โตโยต้า แคมรี่")
MANUAL_ALIASES = {
    # Toyota
    "hilux revo": "toyota-hilux",
    "hilux revo z edition": "toyota-hilux",
    "hilux champ": "toyota-hilux",
    "innova crysta": "toyota-innova",
    "innova zenix": "toyota-innova",
    "corolla altis gr sport": "toyota-corolla-altis",
    "corolla cross gr sport": "toyota-corolla-cross",
    "fortuner gr sport": "toyota-fortuner",
    "fortuner legender": "toyota-fortuner",
    "fortuner leader": "toyota-fortuner",
    "yaris ativ gr sport": "toyota-yaris-ativ",
    "yaris cross nightshade": "toyota-yaris-cross",
    "gr corolla": "toyota-corolla-altis",
    "gr yaris": "yaris",
    "land cruiser fj": "land cruiser",
    "camry": "toyota-camry",
    # Nissan
    "new almera": "almera",
    "new almera 22my": "almera",
    "new terra": "terra",
    "nissan terra mc": "terra",
    "np300 navara double cab": "navara",
    "np300 navara king cab": "navara",
    "new navara single cab": "navara",
    "kicks e-power": "nissan-kicks",
    "kicks e power": "nissan-kicks",
    "serena epower": "serena",
    "new leaf": "leaf",
    "new kicks": "kicks",
    # BYD
    "sealion5": "sealion-5",
    "sealion6": "sealion-6",
    "sealion7": "sealion-7",
    "atto 2": "atto-2",
    "atto 3": "atto-3",
    "seal 6": "seal-6",
    # MG
    "mg3": "mg3-hybrid",
    "mg4": "mg4",
    "mg5": "mg5",
    "s5 ev plus": "mg-s5",
    # Mazda
    "mazda2": "mazda2",
    "mazda3": "mazda3",
    "mazda 6e": "mazda-6e",
    "6e": "mazda-6e",
    # GWM
    "haval jolion": "haval-jolion",
    "haval h6": "haval-h6",
    "ora good cat": "ora-good-cat",
    "ora 07": "ora-07",
    "tank 300": "tank-300",
    "tank 500": "tank-500",
    # Chery
    "omoda 5": "omoda-5",
    "tiggo 8 pro": "tiggo-8-pro",
    "jaecoo j7": "jaecoo-j7",
    # Honda
    "city hatchback": "city-hatchback",
    "civic type r": "civic-type-r",
    "honda crv": "honda-cr-v",
    "honda cr-v": "honda-cr-v",
    "honda hrv": "honda-hr-v",
    "honda hr-v": "honda-hr-v",
    "super one": "super-one",
    # Mitsubishi
    "pajero sport": "pajero-sport",
    "xpander cross": "xpander-cross",
    # Suzuki
    "s-presso": "s-presso",
    "s presso": "s-presso",
    "suzuki fronx": "fronx",
    "ford fronx": "fronx",
    # Isuzu
    "d-max": "d-max",
    "dmax": "d-max",
    "mu-x": "mu-x",
    "mux": "mu-x",
    # BMW
    "1 series": "1-series",
    "3 series": "3-series",
    "5 series": "5-series",
    # Tesla
    "model 3": "tesla-model-3",
    "model y": "tesla-model-y",
    "tesla model 3": "tesla-model-3",
    "tesla model y": "tesla-model-y",
    # MG
    "mg hs phev": "mg-hs-phev",
    "mg ep plus": "mg-ep",
    "mg zs ev": "mg-zs-ev",
    "mg urban": "mg-urban",
    "mg urban ev": "mg-urban",
    "vs hev": "mg-vs-hev",
    "maxus 7": "mg-maxus7",
    "maxus 9": "mg-maxus9",
    "mg cyberster": "mg-cyberster",
    # Changan
    "cs55 plus": "cs55-plus",
    "deepal s07": "deepal-s07",
    "uni-k": "uni-k",
    "uni-v": "uni-v",
    # Geely
    "geely ex5": "geely-ex5",
    "geely ex2": "ex2",
    # Hyundai
    "hyundai palisade": "palisade",
    "hyundai ioniq 5": "hyundai-ioniq-5",
    "hyundai santa fe": "hyundai-santa-fe",
    # Kia
    "kia sonet": "sonet",
    "kia sportage": "sportage",
    "kia ev6": "ev6",
    "kia ev9": "ev9",
    "kia carnival": "carnival",
    # Subaru
    "subaru crosstrek": "subaru-crosstrek",
    # Volvo
    "volvo xc40": "xc40",
    "volvo xc60": "xc60",
    "volvo xc90": "xc90",
    "volvo ex30": "ex30",
    # NIO
    "nio es6": "es6",
    "nio firefly": "nio-firefly",
    # BAIC
    "baic bj30": "bj30",
    "baic x55": "x55",
    # Avatr
    "avatr 11": "11",
    # Denza
    "denza z9gt": "z9gt",
    # Xpeng
    "xpeng l03": "l03",
    # Zeekr
    "zeekr 009": "009",
    "zeekr x": "x",
    # Lexus
    "lexus nx": "nx",
    "lexus rx": "rx",
    "lexus rz": "rz",
    # MINI
    "mini cooper": "cooper",
    "mini countryman": "countryman",
    # Porsche
    "porsche cayenne": "cayenne",
    "porsche macan": "macan",
    # Chevrolet
    "chevrolet colorado": "colorado",
    "chevrolet trailblazer": "trailblazer",
    # LDV
    "ldv d90": "d90",
    # Jetour
    "jetour dashing": "dashing",
    "jetour t2": "t2",
    # KG Mobility
    "kg mobility torres": "torres",
    "kg mobility korando": "korando",
}


# ---------------------------------------------------------------------------
# Cross-brand collision registry
# ---------------------------------------------------------------------------

# Model names that are ambiguous across brands.  The value is a list of
# (brand_slug, model_slug) tuples that the short name could refer to.
CROSS_BRAND_COLLISIONS: Dict[str, List[Tuple[str, str]]] = {
    "ex5": [("geely", "ex5"), ("geely", "geely-ex5")],
    "x": [("zeekr", "x")],
    "m6": [("byd", "m6")],
    "11": [("avatr", "11")],
    "es6": [("nio", "es6")],
    "009": [("zeekr", "009")],
}


# ---------------------------------------------------------------------------
# Resolver class
# ---------------------------------------------------------------------------

class ModelIdentityResolver:
    """
    Shared model identity resolver for all Thai media extractors.

    Resolution order:
      1. Brand exact match + canonical model exact match  (confidence 1.0)
      2. Known alias exact match                          (confidence 0.95)
      3. Brand prefix + longest alias match               (confidence 0.85-0.95)
      4. Longest-match whole-word against all aliases     (confidence 0.70-0.90)
      5. Fail-closed: return empty on ambiguity           (confidence 0.0)

    Thai/English/mixed handling:
      - Both nameEn and nameTh are indexed
      - Aliases are lowercased and whitespace-normalized
      - Unicode Thai characters are matched directly (no transliteration needed)
    """

    def __init__(self):
        self.models: List[ModelEntry] = []
        self.alias_index: Dict[str, AliasEntry] = {}       # normalized_alias -> AliasEntry
        self.brand_models: Dict[str, List[ModelEntry]] = defaultdict(list)  # brand_slug -> [ModelEntry]
        self.brand_aliases: Dict[str, Dict[str, AliasEntry]] = defaultdict(dict)  # brand_slug -> {alias -> AliasEntry}
        self.slug_to_model: Dict[str, ModelEntry] = {}     # model_slug -> ModelEntry
        self.collisions = CROSS_BRAND_COLLISIONS
        self.manual_aliases = MANUAL_ALIASES
        self._loaded = False
        self._report: dict = {}

    # ---- loading ----

    def load(self, *, use_db: bool = True) -> None:
        """Build the identity catalog.  If use_db=False, loads from last report."""
        if self._loaded:
            return

        if use_db:
            self._load_from_db()
        else:
            self._load_from_report()

        self._build_indices()
        self._loaded = True

    def _load_from_db(self) -> None:
        """Query live DB for CarModel + Manufacturer."""
        rows = _psql("""
            SELECT cm.id, cm."manufacturerId",
                   m."nameEn", m."nameTh", m.slug,
                   cm."nameEn", cm."nameTh", cm.slug, cm.segment
            FROM "CarModel" cm
            JOIN "Manufacturer" m ON cm."manufacturerId" = m.id
            WHERE cm.status = 'ACTIVE'
            ORDER BY m."nameEn", cm."nameEn"
        """)
        for row in rows:
            parts = row.split("|")
            if len(parts) < 9:
                continue
            entry = ModelEntry(
                model_id=parts[0].strip(),
                manufacturer_id=parts[1].strip(),
                brand_en=parts[2].strip(),
                brand_th=parts[3].strip(),
                brand_slug=parts[4].strip(),
                model_en=parts[5].strip(),
                model_th=parts[6].strip(),
                slug=parts[7].strip(),
                segment=parts[8].strip() if parts[8].strip() else None,
            )
            self.models.append(entry)

    def _load_from_report(self) -> None:
        """Load from existing identity-report.json (for offline/test use)."""
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "storage", "identity-report.json"
        )
        if not os.path.isfile(report_path):
            raise FileNotFoundError(f"No identity-report.json found at {report_path}")
        with open(report_path) as f:
            report = json.load(f)
        # ModelEntry fields (exclude 'aliases' which is report-only)
        _FIELDS = {"model_id", "brand_en", "brand_th",
                    "brand_slug", "model_en", "model_th", "slug", "segment",
                    "manufacturer_id"}
        for m in report.get("models", []):
            filtered = {k: v for k, v in m.items() if k in _FIELDS}
            self.models.append(ModelEntry(**filtered))

    def _build_indices(self) -> None:
        """Build all lookup indices from loaded models."""
        for model in self.models:
            bslug = model.brand_slug.lower()
            self.brand_models[bslug].append(model)
            self.slug_to_model[model.slug.lower()] = model

            # --- 1. nameEn aliases ---
            name_en = model.model_en.strip()
            self._add_alias(name_en, model, "nameEn")
            # Also add lowercase slug-form
            slug_form = model.slug.lower().replace("-", " ").strip()
            if slug_form != name_en.lower():
                self._add_alias(slug_form, model, "slug")

            # --- 2. nameTh aliases ---
            name_th = model.model_th.strip()
            if name_th:
                self._add_alias(name_th, model, "nameTh")

            # --- 3. slug aliases ---
            self._add_alias(model.slug.lower(), model, "slug")

            # --- 4. Trim-suffix variants ---
            self._generate_trim_aliases(model)

            # --- 5. Brand-prefixed aliases ---
            # "Toyota Camry" → "toyota camry"
            brand_pref = f"{bslug} {name_en.lower()}"
            if brand_pref != name_en.lower():
                self._add_alias(brand_pref, model, "brand_prefix")
            # Thai brand prefix: "โตโยต้า แคมรี่"
            if model.brand_th:
                brand_th_pref = f"{model.brand_th.lower()} {name_th.lower()}".strip()
                if brand_th_pref and brand_th_pref != name_th.lower():
                    self._add_alias(brand_th_pref, model, "brand_prefix")
            # Also "Toyota toyota-camry" → "toyota camry"
            bslug_model = f"{bslug} {model.slug.lower().replace('-', ' ')}".strip()
            if bslug_model != model.slug.lower().replace("-", " "):
                self._add_alias(bslug_model, model, "brand_prefix")

        # --- 6. Manual aliases (hardcoded domain knowledge) ---
        self._apply_manual_aliases()

    def _add_alias(self, alias_str: str, model: ModelEntry, source: str) -> None:
        """Add a normalized alias to the index.  Last-write-wins (manual > auto)."""
        norm = self._normalize(alias_str)
        if not norm or len(norm) < 1:
            return
        existing = self.alias_index.get(norm)
        # Allow overwriting if new entry has higher-quality source
        source_priority = {
            "manual": 5, "trim_pattern": 4, "brand_prefix": 3,
            "slug": 2, "nameTh": 2, "nameEn": 1,
        }
        if existing is None or source_priority.get(source, 0) >= source_priority.get(existing.source, 0):
            entry = AliasEntry(alias=norm, model=model, source=source)
            self.alias_index[norm] = entry
            # Per-brand alias index
            bslug = model.brand_slug.lower()
            self.brand_aliases[bslug][norm] = entry

    def _generate_trim_aliases(self, model: ModelEntry) -> None:
        """Generate aliases with common trim suffixes added."""
        base = model.model_en.lower().strip()
        for suffix in TRIM_SUFFIXES:
            candidate = f"{base} {suffix}"
            # Only add if the combined alias is distinct from existing
            if candidate != base and self._normalize(candidate) != self._normalize(base):
                self._add_alias(candidate, model, "trim_pattern")
        # Also from slug form
        base_slug = model.slug.lower().replace("-", " ")
        for suffix in TRIM_SUFFIXES:
            candidate = f"{base_slug} {suffix}"
            norm_cand = self._normalize(candidate)
            if norm_cand != self._normalize(base_slug):
                self._add_alias(candidate, model, "trim_pattern")

    def _apply_manual_aliases(self) -> None:
        """Apply hardcoded manual alias mappings."""
        for alias_text, target_slug in self.manual_aliases.items():
            norm = self._normalize(alias_text)
            target = self.slug_to_model.get(target_slug.lower())
            if target is None:
                # Try partial slug match
                for slug, m in self.slug_to_model.items():
                    if target_slug.lower() in slug:
                        target = m
                        break
            if target and norm:
                self.alias_index[norm] = AliasEntry(alias=norm, model=target, source="manual")
                bslug = target.brand_slug.lower()
                self.brand_aliases[bslug][norm] = self.alias_index[norm]

    # ---- normalization ----

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, collapse whitespace, strip."""
        if not text:
            return ""
        t = text.lower().strip()
        t = re.sub(r"\s+", " ", t)
        return t

    # ---- resolution ----

    def resolve(
        self,
        brand_hint: Optional[str],
        text: str,
        *,
        threshold: float = 0.5,
    ) -> Tuple[str, str, float, bool]:
        """
        Resolve text to (canonical_brand, canonical_model, confidence, ambiguity_flag).

        Args:
            brand_hint: Known brand name (English or Thai). May be None.
            text:       Text that may contain a model name (English/Thai/mixed).
            threshold:  Minimum confidence to accept a match (default 0.5).

        Returns:
            (brand_en, model_en, confidence, is_ambiguous)
        """
        if not self._loaded:
            self.load()

        norm_text = self._normalize(text)
        brand_norm = self._normalize(brand_hint) if brand_hint else ""

        # Step 1: Try direct alias lookup of the full text
        direct = self.alias_index.get(norm_text)
        if direct:
            return self._result(direct, 1.0, brand_norm)

        # Step 2: Strip common prefixes ("new", "all-new", "all new", "the", numbers)
        stripped = self._strip_prefixes(norm_text)
        if stripped != norm_text:
            entry = self.alias_index.get(stripped)
            if entry:
                return self._result(entry, 0.98, brand_norm)

        # Step 3: If brand_hint is given, try brand-scoped alias lookup
        if brand_norm:
            brand_candidates = self._find_brand_slugs(brand_norm)
            for bslug in brand_candidates:
                # Try full text against brand-scoped aliases
                ba = self.brand_aliases.get(bslug, {})
                for alias_len in range(len(norm_text), 0, -1):
                    candidate = norm_text[:alias_len].rstrip()
                    if candidate in ba:
                        entry = ba[candidate]
                        # Whole-word check
                        if self._is_whole_word(candidate, norm_text):
                            conf = min(0.95, 0.85 + 0.10 * (len(candidate) / len(norm_text)))
                            return self._result(entry, conf, brand_norm)

        # Step 4: Longest-match across ALL aliases (whole-word)
        best_entry: Optional[AliasEntry] = None
        best_len = 0
        for alias, entry in self.alias_index.items():
            if len(alias) < 2:
                continue
            # Check if alias appears as whole word in text
            if self._is_whole_word(alias, norm_text) or self._is_whole_word(alias, stripped):
                if len(alias) > best_len:
                    best_len = len(alias)
                    best_entry = entry
        if best_entry and best_len >= 2:
            conf = min(0.90, 0.60 + 0.30 * (best_len / max(len(norm_text), 1)))
            # Check cross-brand collision
            if self._is_collision(best_entry):
                return ("", "", 0.0, True)
            return self._result(best_entry, conf, brand_norm)

        # Step 5: Longest substring match (relaxed, no whole-word constraint)
        best_entry = None
        best_len = 0
        for alias, entry in self.alias_index.items():
            if len(alias) < 2:
                continue
            if alias in norm_text and len(alias) > best_len:
                best_len = len(alias)
                best_entry = entry
        if best_entry and best_len >= 3:
            conf = min(0.80, 0.40 + 0.40 * (best_len / max(len(norm_text), 1)))
            if self._is_collision(best_entry):
                return ("", "", 0.0, True)
            if conf >= threshold:
                return self._result(best_entry, conf, brand_norm)

        # Step 6: Fail closed
        return ("", "", 0.0, False)

    def _result(
        self, entry: AliasEntry, confidence: float, brand_hint_norm: str
    ) -> Tuple[str, str, float, bool]:
        """Build result tuple, bumping confidence if brand hint matches."""
        model = entry.model
        brand = model.brand_en
        model_name = model.model_en
        # If brand hint was provided and matches, confidence stays high
        if brand_hint_norm and brand_hint_norm not in model.brand_en.lower() and brand_hint_norm not in model.brand_th.lower():
            # Brand mismatch — lower confidence
            confidence *= 0.7
        # Check cross-brand collision
        ambig = self._is_collision(entry)
        if ambig:
            return ("", "", 0.0, True)
        return (brand, model_name, round(confidence, 4), False)

    def _find_brand_slugs(self, brand_norm: str) -> List[str]:
        """Find all brand slugs matching the given normalized brand name."""
        candidates = []
        for model in self.models:
            if (brand_norm == model.brand_en.lower() or
                brand_norm == model.brand_slug.lower() or
                brand_norm == model.brand_th.lower()):
                if model.brand_slug.lower() not in candidates:
                    candidates.append(model.brand_slug.lower())
        # Also try partial match
        if not candidates:
            for model in self.models:
                if brand_norm in model.brand_en.lower() or brand_norm in model.brand_th.lower():
                    if model.brand_slug.lower() not in candidates:
                        candidates.append(model.brand_slug.lower())
        return candidates

    @staticmethod
    def _strip_prefixes(text: str) -> str:
        """Remove common prefixes that appear in Thai media naming.
        Repeats until no more prefixes are found (handles 'the new civic' → 'civic')."""
        changed = True
        while changed:
            changed = False
            for prefix in ("all new ", "all-new ", "new ", "the "):
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    changed = True
                    break
        return text

    @staticmethod
    def _is_whole_word(alias: str, text: str) -> bool:
        """Check that alias appears as a whole word in text."""
        pattern = r"(?:^|\s)" + re.escape(alias) + r"(?:\s|$)"
        return bool(re.search(pattern, text))

    def _is_collision(self, entry: AliasEntry) -> bool:
        """Check if this alias is a known cross-brand collision."""
        slug = entry.model.slug.lower()
        for short_name, brands in self.collisions.items():
            if entry.alias == short_name or slug in [b[1] for b in brands]:
                # If multiple brands share this slug, it's ambiguous
                count = sum(1 for m in self.models if m.slug.lower() == slug)
                if count > 1:
                    return True
        return False

    # ---- report generation ----

    def export_report(self, path: str) -> dict:
        """Export identity report to JSON."""
        if not self._loaded:
            self.load()

        # Aggregate stats
        brand_count = len(set(m.brand_en for m in self.models))
        alias_count = len(self.alias_index)
        collision_count = len(self.collisions)

        report = {
            "generated": self._now_iso(),
            "total_models": len(self.models),
            "total_aliases": alias_count,
            "brands_covered": brand_count,
            "cross_brand_collisions": collision_count,
            "models": [],
        }

        for model in sorted(self.models, key=lambda m: (m.brand_en, m.model_en)):
            model_aliases = []
            for alias, entry in self.alias_index.items():
                if entry.model.model_id == model.model_id:
                    model_aliases.append({"alias": alias, "source": entry.source})
            report["models"].append({
                "model_id": model.model_id,
                "brand_en": model.brand_en,
                "brand_th": model.brand_th,
                "brand_slug": model.brand_slug,
                "model_en": model.model_en,
                "model_th": model.model_th,
                "slug": model.slug,
                "segment": model.segment or "",
                "aliases": model_aliases,
            })

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self._report = report
        return report

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # ---- convenience ----

    def get_model_by_slug(self, slug: str) -> Optional[ModelEntry]:
        return self.slug_to_model.get(slug.lower())

    def get_models_by_brand(self, brand: str) -> List[ModelEntry]:
        for m in self.models:
            if (brand.lower() in (m.brand_en.lower(), m.brand_slug.lower(), m.brand_th.lower())):
                return [x for x in self.models if x.brand_en == m.brand_en]
        return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_resolver: Optional[ModelIdentityResolver] = None


def get_resolver() -> ModelIdentityResolver:
    """Get or create the global resolver singleton."""
    global _resolver
    if _resolver is None:
        _resolver = ModelIdentityResolver()
        _resolver.load()
    return _resolver


def resolve(brand_hint: Optional[str], text: str) -> Tuple[str, str, float, bool]:
    """Convenience wrapper around get_resolver().resolve()."""
    return get_resolver().resolve(brand_hint, text)


# ---------------------------------------------------------------------------
# CLI: export report
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "storage", "identity-report.json",
    )
    r = get_resolver()
    report = r.export_report(out_path)
    print(f"Exported {report['total_models']} models, {report['total_aliases']} aliases, "
          f"{report['brands_covered']} brands to {out_path}")

    # Quick sanity tests
    tests = [
        ("Toyota", "Toyota Camry"),
        ("Toyota", "แคมรี่"),
        ("BYD", "ATTO 3"),
        ("BMW", "3 Series"),
        ("Tesla", "Model Y"),
        ("Mazda", "CX-5"),
        (None, "Fortuner"),
        ("Toyota", "Hilux Revo"),
        ("Nissan", "Navara"),
        ("Honda", "CR-V"),
        (None, "MG4"),
        ("GWM", "Haval H6"),
        (None, "Swift"),
        ("Volvo", "XC60"),
        ("Porsche", "Cayenne"),
        ("Subaru", "Outback"),
    ]
    for brand, text in tests:
        b, m, c, a = r.resolve(brand, text)
        status = "✓" if m else "✗"
        amb = " ⚠AMBIG" if a else ""
        print(f"  {status} resolve({brand!r}, {text!r}) -> ({b}, {m}, {c:.2f}){amb}")
