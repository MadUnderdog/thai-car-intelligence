#!/usr/bin/env python3
"""
Real web extraction from official Thai manufacturer websites using Playwright.
Renders SPA pages, extracts model listings, prices, and specs.
Persists results as JSON for Prisma ingestion.
"""

import json, sys, time, hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/home/ubuntu/Projects/thai-car-intelligence/storage/extractions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_brand(page, brand_name, url, model_selector, price_selector=None, timeout_ms=20000):
    """Extract model data from a brand's official website."""
    result = {"brand": brand_name, "url": url, "models": [], "error": None}
    try:
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        time.sleep(3)  # Wait for SPA rendering
        
        # Extract model links/names
        models = page.evaluate("""(selector) => {
            const els = document.querySelectorAll(selector);
            return Array.from(els).map(el => ({
                name: el.textContent.trim().substring(0, 100),
                href: el.href || el.querySelector('a')?.href || '',
                img: el.querySelector('img')?.src || ''
            })).filter(m => m.name.length > 1 && m.name.length < 100);
        }""", model_selector)
        
        result["models"] = models[:30]
        
        # Try to extract prices if selector provided
        if price_selector:
            prices = page.evaluate("""(selector) => {
                const els = document.querySelectorAll(selector);
                return Array.from(els).map(el => el.textContent.trim()).filter(t => t.length > 0);
            }""", price_selector)
            result["prices_found"] = prices[:20]
        
        # Also try to find any price-like text on the page
        all_text = page.evaluate("() => document.body.innerText")
        import re
        price_matches = re.findall(r'[\d,]{6,12}\s*(?:บาท|฿|THB)', all_text)
        result["price_mentions"] = list(set(price_matches))[:10]
        
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result

def main():
    print("=== Real Web Extraction via Playwright ===\n")
    
    results = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        # 1. Toyota Thailand
        print("1. Toyota Thailand...")
        results["toyota"] = extract_brand(
            page, "Toyota", "https://www.toyota.co.th/en/model-list",
            'a[href*="/model/"], .model-card, [class*="model-item"]'
        )
        print(f"   Found {len(results['toyota']['models'])} models, {len(results['toyota'].get('price_mentions', []))} prices")
        
        # 2. Honda Thailand
        print("2. Honda Thailand...")
        results["honda"] = extract_brand(
            page, "Honda", "https://www.honda.co.th/th",
            'a[href*="/car/"], a[href*="/th/car/"]'
        )
        print(f"   Found {len(results['honda']['models'])} models, {len(results['honda'].get('price_mentions', []))} prices")
        
        # 3. Nissan Thailand
        print("3. Nissan Thailand...")
        results["nissan"] = extract_brand(
            page, "Nissan", "https://www.nissan.co.th/en/vehicles",
            'a[href*="/vehicles/"], .vehicle-card, [class*="vehicle"]'
        )
        print(f"   Found {len(results['nissan']['models'])} models, {len(results['nissan'].get('price_mentions', []))} prices")
        
        # 4. MG Thailand
        print("4. MG Thailand...")
        results["mg"] = extract_brand(
            page, "MG", "https://www.mgcars.com/th_th/cars",
            'a[href*="/cars/"], .car-card, [class*="car-item"]'
        )
        print(f"   Found {len(results['mg']['models'])} models, {len(results['mg'].get('price_mentions', []))} prices")
        
        # 5. Mitsubishi Thailand
        print("5. Mitsubishi Thailand...")
        results["mitsubishi"] = extract_brand(
            page, "Mitsubishi", "https://www.mitsubishi-motors.co.th/en/model",
            'a[href*="/cars/"], a[href*="/en/cars/"], .model-card'
        )
        print(f"   Found {len(results['mitsubishi']['models'])} models, {len(results['mitsubishi'].get('price_mentions', []))} prices")
        
        # 6. Mazda Thailand
        print("6. Mazda Thailand...")
        results["mazda"] = extract_brand(
            page, "Mazda", "https://www.mazda.co.th/en/models",
            'a[href*="/cars/"], a[href*="/en/cars/"], .model-card'
        )
        print(f"   Found {len(results['mazda']['models'])} models, {len(results['mazda'].get('price_mentions', []))} prices")
        
        # 7. Suzuki Thailand
        print("7. Suzuki Thailand...")
        results["suzuki"] = extract_brand(
            page, "Suzuki", "https://www.suzukimotor.co.th/en/model",
            'a[href*="/en/"], .model-card, [class*="model"]'
        )
        print(f"   Found {len(results['suzuki']['models'])} models, {len(results['suzuki'].get('price_mentions', []))} prices")
        
        # 8. Ford Thailand
        print("8. Ford Thailand...")
        results["ford"] = extract_brand(
            page, "Ford", "https://www.ford.co.th/vehicles",
            'a[href*="/vehicles/"], .vehicle-card'
        )
        print(f"   Found {len(results['ford']['models'])} models, {len(results['ford'].get('price_mentions', []))} prices")
        
        # 9. BYD Thailand (via Rever Automotive)
        print("9. BYD Thailand (Rever Automotive)...")
        results["byd"] = extract_brand(
            page, "BYD", "https://www.reverautomotive.com/models",
            'a[href*="/models/"], a[href*="/model/"], .model-card'
        )
        print(f"   Found {len(results['byd']['models'])} models, {len(results['byd'].get('price_mentions', []))} prices")
        
        # 10. Hyundai Thailand
        print("10. Hyundai Thailand...")
        results["hyundai"] = extract_brand(
            page, "Hyundai", "https://www.hyundai.com/th/en/models",
            'a[href*="/models/"], .model-card'
        )
        print(f"   Found {len(results['hyundai']['models'])} models, {len(results['hyundai'].get('price_mentions', []))} prices")
        
        browser.close()
    
    # Save results
    output_file = OUTPUT_DIR / "web-extraction-results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to {output_file}")
    
    # Summary
    total_models = sum(len(r.get("models", [])) for r in results.values())
    total_prices = sum(len(r.get("price_mentions", [])) for r in results.values())
    print(f"\n=== Summary ===")
    print(f"Brands extracted: {len(results)}")
    print(f"Total models found: {total_models}")
    print(f"Total price mentions: {total_prices}")
    
    for brand, data in results.items():
        models = len(data.get("models", []))
        prices = len(data.get("price_mentions", []))
        error = data.get("error", "")
        status = "✓" if models > 0 else ("⚠ SPA" if not error else "✗")
        print(f"  {brand}: {status} {models} models, {prices} prices" + (f" ({error[:50]})" if error else ""))

if __name__ == "__main__":
    main()
