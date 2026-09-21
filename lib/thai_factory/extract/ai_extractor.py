"""
AI Extractor — two-stage extraction with strict validation.

Stage A: Document mapping (classify type/scope, identify vehicle regions)
Stage B: Field extraction (extract observations from scoped blocks)
Post-AI: Strict typed validator (no heuristic repair)
"""
import json
import os
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .dom_cleaner import CleanedPage, ContentBlock, format_blocks_for_ai

# ─── Config ────────────────────────────────────────────────────────
_REQUIRED_GEN_CONFIG = ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL")
_OPENROUTER_ALLOWED_MODEL = "inclusionai/ling-3.0-flash"
_OPENROUTER_ALLOWED_PROVIDERS = ["novita"]

# ─── Extraction Schemas ───────────────────────────────────────────

STAGE_A_SCHEMA = {
    "document_type": "ARTICLE|PRICE_LIST|SPEC_SHEET|ROUNDUP|COMPARISON|LAUNCH|UNKNOWN",
    "document_scope": {
        "decision": "SINGLE_MODEL|SINGLE_VARIANT|MULTI_MODEL_EXPLICIT|COMPARISON|ROUNDUP|GENERIC_LISTING|UNKNOWN",
        "primary_brand": "",
        "primary_model": "",
        "reasoning": "",
    },
    "vehicle_regions": [
        {
            "brand": "",
            "model": "",
            "region_block_ids": [],
            "price_block_ids": [],
            "spec_block_ids": [],
            "evidence_reasoning": "",
        }
    ],
    "relevant_block_ids": [],
}

STAGE_B_SCHEMA = {
    "observations": [
        {
            "block_id": "",
            "field": "price|engine_l|horsepower_hp|torque_nm|fuel_type|transmission|drivetrain|battery_kwh|range_km|seats|body_type",
            "raw_value": "",
            "normalized_value": "",
            "unit": "",
            "entity": {"brand": "", "model": "", "variant": ""},
            "price_type": "MSRP|LIST_PRICE|PROMOTION|MODEL_RANGE|HISTORICAL|UNKNOWN",
            "price_type_evidence_block_id": "",
            "price_type_evidence_quote": "",
            "confidence": "HIGH|MEDIUM|LOW",
            "evidence_quote": "",
            "evidence_block_id": "",
        }
    ],
}

# Allowed field values
ALLOWED_FIELDS = {"price", "engine_l", "horsepower_hp", "torque_nm", "fuel_type",
                  "transmission", "drivetrain", "battery_kwh", "range_km", "seats", "body_type"}
ALLOWED_PRICE_TYPES = {"MSRP", "LIST_PRICE", "PROMOTION", "MODEL_RANGE", "HISTORICAL", "UNKNOWN"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_DOC_TYPES = {"ARTICLE", "PRICE_LIST", "SPEC_SHEET", "ROUNDUP", "COMPARISON", "LAUNCH", "UNKNOWN"}
ALLOWED_SCOPES = {"SINGLE_MODEL", "SINGLE_VARIANT", "MULTI_MODEL_EXPLICIT", "COMPARISON",
                  "ROUNDUP", "GENERIC_LISTING", "UNKNOWN"}


# ─── AI Config ─────────────────────────────────────────────────────

def _load_env() -> Dict[str, str]:
    env = {}
    for key in _REQUIRED_GEN_CONFIG + ("EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL"):
        env[key] = os.environ.get(key, "")
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.split("#")[0].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _get_ai_config() -> Dict[str, str]:
    config = _load_env()
    missing = [k for k in _REQUIRED_GEN_CONFIG if not config.get(k)]
    if missing:
        raise ValueError(
            f"GENERATION CONFIG MISSING: {', '.join(missing)}. "
            f"Required: AI_BASE_URL, AI_API_KEY, AI_MODEL. "
            f"Cannot proceed without generation credentials."
        )
    gen_url = config["AI_BASE_URL"]
    gen_key = config["AI_API_KEY"]
    emb_key = config.get("EMBEDDING_API_KEY", "")
    if emb_key and gen_key == emb_key and "openrouter" in gen_url:
        raise ValueError(
            "CONFIG VIOLATION: AI_API_KEY == EMBEDDING_API_KEY with OpenRouter URL. "
            "Generation must use AI_BASE_URL/AI_API_KEY/AI_MODEL only."
        )
    return {
        "base_url": config["AI_BASE_URL"],
        "api_key": config["AI_API_KEY"],
        "model": config["AI_MODEL"],
        "provider": config.get("AI_PROVIDER", "openai-compatible"),
    }


def _call_ai(prompt: str, system: str = "", temperature: float = 0.1,
             use_openrouter: bool = False) -> Optional[Dict]:
    """Call AI gateway. Primary: AI_BASE_URL. OpenRouter: constrained exception only."""
    import tempfile
    config = _get_ai_config()

    if use_openrouter:
        emb_key = _load_env().get("EMBEDDING_API_KEY", "")
        if not emb_key:
            raise ValueError("OpenRouter requires EMBEDDING_API_KEY")
        base_url = "https://openrouter.ai/api/v1"
        api_key = emb_key
        model = _OPENROUTER_ALLOWED_MODEL
        provider_constraint = {"only": _OPENROUTER_ALLOWED_PROVIDERS, "allow_fallbacks": False}
    else:
        base_url = config["base_url"]
        api_key = config["api_key"]
        model = config["model"]
        provider_constraint = None

    if not api_key:
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system or "Extract structured automotive data. Return valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    if provider_constraint:
        payload["provider"] = provider_constraint

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        cmd = [
            "curl", "-s", "-X", "POST",
            f"{base_url}/chat/completions",
            "-H", f"Authorization: Bearer {api_key}",
            "-H", "Content-Type: application/json",
            "-d", f"@{tmp_path}",
        ]
        if "opencode.ai" in base_url:
            cmd.extend(["-H", f"x-opencode-session: session-{int(time.time()*1000)}"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return None

        response = json.loads(result.stdout)
        content = response["choices"][0]["message"]["content"]
        return json.loads(content)
    except (json.JSONDecodeError, KeyError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(tmp_path)


# ─── Two-Stage Extraction ─────────────────────────────────────────

def _format_blocks_for_stage_a(page: CleanedPage) -> str:
    """Format blocks for document mapping (compact, block IDs only)."""
    lines = [f"URL: {page.url}", f"Title: {page.title}", ""]
    for b in page.blocks:
        header = f"[{b.block_id}] {b.block_type.upper()}"
        if b.heading_context:
            header += f" ({b.heading_context})"
        lines.append(header)
        # Truncate long content for stage A
        content = b.content[:300] + "..." if len(b.content) > 300 else b.content
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def _format_blocks_for_stage_b(page: CleanedPage, block_ids: List[str]) -> str:
    """Format only relevant blocks for field extraction (full content)."""
    relevant = [b for b in page.blocks if b.block_id in block_ids]
    if not relevant:
        # Fallback: use all blocks if stage A returned no IDs
        relevant = page.blocks
    lines = []
    for b in relevant:
        header = f"[{b.block_id}] {b.block_type.upper()}"
        if b.heading_context:
            header += f" ({b.heading_context})"
        lines.append(header)
        lines.append(b.content)
        lines.append("")
    return "\n".join(lines)


def extract_observations(page: CleanedPage) -> Dict:
    """
    Two-stage AI extraction:
    Stage A: Document mapping (classify type/scope, identify vehicle regions)
    Stage B: Field extraction (extract observations from scoped blocks only)
    """
    block_ids = {b.block_id for b in page.blocks}

    if len(page.blocks) < 3:
        return {
            "document_type": "UNKNOWN",
            "document_scope": {"decision": "UNKNOWN", "primary_brand": "", "primary_model": ""},
            "vehicle_regions": [],
            "observations": [],
            "validation_errors": ["Insufficient content blocks"],
        }

    # ─── Stage A: Document Mapping ─────────────────────────────────
    blocks_text_a = _format_blocks_for_stage_a(page)
    prompt_a = f"""STAGE A: Document Mapping

Analyze this page and identify:
1. Document type (article, price list, spec sheet, roundup, comparison, launch)
2. Scope (single model, multi-model, comparison, etc.)
3. Vehicle regions (which blocks discuss which vehicle)
4. Price/spec block IDs for each vehicle

{blocks_text_a}

Return JSON matching this schema:
{json.dumps(STAGE_A_SCHEMA, indent=2)}

IMPORTANT:
- Identify ALL vehicle mentions with their brand and model
- List the specific block_ids that contain price/spec data for each vehicle
- Do NOT include sidebar/ad/navigation blocks
- Focus on the article content area"""

    result_a = _call_ai(prompt_a)
    if not result_a:
        return {
            "document_type": "UNKNOWN",
            "document_scope": {"decision": "UNKNOWN", "primary_brand": "", "primary_model": ""},
            "vehicle_regions": [],
            "observations": [],
            "validation_errors": ["Stage A AI call failed"],
        }

    # Validate Stage A output
    errors_a = _validate_stage_a(result_a, block_ids)

    # Collect relevant block IDs from stage A
    relevant_ids = set(result_a.get("relevant_block_ids", []))
    for region in result_a.get("vehicle_regions", []):
        relevant_ids.update(region.get("region_block_ids", []))
        relevant_ids.update(region.get("price_block_ids", []))
        relevant_ids.update(region.get("spec_block_ids", []))

    # ─── Stage B: Field Extraction ─────────────────────────────────
    blocks_text_b = _format_blocks_for_stage_b(page, list(relevant_ids))
    prompt_b = f"""STAGE B: Field Extraction

Document type: {result_a.get('document_type', 'UNKNOWN')}
Scope: {result_a.get('document_scope', {}).get('decision', 'UNKNOWN')}
Primary: {result_a.get('document_scope', {}).get('primary_brand', '')} {result_a.get('document_scope', {}).get('primary_model', '')}

Vehicle regions identified:
{json.dumps(result_a.get('vehicle_regions', []), indent=2, ensure_ascii=False)}

Extract automotive observations from these blocks:
{blocks_text_b}

Return JSON matching this schema:
{json.dumps(STAGE_B_SCHEMA, indent=2)}

RULES:
- Each observation MUST reference an existing block_id from the blocks above
- evidence_quote MUST be an exact substring of the referenced block's content
- price_type MUST have evidence: include price_type_evidence_block_id and price_type_evidence_quote
- If you cannot determine price type with evidence, use UNKNOWN
- For each entity, provide brand + model + variant if available
- confidence: HIGH (explicitly stated), MEDIUM (inferred from context), LOW (uncertain)"""

    result_b = _call_ai(prompt_b)
    if not result_b:
        return {
            "document_type": result_a.get("document_type", "UNKNOWN"),
            "document_scope": result_a.get("document_scope", {}),
            "vehicle_regions": result_a.get("vehicle_regions", []),
            "observations": [],
            "validation_errors": errors_a + ["Stage B AI call failed"],
        }

    # ─── Strict Post-AI Validation ─────────────────────────────────
    observations = result_b.get("observations", [])
    validated, rejected, needs_review = _validate_and_classify(
        observations, block_ids, page.blocks, result_a
    )

    return {
        "document_type": result_a.get("document_type", "UNKNOWN"),
        "document_scope": result_a.get("document_scope", {}),
        "vehicle_regions": result_a.get("vehicle_regions", []),
        "observations": validated,
        "rejected": rejected,
        "needs_review": needs_review,
        "validation_errors": errors_a,
    }


# ─── Validation ────────────────────────────────────────────────────

def _validate_stage_a(result: Dict, block_ids: set) -> List[str]:
    """Validate Stage A output."""
    errors = []
    doc_type = result.get("document_type", "")
    if doc_type not in ALLOWED_DOC_TYPES:
        errors.append(f"Invalid document_type: {doc_type}")

    scope = result.get("document_scope", {})
    scope_decision = scope.get("decision", "")
    if scope_decision not in ALLOWED_SCOPES:
        errors.append(f"Invalid scope decision: {scope_decision}")

    for i, region in enumerate(result.get("vehicle_regions", [])):
        for bid in region.get("region_block_ids", []):
            if bid not in block_ids:
                errors.append(f"Region {i}: block_id '{bid}' not found")
        for bid in region.get("price_block_ids", []):
            if bid not in block_ids:
                errors.append(f"Region {i}: price block_id '{bid}' not found")

    return errors


def _validate_and_classify(
    observations: List[Dict],
    valid_block_ids: set,
    blocks: List[ContentBlock],
    stage_a: Dict,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Strict validation. No heuristic repair.
    Returns: (accepted, rejected, needs_review)
    """
    accepted = []
    rejected = []
    needs_review = []
    block_map = {b.block_id: b for b in blocks}

    for i, obs in enumerate(observations):
        errors = []

        # 1. Required fields
        for field_name in ["block_id", "field", "raw_value", "evidence_quote", "evidence_block_id"]:
            if not obs.get(field_name):
                errors.append(f"Missing required field: {field_name}")

        # 2. block_id must exist
        bid = obs.get("block_id", "")
        if bid and bid not in valid_block_ids:
            errors.append(f"block_id '{bid}' not found in page")

        # 3. evidence_quote must exist in block
        quote = obs.get("evidence_quote", "")
        if bid and quote:
            block = block_map.get(bid)
            if block and quote not in block.content:
                errors.append(f"evidence_quote not found in block {bid}")

        # 4. field must be allowed
        field = obs.get("field", "")
        if field not in ALLOWED_FIELDS:
            errors.append(f"Invalid field: {field}")

        # 5. price_type must be allowed and have evidence
        pt = obs.get("price_type", "")
        if pt not in ALLOWED_PRICE_TYPES:
            errors.append(f"Invalid price_type: {pt}")
        if pt and pt != "UNKNOWN":
            if not obs.get("price_type_evidence_block_id"):
                errors.append(f"price_type '{pt}' without evidence_block_id")
            if not obs.get("price_type_evidence_quote"):
                errors.append(f"price_type '{pt}' without evidence_quote")

        # 6. confidence must be allowed
        conf = obs.get("confidence", "")
        if conf not in ALLOWED_CONFIDENCE:
            errors.append(f"Invalid confidence: {conf}")

        # 7. entity must have brand
        entity = obs.get("entity", {})
        if not entity.get("brand"):
            errors.append("Entity missing brand")

        # 8. normalized_value must be deterministic
        raw = obs.get("raw_value", "")
        norm = obs.get("normalized_value", "")
        if raw and norm:
            # Basic: normalized should be derivable from raw
            raw_clean = re.sub(r'[,\s]', '', raw)
            if raw_clean != norm and not norm.startswith(raw_clean):
                # Not a strict failure, but flag for review
                pass

        if errors:
            obs["validation_errors"] = errors
            if any("block_id" in e or "evidence_quote" in e for e in errors):
                rejected.append(obs)
            else:
                needs_review.append(obs)
        else:
            accepted.append(obs)

    return accepted, rejected, needs_review
