#!/usr/bin/env python3
"""
Real Thailand automotive research toolkit.
Captures network requests from SPA sites to find actual API endpoints.
Thai locale, Bangkok timezone, realistic browser behavior.
"""

import json, time, re, hashlib
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/home/ubuntu/Projects/thai-car-intelligence/storage/research")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def create_thai_browser_context(p):
    """Create a browser context with Thai locale and Bangkok timezone."""
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(
        locale="th-TH",
        timezone_id="Asia/Bangkok",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        extra_http_headers={
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    return browser, context

def capture_network_requests(page, url, wait_seconds=8):
    """Navigate to URL and capture all network requests/responses."""
    captured = {"requests": [], "responses": [], "xhr_data": []}
    
    def handle_request(request):
        captured["requests"].append({
            "url": request.url,
            "method": request.method,
            "resource_type": request.resource_type,
            "headers": dict(request.headers) if request.headers else {},
        })
    
    def handle_response(response):
        content_type = response.headers.get("content-type", "")
        is_data = any(t in content_type for t in ["json", "javascript", "xml"])
        
        resp_info = {
            "url": response.url,
            "status": response.status,
            "content_type": content_type,
            "size": 0,
        }
        
        try:
            if is_data and response.status == 200:
                body = response.text()
                resp_info["size"] = len(body)
                resp_info["body_preview"] = body[:2000]
                
                # Check if it's JSON with model/price data
                if "json" in content_type:
                    try:
                        data = json.loads(body)
                        resp_info["json_keys"] = list(data.keys()) if isinstance(data, dict) else f"array[{len(data)}]"
                        # Look for model/price related keys
                        if isinstance(data, dict):
                            interesting_keys = [k for k in data.keys() if any(t in k.lower() for t in ["model", "price", "car", "vehicle", "spec", "grade", "variant"])]
                            if interesting_keys:
                                resp_info["interesting_keys"] = interesting_keys
                    except:
                        pass
        except:
            pass
        
        captured["responses"].append(resp_info)
    
    page.on("request", handle_request)
    page.on("response", handle_response)
    
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(wait_seconds)  # Wait for delayed XHR/fetch
    except Exception as e:
        captured["error"] = str(e)[:200]
    
    page.remove_listener("request", handle_request)
    page.remove_listener("response", handle_response)
    
    return captured

def extract_rendered_specs(page):
    """Extract specs from the fully rendered DOM."""
    specs = {}
    
    # Get all visible text
    text = page.evaluate("() => document.body.innerText")
    
    # Thai spec patterns
    patterns = {
        "power_hp": [
            r'กำลัง.*?(\d+\.?\d*)\s*(?:แรงม้า|hp|PS)',
            r'(\d+\.?\d*)\s*(?:แรงม้า|hp|PS)',
            r'Power.*?(\d+\.?\d*)\s*(?:hp|PS)',
        ],
        "torque_nm": [
            r'แรงบิด.*?(\d+)\s*(?:Nm|นิวตัน)',
            r'(\d+)\s*Nm',
            r'Torque.*?(\d+)\s*Nm',
        ],
        "battery_kwh": [
            r'(\d+\.?\d*)\s*kWh',
            r'แบตเตอรี่.*?(\d+\.?\d*)\s*kWh',
        ],
        "range_km": [
            r'(\d{3,4})\s*(?:กิโลเมตร|km|ระยะทางวิ่ง)',
            r'Range.*?(\d{3,4})\s*km',
        ],
        "length_mm": [
            r'ยาว\s*([\d,]+)\s*(?:มิลลิเมตร|mm)',
            r'Length.*?([\d,]+)\s*mm',
        ],
        "width_mm": [
            r'กว้าง\s*([\d,]+)\s*(?:มิลลิเมตร|mm)',
            r'Width.*?([\d,]+)\s*mm',
        ],
        "height_mm": [
            r'สูง\s*([\d,]+)\s*(?:มิลลิเมตร|mm)',
            r'Height.*?([\d,]+)\s*mm',
        ],
        "wheelbase_mm": [
            r'ฐานล้อ\s*([\d,]+)\s*(?:มิลลิเมตร|mm)',
            r'Wheelbase.*?([\d,]+)\s*mm',
        ],
        "engine_cc": [
            r'(\d{3,4})\s*cc',
            r'เครื่องยนต์.*?(\d{3,4})\s*cc',
        ],
        "displacement_l": [
            r'(\d\.\d)\s*(?:L|ลิตร|liter)',
        ],
    }
    
    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).replace(",", "")
                try:
                    specs[key] = float(val) if "." in val else int(val)
                except:
                    specs[key] = val
                break
    
    return specs

def extract_prices_from_dom(page):
    """Extract prices from rendered DOM."""
    prices = []
    
    # Look for price elements
    price_elements = page.evaluate("""() => {
        const results = [];
        // Look for elements with price-like content
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
            const text = el.textContent.trim();
            // Match Thai price patterns
            const match = text.match(/([\d,]{6,12})\s*(?:บาท|฿|THB)/);
            if (match && text.length < 200) {
                results.push({
                    text: text.substring(0, 150),
                    value: match[1].replace(/,/g, ''),
                    tag: el.tagName,
                    className: el.className?.substring(0, 50) || '',
                });
            }
        }
        return results.slice(0, 20);
    }""")
    
    return price_elements

def research_brand(page, brand_name, thai_name, official_url, model_index_path):
    """Complete research loop for one brand."""
    print(f"\n{'='*60}")
    print(f"RESEARCHING: {brand_name} ({thai_name})")
    print(f"{'='*60}")
    
    result = {
        "brand": brand_name,
        "thai_name": thai_name,
        "official_url": official_url,
        "timestamp": datetime.now().isoformat(),
        "discovery": {},
        "models": [],
        "network_requests": [],
        "api_endpoints": [],
        "errors": [],
    }
    
    # Step 1: Navigate to model index
    full_url = f"{official_url}{model_index_path}"
    print(f"\n1. Navigating to: {full_url}")
    captured = capture_network_requests(page, full_url, wait_seconds=10)
    
    # Find interesting API endpoints
    for resp in captured.get("responses", []):
        if resp.get("interesting_keys"):
            result["api_endpoints"].append({
                "url": resp["url"],
                "keys": resp["interesting_keys"],
                "content_type": resp.get("content_type"),
            })
            print(f"   API FOUND: {resp['url']}")
            print(f"   Keys: {resp['interesting_keys']}")
    
    # Extract rendered model list
    models = page.evaluate("""() => {
        const links = document.querySelectorAll('a[href]');
        const models = [];
        for (const link of links) {
            const href = link.href || '';
            const text = link.textContent.trim();
            if (text.length > 2 && text.length < 100 && 
                (href.includes('/model/') || href.includes('/car/') || href.includes('/vehicle/'))) {
                models.push({name: text, href: href});
            }
        }
        return models;
    }""")
    
    result["discovery"]["models_found"] = len(models)
    result["discovery"]["models"] = models[:20]
    print(f"   Models found: {len(models)}")
    for m in models[:10]:
        print(f"   - {m['name']}: {m['href']}")
    
    # Extract prices from DOM
    prices = extract_prices_from_dom(page)
    result["discovery"]["prices_found"] = len(prices)
    print(f"   Prices found: {len(prices)}")
    for p in prices[:5]:
        print(f"   - {p['value']} THB ({p['text'][:50]})")
    
    # Step 2: Visit each model page
    print(f"\n2. Visiting model pages...")
    for model in models[:5]:  # Limit to first 5 for now
        model_url = model["href"]
        print(f"   Visiting: {model['name']} → {model_url}")
        
        try:
            page.goto(model_url, wait_until="networkidle", timeout=20000)
            time.sleep(5)
            
            # Extract specs
            specs = extract_rendered_specs(page)
            prices = extract_prices_from_dom(page)
            
            model_data = {
                "name": model["name"],
                "url": model_url,
                "specs": specs,
                "prices": prices[:5],
                "spec_count": len(specs),
            }
            result["models"].append(model_data)
            
            print(f"     Specs: {len(specs)} fields")
            for k, v in specs.items():
                print(f"       {k}: {v}")
            if prices:
                print(f"     Prices: {len(prices)}")
                
        except Exception as e:
            result["errors"].append(f"{model['name']}: {str(e)[:100]}")
            print(f"     ERROR: {str(e)[:80]}")
    
    # Save result
    output_file = OUTPUT_DIR / f"{brand_name.lower().replace(' ', '-')}-research.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n   Saved to: {output_file}")
    
    return result

def main():
    print("=== Thailand Automotive Research Toolkit ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Locale: th-TH, Timezone: Asia/Bangkok\n")
    
    all_results = {}
    
    with sync_playwright() as p:
        browser, context = create_thai_browser_context(p)
        page = context.new_page()
        
        # Research brands one by one
        brands = [
            ("Honda", "ฮอนด้า", "https://www.honda.co.th", "/th/car"),
            ("Toyota", "โตโยต้า", "https://www.toyota.co.th", "/en/model-list"),
            ("Nissan", "นิสสัน", "https://www.nissan.co.th", "/en/vehicles"),
            ("Mazda", "มาสด้า", "https://www.mazda.co.th", "/en/models"),
            ("Mitsubishi", "มิตซูบิชิ", "https://www.mitsubishi-motors.co.th", "/en/model"),
            ("MG", "เอ็มจี", "https://www.mgcars.com", "/th_th/cars"),
        ]
        
        for brand_name, thai_name, official_url, model_path in brands:
            try:
                result = research_brand(page, brand_name, thai_name, official_url, model_path)
                all_results[brand_name] = result
            except Exception as e:
                print(f"FATAL ERROR for {brand_name}: {e}")
                all_results[brand_name] = {"error": str(e)}
        
        browser.close()
    
    # Save all results
    summary_file = OUTPUT_DIR / "research-summary.json"
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n{'='*60}")
    print("RESEARCH SUMMARY")
    print(f"{'='*60}")
    for brand, data in all_results.items():
        models = len(data.get("models", []))
        api_endpoints = len(data.get("api_endpoints", []))
        specs_total = sum(m.get("spec_count", 0) for m in data.get("models", []))
        errors = len(data.get("errors", []))
        print(f"  {brand}: {models} models visited, {api_endpoints} API endpoints, {specs_total} specs, {errors} errors")

if __name__ == "__main__":
    main()
