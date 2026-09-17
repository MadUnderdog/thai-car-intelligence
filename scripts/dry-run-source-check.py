#!/usr/bin/env python3
"""
Dry-run source accessibility check for Thai Car Intelligence database.
Checks all official source URLs for HTTP accessibility without modifying any data.
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
                # Some 4xx/5xx are "reachable but not serving"
                if e.code < 500:
                    result["accessible"] = True  # reachable, just not 200
                return result
            except urllib.error.URLError as e:
                if hasattr(e, 'reason') and isinstance(e.reason, urllib.error.HTTPError):
                    # Redirect loop or similar
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
    print(f"  THAI CAR INTELLIGENCE — Dry-Run Source Accessibility Check")
    print(f"  Timestamp: {now.isoformat()}")
    print(f"{'='*70}")
    
    # Connect to database
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    # Collect all URLs with metadata
    urls_to_check = []
    url_map = {}  # url -> list of {entity, entity_name, field}
    
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
    
    # Also check SourceHealth if table exists
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
    
    print(f"\n📊 Database Summary:")
    print(f"   Unique URLs to check: {total_urls}")
    print(f"   Source base URLs: {sum(1 for refs in url_map.values() if any(r['field'] == 'baseUrl' for r in refs))}")
    print(f"   Source document URLs: {sum(1 for refs in url_map.values() if any(r['field'] == 'url' for r in refs))}")
    print(f"   Manufacturer websites: {sum(1 for refs in url_map.values() if any(r['field'] == 'websiteUrl' for r in refs))}")
    
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
    
    # Performance stats
    times = [r["response_time_ms"] for r in results if r["response_time_ms"]]
    if times:
        print(f"\n  ⏱️  Response Times:")
        print(f"     Average: {sum(times)//len(times)}ms")
        print(f"     Min:     {min(times)}ms")
        print(f"     Max:     {max(times)}ms")
    
    # Domain breakdown
    domain_stats = defaultdict(lambda: {"accessible": 0, "inaccessible": 0})
    for r in results:
        try:
            domain = urllib.parse.urlparse(r["url"]).netloc
        except:
            domain = "unknown"
        if r["accessible"]:
            domain_stats[domain]["accessible"] += 1
        else:
            domain_stats[domain]["inaccessible"] += 1
    
    print(f"\n  🌐 Domain Breakdown:")
    for domain in sorted(domain_stats.keys()):
        stats = domain_stats[domain]
        total = stats["accessible"] + stats["inaccessible"]
        icon = "✅" if stats["inaccessible"] == 0 else "❌"
        print(f"     {icon} {domain}: {stats['accessible']}/{total} accessible")
    
    # Save results
    report = {
        "run_timestamp": now.isoformat(),
        "run_type": "dry_run_source_check",
        "total_urls": total_urls,
        "accessible_count": len(accessible),
        "inaccessible_count": len(inaccessible),
        "published_data_changed": False,
        "results": results,
        "summary": {
            "accessible": [{"url": r["url"], "http_status": r["http_status"], "response_time_ms": r["response_time_ms"], 
                            "referenced_by": r["referenced_by"]} for r in accessible],
            "inaccessible": [{"url": r["url"], "http_status": r["http_status"], "error": r["error"],
                              "referenced_by": r["referenced_by"]} for r in inaccessible],
        }
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
