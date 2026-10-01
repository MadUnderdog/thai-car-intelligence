#!/usr/bin/env python3
"""P107 — re-acquire PDFs whose base64 artifact was corrupted by sanitisation.

The mandatory credential sanitizer inside AcquisitionWriter scanned the base64
payload of a captured PDF and replaced a chance `AIza…`-like sequence with
`[REDACTED:google_api_key]`, which corrupts the encoding (the stored sidecar is
still self-consistent, but the bytes are no longer a decodable PDF).

Those sources are re-fetched once (same polite GET, no blocked host, no retry of
an HTTP error) and stored as **derived text** produced by `pdftotext -layout`,
written through AcquisitionWriter as `http_get_pdf_pdftotext`, so the sidecar
hash always covers exactly what is on disk.  The capture log records both the
downloaded PDF's SHA-256 and the stored text's SHA-256, and why the raw-PDF
artifact was replaced.  Nothing is back-filled and no price is read.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from thai_factory.acquisition.provenance import AcquisitionWriter  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO, "tests/fixtures/oem-artifacts")
OUT = os.path.join(REPO, "audit/coverage")
SESSION_ID = "p107_batch_sources_20260927"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
POLITENESS_S = 0.5


def pdf_text(data: bytes) -> str:
    fh = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        fh.write(data)
        fh.close()
        return subprocess.run(["pdftotext", "-layout", fh.name, "-"],
                              capture_output=True, text=True, timeout=120).stdout
    finally:
        try:
            os.unlink(fh.name)
        except OSError:
            pass


def is_decodable_pdf(path: str) -> bool:
    """True only when the stored base64 is a clean PDF with no sanitizer hole."""
    if not path.endswith(".b64"):
        return True
    raw = open(path, "rb").read()
    if b"REDACTED" in raw:
        return False
    try:
        return base64.b64decode(raw, validate=False)[:4] == b"%PDF"
    except Exception:
        return False


def main() -> int:
    log_path = os.path.join(OUT, "p107_capture_log.json")
    log = json.load(open(log_path, encoding="utf-8"))
    results = log["results"]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "th-TH,th;q=0.9"})

    replaced, failed = 0, 0
    for entry in results:
        fname = entry.get("filename")
        if not entry.get("ok") or not fname or not fname.endswith(".b64"):
            continue
        path = os.path.join(FIXTURE_DIR, fname)
        if not os.path.exists(path) or is_decodable_pdf(path):
            continue
        prov = json.load(open(path + ".prov.json", encoding="utf-8"))
        url = prov["source_url"]
        entry["raw_pdf_storage"] = "corrupted_by_credential_sanitizer"
        try:
            resp = session.get(url, timeout=60)
        except Exception as exc:
            entry.update(ok=False, error=f"REACQUIRE_ERROR {type(exc).__name__}: {exc}")
            failed += 1
            time.sleep(POLITENESS_S)
            continue
        if resp.status_code != 200:
            entry.update(ok=False, error=f"REACQUIRE_HTTP_{resp.status_code}")
            failed += 1
            time.sleep(POLITENESS_S)
            continue
        pdf_sha = hashlib.sha256(resp.content).hexdigest()
        text = pdf_text(resp.content) if resp.content[:4] == b"%PDF" else ""
        if len(text.strip()) < 200:
            entry.update(ok=False,
                         error="REACQUIRE_NO_TEXT_LAYER: PDF has no extractable text; "
                               "raw-PDF artifact dropped, no evidence taken")
            os.remove(path)
            os.remove(path + ".prov.json")
            failed += 1
            time.sleep(POLITENESS_S)
            continue
        stem = fname[:-len(".b64")]
        new_name = stem + ".txt"
        new_path = os.path.join(FIXTURE_DIR, new_name)
        if os.path.exists(new_path):
            new_name = stem + "_2.txt"
            new_path = os.path.join(FIXTURE_DIR, new_name)
        prov_new = AcquisitionWriter.write(
            content=text, source_url=url, acquisition_method="http_get_pdf_pdftotext",
            output_dir=FIXTURE_DIR, filename=new_name, session_id=SESSION_ID)
        os.remove(path)
        os.remove(path + ".prov.json")
        entry.update(filename=new_name, sha256=prov_new.get("sha256"),
                     pdf_sha256=pdf_sha, pdf_bytes=len(resp.content),
                     text_chars=len(text), tool="pdftotext -layout",
                     replaced_artifact=fname)
        replaced += 1
        time.sleep(POLITENESS_S)

    log["reacquired"] = {"replaced": replaced, "failed": failed,
                         "generated_at": datetime.datetime.now(
                             datetime.timezone.utc).isoformat()}
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"replaced={replaced} failed={failed}")
    for e in results:
        if e.get("replaced_artifact"):
            print(f"  ok   {e['filename']:70s} pdf_sha={e['pdf_sha256'][:12]} "
                  f"text_chars={e['text_chars']}")
        elif not e.get("ok"):
            print(f"  FAIL {str(e.get('error'))[:90]:90s} {e['url'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
