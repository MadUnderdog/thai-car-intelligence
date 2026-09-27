"""
P102 — identity pass: high-recall MODEL/VARIANT enumeration + first-party
reconciliation, using the source roles defined in Blueprint §96.

Source roles (never silently upgraded, §96):
    IDENTITY_ENUMERATOR  taxonomy / insurance / used-car / finance style sources
    MARKET_REFERENCE     reference datasets (Thai makes, FIPE, DLT)
    MEDIA_DISCOVERY      media indexes/articles — discovery only
    MARKET_TRUTH         first-party OEM/importer artifacts (staged rows)

What lives here and what deliberately does NOT:

  * This module builds a *Phase-1 identity/catalog universe* — a separate,
    machine-readable artifact.  It never writes staging rows and never touches
    the production DB, because §95's mandatory-field contract (identity + price
    + scope + re-resolvable locator) cannot be satisfied by identity-only
    candidates.  Rather than fabricate price rows or change the acceptance
    architecture, identity-only candidates stay in this artifact with an
    explicit `first_party_status`.
  * No price is invented.  A price only exists here if the enumerating source
    published it on the same line, and it is always tagged with that source's
    role; only MARKET_TRUTH prices ever reach staging (they already do, through
    the existing adapters).
  * Variant labels are copied verbatim from the published label — never split,
    never synthesised (§95: no invented Standard/Base/Entry).
  * Sibling brands are never merged (Deepal≠Changan, Haval≠GWM, Lexus≠Toyota …).
"""
import html as _html
import json
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .universe import (
    CandidateConfidence,
    IdentityUniverse,
    IdentityUniverseCandidate,
    SourceRole,
)

SCHEMA = "p102-identity-universe/1"

# ─────────────────────────────────────────────────────────────────────────────
# brand vocabulary
# ─────────────────────────────────────────────────────────────────────────────
# Display-form aliases used only to decide "does this published label talk about
# brand X?".  They never create or rename an identity on their own.
BRAND_ALIASES: Dict[str, List[str]] = {
    "Audi": ["AUDI", "ออดี้"],
    "Avance": ["AVANCE"],
    "BMW": ["BMW", "บีเอ็มดับเบิลยู", "บีเอ็ม"],
    "BYD": ["BYD", "บีวายดี"],
    "Changan": ["CHANGAN", "CHANG AN", "ฉางอัน"],
    "Chery": ["CHERY", "เชอรี", "เชอรี่"],
    "Chevrolet": ["CHEVROLET", "เชฟโรเลต"],
    "Deepal": ["DEEPAL", "ดีพอล"],
    "Ford": ["FORD", "ฟอร์ด"],
    "GWM": ["GWM", "GREAT WALL", "ORA", "เกรท วอลล์", "เกรทวอลล์"],
    "Haval": ["HAVAL", "ฮาวาล"],
    "Honda": ["HONDA", "ฮอนด้า"],
    "Isuzu": ["ISUZU", "อีซูซุ"],
    "Jaguar": ["JAGUAR", "จากัวร์"],
    "Kia": ["KIA", "เกีย"],
    "Land Rover": ["LAND ROVER", "RANGE ROVER"],
    "Lexus": ["LEXUS", "เล็กซัส"],
    "MG": ["MG", "เอ็มจี"],
    "MINI": ["MINI"],
    "Mazda": ["MAZDA", "มาสด้า"],
    "Mercedes-Benz": ["MERCEDES-BENZ", "MERCEDES BENZ", "MERCEDES", "เบนซ์"],
    "Mitsubishi": ["MITSUBISHI", "มิตซูบิชิ", "มิตซู"],
    "NETA": ["NETA", "เนต้า", "เนตา"],
    "Nissan": ["NISSAN", "นิสสัน"],
    "Peugeot": ["PEUGEOT", "เปอโยต์", "เปจโยต์"],
    "Porsche": ["PORSCHE", "ปอร์ช", "ปอร์เช่"],
    "Smart": ["SMART"],
    "Subaru": ["SUBARU", "ซูบารุ"],
    "Suzuki": ["SUZUKI", "ซูซูกิ"],
    "Tesla": ["TESLA", "เทสล่า", "เทสลา"],
    "Toyota": ["TOYOTA", "โตโยต้า"],
    "Volvo": ["VOLVO", "วอลโว่"],
}


def brand_tokens(brand: str) -> List[str]:
    """Alias tokens for a brand, longest first (so 'MERCEDES BENZ' wins over
    'MERCEDES'), uppercased and whitespace-collapsed."""
    toks = BRAND_ALIASES.get(brand, [brand.upper()])
    out = [normalize_identity(t) for t in toks]
    out.append(normalize_identity(brand))
    seen, uniq = set(), []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return sorted(set(uniq), key=len, reverse=True)


def normalize_identity(text: str) -> str:
    """Case/width/punctuation normalisation used for identity matching.

    Keeps Latin and Thai characters, digits and single spaces.  It never
    translates, never transliterates and never invents a token."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.upper()
    s = re.sub(r"[^\w\u0E00-\u0E7F]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# tokens that carry no identity meaning when matching two published labels
_MATCH_STOPWORDS = {
    "NEW", "ALL", "ALLNEW", "GEN", "MK", "MY", "LCI", "FACELIFT",
    "โฉม", "ใหม่", "รุ่น", "ราคา", "ปี",
}
_YEAR = re.compile(r"^(19|20)\d{2}$")


def match_key(brand: str, name: str) -> str:
    """Normalised comparison key for a model/variant label of `brand`."""
    s = normalize_identity(name)
    for alias in brand_tokens(brand):
        if s.startswith(alias + " "):
            s = s[len(alias):].strip()
        elif s == alias:
            s = ""
    toks = [t for t in s.split()
            if t not in _MATCH_STOPWORDS and not _YEAR.match(t)]
    return " ".join(toks)


def labels_match(brand: str, a: str, b: str) -> Optional[str]:
    """Return the match method for two published labels, or None.

    Deliberately conservative: exact key equality, or a token-subset where the
    shorter key is at least 4 characters and every token appears in the longer.
    Anything else stays unmatched and is reported as unresolved."""
    ka, kb = match_key(brand, a), match_key(brand, b)
    if not ka or not kb:
        return None
    if ka == kb:
        return "exact_normalized"
    ta, tb = ka.split(), kb.split()
    short, long_ = (ta, tb) if len(ka) <= len(kb) else (tb, ta)
    if len("".join(short)) < 4:
        return None
    if all(t in long_ for t in short):
        return "token_subset"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# index-page parsing (media / lineage index pages, never market truth)
# ─────────────────────────────────────────────────────────────────────────────
_TAG = re.compile(r"<(h[1-4]|li|p)\b[^>]*>(.*?)</\1>", re.S | re.I)
_PRICE_TOKEN = re.compile(r"ราคา(?:เริ่ม|เริ่มต้น|พิเศษ|เพียง|สุดพิเศษ)?")
_PRICE_NUM = re.compile(r"(?<![\d,])\d{1,3}(?:,\d{3})+(?![\d,])")
_GRADE = re.compile(r"รุ่น\s*(.+)", re.S)
_FILLER = re.compile(
    r"^(?:ALL[\s\-]*NEW|ALL[\s\-]*NEWEST|RE[\s\-]*|THE\s+|ใหม่|รุ่นใหม่"
    r"|โฉมใหม่|แนะนำ|New)\s+",
    re.IGNORECASE,
)

# headings that are navigation/section furniture, not a model identity.
# Meeting one of these ALSO clears the current model context, so a cross-brand
# "other brands" section can never bleed its labels into the previous model.
_HEADING_NOISE = re.compile(
    r"ราคารถ|ตารางผ่อน|โปรโมชั่น|ความคิดเห็น|เรื่องที่เกี่ยวข้อง|อัพเดทล่าสุด"
    r"|เกี่ยวกับ|ยกเลิก|Cancel|Share|Facebook|Twitter|ตอบกลับ|สมัครงาน"
    r"|อุปกรณ์มาตรฐาน|EXTERIOR|INTERIOR|PERFORMANCE|SAFETY|TECHNOLOGY|Dimension"
    r"|ข้อมูลรถยนต์|สเปค|SPECIFICATION|Specification|ดูรถทั้งหมด|ทั้งหมด"
    r"|แสดงความคิดเห็น|เข้าสู่ระบบ|ใส่ความคิดเห็น|รีวิว|ทดลองขับ|เปิดตัว"
    r"|รวมรูป|วิดีโอ|คลิป|ค้นหา|มีให้เลือก|ดังนี้|COLORS|รถไฟฟ้าที่น่าสนใจ"
    r"|ขับง่าย|คันเล็ก|และมีระยะ|รับประกัน",
    re.I,
)

# prose that must never become a variant label
_VARIANT_NOISE = re.compile(
    r"ครับ|คะ|สนใจ|สอบถาม|โทร|เบอร์|LINE\s*:|HTTPS?://|ตอบ|ขอบคุณ|ดิฉัน"
    r"|ราคาลด|แถม|ส่วนลด|กำไร|ประกันภัย|ไม่เกิน|^ราคา|รับประกัน|นาน \d+ ปี"
    r"|^สี | บาท|บาท \(|\+ บาท|เพิ่ม \d|และสี|สีพิเศษ",
    re.I,
)

_COMMENT_MARKERS = [
    '<div id="comments"',
    'class="comments-area"',
    'class="tt_ct_comment"',
    'class="tt_comment"',
    'class="comment-respond"',
    'id="commentform"',
    "แสดงความคิดเห็น",
    "Log in to Reply",
    "ดูราคารถแบรนด์อื่น",
    "ราคารถแบรนด์อื่น",
    "รถไฟฟ้าที่น่าสนใจ",
]

# published labels that are never a real grade (§95 fabrication guard)
_GENERIC_VARIANTS = {
    "STANDARD", "BASE", "ENTRY", "DEFAULT", "GENERIC", "OTHER", "อื่นๆ",
}

# Manufacturers that appear in Thai-market price indexes but are NOT the page's
# manufacturer.  They are registered for REJECTION only — never as an
# attribution target — so a cross-brand list can never be adopted wholesale.
OTHER_BRAND_NAMES = [
    "Wuling", "Geely", "Aion", "Zeekr", "Jaecoo", "Omoda", "Denza", "Hyundai",
    "Proton", "Leapmotor", "GAC", "Great Wall", "Chana", "Foton", "JAC",
    "Maxus", "Roewe", "Renault", "Fiat", "Volkswagen", "Skoda", "Citroen",
    "Opel", "Ssangyong", "Alpina", "Bentley", "Lamborghini", "Maserati",
    "Ferrari", "McLaren", "Rolls-Royce", "Aston Martin", "Lotus", "Honda Motorcycle",
    "Yamaha", "Kawasaki", "Ducati", "KTM", "Triumph", "Aprilia", "Vespa",
    "Piaggio", "Benelli", "Harley-Davidson", "Royal Enfield", "GPX", "Zontes",
    "Scomadi", "Lambretta", "Bajaj", "Mazda Motorcycle",
]

# aliases of every brand we know how to attribute, longest first.
# In-scope brands win any alias collision (e.g. "Great Wall" -> GWM).
_ALIAS_MAP: Dict[str, str] = {normalize_identity(n): n for n in OTHER_BRAND_NAMES}
for _b, _alts in BRAND_ALIASES.items():
    for _a in _alts:
        _ALIAS_MAP[normalize_identity(_a)] = _b
    _ALIAS_MAP[normalize_identity(_b)] = _b
_ALL_ALIASES: List[Tuple[str, str]] = sorted(_ALIAS_MAP.items(),
                                             key=lambda kv: -len(kv[0]))


def leading_brand(label: str) -> Optional[str]:
    """The manufacturer whose alias the published label starts with, else None.

    This is the attribution gate: a published label may only be attributed to
    the page's own brand, which is what keeps sibling brands and cross-brand
    link lists out of each other's records."""
    up = normalize_identity(_FILLER.sub("", str(label).strip()))
    if not up:
        return None
    for alias, brand in _ALL_ALIASES:
        if up == alias:
            return brand
        if up.startswith(alias + " "):
            return brand
        # short aliases glued to a digit (MG5, MG3 …) still count
        if up.startswith(alias) and len(alias) >= 2 and not up[len(alias)].isalpha():
            return brand
    return None


@dataclass
class ParsedIdentity:
    """Everything one index page published about identities, plus the parts the
    parser could not attribute — those are reported, never guessed."""
    source_name: str
    source_role: str
    source_url: str
    brand: str
    models: List[Dict] = field(default_factory=list)
    variants: List[Dict] = field(default_factory=list)
    unresolved: List[Dict] = field(default_factory=list)
    body_cut_at: Optional[int] = None
    headings_seen: int = 0
    seen_models: dict = field(default_factory=dict)
    seen_variants: set = field(default_factory=set)

    @property
    def counters(self) -> Dict:
        return {
            "models": len(self.models),
            "variants": len(self.variants),
            "unresolved": len(self.unresolved),
            "headings_seen": self.headings_seen,
        }


def _strip_tags(fragment: str) -> str:
    t = re.sub(r"<[^>]+>", " ", fragment)
    t = _html.unescape(t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" \t\r\n–—-•*")


def cut_article_body(page_html: str) -> Tuple[str, Optional[int]]:
    """Return (body, cut_index).  Everything from the first comment /
    cross-brand / related-post marker onwards is reader prose and section
    furniture — excluded so it can never become a model or variant identity."""
    best = None
    for marker in _COMMENT_MARKERS:
        i = page_html.find(marker)
        if i >= 0 and (best is None or i < best):
            best = i
    if best is None:
        return page_html, None
    return page_html[:best], best


def clean_model_label(raw: str) -> Optional[str]:
    """Turn a heading into a published model label, or None if it is furniture."""
    t = _strip_tags(raw)
    if not t or len(t) < 3 or len(t) > 60:
        return None
    if _HEADING_NOISE.search(t):
        return None
    m = _PRICE_TOKEN.search(t)
    if m and m.start() >= 3:
        t = t[:m.start()].strip()
    elif m and m.start() < 3:
        # the line opens with a price word: it is a price line, not a model
        return None
    t = re.sub(r"\s*[-–—]?\s*\d{4}\s*[-–/]\s*\d{4}\s*$", "", t)  # 2026-2027
    t = re.sub(r"\s+20\d{2}\s*$", "", t)                        # trailing year
    t = t.strip(" \t.,:;|/()[]")
    if len(t) < 3 or len(t) > 90:
        return None
    return t


def _split_grade(text: str) -> Tuple[str, str]:
    """Split a published label at its first รุ่น marker -> (model_part, grade)."""
    m = _GRADE.search(text)
    if not m:
        return text.strip(), ""
    return text[:m.start()].strip(), m.group(1).strip()


def _clause_labels(line: str) -> List[Tuple[str, int]]:
    """Split one published line into (label, published_price_thb) clauses.

    Each price number opens a clause; the clause's label is the text between the
    previous price and this one.  Nothing is joined across clauses and nothing
    is invented — every clause keeps the exact published wording."""
    out, prev_end = [], 0
    for m in _PRICE_NUM.finditer(line):
        raw_label = line[prev_end:m.start()]
        price = int(m.group(0).replace(",", ""))
        prev_end = m.end()

        core = raw_label
        tok = _PRICE_TOKEN.search(raw_label)
        if tok:
            after = raw_label[tok.end():].strip()
            if after and not _PRICE_NUM.fullmatch(after):
                core = after
            else:
                core = raw_label[:tok.start()]
        core = core.strip(" \t.,:;|/()[]–—-•*")
        core = re.sub(r"^\d{1,3},\d{3}\s*\.?\s*", "", core).lstrip("-–—•* ")
        core = re.sub(r"\s*ราคา(?:เริ่ม|เริ่มต้น|พิเศษ|เพียง)?\s*$", "", core).strip()
        if len(core) >= 3:
            out.append((core, price))
    return out


def _reject(rec: "ParsedIdentity", kind: str, text: str, reason: str) -> None:
    rec.unresolved.append({"kind": kind, "text": text[:180], "reason": reason})


def _heading_is_modelish(label: str) -> bool:
    latin = re.findall(r"[A-Z]{2,}|\b[A-Z][a-z]{2,}", label)
    return len("".join(latin)) >= 4


def _add_model(rec: "ParsedIdentity", brand: str, label: str, origin: str,
               source_text: str, price: int = 0) -> Optional[str]:
    """Register a model identity if it attributes to this brand; otherwise record
    the rejection.  Returns the model label when it was accepted."""
    if not label or len(label) > 90:
        return None
    lb = leading_brand(label)
    if lb is not None and lb != brand:
        _reject(rec, "other_brand_contamination", source_text,
                f"published label starts with a different manufacturer "
                f"({lb}) — not attributed to {brand}")
        return None
    if not match_key(brand, label):
        _reject(rec, "manufacturer_only_label", source_text,
                f"published label '{label}' is only the manufacturer name — "
                f"it carries no model identity")
        return None
    if lb is None:
        # price lines always name their brand; headings may not, so only a
        # heading may fall back to the Latin-token heuristic
        if origin == "clause":
            _reject(rec, "no_brand_token", source_text,
                    "price line does not name the page's manufacturer — "
                    "not guessed")
            return None
        if not _heading_is_modelish(label):
            _reject(rec, "heading_unattributed", source_text,
                    "heading names neither the brand nor a Latin model token "
                    "— not guessed")
            return None
    key = match_key(brand, label)
    if key in rec.seen_models:
        # a second published spelling of the same model keeps the first label,
        # so variants never split across two near-identical records
        return rec.seen_models[key]

    # A grade line whose published text *extends* a known model identity is a
    # VARIANT of that model, not a new model: the remainder is the site's own
    # published label (longest published model prefix wins), so nothing is
    # split out of thin air.
    for known in sorted(rec.seen_models.values(), key=len, reverse=True):
        if len(known) >= 6 and len(label) > len(known) \
                and label.upper().startswith(known.upper()):
            grade = label[len(known):].strip(" -–—")
            if grade and not _VARIANT_NOISE.search(grade) \
                    and not _PRICE_TOKEN.search(grade):
                _add_variant(rec, brand, known, grade, price, origin,
                             source_text)
            return known

    rec.seen_models[key] = label
    # the label is the *rendered text* of the published statement, kept in full
    # so every extracted identity can be re-checked against its own source
    rec.models.append({"model": label, "label": _strip_tags(source_text),
                       "origin": origin, "match_key": match_key(brand, label)})
    return label


def _add_variant(rec: "ParsedIdentity", brand: str, model: Optional[str],
                 variant: str, price: int, origin: str, source_text: str) -> None:
    """Register a published grade label under `model`, or record why not."""
    variant = variant.strip(" \t.,:;|/()[]–—-•*")
    if not variant or len(variant) > 70:
        _reject(rec, "variant_unattributed", source_text,
                "price line with no usable published grade label")
        return
    if _VARIANT_NOISE.search(variant) or _PRICE_TOKEN.search(variant):
        _reject(rec, "variant_noise", source_text,
                f"published fragment '{variant[:60]}' is prose/price wording, "
                f"not a grade label")
        return
    if normalize_identity(variant) in _GENERIC_VARIANTS:
        _reject(rec, "generic_variant_rejected", source_text,
                f"generic grade label '{variant}' is never a real variant (§95)")
        return
    lb = leading_brand(variant)
    if lb is not None and lb != brand:
        _reject(rec, "other_brand_contamination", source_text,
                f"grade label starts with a different manufacturer ({lb}) — "
                f"not attributed to {brand}")
        return
    if model is None:
        _reject(rec, "variant_no_model_context", source_text,
                "grade line precedes any model identity on this page")
        return
    vkey = (match_key(brand, model), match_key(brand, variant))
    if vkey in rec.seen_variants:
        return
    rec.seen_variants.add(vkey)
    rec.variants.append({
        "model": model, "variant": variant, "label": _strip_tags(source_text),
        "published_price_thb": price, "published_price_role": rec.source_role,
        "origin": origin, "match_key_model": vkey[0],
        "match_key_variant": vkey[1],
    })



_STRONG_SPLIT = re.compile(r"(<(?:strong|b)>\s*.*?</(?:strong|b)>)", re.S | re.I)
_TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_TD = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S | re.I)
_MODEL_SLUG = re.compile(r"https://www\.9carthai\.com/([a-z0-9\-]+?)-price/")


def _published_models(page_html: str) -> List[str]:
    """Model identities published as the enumerator's own per-model URLs.

    The slug is the site's published model taxonomy (`new-audi-q5-price` ->
    `audi q5`): a statement by the *enumerator*, never by the OEM, so these are
    candidate models carrying the MEDIA_DISCOVERY role.  Brand index links
    (`audi-price`) resolve to the manufacturer itself and are dropped by the
    manufacturer-only guard in `_add_model`.
    """
    repair = {"E Tron": "e-tron", "Hev": "HEV", "Ev": "EV", "Rs": "RS",
              "Gt": "GT", "Gti": "GTI", "Tfsi": "TFSI", "Mt": "MT", "At": "AT"}
    out: List[str] = []
    for slug in dict.fromkeys(_MODEL_SLUG.findall(page_html)):
        slug = re.sub(r"^(all-new|new)-", "", slug)
        label = _FILLER.sub(" ", slug.replace("-", " ")).title()
        label = re.sub(r"\b([A-Z][a-z]?) (\d{1,2})\b", r"\1-\2", label)
        for a, b in repair.items():
            label = re.sub(rf"\b{a}\b", b, label)
        label = re.sub(r"\s+", " ", label).strip()
        if len(label) > 1:
            out.append(label)
    return out

# bold labels that describe a section (engine text, dealer locations …) rather
# than naming a model — skipped without disturbing the current model context
_STRONG_NOISE = re.compile(
    r"เครื่องยนต์|เกียร์อัตโนมัติ|กทม|ปริมณฑล|สาขา|และปริมณฑล|ที่น่าสนใจ",
    re.I,
)


def _handle_label_text(rec: "ParsedIdentity", brand: str, raw: str,
                       origin: str, strict: bool) -> str:
    """Turn a bold/heading label into a model identity.

    Returns 'model' (context set), 'clear' (the label belongs to another brand,
    so the previous model context must not leak into what follows) or 'keep'."""
    if _STRONG_NOISE.search(raw or ""):
        return "keep"
    label = clean_model_label(raw)
    if label is None:
        return "keep"
    model_part, grade = _split_grade(label)
    lb = leading_brand(model_part or label)
    if strict and lb != brand:
        _reject(rec, "no_brand_token" if lb is None else
                "other_brand_contamination", raw,
                "bold label does not name the page's manufacturer — "
                "context not inherited" if lb is None else
                f"bold label starts with a different manufacturer ({lb})")
        return "clear"
    accepted = _add_model(rec, brand, model_part, origin, raw)
    if accepted:
        if grade:
            _add_variant(rec, brand, accepted, grade, 0, origin, raw)
        return "model"
    return "clear"


def parse_index_page(page_html: str, brand: str, source_name: str,
                     source_url: str, source_role: str) -> ParsedIdentity:
    """Parse one published index/price page into model + variant candidates.

    Deterministic attribution rules, in order:
      * a clean heading sets the current model context; a furniture heading
        clears it (so a cross-brand list at the foot of the page cannot bleed);
      * each price-bearing clause is read on its own — a clause that names the
        brand starts a model, a รุ่น marker splits model/grade, and the remainder
        becomes a variant of the current model;
      * anything that cannot be attributed is returned in `unresolved` with an
        explicit reason — never dropped, never guessed."""
    out = ParsedIdentity(source_name=source_name, source_role=source_role,
                         source_url=source_url, brand=brand)
    body, cut = cut_article_body(page_html)
    out.body_cut_at = cut
    current_model: Optional[str] = None

    # (a) the enumerator's own per-model URLs — the highest-recall model layer
    for pm in _published_models(page_html):
        if leading_brand(pm) == brand and match_key(brand, pm):
            _add_model(out, brand, pm, "model_link", pm)

    # (b) body content, in document order: headings/<p>/<li> and price tables
    events = [(m.start(), 0, "tag", m) for m in _TAG.finditer(body)]
    events += [(m.start(), 1, "row", m) for m in _TR.finditer(body)]
    events.sort(key=lambda e: e[:3])
    for _, _, kind, m in events:
        if kind == "row":
            current_model = _consume_table_row(out, brand, current_model, m)
            continue
        tag, frag = m.group(1).lower(), m.group(2)
        tag, frag = m.group(1).lower(), m.group(2)
        text = _strip_tags(frag)
        if not text:
            continue

        if tag.startswith("h"):
            out.headings_seen += 1
            label = clean_model_label(text)
            if label is None:
                current_model = None       # furniture heading: section changed
                continue
            model_part, grade = _split_grade(label)
            accepted = _add_model(out, brand, model_part, "heading", text)
            if accepted:
                current_model = accepted
                if grade:
                    _add_variant(out, brand, accepted, grade, 0, "heading", text)
            else:
                current_model = None
            continue

        # price lists are usually a <strong> model label followed by grade
        # lines inside one <p> — the label must open the section, otherwise
        # every grade line would inherit the previous model.
        parts = _STRONG_SPLIT.split(frag)
        for part in parts:
            if not part:
                continue
            if re.match(r"\s*<(?:strong|b)>", part, re.I):
                out.headings_seen += 1
                state = _handle_label_text(out, brand, _strip_tags(part),
                                           "strong", strict=True)
                if state == "model":
                    current_model = _last_model(out)
                elif state == "clear":
                    current_model = None
                continue
            ptext = _strip_tags(part)
            if not ptext or not _PRICE_NUM.search(ptext) or len(ptext) > 600:
                continue
            current_model = _consume_clauses(out, brand, current_model,
                                             ptext, part)

    return out


def _last_model(rec: "ParsedIdentity") -> Optional[str]:
    return rec.models[-1]["model"] if rec.models else None


def _consume_table_row(out: "ParsedIdentity", brand: str, current_model,
                       m) -> Optional[str]:
    """One <tr> of a published price table.

    A price row publishes label + price in separate cells; a lone text cell is
    a model-family row header.  Nothing is split or guessed: the label cells
    are handed to the ordinary clause reader unchanged.
    """
    cells = []
    for c in _TD.findall(m.group(1)):
        t = re.sub(r"\s+", " ", _strip_tags(c)).replace("\xa0", " ").strip()
        if t:
            cells.append(t)
    if not cells:
        return current_model
    last = cells[-1]
    if len(cells) >= 2 and _PRICE_NUM.search(last) and \
            re.fullmatch(r"[\s\d,.]+", last):
        label = " ".join(cells[:-1])
        if label and not _PRICE_NUM.search(label):
            return _consume_clauses(out, brand, current_model,
                                    f"{label} {last}", m.group(0))
    if len(cells) == 1:
        if leading_brand(cells[0]) == brand:
            return _add_model(out, brand, cells[0], "table_header",
                              cells[0]) or current_model
        _reject(out, "table_header_unattributed", cells[0],
                "table header row names neither the page manufacturer nor a "
                "model identity — not guessed")
    return current_model


def _consume_clauses(out: "ParsedIdentity", brand: str, current_model,
                     text: str, source_text: str):
    """Clause loop for one content segment; returns the updated model context."""
    for clause, price in _clause_labels(text):
        model_part, grade = _split_grade(clause)
        if grade:
            if model_part:
                accepted = _add_model(out, brand, model_part, "clause",
                                      source_text)
                if accepted is None:
                    continue
                _add_variant(out, brand, accepted, grade, price, "clause",
                             source_text)
                current_model = accepted
            else:
                _add_variant(out, brand, current_model, grade, price, "clause",
                             source_text)
            continue

        lb = leading_brand(clause)
        if current_model and clause.lower().startswith(
                current_model.lower()) and len(clause) > len(current_model):
            _add_variant(out, brand, current_model,
                         clause[len(current_model):], price, "clause",
                         source_text)
        elif lb == brand:
            accepted = _add_model(out, brand, clause, "clause", source_text,
                                  price)
            if accepted:
                current_model = accepted
        elif lb is None:
            # no brand named: only usable as a grade of the current model
            _add_variant(out, brand, current_model, clause, price, "clause",
                         source_text)
        else:
            _reject(out, "other_brand_contamination", source_text,
                    f"published label starts with a different manufacturer "
                    f"({lb}) — not attributed to {brand}")
    return current_model


# ─────────────────────────────────────────────────────────────────────────────
# reconciliation
# ─────────────────────────────────────────────────────────────────────────────
class FirstPartyStatus(Enum):
    CONFIRMED_VARIANT = "CONFIRMED_VARIANT"     # model + variant seen in MARKET_TRUTH
    CONFIRMED_MODEL = "CONFIRMED_MODEL"         # model seen in MARKET_TRUTH
    IDENTITY_ONLY = "IDENTITY_ONLY"             # enumerator-only, no first-party row
    CONFLICT = "CONFLICT"                       # first-party says something else


@dataclass(eq=False)   # identity-hashed: records are de-duplicated in sets by object identity
class ReconciledIdentity:
    manufacturer: str
    model: str
    variant: str = ""
    generation: str = ""
    sources: List[Dict] = field(default_factory=list)
    first_party: List[Dict] = field(default_factory=list)
    status: str = FirstPartyStatus.IDENTITY_ONLY.value
    match_method: str = ""
    rejection_reasons: List[str] = field(default_factory=list)
    # non-blocking observations that keep an identity explicit without
    # accusing any source of disagreeing with itself
    notes: List[str] = field(default_factory=list)
    published_price_thb: Optional[int] = None
    published_price_role: str = ""
    scope: str = "TH"

    @property
    def canonical_key(self) -> str:
        return "|".join([
            self.manufacturer.lower().strip(),
            self.model.lower().strip(),
            self.generation.lower().strip(),
            self.variant.lower().strip(),
        ])

    @property
    def has_market_truth(self) -> bool:
        return any(s.get("source_role") == SourceRole.MARKET_TRUTH.value
                   for s in self.sources)


@dataclass
class IdentityReconciliation:
    """Phase-1 identity/catalog universe result (separate from staging)."""
    target_date: str = ""
    records: List[ReconciledIdentity] = field(default_factory=list)
    rejected: List[Dict] = field(default_factory=list)
    sources_used: List[Dict] = field(default_factory=list)
    # publications that declare no identity_level — excluded from level-clash
    # detection (fail closed), never guessed into evidence
    unlevelled_publications: List[Dict] = field(default_factory=list)
    # every identity key where two distinct publications disagree on level,
    # whether or not the record ends up CONFLICT (a MARKET_TRUTH confirmation
    # outranks a conflict downgrade)
    level_clash_evidence: List[Dict] = field(default_factory=list)

    def add_source(self, name: str, role: str, url: str, note: str = "") -> None:
        self.sources_used.append({"source_name": name, "source_role": role,
                                  "source_url": url, "note": note})

    def reject(self, manufacturer: str, label: str, reason: str,
               source_name: str) -> None:
        self.rejected.append({
            "manufacturer": manufacturer, "label": label,
            "reason": reason, "source_name": source_name,
        })

    def _find(self, manufacturer: str, model: str, variant: str) -> Optional[ReconciledIdentity]:
        mk, vk = match_key(manufacturer, model), match_key(manufacturer, variant) if variant else ""
        for r in self.records:
            if r.manufacturer != manufacturer:
                continue
            if match_key(r.manufacturer, r.model) != mk:
                continue
            if (match_key(r.manufacturer, r.variant) if r.variant else "") != vk:
                continue
            return r
        return None

    @staticmethod
    def declared_level(source: Dict, variant: str = "") -> str:
        """Identity level a publication actually DECLARES — read, never guessed.

        Only `source["identity_level"]` is consulted.  `variant` is accepted for
        call-site compatibility and is deliberately never used: falling back to
        the reconciled record's shape would manufacture level evidence from a
        guess, which §95 does not allow.  First-party rows already carry the
        value from the staging loader (`identity.identity_level`); enumerator
        loaders must pass `identity_level` explicitly when they enqueue a
        candidate.

        Returns `"MODEL"`/`"VARIANT"` when declared, `""` otherwise.
        """
        lvl = str(source.get("identity_level") or "").strip().upper()
        return lvl if lvl in ("MODEL", "VARIANT") else ""

    @classmethod
    def _attach(cls, rec: "ReconciledIdentity", source: Dict,
                variant: str) -> None:
        """Append a publication entry carrying its own declared identity_level.

        An entry with no declared level is stored with `identity_level=""` and
        is later excluded from level-clash detection (fail closed).
        """
        entry = dict(source)
        entry["identity_level"] = cls.declared_level(entry, variant)
        key = (entry.get("source_name"), entry.get("source_url"),
               entry["identity_level"])
        if not any((s.get("source_name"), s.get("source_url"),
                    s.get("identity_level")) == key for s in rec.sources):
            rec.sources.append(entry)

    def add_enumerator(self, manufacturer: str, model: str, variant: str,
                       source: Dict, published_price: Optional[int] = None,
                       price_role: str = "", generation: str = "") -> ReconciledIdentity:
        if variant and variant.strip().upper() in _GENERIC_VARIANTS:
            self.reject(manufacturer, f"{model} {variant}".strip(),
                        "generic_grade: published label is only "
                        f"'{variant.strip()}' — a generic grade token carries "
                        "no trim identity and is never invented into one "
                        "(§95)", source.get("source_name", "unknown"))
            variant = ""
        rec = self._find(manufacturer, model, variant)
        if rec is None:
            rec = ReconciledIdentity(manufacturer=manufacturer, model=model,
                                     variant=variant, generation=generation)
            self.records.append(rec)
        self._attach(rec, source, variant)
        if published_price and not rec.published_price_thb:
            rec.published_price_thb = int(published_price)
            rec.published_price_role = price_role
        return rec

    def add_first_party(self, manufacturer: str, model: str, variant: str,
                        source: Dict) -> ReconciledIdentity:
        rec = self._find(manufacturer, model, variant)
        if rec is None:
            rec = ReconciledIdentity(manufacturer=manufacturer, model=model,
                                     variant=variant)
            self.records.append(rec)
        self._attach(rec, source, variant)
        rec.first_party.append(dict(source))
        return rec

    def resolve_statuses(self) -> None:
        """Set first_party_status once every source has been added.

        A record is only CONFIRMED_* when a MARKET_TRUTH record carries the very
        same identity; enumerator agreement can never do it on its own.

        Conflicts are *evidence-based*, fail-closed but never speculative.  The
        unit of evidence is a publication: one `(source_name, source_url)` pair
        that published one identity at one level.

          * CROSS-MANUFACTURER — only when a single shared *publication*
            (`source_name` + `source_url`) attributes the same identity to two
            different OEMs.  Equal `source_name` on different URLs is two
            publications, not one.  Two different
            sources each naming the same label for their own OEM is a
            legitimate same-name identity, not a disagreement, so it stays
            IDENTITY_ONLY and gets an explicit note instead.
          * LEVEL CLASH — only when distinct publications publish the same
            identity (within one OEM) at conflicting levels, one as a MODEL and
            one as a VARIANT.  Every source entry carries its own
            `identity_level` declared at ingestion (never derived from the
            record's shape), and a level set is built exclusively from the
            levels each publication declares: a publication that declares
            VARIANT is never treated as MODEL evidence merely because it is
            attached to a record that also has a model.  Publications with no
            declared level keep `identity_level=""`, are collected in
            `unlevelled_publications` and are excluded from level-clash
            detection (fail closed).  A single publication that appears at both levels
            is internally ambiguous, not source-level disagreement: it is kept
            unresolved with an explicit reason and is *not* marked CONFLICT.

        Nothing is ever merged; conflicts and unresolved identities stay as
        separate records with their reasons.
        """
        # (manufacturer, identity key) -> level -> set of publications
        levels: Dict[Tuple[str, str], Dict[str, Set[Tuple[str, str]]]] = {}
        # FULL identity pair (model key, variant key) -> manufacturer ->
        # set of PUBLICATION tuples (source_name, source_url).  The
        # cross-manufacturer check deliberately uses
        # the whole identity, not a bare grade token: "Double Cab" or "Premium"
        # legitimately recurs across OEMs and must never be treated as one
        # shared identity.
        ownership: Dict[Tuple[str, str],
                        Dict[str, Set[Tuple[str, str]]]] = {}
        # (manufacturer, identity key) -> records publishing it
        members: Dict[Tuple[str, str], List[ReconciledIdentity]] = {}
        # identity pair -> records (for the cross-manufacturer check)
        by_identity: Dict[Tuple[str, str], List[ReconciledIdentity]] = {}

        self.unlevelled_publications = []
        self.level_clash_evidence = []
        for rec in self.records:
            pubs = {(s.get("source_name", ""), s.get("source_url", ""))
                    for s in rec.sources} or {("", "")}
            mkey = match_key(rec.manufacturer, rec.model)
            vkey = match_key(rec.manufacturer, rec.variant) if rec.variant else ""

            # ── LEVEL evidence: built strictly from each publication's own
            # declared identity_level.  A publication that declares VARIANT is
            # never counted as MODEL evidence just because it is attached to a
            # record that also has a model, and vice versa.  A publication with
            # no declared level contributes to neither side. ──
            for entry in rec.sources:
                pub = (entry.get("source_name", ""), entry.get("source_url", ""))
                lvl = str(entry.get("identity_level") or "").strip().upper()
                if lvl == "MODEL" and mkey:
                    bucket = levels.setdefault(
                        (rec.manufacturer, mkey),
                        {"MODEL": set(), "VARIANT": set()})
                    bucket["MODEL"].add(pub)
                    members.setdefault((rec.manufacturer, mkey), set()).add(rec)
                elif lvl == "VARIANT" and vkey:
                    bucket = levels.setdefault(
                        (rec.manufacturer, vkey),
                        {"MODEL": set(), "VARIANT": set()})
                    bucket["VARIANT"].add(pub)
                    members.setdefault((rec.manufacturer, vkey), set()).add(rec)
                elif lvl not in ("MODEL", "VARIANT"):
                    self.unlevelled_publications.append({
                        "manufacturer": rec.manufacturer, "model": rec.model,
                        "variant": rec.variant, "source_name": pub[0],
                        "source_url": pub[1],
                    })

            # membership for marking: only records that actually published
            # this identity at some declared level
            if mkey and any(True for e in rec.sources
                            if str(e.get("identity_level") or "").upper() == "MODEL"):
                members.setdefault((rec.manufacturer, mkey), set()).add(rec)
            if vkey and any(True for e in rec.sources
                            if str(e.get("identity_level") or "").upper() == "VARIANT"):
                members.setdefault((rec.manufacturer, vkey), set()).add(rec)

            if mkey:
                pair = (mkey, vkey)
                ownership.setdefault(pair, {}).setdefault(
                    rec.manufacturer, set()).update(
                    (s.get("source_name", ""), s.get("source_url", ""))
                    for s in rec.sources)
                by_identity.setdefault(pair, []).append(rec)

        for rec in self.records:
            roles = {s.get("source_role") for s in rec.sources}
            if rec.first_party:
                rec.status = (FirstPartyStatus.CONFIRMED_VARIANT.value
                              if rec.variant else
                              FirstPartyStatus.CONFIRMED_MODEL.value)
            else:
                rec.status = FirstPartyStatus.IDENTITY_ONLY.value
                rec.rejection_reasons.append(
                    "no MARKET_TRUTH record carries this identity — "
                    "identity-only, never promotable to the accepted set")
            if SourceRole.MARKET_TRUTH.value in roles and \
                    roles - {SourceRole.MARKET_TRUTH.value}:
                rec.match_method = "first_party_plus_enumerator"

        # ── conflict A: one shared source attributes a label to two OEMs ──
        for key, per_mfr in ownership.items():
            if len(per_mfr) < 2:
                continue
            names = sorted(per_mfr)
            # a shared PUBLICATION, not merely a shared source_name: one
            # enumerator serving brand-specific pages must not be mistaken for
            # one page claiming the identity for two OEMs
            shared = {p for p in set.intersection(*[per_mfr[m] for m in names])
                      if p[0] or p[1]}
            recs = by_identity.get(key, [])
            if shared:
                cited = ", ".join(f"{n} <{u}>" for n, u in sorted(shared))
                for rec in recs:
                    _mark_conflict(
                        rec, "same model+variant label attributed to multiple "
                             "manufacturers across sources: "
                             + ", ".join(names)
                             + " (shared publication: " + cited + ")")
            else:
                # distinct sources, each internally consistent — a legitimate
                # same-name identity.  Recorded, never merged, never accused.
                for rec in recs:
                    _note(rec, "same identity label is also published for "
                               + ", ".join(m for m in names
                                           if m != rec.manufacturer)
                               + " by different sources — treated as a "
                                 "legitimate same-name identity, not merged")

        # ── conflict B: distinct publications put one OEM's identity at two
        #    different levels (MODEL on one, VARIANT on the other) ──
        for (mfr, key), lv in levels.items():
            model_pubs, variant_pubs = lv["MODEL"], lv["VARIANT"]
            if not model_pubs or not variant_pubs:
                continue
            if model_pubs == variant_pubs:
                # a single publication at both levels: ambiguous, not a
                # source-level disagreement — kept unresolved and explicit
                for rec in members.get((mfr, key), []):
                    _note(rec, "one source publishes this identity at both the "
                               "MODEL and the VARIANT level — ambiguous, kept "
                               "unresolved rather than called a conflict")
                continue
            m_src = sorted({p[0] for p in model_pubs if p[0]})
            v_src = sorted({p[0] for p in variant_pubs if p[0]})
            affected = members.get((mfr, key), set())
            self.level_clash_evidence.append({
                "manufacturer": mfr, "identity_key": key,
                "model_evidence": sorted(f"{n} <{u}>" for n, u in model_pubs),
                "variant_evidence": sorted(f"{n} <{u}>" for n, u in variant_pubs),
                "records": len(affected),
                "records_first_party_confirmed_not_downgraded": sum(
                    1 for r in affected if r.first_party),
            })
            for rec in affected:
                _mark_conflict(
                    rec, "label published as a MODEL by one source and as a "
                         "VARIANT by another: MODEL evidence ["
                         + ", ".join(m_src) + "] vs VARIANT evidence ["
                         + ", ".join(v_src) + "]")


    @property
    def confidence(self) -> Dict[str, int]:
        out = {c.value: 0 for c in CandidateConfidence}
        for rec in self.records:
            roles = {s.get("source_role") for s in rec.sources}
            if SourceRole.MARKET_TRUTH.value in roles:
                out[CandidateConfidence.OFFICIAL_VERIFIED.value] += 1
            elif len(roles) > 1:
                out[CandidateConfidence.MULTI_SOURCE.value] += 1
            elif len(roles) == 1:
                out[CandidateConfidence.SINGLE_SOURCE.value] += 1
            else:
                out[CandidateConfidence.UNRESOLVED.value] += 1
        return out

    def universe(self) -> IdentityUniverse:
        """Project the reconciliation onto the existing IdentityUniverse type."""
        u = IdentityUniverse(target_date=self.target_date)
        u.sources_used = [s["source_name"] for s in self.sources_used]
        for rec in self.records:
            for s in rec.sources:
                u.add_candidate(IdentityUniverseCandidate(
                    manufacturer_name=rec.manufacturer,
                    model_name=rec.model,
                    generation_name=rec.generation,
                    variant_name=rec.variant,
                    source_name=s.get("source_name", ""),
                    source_role=SourceRole(s.get("source_role",
                                                 SourceRole.IDENTITY_ENUMERATOR.value)),
                    source_url=s.get("source_url", ""),
                    source_label=s.get("label", ""),
                    evidence=[{"first_party_status": rec.status}],
                ))
        return u

    def summary(self) -> Dict:
        by_mfr: Dict[str, Dict] = {}
        for rec in self.records:
            slot = by_mfr.setdefault(rec.manufacturer, {
                "models": set(), "variants": set(),
                "confirmed_models": set(), "confirmed_variants": set(),
                "identity_only_models": set(), "identity_only_variants": set(),
                "conflicts": 0, "sources": set(),
            })
            mk = match_key(rec.manufacturer, rec.model)
            slot["models"].add(mk)
            slot["sources"].update(s["source_name"] for s in rec.sources)
            if rec.variant:
                slot["variants"].add((mk, match_key(rec.manufacturer, rec.variant)))
            if rec.status in (FirstPartyStatus.CONFIRMED_MODEL.value,
                              FirstPartyStatus.CONFIRMED_VARIANT.value):
                slot["confirmed_models"].add(mk)
                if rec.variant:
                    slot["confirmed_variants"].add((mk, match_key(rec.manufacturer, rec.variant)))
            elif rec.status == FirstPartyStatus.IDENTITY_ONLY.value:
                (slot["identity_only_variants"] if rec.variant
                 else slot["identity_only_models"]).add(
                    (mk, match_key(rec.manufacturer, rec.variant)) if rec.variant else mk)
            elif rec.status == FirstPartyStatus.CONFLICT.value:
                slot["conflicts"] += 1
        return {
            "schema": SCHEMA,
            "records": len(self.records),
            "models": len({(r.manufacturer, match_key(r.manufacturer, r.model))
                           for r in self.records}),
            "variants": len({(r.manufacturer, match_key(r.manufacturer, r.model),
                              match_key(r.manufacturer, r.variant))
                             for r in self.records if r.variant}),
            "confirmed_models": len({(r.manufacturer, match_key(r.manufacturer, r.model))
                                     for r in self.records
                                     if r.status in (FirstPartyStatus.CONFIRMED_MODEL.value,
                                                     FirstPartyStatus.CONFIRMED_VARIANT.value)}),
            "confirmed_variants": len({(r.manufacturer, match_key(r.manufacturer, r.model),
                                        match_key(r.manufacturer, r.variant))
                                       for r in self.records
                                       if r.variant and r.status == FirstPartyStatus.CONFIRMED_VARIANT.value}),
            "identity_only": sum(1 for r in self.records
                                 if r.status == FirstPartyStatus.IDENTITY_ONLY.value),
            "conflicts": sum(1 for r in self.records
                             if r.status == FirstPartyStatus.CONFLICT.value),
            "unlevelled_publications": len(self.unlevelled_publications),
            "level_clash_keys": len(self.level_clash_evidence),
            "level_clash_records": sum(e["records"]
                                       for e in self.level_clash_evidence),
            "level_clash_records_confirmed_not_downgraded": sum(
                e["records_first_party_confirmed_not_downgraded"]
                for e in self.level_clash_evidence),
            "rejected": len(self.rejected),
            "confidence": self.confidence,
            "by_manufacturer": {
                m: {
                    "models": len(v["models"]),
                    "variants": len(v["variants"]),
                    "first_party_confirmed_models": len(v["confirmed_models"]),
                    "first_party_confirmed_variants": len(v["confirmed_variants"]),
                    "identity_only_models": len(v["identity_only_models"]),
                    "identity_only_variants": len(v["identity_only_variants"]),
                    "conflicts": v["conflicts"],
                    "sources": sorted(v["sources"]),
                }
                for m, v in sorted(by_mfr.items())
            },
        }

    def to_json(self) -> Dict:
        return {
            "schema": SCHEMA,
            "target_date": self.target_date,
            "role_policy": {
                "IDENTITY_ENUMERATOR": "enumeration evidence only; never market truth",
                "MARKET_REFERENCE": "reference datasets; never market truth",
                "MEDIA_DISCOVERY": "discovery only; never market truth",
                "MARKET_TRUTH": "first-party OEM/importer artifacts only",
            },
            "summary": self.summary(),
            "sources_used": self.sources_used,
            "records": [
                {
                    "manufacturer": r.manufacturer,
                    "model": r.model,
                    "variant": r.variant,
                    "generation": r.generation,
                    "identity_level": "VARIANT" if r.variant else "MODEL",
                    "status": r.status,
                    "sources": r.sources,
                    "first_party": r.first_party,
                    "sources_with_levels": [
                        {"source_name": s.get("source_name"),
                         "source_url": s.get("source_url"),
                         "identity_level": s.get("identity_level")}
                        for s in r.sources],
                    "match_method": r.match_method,
                    "rejection_reasons": r.rejection_reasons,
                    "notes": r.notes,
                    "published_price_thb": r.published_price_thb,
                    "published_price_role": r.published_price_role,
                    "scope": r.scope,
                    "canonical_key": r.canonical_key,
                }
                for r in self.records
            ],
            "rejected": self.rejected,
            "unlevelled_publications": self.unlevelled_publications,
            "level_clash_evidence": self.level_clash_evidence,
        }


def _note(rec: ReconciledIdentity, text: str) -> None:
    """Record a non-blocking observation without accusing a source."""
    if text not in rec.notes:
        rec.notes.append(text)


def _mark_conflict(rec: ReconciledIdentity, reason: str) -> None:
    if rec.status == FirstPartyStatus.IDENTITY_ONLY.value:
        rec.status = FirstPartyStatus.CONFLICT.value
    if reason not in rec.rejection_reasons:
        rec.rejection_reasons.append(reason)
