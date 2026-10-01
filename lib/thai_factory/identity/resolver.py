"""
Two-stage identity resolver.

Stage A: Deterministic lexical resolution (exact aliases).
Stage B: Contextual scoring (proximity, mentions, brand context).

Output: structured IdentityResult with RESOLVED / AMBIGUOUS / UNRESOLVED.
"""
import re
from typing import Dict, List, Optional, Tuple
from ..models import IdentityResult, IdentityDecision


# ─── Brand Keywords (Thai + English) ────────────────────────────────

BRAND_KEYWORDS: Dict[str, List[str]] = {
    "toyota": ["toyota", "โตโยต้า", "yaris", "corolla", "camry", "fortuner",
               "hilux", "innova", "veloz", "avanza", "bz4x", "land cruiser",
               "alphard", "hiace", "commuter", "rav4"],
    "honda": ["honda", "ฮอนด้า", "city", "civic", "hr-v", "cr-v", "br-v",
              "accord", "wr-v", "zr-v"],
    "nissan": ["nissan", "นิสสัน", "almera", "kicks", "x-trail", "terra",
               "navara", "serena", "leaf", "sakura", "urvan"],
    "mazda": ["mazda", "มาสด้า", "mazda2", "mazda3", "cx-3", "cx-30", "cx-5",
              "cx-80", "cx-60", "cx-90", "6e"],
    "mg": ["mg", "mg3", "mg4", "mg5", "zs-ev", "hs-", "im5", "im6", "s5-ev"],
    "byd": ["byd", "บีวายดี", "atto", "dolphin", "seal", "sealion", "m6"],
    "gwm": ["gwm", "haval", "ora", "tank"],
    "ford": ["ford", "ฟอร์ด", "ranger", "everest", "territory"],
    "isuzu": ["isuzu", "อีซูซุ", "d-max", "mu-x"],
    "bmw": ["bmw", "ซีรีส์", "iX", "i5"],
    "mercedes-benz": ["mercedes", "เบนซ์", "เมอร์เซเดส", "class", "gla", "glc", "gle"],
    "volvo": ["volvo", "วอลโว่", "xc40", "xc60", "xc90", "ex30"],
    "hyundai": ["hyundai", "ฮุนได", "ioniq", "santa fe", "stargazer", "staria"],
    "kia": ["kia", "เกีย", "sonet", "sportage", "ev6", "ev9", "carnival"],
    "suzuki": ["suzuki", "ซูซูกิ", "swift", "vitara", "xl7", "fronx", "jimny"],
    "mitsubishi": ["mitsubishi", "มิตซูบิชิ", "mirage", "attrage", "xpander",
                    "triton", "pajero"],
    "subaru": ["subaru", "สубารุ", "crosstrek", "outback", "forester"],
    "porsche": ["porsche", "ปอร์เช่", "cayenne", "macan", "taycan"],
    "mini": ["mini", "cooper", "countryman", "aceman"],
    "tesla": ["tesla", "เทสลา", "model 3", "model y"],
    "denza": ["denza", "ดีนซ่า", "d9", "n7", "z9gt"],
    "geely": ["geely", "geely", "starray", "ex5"],
    "changan": ["changan", "ช้าง", "cs55", "uni-v", "uni-k", "deepal"],
    "lexus": ["lexus", "เล็กซัส", "nx", "rx", "rz"],
    "nio": ["nio", "nio", "es6", "et5", "firefly"],
    "zeekr": ["zeekr", "zeekr"],
    "chery": ["chery", "เชอรี่", "omoda", "tiggo", "jaecoo"],
    "xpeng": ["xpeng", "เอ็กซ์ปง", "g6", "g9"],
    "mg": ["mg", "mg3", "mg4", "mg5", "zs-ev", "im5", "im6"],
    "dongfeng": ["dongfeng", "东风"],
    "ldv": ["ldv", "d90", "t60"],
    "baic": ["baic", "x55", "bj30"],
    "jetour": ["jetour", "dashing", "t2"],
    "kg-mobility": ["kg mobility", "torres", "korando"],
    "avatr": ["avatr", "avatr", "11"],
    "nio": ["nio", "es6", "et5", "firefly"],
}

# ─── Manual Aliases ─────────────────────────────────────────────────
# Maps common variants to canonical model slugs

MANUAL_ALIASES = {
    "hilux revo": ("toyota", "hilux"),
    "innova crysta": ("toyota", "innova"),
    "innova zenix": ("toyota", "innova"),
    "fortuner legender": ("toyota", "fortuner"),
    "fortuner gr sport": ("toyota", "fortuner"),
    "corolla altis": ("toyota", "corolla altis"),
    "corolla cross": ("toyota", "corolla cross"),
    "yaris ativ": ("toyota", "yaris ativ"),
    "yaris cross": ("toyota", "yaris cross"),
    "city hatchback": ("honda", "city hatchback"),
    "civic type r": ("honda", "civic type r"),
    "haval jolion": ("gwm", "haval jolion"),
    "haval h6": ("gwm", "haval h6"),
    "ora good cat": ("gwm", "ora good cat"),
    "tank 300": ("gwm", "tank 300"),
    "tank 500": ("gwm", "tank 500"),
    "mg hs phev": ("mg", "mg hs phev"),
    "mg zs ev": ("mg", "mg zs ev"),
    "atto 2": ("byd", "atto 2"),
    "atto 3": ("byd", "atto 3"),
    "seal 5": ("byd", "seal 5"),
    "sealion 5": ("byd", "sealion 5"),
    "sealion 6": ("byd", "sealion 6"),
    "sealion 7": ("byd", "sealion 7"),
    "omoda 5": ("chery", "omoda 5"),
    "tiggo 8 pro": ("chery", "tiggo 8 pro"),
    "jaecoo j7": ("chery", "jaecoo j7"),
    "pajero sport": ("mitsubishi", "pajero sport"),
    "xpander cross": ("mitsubishi", "xpander cross"),
    "cs55 plus": ("changan", "cs55 plus"),
    "deepal s07": ("changan", "deepal s07"),
    "model 3": ("tesla", "model 3"),
    "model y": ("tesla", "model y"),
}


class IdentityResolver:
    """
    Two-stage identity resolver.

    Stage A: Deterministic lexical resolution.
    Stage B: Contextual scoring.
    """

    def __init__(self):
        self._brand_index: Dict[str, str] = {}  # keyword -> brand slug
        self._model_index: Dict[str, Tuple[str, str]] = {}  # keyword -> (brand, model)
        self._alias_index: Dict[str, Tuple[str, str]] = {}  # normalized -> (brand, model)
        self._build_indices()

    def _build_indices(self):
        """Build lookup indices from brand keywords and manual aliases."""
        for brand, keywords in BRAND_KEYWORDS.items():
            for kw in keywords:
                self._brand_index[kw.lower()] = brand

        for alias, (brand, model) in MANUAL_ALIASES.items():
            self._alias_index[alias.lower()] = (brand, model)

    def resolve(self, brand_hint: Optional[str], text: str) -> IdentityResult:
        """
        Resolve brand/model from text.

        Stage A: Try exact alias match.
        Stage B: Contextual scoring with brand hint.
        """
        if not text:
            return IdentityResult(
                decision=IdentityDecision.UNRESOLVED,
                reason="empty_text",
            )

        lower = text.lower()

        # Stage A: Exact alias match
        for alias, (brand, model) in self._alias_index.items():
            if alias in lower:
                return IdentityResult(
                    decision=IdentityDecision.RESOLVED,
                    canonical_brand=brand,
                    canonical_model=model,
                    confidence=0.95,
                    reason=f"EXACT_ALIAS:{alias}",
                    evidence=[alias],
                )

        # Stage A: Brand keyword match
        detected_brand = ""
        if brand_hint:
            hint_lower = brand_hint.lower()
            for kw, brand in self._brand_index.items():
                if brand == hint_lower:
                    detected_brand = brand
                    break
            if not detected_brand:
                detected_brand = hint_lower

        if not detected_brand:
            # Find brand from text
            best_pos = -1
            for kw, brand in self._brand_index.items():
                pos = lower.find(kw)
                if pos != -1 and (best_pos == -1 or pos < best_pos):
                    detected_brand = brand
                    best_pos = pos

        if not detected_brand:
            return IdentityResult(
                decision=IdentityDecision.UNRESOLVED,
                reason="no_brand_found",
            )

        # Stage B: Contextual model extraction
        brand_kws = BRAND_KEYWORDS.get(detected_brand, [])
        model_mentions = {}

        for kw in brand_kws:
            count = lower.count(kw.lower())
            if count > 0 and kw.lower() != detected_brand:
                model_mentions[kw] = count

        if not model_mentions:
            return IdentityResult(
                decision=IdentityDecision.RESOLVED,
                canonical_brand=detected_brand,
                confidence=0.6,
                reason="BRAND_ONLY",
            )

        # Pick model with most mentions
        best_model = max(model_mentions, key=model_mentions.get)
        best_count = model_mentions[best_model]

        # Check for ambiguity
        if best_count > 1:
            return IdentityResult(
                decision=IdentityDecision.RESOLVED,
                canonical_brand=detected_brand,
                canonical_model=best_model,
                confidence=0.8,
                reason=f"CONTEXT_MENTIONS:{best_count}",
            )
        else:
            # Single mention — still resolved but lower confidence
            return IdentityResult(
                decision=IdentityDecision.RESOLVED,
                canonical_brand=detected_brand,
                canonical_model=best_model,
                confidence=0.65,
                reason="SINGLE_MENTION",
            )

    def resolve_brand(self, text: str) -> Optional[str]:
        """Quick brand-only resolution."""
        lower = text.lower()
        best_pos = -1
        best_brand = ""
        for kw, brand in self._brand_index.items():
            pos = lower.find(kw)
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_brand = brand
                best_pos = pos
        return best_brand or None


# ─── Toyota Series Code Mapping ────────────────────────────────────
# Maps Toyota OEM API series_code to canonical model name.
# Used to validate that a source endpoint matches the asserted model.
TOYOTA_SERIES_CODE_MAP: Dict[str, str] = {
    "yaris": "Yaris",
    "yarisativ": "Yaris ATIV",
    "yaris_cross": "Yaris Cross",
    "altis": "Corolla Altis",
    "corollacross": "Corolla Cross",
    "camry": "Camry",
    "hilux": "Hilux",
    "fortuner": "Fortuner",
    "fortuner_le": "Fortuner Legender",
    "innovacross": "Innova Zenix",
    "innova": "Innova Zenix",
    "veloz": "Veloz",
    "avanza": "Avanza",
    "bz4x": "bZ4X",
    "grcorolla": "GR Corolla",
    "gryaris": "GR Yaris",
    "landcruiser": "Land Cruiser",
    "alphard": "Alphard",
    "hiace": "Hiace",
    "commuter": "Commuter",
}


def validate_toyota_series_code(url: str, expected_model: str) -> Tuple[bool, str]:
    """
    Validate that a Toyota OEM API URL's series_code matches the expected model.
    Returns (is_valid, reason).
    """
    if "toyota.co.th" not in url:
        return True, "not_toyota_oem"

    m = re.search(r"series_code=(\w+)", url)
    if not m:
        return True, "no_series_code"

    series_code = m.group(1).lower()
    mapped_model = TOYOTA_SERIES_CODE_MAP.get(series_code)

    if not mapped_model:
        return False, f"unknown_series_code:{series_code}"

    if mapped_model.lower() == expected_model.lower():
        return True, "series_code_matches"

    return False, f"series_code_mismatch:{series_code}->{mapped_model}!=expected:{expected_model}"
