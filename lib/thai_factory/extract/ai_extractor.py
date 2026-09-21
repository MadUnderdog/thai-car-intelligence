"""
AI Extractor — structured extraction using existing AI gateway.

Uses OpenAI-compatible API with structured JSON output.
Two-stage extraction: document understanding + field extraction.
"""
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .dom_cleaner import CleanedPage, ContentBlock, format_blocks_for_ai


# ─── Extraction Schema ─────────────────────────────────────────────

EXTRACTION_SCHEMA = {
    "document_type": "ARTICLE|PRICE_LIST|SPEC_SHEET|ROUNDUP|COMPARISON|UNKNOWN",
    "document_scope": {
        "decision": "SINGLE_MODEL|SINGLE_VARIANT|MULTI_MODEL_EXPLICIT|COMPARISON|ROUNDUP|GENERIC_LISTING|UNKNOWN",
        "primary_brand": "",
        "primary_model": "",
        "evidence_block_ids": []
    },
    "observations": [
        {
            "block_id": "",
            "field": "price|power_hp|power_kw|torque_nm|engine_cc|engine_l|fuel_type|transmission|drive_type|length_mm|width_mm|height_mm|wheelbase_mm|weight_kg|battery_kwh|range_km|seating",
            "brand": "",
            "model": "",
            "variant": "",
            "raw_value": "",
            "normalized_value": "",
            "unit": "",
            "price_type": "MSRP|LIST_PRICE|PROMOTION|MODEL_RANGE|HISTORICAL|UNKNOWN",
            "identity_decision": "RESOLVED|AMBIGUOUS|UNRESOLVED",
            "scope_decision": "SINGLE_MODEL|SINGLE_VARIANT|MULTI_MODEL_EXPLICIT|COMPARISON|ROUNDUP|GENERIC_LISTING|UNKNOWN",
            "evidence_quote": "",
            "confidence": 0.0,
            "reason": ""
        }
    ]
}


# ─── System Prompt ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an automotive data extraction engine, NOT a summarizer.

RULES:
- Extract only facts explicitly present in the supplied source blocks.
- Never infer a trim/variant from a nearby number unless the source block explicitly links them.
- Never assign a price to a model merely because the model appears elsewhere on the page.
- Never move a value across headings, cards, table rows, or unrelated blocks.
- A shared/sidebar/recommendation price block is UNSCOPED unless the block itself identifies the vehicle.
- A model-range price must remain MODEL_RANGE.
- Promotion/special/launch/early-bird/dealer/warehouse prices must not become MSRP.
- Historical prices must remain HISTORICAL.
- When variant identity is not explicitly supported, output AMBIGUOUS or UNRESOLVED.
- Do not invent missing values.
- Every observation MUST cite one or more supplied block_ids.
- evidence_quote must be copied from those blocks, not generated.
- If the page does not contain sufficient evidence, return no observation rather than guessing.
- Prefer exact Thai/English trim names from the source.
- Preserve source terminology before normalization.

OUTPUT: Valid JSON matching the extraction schema provided in the user message."""


# ─── AI Client ─────────────────────────────────────────────────────
# CONFIG BOUNDARY: Generation uses ONLY these 3 env vars.
# EMBEDDING_* must NEVER be used for generation.
# No provider fallback. No hardcoded models. Fail-closed.

_REQUIRED_GEN_CONFIG = ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL")


def _load_env() -> Dict:
    """Load .env file into dict. Separated for testability."""
    config = {}
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    val = val.split("#")[0].strip()
                    config[key.strip()] = val.strip().strip('"').strip("'")
    return config


def _get_ai_config() -> Dict:
    """
    Load generation config from .env. FAIL-CLOSED.
    Uses ONLY AI_BASE_URL, AI_API_KEY, AI_MODEL.
    Raises ValueError if any required config is missing.
    Never uses EMBEDDING_* credentials. Never falls back to other providers.
    """
    config = _load_env()

    # Validate required generation config
    missing = [k for k in _REQUIRED_GEN_CONFIG if not config.get(k)]
    if missing:
        raise ValueError(
            f"GENERATION CONFIG MISSING: {', '.join(missing)}. "
            f"Required: AI_BASE_URL, AI_API_KEY, AI_MODEL. "
            f"Cannot proceed without generation credentials."
        )

    # Verify we're NOT accidentally using embedding credentials
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


def _call_ai(prompt: str, system: str = SYSTEM_PROMPT, temperature: float = 0.1) -> Optional[Dict]:
    """Call AI gateway with structured extraction prompt. Uses temp file for large prompts."""
    import tempfile
    config = _get_ai_config()

    base_url = config["base_url"]
    api_key = config["api_key"]
    model = config["model"]

    if not api_key:
        return None

    # Build request
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }

    # Write payload to temp file to avoid argument list too long
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

        # OpenCode requires x-opencode-session header
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


# ─── Two-Stage Extraction ──────────────────────────────────────────

def extract_observations(page: CleanedPage) -> Dict:
    """
    Two-stage AI extraction:
    Stage A: Document understanding (classify type/scope, identify sections)
    Stage B: Field extraction (extract observations from scoped blocks)
    """
    # Format blocks for AI input
    blocks_text = format_blocks_for_ai(page)

    # Check if page has meaningful content
    if len(page.blocks) < 3:
        return {
            "document_type": "UNKNOWN",
            "document_scope": {"decision": "UNKNOWN", "primary_brand": "", "primary_model": "", "evidence_block_ids": []},
            "observations": [],
            "validation_errors": ["Insufficient content blocks"],
        }

    # Build extraction prompt
    prompt = f"""Extract automotive data from this cleaned page.

{blocks_text}

Return JSON matching this schema:
{json.dumps(EXTRACTION_SCHEMA, indent=2)}

Focus on:
1. Identify document type (article, price list, spec sheet, roundup, comparison)
2. Determine scope (single model, multi-model, comparison, etc.)
3. Extract price and specification observations with exact block_id references
4. For each observation, copy the exact evidence_quote from the source block
5. Preserve Thai/English terminology exactly as in source"""

    # Stage A+B: Single AI call with structured output
    result = _call_ai(prompt)

    if not result:
        return {
            "document_type": "UNKNOWN",
            "document_scope": {"decision": "UNKNOWN", "primary_brand": "", "primary_model": "", "evidence_block_ids": []},
            "observations": [],
            "validation_errors": ["AI call failed"],
        }

    # Validate extraction
    validation_errors = _validate_extraction(result, page)

    result["validation_errors"] = validation_errors
    return result


def _validate_extraction(result: Dict, page: CleanedPage) -> List[str]:
    """Validate extraction results against source blocks."""
    errors = []
    block_ids = {b.block_id for b in page.blocks}

    # Validate document scope
    scope = result.get("document_scope", {})
    if scope.get("evidence_block_ids"):
        for bid in scope["evidence_block_ids"]:
            if bid not in block_ids:
                errors.append(f"Scope evidence block_id not found: {bid}")

    # Validate observations
    for i, obs in enumerate(result.get("observations", [])):
        # Block ID must exist
        bid = obs.get("block_id", "")
        if bid and bid not in block_ids:
            errors.append(f"Obs {i}: block_id '{bid}' not found in page")

        # Evidence quote must exist in block
        quote = obs.get("evidence_quote", "")
        if bid and quote:
            block = next((b for b in page.blocks if b.block_id == bid), None)
            if block and quote not in block.text:
                errors.append(f"Obs {i}: evidence_quote not found in block {bid}")

        # Normalized value must correspond to raw value
        raw = obs.get("raw_value", "")
        norm = obs.get("normalized_value", "")
        if raw and norm:
            # Basic check: normalized should be derivable from raw
            raw_clean = re.sub(r'[,\s]', '', raw)
            if raw_clean != norm and not norm.startswith(raw_clean):
                errors.append(f"Obs {i}: normalized_value '{norm}' doesn't match raw_value '{raw}'")

        # Price type consistency
        if obs.get("field") == "price":
            pt = obs.get("price_type", "")
            if pt == "MSRP" and obs.get("scope_decision") == "ROUNDUP":
                errors.append(f"Obs {i}: MSRP in ROUNDUP scope is suspicious")

    return errors
