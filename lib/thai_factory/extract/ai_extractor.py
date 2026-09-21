"""
AI Extractor — two-stage extraction with strict validation.

Stage A: Document mapping (classify type/scope, identify article body + vehicle regions)
Stage B: Field extraction per vehicle region (scoped blocks only)
Post-AI: Strict typed validator (no heuristic repair)
"""
import hashlib
import json
import os
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from .dom_cleaner import CleanedPage, ContentBlock

_REQUIRED_GEN_CONFIG = ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL")
_OPENROUTER_ALLOWED_MODEL = "inclusionai/ling-3.0-flash"
_OPENROUTER_ALLOWED_PROVIDERS = ["novita"]

STAGE_B_SCHEMA = {
    "observations": [{
        "block_id": "", "field": "price|engine_l|horsepower_hp|torque_nm|fuel_type|transmission|drivetrain|battery_kwh|range_km|seats|body_type",
        "raw_value": "", "normalized_value": "", "unit": "",
        "entity": {"brand": "", "model": "", "variant": ""},
        "price_type": "MSRP|LIST_PRICE|PROMOTION|MODEL_RANGE|HISTORICAL|UNKNOWN",
        "price_type_evidence_block_id": "", "price_type_evidence_quote": "",
        "confidence": "HIGH|MEDIUM|LOW",
        "evidence_quote": "", "evidence_block_id": "",
    }],
}

ALLOWED_FIELDS = {"price", "engine_l", "horsepower_hp", "torque_nm", "fuel_type",
                  "transmission", "drivetrain", "battery_kwh", "range_km", "seats", "body_type"}
ALLOWED_PRICE_TYPES = {"MSRP", "LIST_PRICE", "PROMOTION", "MODEL_RANGE", "HISTORICAL", "UNKNOWN"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_DOC_TYPES = {"ARTICLE", "PRICE_LIST", "SPEC_SHEET", "ROUNDUP", "COMPARISON", "LAUNCH", "UNKNOWN"}
ALLOWED_SCOPES = {"SINGLE_MODEL", "SINGLE_VARIANT", "MULTI_MODEL_EXPLICIT", "COMPARISON",
                  "ROUNDUP", "GENERIC_LISTING", "UNKNOWN"}

NAVIGATION_KEYWORDS = [
    "หน้าแรก", "Review By Brand", "View by Brand", "View by Segment",
    "Sign in", "Search", "Close", "Accept", "Read more",
    "NEWS", "SPYSHOT", "MOTOR SHOW", "CONTACT", "WEBBOARD",
    "Copyright", "Privacy Policy", "Terms of Use",
]


# ─── AI Config ─────────────────────────────────────────────────────

def _load_env():
    env = {}
    for key in _REQUIRED_GEN_CONFIG + ("EMBEDDING_BASE_URL", "EMBEDDING_API_KEY"):
        env[key] = os.environ.get(key, "")
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _get_ai_config():
    config = _load_env()
    missing = [k for k in _REQUIRED_GEN_CONFIG if not config.get(k)]
    if missing:
        raise ValueError(f"GENERATION CONFIG MISSING: {', '.join(missing)}")
    gen_url = config["AI_BASE_URL"]
    gen_key = config["AI_API_KEY"]
    emb_key = config.get("EMBEDDING_API_KEY", "")
    if emb_key and gen_key == emb_key and "openrouter" in gen_url:
        raise ValueError("CONFIG VIOLATION: AI_API_KEY == EMBEDDING_API_KEY with OpenRouter")
    return {"base_url": config["AI_BASE_URL"], "api_key": config["AI_API_KEY"],
            "model": config["AI_MODEL"], "provider": config.get("AI_PROVIDER", "openai-compatible")}


def _call_ai(prompt, system="", temperature=0.1, use_openrouter=False):
    import tempfile
    config = _get_ai_config()
    if use_openrouter:
        emb_key = _load_env().get("EMBEDDING_API_KEY", "")
        if not emb_key:
            raise ValueError("OpenRouter requires EMBEDDING_API_KEY")
        base_url, api_key, model = "https://openrouter.ai/api/v1", emb_key, _OPENROUTER_ALLOWED_MODEL
        pc = {"only": _OPENROUTER_ALLOWED_PROVIDERS, "allow_fallbacks": False}
    else:
        base_url, api_key, model = config["base_url"], config["api_key"], config["model"]
        pc = None
    if not api_key:
        return None
    payload = {"model": model, "messages": [
        {"role": "system", "content": system or "Extract structured automotive data. Return valid JSON."},
        {"role": "user", "content": prompt}],
        "temperature": temperature, "response_format": {"type": "json_object"}}
    if pc:
        payload["provider"] = pc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp = f.name
    try:
        cmd = ["curl", "-s", "-X", "POST", f"{base_url}/chat/completions",
               "-H", f"Authorization: Bearer {api_key}",
               "-H", "Content-Type: application/json", "-d", f"@{tmp}"]
        if "opencode.ai" in base_url:
            cmd.extend(["-H", f"x-opencode-session: session-{int(time.time()*1000)}"])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return None
        resp = json.loads(result.stdout)
        return json.loads(resp["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(tmp)


# ─── Block Filtering (Gate 3) ─────────────────────────────────────

def _is_navigation_block(block):
    text = block.content.strip()
    if len(text) < 15 and block.block_type == "list":
        return True
    for kw in NAVIGATION_KEYWORDS:
        if text.lower() == kw.lower() or text.lower().startswith(kw.lower()):
            return True
    if block.block_type == "list" and text.count("http") > 2:
        return True
    return False


def _filter_article_blocks(blocks):
    article_ids = []
    in_article = False
    heading_count = 0
    for b in blocks:
        if b.block_type == "heading":
            heading_count += 1
            if heading_count >= 2:
                in_article = True
            if not _is_navigation_block(b):
                article_ids.append(b.block_id)
            continue
        if _is_navigation_block(b):
            continue
        if in_article or (heading_count >= 1 and b.block_type in ("paragraph", "table")):
            if len(b.content) > 20:
                article_ids.append(b.block_id)
    return article_ids


# ─── Two-Stage Extraction ─────────────────────────────────────────

def _format_compact(blocks, ids):
    lines = []
    for b in blocks:
        if b.block_id not in ids:
            continue
        h = f"[{b.block_id}] {b.block_type.upper()}"
        if b.heading_context:
            h += f" ({b.heading_context})"
        lines.append(h)
        lines.append(b.content[:300] + "..." if len(b.content) > 300 else b.content)
        lines.append("")
    return "\n".join(lines)


def _format_region(blocks, ids):
    lines = []
    for b in blocks:
        if b.block_id not in ids:
            continue
        h = f"[{b.block_id}] {b.block_type.upper()}"
        if b.heading_context:
            h += f" ({b.heading_context})"
        lines.append(h)
        lines.append(b.content)
        lines.append("")
    return "\n".join(lines)


def extract_observations(page):
    all_ids = {b.block_id for b in page.blocks}
    if len(page.blocks) < 3:
        return _empty("Insufficient content blocks")

    article_ids = set(_filter_article_blocks(page.blocks))
    if len(article_ids) < 3:
        article_ids = all_ids

    # ─── Stage A ───────────────────────────────────────────────────
    bt = _format_compact(page.blocks, article_ids)
    if len(bt) > 4000:
        bt = bt[:4000] + "\n... (truncated)"

    pa = STAGE_A_PROMPT.format(blocks=bt)
    ra = _call_ai(pa)
    if not ra:
        return _empty("Stage A AI call failed")

    errors_a = _validate_stage_a(ra, all_ids)

    ab_ids = set(ra.get("article_body_block_ids", []))
    if not ab_ids:
        ab_ids = article_ids

    regions = ra.get("vehicle_regions", [])
    all_obs, all_rej, all_rev = [], [], []

    # ─── Stage B per region ────────────────────────────────────────
    for region in regions:
        rids = set(region.get("region_block_ids", []))
        pids = set(region.get("price_block_ids", []))
        sids = set(region.get("spec_block_ids", []))
        scoped = (rids | pids | sids) & ab_ids
        if not scoped:
            continue
        if len(scoped) > 20:
            scoped = set(list(scoped)[:20])

        bt_b = _format_region(page.blocks, scoped)
        if not bt_b.strip():
            continue

        brand = region.get("brand", "")
        model = region.get("model", "")
        pb = _stage_b_prompt(brand, model, bt_b)
        rb = _call_ai(pb)
        if not rb:
            continue

        obs = rb.get("observations", [])
        v, r, rv = _validate(obs, all_ids, page.blocks, region)
        all_obs.extend(v)
        all_rej.extend(r)
        all_rev.extend(rv)

    deduped = _dedup(all_obs)
    return {
        "document_type": ra.get("document_type", "UNKNOWN"),
        "document_scope": ra.get("document_scope", {}),
        "vehicle_regions": regions,
        "observations": deduped,
        "rejected": all_rej,
        "needs_review": all_rev,
        "validation_errors": errors_a,
    }


def _empty(reason):
    return {"document_type": "UNKNOWN",
            "document_scope": {"decision": "UNKNOWN", "primary_brand": "", "primary_model": ""},
            "vehicle_regions": [], "observations": [], "rejected": [],
            "needs_review": [], "validation_errors": [reason]}


# ─── Prompts ───────────────────────────────────────────────────────

STAGE_A_PROMPT = """STAGE A: Document Mapping

You must return EXACTLY this JSON structure (all enum values must be UPPERCASE):
{{
  "document_type": "ARTICLE" or "PRICE_LIST" or "SPEC_SHEET" or "ROUNDUP" or "COMPARISON" or "LAUNCH" or "UNKNOWN",
  "document_scope": {{
    "decision": "SINGLE_MODEL" or "SINGLE_VARIANT" or "MULTI_MODEL_EXPLICIT" or "COMPARISON" or "ROUNDUP" or "GENERIC_LISTING" or "UNKNOWN",
    "primary_brand": "",
    "primary_model": ""
  }},
  "article_body_block_ids": ["block_id1", "block_id2"],
  "vehicle_regions": [
    {{
      "brand": "BrandName",
      "model": "ModelName",
      "region_block_ids": ["block_id"],
      "price_block_ids": ["block_id"],
      "spec_block_ids": ["block_id"]
    }}
  ]
}}

Analyze these blocks from the article:
{blocks}

Rules:
- document_type MUST be one of the exact values above (UPPERCASE)
- document_scope.decision MUST be one of the exact values above (UPPERCASE)
- article_body_block_ids: only blocks from the main article content (not sidebar/nav/ads)
- vehicle_regions: identify each vehicle discussed with its brand and model
- Each vehicle region lists block_ids that SPECIFICALLY discuss that vehicle"""

def _stage_b_prompt(brand, model, blocks):
    return f"""STAGE B: Field Extraction for {brand} {model}

Extract automotive observations for {brand} {model} ONLY from these blocks:
{blocks}

Return JSON matching this schema:
{{
  "observations": [
    {{
      "block_id": "",
      "field": "price",
      "raw_value": "",
      "normalized_value": "",
      "unit": "",
      "entity": {{"brand": "", "model": "", "variant": ""}},
      "price_type": "MSRP",
      "price_type_evidence_block_id": "",
      "price_type_evidence_quote": "",
      "confidence": "HIGH",
      "evidence_quote": "",
      "evidence_block_id": ""
    }}
  ]
}}

CRITICAL RULES:
- Extract ONLY data for {brand} {model}
- Each observation MUST reference a block_id from the blocks above
- evidence_quote MUST be an exact substring of the referenced block's content
- price_type MUST have evidence: price_type_evidence_block_id and price_type_evidence_quote
- If you cannot determine price type with evidence, use UNKNOWN
- confidence: HIGH (explicitly stated), MEDIUM (inferred), LOW (uncertain)"""


# ─── Validation (Gate 5) ──────────────────────────────────────────

def _validate_stage_a(result, block_ids):
    errors = []
    dt = result.get("document_type", "")
    if dt not in ALLOWED_DOC_TYPES:
        errors.append(f"Invalid document_type: {dt}")
    sd = result.get("document_scope", {}).get("decision", "")
    if sd not in ALLOWED_SCOPES:
        errors.append(f"Invalid scope: {sd}")
    for i, reg in enumerate(result.get("vehicle_regions", [])):
        for bid in reg.get("region_block_ids", []):
            if bid not in block_ids:
                errors.append(f"Region {i}: block_id '{bid}' not found")
    return errors


def _validate(observations, valid_ids, blocks, region):
    accepted, rejected, review = [], [], []
    bmap = {b.block_id: b for b in blocks}
    rbrand = region.get("brand", "")

    for obs in observations:
        errs = []
        # Required fields
        for fn in ["block_id", "field", "raw_value", "evidence_quote", "evidence_block_id"]:
            if not obs.get(fn):
                errs.append(f"Missing: {fn}")
        # block_id exists
        bid = obs.get("block_id", "")
        if bid and bid not in valid_ids:
            errs.append(f"block_id '{bid}' not found")
        # evidence_quote in block
        q = obs.get("evidence_quote", "")
        if bid and q:
            blk = bmap.get(bid)
            if blk and q not in blk.content:
                errs.append(f"quote not in block {bid}")
        # evidence_block_id exists and contains quote
        ebid = obs.get("evidence_block_id", "")
        if ebid and ebid not in valid_ids:
            errs.append(f"evidence_block_id '{ebid}' not found")
        if ebid and q:
            eblk = bmap.get(ebid)
            if eblk and q not in eblk.content:
                errs.append(f"quote not in evidence_block {ebid}")
        # field allowed
        f = obs.get("field", "")
        if f not in ALLOWED_FIELDS:
            errs.append(f"Invalid field: {f}")
        # price_type
        pt = obs.get("price_type", "")
        if pt not in ALLOWED_PRICE_TYPES:
            errs.append(f"Invalid price_type: {pt}")
        if pt and pt != "UNKNOWN":
            if not obs.get("price_type_evidence_block_id"):
                errs.append(f"price_type '{pt}' no evidence_block_id")
            if not obs.get("price_type_evidence_quote"):
                errs.append(f"price_type '{pt}' no evidence_quote")
        # confidence
        c = obs.get("confidence", "")
        if c not in ALLOWED_CONFIDENCE:
            errs.append(f"Invalid confidence: {c}")
        # entity brand matches region (Gate 4)
        ent = obs.get("entity", {})
        if not ent.get("brand"):
            errs.append("Entity missing brand")
        elif rbrand and ent["brand"].lower() != rbrand.lower():
            errs.append(f"Brand '{ent['brand']}' != region '{rbrand}'")
        # UNKNOWN/AMBIGUOUS not promoted
        if c in ("AMBIGUOUS", "UNRESOLVED"):
            errs.append(f"Confidence '{c}' must not be promoted")

        if errs:
            obs["validation_errors"] = errs
            if any(x in " ".join(errs) for x in ["block_id", "quote", "Brand"]):
                rejected.append(obs)
            else:
                review.append(obs)
        else:
            accepted.append(obs)
    return accepted, rejected, review


# ─── Deduplication (Gate 6) ────────────────────────────────────────

def _obs_fp(obs):
    e = obs.get("entity", {})
    parts = [obs.get("field", ""), obs.get("raw_value", ""),
             e.get("brand", ""), e.get("model", ""), e.get("variant", ""),
             obs.get("price_type", "")]
    return hashlib.sha256("|".join(p.strip().lower() for p in parts).encode()).hexdigest()[:16]


def _dedup(observations):
    seen = set()
    result = []
    for obs in observations:
        fp = _obs_fp(obs)
        if fp not in seen:
            seen.add(fp)
            obs["fingerprint"] = fp
            result.append(obs)
    return result
