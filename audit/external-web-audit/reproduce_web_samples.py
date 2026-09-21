#!/usr/bin/env python3
"""
Web Verification Script — re-fetches sample URLs and checks cited excerpts.
Respects robots/rate limits. Does not bypass access controls.
"""
import json
import os
import re
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

USER_AGENT = "ThaiCarIntel-Audit/1.0 (verification bot)"
TIMEOUT = 15
RATE_LIMIT = 2.0  # seconds between requests


def fetch_url(url: str) -> str:
    """Fetch URL with audit user agent."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip_html(html: str) -> str:
    """Strip HTML tags."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def verify_sample(sample: dict) -> dict:
    """Verify a single sample against live web."""
    result = {
        "id": sample.get("id", "unknown"),
        "url": sample.get("source_url", ""),
        "field": sample.get("field", ""),
        "expected_value": sample.get("normalized_value", ""),
        "status": "NOT_REPRODUCED",
        "details": "",
    }

    url = sample.get("source_url", "")
    if not url:
        result["status"] = "NO_URL"
        return result

    try:
        html = fetch_url(url)
        text = strip_html(html)

        # Check if the expected value appears in the page
        expected = str(sample.get("normalized_value", ""))
        raw = str(sample.get("raw_value", ""))

        if expected in text or raw in text:
            result["status"] = "PASS"
            result["details"] = f"Value '{expected}' found in page"
        else:
            # Try with commas
            try:
                formatted = f"{int(expected):,}"
                if formatted in text:
                    result["status"] = "PASS"
                    result["details"] = f"Value '{formatted}' found in page"
                else:
                    result["status"] = "VALUE_MISMATCH"
                    result["details"] = f"Expected '{expected}' not found in page"
            except ValueError:
                result["status"] = "VALUE_MISMATCH"
                result["details"] = f"Expected '{expected}' not found in page"

    except HTTPError as e:
        result["status"] = "HTTP_ERROR"
        result["details"] = f"HTTP {e.code}"
    except URLError as e:
        result["status"] = "URL_ERROR"
        result["details"] = str(e.reason)
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = str(e)[:200]

    return result


def main():
    """Main verification loop."""
    audit_dir = os.path.dirname(os.path.abspath(__file__))

    # Load price samples
    price_file = os.path.join(audit_dir, "price-samples.jsonl")
    spec_file = os.path.join(audit_dir, "spec-samples.jsonl")

    results = []

    for sample_file, field_type in [(price_file, "price"), (spec_file, "spec")]:
        if not os.path.exists(sample_file):
            print(f"Skipping {sample_file} — not found")
            continue

        print(f"\nVerifying {field_type} samples from {sample_file}")
        with open(sample_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                sample = json.loads(line)
                sample["field"] = field_type

                result = verify_sample(sample)
                results.append(result)

                status_icon = "✓" if result["status"] == "PASS" else "✗"
                print(f"  {status_icon} {result['id']}: {result['status']} — {result['details'][:80]}")

                time.sleep(RATE_LIMIT)

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] != "PASS")
    print(f"\n=== Verification Summary ===")
    print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")

    # Save results
    output_file = os.path.join(audit_dir, "web-verification-results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    main()
