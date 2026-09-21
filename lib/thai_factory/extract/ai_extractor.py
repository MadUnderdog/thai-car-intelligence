"""
AI Extractor — two-stage extraction with strict validation.
Compact prompts for latency. Parallel Stage B per region.
"""
import hashlib
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from .dom_cleaner import CleanedPage, ContentBlock

_REQUIRED_GEN_CONFIG = ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL")
_OPENROUTER_ALLOWED_MODEL = "inclusionai/ling-3.0-flash"
_OPENROUTER_ALLOWED_PROVIDERS = ["novita"]

ALLOWED_FIELDS = {"price", "engine_l", "horsepower_hp", "torque_nm", "fuel_type",
                  "transmission", "drivetrain", "battery_kwh", "range_km", "seats", "body_type"}
ALLOWED_PRICE_TYPES = {"MSRP", "LIST_PRICE", "PROMOTION", "MODEL_RANGE", "HISTORICAL", "UNKNOWN"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
ALLOWED_DOC_TYPES = {"ARTICLE", "PRICE_LIST", "SPEC_SHEET", "ROUNDUP", "COMPARISON", "LAUNCH", "UNKNOWN"}
ALLOWED_SCOPES = {"SINGLE_MODEL", "SINGLE_VARIANT", "MULTI_MODEL_EXPLICIT", "COMPARISON",
                  "ROUNDUP", "GENERIC_LISTING", "UNKNOWN"}

NAV_KEYWORDS = ["หน้าแรก", "Review By Brand", "View by Brand", "View by Segment",
                "Sign in", "Search", "Close", "Accept", "Read more", "Copyright",
                "Privacy Policy", "Terms of Use", "WEBBOARD", "CONTACT"]


# ─── AI Config ─────────────────────────────────────────────────────
def _load_env():
    env = {}
    for k in _REQUIRED_GEN_CONFIG + ("EMBEDDING_BASE_URL", "EMBEDDING_API_KEY"):
        env[k] = os.environ.get(k, "")
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _get_ai_config():
    c = _load_env()
    missing = [k for k in _REQUIRED_GEN_CONFIG if not c.get(k)]
    if missing:
        raise ValueError(f"GENERATION CONFIG MISSING: {', '.join(missing)}")
    if c.get("EMBEDDING_API_KEY") and c["AI_API_KEY"] == c["EMBEDDING_API_KEY"] and "openrouter" in c["AI_BASE_URL"]:
        raise ValueError("CONFIG VIOLATION")
    return {"base_url": c["AI_BASE_URL"], "api_key": c["AI_API_KEY"],
            "model": c["AI_MODEL"], "provider": c.get("AI_PROVIDER", "openai-compatible")}


def _call_ai(prompt, system="", temperature=0.1):
    import tempfile
    config = _get_ai_config()
    if not config["api_key"]:
        return None
    payload = {"model": config["model"],
               "messages": [{"role": "system", "content": system or "Return valid JSON."},
                            {"role": "user", "content": prompt}],
               "temperature": temperature, "response_format": {"type": "json_object"}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp = f.name
    try:
        cmd = ["curl", "-s", "-X", "POST", f"{config['base_url']}/chat/completions",
               "-H", f"Authorization: Bearer {config['api_key']}",
               "-H", "Content-Type: application/json", "-d", f"@{tmp}"]
        if "opencode.ai" in config["base_url"]:
            cmd.extend(["-H", f"x-opencode-session: session-{int(time.time()*1000)}"])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            return None
        resp = json.loads(r.stdout)
        return json.loads(resp["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(tmp)


# ─── Block Filtering ───────────────────────────────────────────────
def _is_nav_block(block):
    t = block.content.strip()
    if len(t) < 15 and block.block_type == "list":
        return True
    for kw in NAV_KEYWORDS:
        if t.lower() == kw.lower() or t.lower().startswith(kw.lower()):
            return True
    if block.block_type == "list" and t.count("http") > 2:
        return True
    return False


def _filter_article_blocks(blocks):
    """Return block IDs that are article body (not nav/sidebar). Aggressive filtering."""
    ids = []
    heading_count = 0
    in_article = False
    article_heading = ""
    for b in blocks:
        if b.block_type == "heading":
            heading_count += 1
            if heading_count >= 2:
                in_article = True
                article_heading = b.content[:50]
            if not _is_nav_block(b) and heading_count >= 2:
                ids.append(b.block_id)
            continue
        if _is_nav_block(b):
            continue
        if not in_article:
            continue
        # Only paragraphs and tables after article starts
        if b.block_type in ("paragraph", "table"):
            if len(b.content) > 30:
                ids.append(b.block_id)
        # Skip list items unless they contain price/spec data
        elif b.block_type == "list":
            if any(kw in b.content.lower() for kw in ["ราคา", "price", "บาท", "ล้าน", "cc", "hp", "kw"]):
                ids.append(b.block_id)
    # Cap at 40 most relevant blocks
    if len(ids) > 40:
        ids = ids[:40]
    return ids


# ─── Compact Serialization ─────────────────────────────────────────
def _compact_line(block):
    """One-line compact representation: [id] TYPE (heading): first 120 chars."""
    h = block.heading_context[:40] if block.heading_context else ""
    c = block.content[:120].replace("\n", " ")
    return f"[{block.block_id}] {block.block_type.upper()}" + (f" ({h})" if h else "") + f": {c}"


def _compact_text(blocks, ids):
    """Compact one-per-line representation of blocks."""
    lines = []
    for b in blocks:
        if b.block_id in ids:
            lines.append(_compact_line(b))
    return "\n".join(lines)


def _region_text(blocks, ids):
    """Full content for specific block IDs."""
    lines = []
    for b in blocks:
        if b.block_id in ids:
            lines.append(f"[{b.block_id}] {b.block_type.upper()}: {b.content}")
    return "\n".join(lines)


# ─── Stage A Prompt ────────────────────────────────────────────────
STAGE_A_PROMPT = """Map this article. Return JSON:
{{
  "document_type": "ARTICLE",
  "document_scope": {{"decision": "SINGLE_MODEL", "primary_brand": "", "primary_model": ""}},
  "article_body_block_ids": ["id1", "id2"],
  "vehicle_regions": [{{"brand": "X", "model": "Y", "region_block_ids": ["id"],
                       "price_block_ids": ["id"], "spec_block_ids": ["id"]}}]
}}
document_type: ARTICLE|PRICE_LIST|SPEC_SHEET|ROUNDUP|COMPARISON|LAUNCH|UNKNOWN
decision: SINGLE_MODEL|SINGLE_VARIANT|MULTI_MODEL_EXPLICIT|COMPARISON|ROUNDUP|GENERIC_LISTING|UNKNOWN
ALL VALUES UPPERCASE. Identify article body blocks and vehicle regions.

BLOCKS:
{blocks}"""


def _stage_b_prompt(brand, model, blocks):
    return f"""Extract {brand} {model} data. Return JSON:
{{
  "observations": [{{
    "block_id": "", "field": "price", "raw_value": "", "normalized_value": "",
    "entity": {{"brand": "{brand}", "model": "{model}", "variant": ""}},
    "price_type": "MSRP|PROMOTION|UNKNOWN", "confidence": "HIGH|MEDIUM|LOW",
    "evidence_quote": "", "evidence_block_id": "",
    "price_type_evidence_block_id": "", "price_type_evidence_quote": ""
  }}]
}}
field: price|engine_l|horsepower_hp|torque_nm|fuel_type|transmission|drivetrain|battery_kwh|range_km|seats|body_type
Each observation MUST reference a block_id from below. evidence_quote MUST be exact substring of block content.

BLOCKS:
{blocks}"""


# ─── Two-Stage Extraction ─────────────────────────────────────────
def extract_observations(page):
    all_ids = {b.block_id for b in page.blocks}
    if len(page.blocks) < 3:
        return _empty("Insufficient blocks")

    article_ids = set(_filter_article_blocks(page.blocks))
    if len(article_ids) < 3:
        article_ids = all_ids

    # Stage A: compact representation
    bt = _compact_text(page.blocks, article_ids)
    pa = STAGE_A_PROMPT.format(blocks=bt)
    ra = _call_ai(pa)
    if not ra:
        return _empty("Stage A failed")

    errs_a = _validate_stage_a(ra, all_ids)

    ab_ids = set(ra.get("article_body_block_ids", []))
    if not ab_ids:
        ab_ids = article_ids
    regions = ra.get("vehicle_regions", [])

    # Stage B: parallel per region
    all_obs, all_rej, all_rev = [], [], []

    def run_region(region):
        rids = set(region.get("region_block_ids", []))
        pids = set(region.get("price_block_ids", []))
        sids = set(region.get("spec_block_ids", []))
        scoped = (rids | pids | sids) & ab_ids
        if not scoped:
            return [], [], []
        if len(scoped) > 15:
            scoped = set(list(scoped)[:15])

        bt_b = _region_text(page.blocks, scoped)
        if not bt_b.strip():
            return [], [], []

        brand = region.get("brand", "")
        model = region.get("model", "")
        pb = _stage_b_prompt(brand, model, bt_b)
        rb = _call_ai(pb)
        if not rb:
            return [], [], [{"brand": brand, "model": model, "error": "Stage B timeout/error"}]

        obs = rb.get("observations", [])
        v, r, rv = _validate(obs, all_ids, page.blocks, region)
        return v, r, rv

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(run_region, reg): reg for reg in regions}
        for fut in as_completed(futures):
            v, r, rv = fut.result()
            all_obs.extend(v)
            all_rej.extend(r)
            all_rev.extend(rv)

    _apply_normalization(all_obs)
    deduped = _dedup(all_obs)
    return {
        "document_type": ra.get("document_type", "UNKNOWN"),
        "document_scope": ra.get("document_scope", {}),
        "article_body_block_ids": sorted(list(ab_ids)),
        "vehicle_regions": regions,
        "observations": deduped,
        "rejected": all_rej,
        "needs_review": all_rev,
        "validation_errors": errs_a,
    }


def _empty(reason):
    return {"document_type": "UNKNOWN",
            "document_scope": {"decision": "UNKNOWN", "primary_brand": "", "primary_model": ""},
            "article_body_block_ids": [], "vehicle_regions": [], "observations": [], "rejected": [],
            "needs_review": [], "validation_errors": [reason]}


# ─── Validation ────────────────────────────────────────────────────
def _validate_stage_a(result, block_ids):
    errs = []
    dt = result.get("document_type", "")
    if dt not in ALLOWED_DOC_TYPES:
        errs.append(f"Invalid document_type: {dt}")
    sd = result.get("document_scope", {}).get("decision", "")
    if sd not in ALLOWED_SCOPES:
        errs.append(f"Invalid scope: {sd}")
    for i, reg in enumerate(result.get("vehicle_regions", [])):
        for bid in reg.get("region_block_ids", []):
            if bid not in block_ids:
                errs.append(f"Region {i}: block '{bid}' not found")
    return errs


def _validate(observations, valid_ids, blocks, region):
    acc, rej, rev = [], [], []
    bmap = {b.block_id: b for b in blocks}
    rbrand = region.get("brand", "")

    for obs in observations:
        errs = []
        for fn in ["block_id", "field", "raw_value", "evidence_quote", "evidence_block_id"]:
            if not obs.get(fn):
                errs.append(f"Missing: {fn}")
        bid = obs.get("block_id", "")
        if bid and bid not in valid_ids:
            errs.append(f"block_id '{bid}' not found")
        q = obs.get("evidence_quote", "")
        if bid and q:
            blk = bmap.get(bid)
            if blk and q not in blk.content:
                errs.append(f"quote not in block {bid}")
        ebid = obs.get("evidence_block_id", "")
        if ebid and ebid not in valid_ids:
            errs.append(f"evidence_block_id '{ebid}' not found")
        f = obs.get("field", "")
        if f not in ALLOWED_FIELDS:
            errs.append(f"Invalid field: {f}")
        pt = obs.get("price_type", "")
        if pt not in ALLOWED_PRICE_TYPES:
            errs.append(f"Invalid price_type: {pt}")
        c = obs.get("confidence", "")
        if c not in ALLOWED_CONFIDENCE:
            errs.append(f"Invalid confidence: {c}")
        ent = obs.get("entity", {})
        if not ent.get("brand"):
            errs.append("Entity missing brand")
        elif rbrand and ent["brand"].lower() != rbrand.lower():
            errs.append(f"Brand '{ent['brand']}' != region '{rbrand}'")
        if c in ("AMBIGUOUS", "UNRESOLVED"):
            errs.append(f"Confidence '{c}' not promoted")

        if errs:
            obs["validation_errors"] = errs
            if any(x in " ".join(errs) for x in ["block_id", "quote", "Brand"]):
                rej.append(obs)
            else:
                rev.append(obs)
        else:
            acc.append(obs)
    return acc, rej, rev



# ─── Code-based Normalization (deterministic, post-AI) ────────────
import re as _re

_BODY_TYPE_MAP = {
    "sedan": "Sedan", "c-sedan": "Sedan", "d-sedan": "Sedan",
    "suv": "SUV", "c-suv": "SUV", "b-suv": "SUV", "d-suv": "SUV", "compact suv": "SUV",
    "mpv": "MPV", "c-mpv": "MPV",
    "pickup": "Pickup", "ppv": "PPV",
    "hatchback": "Hatchback", "c-hatchback": "Hatchback",
    "coupe": "Coupe",
    "ev": "EV", "bev": "EV", "phev": "PHEV", "hev": "HEV",
}

_FUEL_MAP = {
    "benzin": "Gasoline", "gasoline": "Gasoline", "petrol": "Gasoline",
    "ดีเซล": "Diesel", "diesel": "Diesel",
    "ไฟฟ้า": "Electric", "electric": "Electric", "รถไฟฟ้า": "Electric",
    "รถไฟฟ้า100%": "Electric", "bev": "Electric",
    "hybrid": "Hybrid", "phev": "PHEV",
}

_DRIVETRAIN_MAP = {
    "fwd": "FWD", "front-wheel drive": "FWD", "ขับเคลื่อนล้อหน้า": "FWD",
    "rwd": "RWD", "rear-wheel drive": "RWD", "ขับเคลื่อนล้อหลัง": "RWD",
    "awd": "AWD", "all-wheel drive": "AWD", "4wd": "4WD", "4x4": "4WD",
}

_BODY_RE = _re.compile(r"[Cc]-?SUV|[Bb]-?SUV|[Dd]-?SUV|SUV|MPV|PPV|Sedan|Hatchback|Coupe|Pickup", _re.I)




def _normalize_price_type(raw_value, price_type):
    """Deterministic price_type normalization."""
    r = raw_value.lower()
    if "xx" in r or "xxx" in r:
        return "MODEL_RANGE"  # Fuzzy price = model range estimate
    if "ประมาณ" in r or "คาด" in r:
        return "MODEL_RANGE"
    if price_type in ("MSRP", "LIST_PRICE", "PROMOTION", "HISTORICAL"):
        return price_type
    return "UNKNOWN"

def _normalize_value(field, raw):
    """Deterministic normalization. Raw input varies; output must not."""
    r = raw.strip()
    if field == "price":
        # Handle xx,xxx format (Thai: 7xx,xxx = 700,000-799,999)
        if "xx" in r.lower() or "xxx" in r.lower():
            # Extract the leading digit
            m = _re.search(r"(\d)xx", r)
            if m:
                base = int(m.group(1)) * 100000
                return f"{base}-{base+99999} THB"
            return "UNRESOLVED THB"
        nums = _re.findall(r"[\d,]+(?:\.\d+)?", r.replace(",", ""))
        if nums:
            return f"{nums[0].replace(',','')} THB"
        return "UNRESOLVED THB"
    elif field == "horsepower_hp":
        m = _re.search(r"(\d+)", r)
        return f"{m.group(1)} HP" if m else "UNRESOLVED HP"
    elif field == "torque_nm":
        m = _re.search(r"(\d+)", r)
        return f"{m.group(1)} Nm" if m else "UNRESOLVED Nm"
    elif field == "engine_l":
        m = _re.search(r"(\d+\.?\d*)", r)
        return f"{m.group(1)}L" if m else "UNRESOLVED L"
    elif field == "battery_kwh":
        m = _re.search(r"(\d+\.?\d*)", r)
        return f"{m.group(1)} kWh" if m else "UNRESOLVED kWh"
    elif field == "range_km":
        m = _re.search(r"(\d+)", r)
        return f"{m.group(1)} km" if m else "UNRESOLVED km"
    elif field == "seats":
        # Look for "X ที่นั่ง" pattern first
        m = _re.search(r"(\d+)\s*ที่นั่ง", r)
        if m:
            return m.group(1)
        m = _re.search(r"(\d+)\s*seat", r.lower())
        if m:
            return m.group(1)
        # Fallback: first number
        m = _re.search(r"(\d+)", r)
        return m.group(1) if m else "UNRESOLVED"
    elif field == "fuel_type":
        low = r.lower()
        for k, v in _FUEL_MAP.items():
            if k in low:
                return v
        return r  # keep original if no match
    elif field == "drivetrain":
        low = r.lower()
        for k, v in _DRIVETRAIN_MAP.items():
            if k in low:
                return v
        return r.upper()[:10]
    elif field == "body_type":
        low = r.lower().strip()
        if low in _BODY_TYPE_MAP:
            return _BODY_TYPE_MAP[low]
        m = _BODY_RE.search(r)
        return m.group(0).upper() if m else r.upper()[:10]
    elif field == "transmission":
        low = r.lower()
        if "auto" in low or "อัตโนมัติ" in low:
            return "Automatic"
        if "manual" in low or "เกียร์ธรรมดา" in low:
            return "Manual"
        if "cvt" in low:
            return "CVT"
        return r
    return r


def _apply_normalization(observations):
    """Apply code-based normalization to all observations."""
    for obs in observations:
        obs["normalized_value"] = _normalize_value(obs.get("field", ""), obs.get("raw_value", ""))
        if obs.get("field") == "price":
            obs["price_type"] = _normalize_price_type(obs.get("raw_value", ""), obs.get("price_type", "UNKNOWN"))
    return observations


# ─── Deduplication ─────────────────────────────────────────────────
def _obs_fp(obs):
    e = obs.get("entity", {})
    parts = [obs.get("field", ""), obs.get("normalized_value", ""),
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
