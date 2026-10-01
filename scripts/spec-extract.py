#!/usr/bin/env python3
"""
Real spec extraction from official Thai manufacturer websites.
Uses Playwright to render SPAs and extract power, dimensions, battery, etc.
"""

import json, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/home/ubuntu/Projects/thai-car-intelligence/storage/extractions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_specs_from_page(page, url, model_name, timeout_ms=20000):
    """Navigate to a model page and extract spec data."""
    result = {"model": model_name, "url": url, "specs": {}, "raw_text": "", "error": None}
    
    try:
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        time.sleep(2)
        
        # Get all text content
        text = page.evaluate("() => document.body.innerText")
        result["raw_text"] = text[:5000]
        
        # Extract spec patterns from Thai/English text
        specs = {}
        
        # Power/torque
        power_match = re.search(r'(\d+\.?\d*)\s*(?:แรงม้า|hp|PS|馬力|匹)', text, re.IGNORECASE)
        if power_match:
            specs["power_hp"] = float(power_match.group(1))
        
        torque_match = re.search(r'(\d+)\s*(?:Nm|นิวตันเมตร| Newton)', text, re.IGNORECASE)
        if torque_match:
            specs["torque_nm"] = int(torque_match.group(1))
        
        power_kw = re.search(r'(\d+\.?\d*)\s*kW', text)
        if power_kw:
            specs["power_kw"] = float(power_kw.group(1))
        
        # Dimensions
        length = re.search(r'ยาว.*?(\d{4,5})\s*mm|length.*?(\d{4,5})\s*mm', text, re.IGNORECASE)
        if length:
            specs["length_mm"] = int(length.group(1) or length.group(2))
        
        width = re.search(r'กว้าง.*?(\d{4,5})\s*mm|width.*?(\d{4,5})\s*mm', text, re.IGNORECASE)
        if width:
            specs["width_mm"] = int(width.group(1) or width.group(2))
        
        height = re.search(r'สูง.*?(\d{4,5})\s*mm|height.*?(\d{4,5})\s*mm', text, re.IGNORECASE)
        if height:
            specs["height_mm"] = int(height.group(1) or height.group(2))
        
        wheelbase = re.search(r'ฐานล้อ.*?(\d{4,5})\s*mm|wheelbase.*?(\d{4,5})\s*mm', text, re.IGNORECASE)
        if wheelbase:
            specs["wheelbase_mm"] = int(wheelbase.group(1) or wheelbase.group(2))
        
        ground = re.search(r'ระยะต่ำสุด.*?(\d{2,3})\s*mm|ground clearance.*?(\d{2,3})\s*mm', text, re.IGNORECASE)
        if ground:
            specs["ground_clearance_mm"] = int(ground.group(1) or ground.group(2))
        
        # Battery/EV
        battery = re.search(r'(\d+\.?\d*)\s*kWh', text)
        if battery:
            specs["battery_kwh"] = float(battery.group(1))
        
        range_km = re.search(r'(\d{2,4})\s*(?:กิโลเมตร|km|ระยะทาง)', text, re.IGNORECASE)
        if range_km and int(range_km.group(1)) > 100:
            specs["range_km"] = int(range_km.group(1))
        
        # Engine
        engine = re.search(r'(\d\.\d)\s*(?:L|ลิตร|cc|ซีซี)', text, re.IGNORECASE)
        if engine:
            specs["engine_displacement"] = engine.group(1)
        
        # Transmission
        if re.search(r'CVT|เกียร์อัตโนมัติ|automatic', text, re.IGNORECASE):
            specs["transmission"] = "Automatic/CVT"
        elif re.search(r'เกียร์ธรรมดา|manual|6MT|5MT', text, re.IGNORECASE):
            specs["transmission"] = "Manual"
        
        # Drive type
        if re.search(r'ขับสี่|4WD|AWD|four.wheel', text, re.IGNORECASE):
            specs["drive"] = "AWD/4WD"
        elif re.search(r'ขับหลัง|rear.wheel|RWD', text, re.IGNORECASE):
            specs["drive"] = "RWD"
        elif re.search(r'ขับหน้า|front.wheel|FWD', text, re.IGNORECASE):
            specs["drive"] = "FWD"
        
        # Seating
        seats = re.search(r'(\d)\s*(?:ที่นั่ง| seats)', text, re.IGNORECASE)
        if seats:
            specs["seating"] = int(seats.group(1))
        
        result["specs"] = specs
        result["spec_count"] = len(specs)
        
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result

def main():
    print("=== Real Spec Extraction via Playwright ===\n")
    
    # Models to extract specs for (from verified brands)
    targets = [
        # Honda (verified prices)
        ("Honda City", "https://www.honda.co.th/th/car/city"),
        ("Honda Civic", "https://www.honda.co.th/th/car/civic"),
        ("Honda HR-V", "https://www.honda.co.th/th/car/hr-v"),
        ("Honda CR-V", "https://www.honda.co.th/th/car/cr-v"),
        # Nissan (verified prices)
        ("Nissan Almera", "https://www.nissan.co.th/en/vehicles/new-vehicles/new-almera.html"),
        ("Nissan Kicks", "https://www.nissan.co.th/en/vehicles/new-vehicles/kicks-epower.html"),
        ("Nissan X-Trail", "https://www.nissan.co.th/en/vehicles/new-vehicles/xtrail-epower.html"),
        # MG (verified prices)
        ("MG EXTENDER", "https://www.mgcars.com/th_th/cars/mg-extender"),
        ("MG S5 EV PLUS", "https://www.mgcars.com/th_th/cars/mg-s5-ev-plus"),
        # Mazda (from Playwright extraction)
        ("Mazda CX-5", "https://www.mazda.co.th/en/cars/mazda-cx5"),
        ("Mazda3", "https://www.mazda.co.th/en/cars/mazda3-fastback"),
    ]
    
    all_results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        for model_name, url in targets:
            print(f"Extracting: {model_name}...")
            result = extract_specs_from_page(page, url, model_name)
            all_results.append(result)
            
            specs = result.get("specs", {})
            count = result.get("spec_count", 0)
            error = result.get("error", "")
            
            if specs:
                print(f"  ✓ {count} spec fields: {list(specs.keys())}")
                for k, v in specs.items():
                    print(f"    {k}: {v}")
            elif error:
                print(f"  ✗ Error: {error[:80]}")
            else:
                print(f"  - No specs found (SPA or no data)")
        
        browser.close()
    
    # Save results
    output_file = OUTPUT_DIR / "spec-extraction-results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # Summary
    total_specs = sum(r.get("spec_count", 0) for r in all_results)
    models_with_specs = sum(1 for r in all_results if r.get("spec_count", 0) > 0)
    print(f"\n=== Summary ===")
    print(f"Models attempted: {len(targets)}")
    print(f"Models with specs: {models_with_specs}")
    print(f"Total spec fields: {total_specs}")
    print(f"Results saved to: {output_file}")

if __name__ == "__main__":
    main()
