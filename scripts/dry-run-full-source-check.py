#!/usr/bin/env python3
"""
Full dry-run source accessibility check for Thai Car Intelligence database.
Checks ALL source URLs including Price.sourceUrl, Manufacturer.websiteUrl,
Source.baseUrl, and SourceDocument.url — without modifying any data.
"""
import psycopg2
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import ssl
import socket
from datetime import datetime, timezone, timedelta
from collections import defaultdict

DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "dbname": "thai_car_intelligence",
    "user": "hermes",
    "password": "hermes2026"
}

TIMEOUT = 12  # seconds per request
USER_AGENT = "ThaiCarIntel/1.0 (dry-run source check)"
RESULTS_DIR = "/home/ubuntu/thai-car-intelligence/storage"

def create_ssl_context():
    ctx = ssl.create_default_context()
    return ctx

def check_url(url, timeout=TIMEOUT):
    """Check a URL's accessibility. Returns a result dict."""
    result = {
        "url": url,
        "accessible": False,
        "http_status": None,
        "response_time_ms": None,
        "final_url": None,
        "redirect_chain": [],
        "error": None,
        "ssl_error": False,
        "timeout": False,
        "content_length": None,
        "content_type": None,
        "server": None,
        "last_modified": None,
        "etag": None,
    }

    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET", headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "th,en;q=0.9",
        })

        ssl_ctx = create_ssl_context()

        # Follow redirects manually to capture chain
        max_redirects = 5
        redirects = []
        current_url = url

        for _ in range(max_redirects + 1):
            try:
                resp = urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)
                elapsed = int((time.monotonic() - start) * 1000)

                final_url = resp.geturl()
                if final_url != url:
                    redirects.append(final_url)

                headers = dict(resp.headers)
                result["accessible"] = True
                result["http_status"] = resp.status
                result["response_time_ms"] = elapsed
                result["final_url"] = final_url
                result["redirect_chain"] = redirects
                result["content_type"] = headers.get("Content-Type", "")
                result["content_length"] = headers.get("Content-Length")
                result["server"] = headers.get("Server", "")
                result["last_modified"] = headers.get("Last-Modified")
                result["etag"] = headers.get("ETag")
                resp.close()
                return result
            except urllib.error.HTTPError as e:
                elapsed = int((time.monotonic() - start) * 1000)
                result["http_status"] = e.code
                result["response_time_ms"] = elapsed
                result["error"] = f"HTTP {e.code}: {e.reason}"
                if e.code < 500:
                    result["accessible"] = True  # reachable, just not 200
                return result
            except urllib.error.URLError as e:
                if hasattr(e, 'reason') and isinstance(e.reason, urllib.error.HTTPError):
                    pass
                raise
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        result["http_status"] = e.code
        result["response_time_ms"] = elapsed
        result["error"] = f"HTTP {e.code}: {e.reason}"
        if e.code < 500:
            result["accessible"] = True
    except urllib.error.URLError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        result["response_time_ms"] = elapsed
        result["error"] = str(e.reason) if hasattr(e, 'reason') else str(e)
    except socket.timeout:
        elapsed = int((time.monotonic() - start) * 1000)
        result["response_time_ms"] = elapsed
        result["timeout"] = True
        result["error"] = f"Timeout after {timeout}s"
    except ssl.SSLError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        result["response_time_ms"] = elapsed
        result["ssl_error"] = True
        result["error"] = f"SSL Error: {e}"
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        result["response_time_ms"] = elapsed
        result["error"] = f"{type(e).__name__}: {e}"

    return result

def main():
    now = datetime.now(timezone(timedelta(hours=7)))
    print(f"{'='*70}")
    print(f"  THAI CAR INTELLIGENCE — Full Dry-Run Source Check")
    print(f"  Timestamp: {now.isoformat()}")
    print(f"  Mode: DRY-RUN (no data modified)")
    print(f"{'='*70}")

    # Connect to database
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # Collect all URLs with metadata
    url_map = {}  # url -> list of {entity, entity_name, field, ...}

    # 1. Source.baseUrl
    cur.execute('SELECT id, "nameEn", "sourceType", "baseUrl", "domain", status FROM "Source" WHERE status = \'ACTIVE\'')
    for row in cur.fetchall():
        src_id, name, src_type, base_url, domain, status = row
        if base_url and base_url not in url_map:
            url_map[base_url] = []
        if base_url:
            url_map[base_url].append({"entity": "Source", "id": src_id, "name": name, "field": "baseUrl", "source_type": src_type})

    # 2. SourceDocument.url
    cur.execute('''SELECT sd.id, sd.url, sd.status, sd."sourceId", s."nameEn"
                   FROM "SourceDocument" sd
                   JOIN "Source" s ON s.id = sd."sourceId"
                   WHERE sd.url IS NOT NULL''')
    for row in cur.fetchall():
        doc_id, url, status, source_id, source_name = row
        if url not in url_map:
            url_map[url] = []
        url_map[url].append({"entity": "SourceDocument", "id": doc_id, "name": source_name, "field": "url", "doc_status": status})

    # 3. Manufacturer.websiteUrl
    cur.execute('SELECT id, "nameEn", "websiteUrl" FROM "Manufacturer" WHERE "websiteUrl" IS NOT NULL')
    for row in cur.fetchall():
        mfr_id, name, website = row
        if website and website not in url_map:
            url_map[website] = []
        if website:
            url_map[website].append({"entity": "Manufacturer", "id": mfr_id, "name": name, "field": "websiteUrl"})

    # 4. Price.sourceUrl — the main data source URLs
    cur.execute('''
        SELECT p."sourceUrl", v."nameEn" as variant_name, cm."nameEn" as model_name,
               mfr."nameEn" as mfr_name, p.amount, p.currency, p."validFrom"
        FROM "Price" p
        JOIN "Variant" v ON v.id = p."variantId"
        JOIN "CarModel" cm ON cm.id = v."modelId"
        JOIN "Manufacturer" mfr ON mfr.id = cm."manufacturerId"
        WHERE p."sourceUrl" IS NOT NULL AND p."isCurrent" = true
        ORDER BY mfr."nameEn", cm."nameEn", v."nameEn"
    ''')
    price_urls = []
    for row in cur.fetchall():
        src_url, variant_name, model_name, mfr_name, amount, currency, valid_from = row
        if src_url not in url_map:
            url_map[src_url] = []
        url_map[src_url].append({
            "entity": "Price",
            "name": f"{mfr_name} {model_name} {variant_name}",
            "field": "sourceUrl",
            "amount": amount,
            "currency": currency,
            "valid_from": str(valid_from) if valid_from else None,
        })
        price_urls.append({
            "url": src_url,
            "mfr": mfr_name,
            "model": model_name,
            "variant": variant_name,
            "amount": amount,
        })

    # Collect SourceHealth if available
    source_health = []
    try:
        cur.execute('''SELECT source_url, domain, last_checked_at, last_success_at, http_status,
                       response_time_ms, last_error, consecutive_failures
                       FROM "SourceHealth" ORDER BY consecutive_failures DESC''')
        source_health = cur.fetchall()
    except Exception:
        pass

    conn.close()

    unique_urls = sorted(url_map.keys())
    total_urls = len(unique_urls)

    # Count by entity type
    price_url_count = sum(1 for refs in url_map.values() if any(r['field'] == 'sourceUrl' and r['entity'] == 'Price' for r in refs))
    mfr_url_count = sum(1 for refs in url_map.values() if any(r['field'] == 'websiteUrl' for r in refs))
    source_url_count = sum(1 for refs in url_map.values() if any(r['field'] == 'baseUrl' for r in refs))
    doc_url_count = sum(1 for refs in url_map.values() if any(r['field'] == 'url' and r['entity'] == 'SourceDocument' for r in refs))

    print(f"\n📊 Database Summary:")
    print(f"   Total unique URLs:        {total_urls}")
    print(f"   ├── Price.sourceUrl:      {price_url_count} (product pages)")
    print(f"   ├── Manufacturer website:  {mfr_url_count}")
    print(f"   ├── Source.baseUrl:        {source_url_count}")
    print(f"   └── SourceDocument.url:    {doc_url_count}")

    if source_health:
        print(f"\n📋 Previous SourceHealth entries: {len(source_health)}")
        for sh in source_health:
            print(f"   {sh[1]}: failures={sh[7]}, last_ok={sh[3]}, error={sh[6]}")

    # Check each URL
    print(f"\n🔍 Checking {total_urls} URLs (timeout={TIMEOUT}s each)...\n")

    results = []
    accessible = []
    inaccessible = []

    for i, url in enumerate(unique_urls, 1):
        refs = url_map[url]
        primary = refs[0]
        label = f"{primary['name']} ({primary['entity']}.{primary['field']})"
        print(f"  [{i:2d}/{total_urls}] {label}")
        print(f"           URL: {url}")

        result = check_url(url)
        result["referenced_by"] = refs
        results.append(result)

        status_icon = "✅" if result["accessible"] else "❌"
        status_code = result["http_status"] or "N/A"
        resp_time = result["response_time_ms"] or "?"
        final = result["final_url"] if result["final_url"] != url else ""
        error = result["error"] or ""

        line = f"           {status_icon} HTTP {status_code} | {resp_time}ms"
        if final:
            line += f" | → {final}"
        if error:
            line += f" | {error}"
        print(line)

        if result["redirect_chain"]:
            print(f"           ↳ Redirects: {' → '.join(result['redirect_chain'][:3])}")

        if result["accessible"]:
            accessible.append(result)
        else:
            inaccessible.append(result)

        # Small delay between requests
        if i < total_urls:
            time.sleep(0.3)

    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  Total URLs checked:    {total_urls}")
    print(f"  Accessible:            {len(accessible)} ✅")
    print(f"  Inaccessible:          {len(inaccessible)} ❌")
    print(f"  Published data changed: NO (dry-run)")

    if inaccessible:
        print(f"\n  ❌ INACCESSIBLE SOURCES:")
        for r in inaccessible:
            refs = r["referenced_by"]
            primary = refs[0]
            print(f"     • {primary['name']}: {r['url']}")
            http_code = r["http_status"] or "N/A"
            reason = r['error'] or f'HTTP {http_code}'
            print(f"       Reason: {reason}")
            if r.get("timeout"):
                print(f"       ⚠️  May indicate slow server or geo-blocking")

    # Performance stats
    times = [r["response_time_ms"] for r in results if r["response_time_ms"]]
    if times:
        print(f"\n  ⏱️  Response Times:")
        print(f"     Average: {sum(times)//len(times)}ms")
        print(f"     Min:     {min(times)}ms")
        print(f"     Max:     {max(times)}ms")

    # Domain breakdown
    domain_stats = defaultdict(lambda: {"accessible": 0, "inaccessible": 0, "urls": []})
    for r in results:
        try:
            domain = urllib.parse.urlparse(r["url"]).netloc
        except:
            domain = "unknown"
        if r["accessible"]:
            domain_stats[domain]["accessible"] += 1
        else:
            domain_stats[domain]["inaccessible"] += 1
        domain_stats[domain]["urls"].append(r["url"])

    print(f"\n  🌐 Domain Breakdown:")
    for domain in sorted(domain_stats.keys()):
        stats = domain_stats[domain]
        total = stats["accessible"] + stats["inaccessible"]
        icon = "✅" if stats["inaccessible"] == 0 else "❌"
        print(f"     {icon} {domain}: {stats['accessible']}/{total} accessible")

    # Manufacturer-specific summary
    print(f"\n  🚗 Manufacturer Source Status:")
    mfr_stats = defaultdict(lambda: {"ok": 0, "fail": 0, "urls": []})
    for r in results:
        for ref in r["referenced_by"]:
            mfr_name = None
            if ref["entity"] == "Manufacturer":
                mfr_name = ref["name"]
            elif ref["entity"] == "Price":
                mfr_name = ref["name"].split()[0]  # first word is manufacturer
            elif ref["entity"] == "Source":
                mfr_name = ref["name"]
            if mfr_name:
                if r["accessible"]:
                    mfr_stats[mfr_name]["ok"] += 1
                else:
                    mfr_stats[mfr_name]["fail"] += 1
                mfr_stats[mfr_name]["urls"].append(r["url"])
                break  # count each URL once per manufacturer

    for mfr in sorted(mfr_stats.keys()):
        stats = mfr_stats[mfr]
        total = stats["ok"] + stats["fail"]
        icon = "✅" if stats["fail"] == 0 else "❌"
        print(f"     {icon} {mfr}: {stats['ok']}/{total} sources accessible")

    # Save results
    report = {
        "run_timestamp": now.isoformat(),
        "run_type": "dry_run_full_source_check",
        "total_urls": total_urls,
        "accessible_count": len(accessible),
        "inaccessible_count": len(inaccessible),
        "published_data_changed": False,
        "url_breakdown": {
            "price_source_urls": price_url_count,
            "manufacturer_websites": mfr_url_count,
            "source_base_urls": source_url_count,
            "source_document_urls": doc_url_count,
        },
        "results": results,
        "summary": {
            "accessible": [{"url": r["url"], "http_status": r["http_status"], "response_time_ms": r["response_time_ms"],
                            "referenced_by": r["referenced_by"]} for r in accessible],
            "inaccessible": [{"url": r["url"], "http_status": r["http_status"], "error": r["error"],
                              "referenced_by": r["referenced_by"]} for r in inaccessible],
        },
        "domain_breakdown": {k: {"accessible": v["accessible"], "inaccessible": v["inaccessible"]}
                             for k, v in domain_stats.items()},
    }

    report_path = f"{RESULTS_DIR}/dry-run-source-check-{now.strftime('%Y%m%d-%H%M%S')}.json"
    latest_path = f"{RESULTS_DIR}/dry-run-source-check-latest.json"

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    with open(latest_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  📁 Results saved to:")
    print(f"     {report_path}")
    print(f"     {latest_path}")
    print(f"\n{'='*70}")

if __name__ == "__main__":
    main()
