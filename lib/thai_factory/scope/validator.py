"""
Structured scope validator.

Classifies document/region scope into structured decisions:
SINGLE_MODEL, SINGLE_VARIANT, MULTI_MODEL_EXPLICIT, COMPARISON,
ROUNDUP, GENERIC_LISTING, UNKNOWN.

For each extracted field, stores the region/node that established its scope.
"""
import re
from typing import Dict, List, Optional
from ..models import ScopeResult, ScopeDecision
from ..identity.resolver import BRAND_KEYWORDS


# Comparison signals (Thai + English)
COMPARISON_PATTERNS = [
    r"เปรียบเทียบ",
    r"versus|vs\.?\b",
    r"เทียบ",
    r"เปรียบ",
    r"(\d+)\s*(?:แบรนด์|ยี่ห้อ|brand)",
]

# Roundup signals
ROUNDUP_PATTERNS = [
    r"ทุกยี่ห้อ",
    r"every brand",
    r"all brands",
    r"ทุกรุ่น",
    r"ทั้งหมด",
    r"ราคารถใหม่",
    r"ตารางราคา",
]

# Generic listing signals
LISTING_PATTERNS = [
    r"โปรโมชั่น",
    r"ส่วนลด",
    r"ดาวน์",
    r"ผ่อน",
    r"ออกรถ",
]


class ScopeValidator:
    """
    Structured scope validator for documents.
    """

    def __init__(self):
        self._brand_keywords = BRAND_KEYWORDS

    def validate(self, title: str, text: str,
                 brand_hint: Optional[str] = None) -> ScopeResult:
        """
        Validate document scope from title + full text.
        Returns structured ScopeResult.
        """
        lower_text = text.lower()
        lower_title = title.lower()

        # Count brand mentions
        brand_counts: Dict[str, int] = {}
        for brand, keywords in self._brand_keywords.items():
            count = 0
            for kw in keywords:
                count += len(re.findall(rf"\b{re.escape(kw)}\b", lower_text))
            if count > 0:
                brand_counts[brand] = count

        # Detect comparison signals
        for pattern in COMPARISON_PATTERNS:
            if re.search(pattern, lower_text):
                return ScopeResult(
                    decision=ScopeDecision.COMPARISON,
                    brand_mentions=brand_counts,
                    confidence=0.9,
                    reason=f"comparison_signal:{pattern}",
                )

        # Detect roundup signals
        for pattern in ROUNDUP_PATTERNS:
            if re.search(pattern, lower_text):
                return ScopeResult(
                    decision=ScopeDecision.ROUNDUP,
                    brand_mentions=brand_counts,
                    confidence=0.85,
                    reason=f"roundup_signal:{pattern}",
                )

        # Detect generic listing signals
        for pattern in LISTING_PATTERNS:
            if re.search(pattern, lower_text):
                return ScopeResult(
                    decision=ScopeDecision.GENERIC_LISTING,
                    brand_mentions=brand_counts,
                    confidence=0.7,
                    reason=f"listing_signal:{pattern}",
                )

        # Determine scope from brand counts
        if not brand_counts:
            return ScopeResult(
                decision=ScopeDecision.UNKNOWN,
                confidence=0.3,
                reason="no_brands_detected",
            )

        sorted_brands = sorted(brand_counts.items(), key=lambda x: -x[1])
        top_brand, top_count = sorted_brands[0]

        if len(sorted_brands) == 1:
            # Single brand
            return ScopeResult(
                decision=ScopeDecision.SINGLE_MODEL,
                primary_brand=top_brand,
                brand_mentions=brand_counts,
                confidence=0.8,
                reason="single_brand_dominant",
            )

        # Multiple brands
        second_brand, second_count = sorted_brands[1] if len(sorted_brands) > 1 else ("", 0)

        if top_count > second_count * 3 and top_count >= 3:
            # One brand dominates
            return ScopeResult(
                decision=ScopeDecision.SINGLE_MODEL,
                primary_brand=top_brand,
                brand_mentions=brand_counts,
                confidence=0.7,
                reason="brand_dominant",
            )

        if top_count == second_count or top_count <= second_count * 1.5:
            # Multiple brands with comparable mentions
            return ScopeResult(
                decision=ScopeDecision.MULTI_MODEL_EXPLICIT,
                primary_brand=top_brand,
                brand_mentions=brand_counts,
                confidence=0.6,
                reason="multi_brand_comparable",
            )

        # Default: single model with lower confidence
        return ScopeResult(
            decision=ScopeDecision.SINGLE_MODEL,
            primary_brand=top_brand,
            brand_mentions=brand_counts,
            confidence=0.5,
            reason="default_single",
        )
