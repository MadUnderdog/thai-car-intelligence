#!/usr/bin/env python3
"""
Reusable Thailand automotive research engine.
Captures network traffic from official Thai manufacturer websites,
discovers real API endpoints, extracts model/price/spec data,
and persists evidence with proper provenance.
"""

import json, time, re, hashlib
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/home/ubuntu/Projects/thai-car-intelligence/storage/research")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class ThailandAutoResearchEngine:
    """Real research engine using Playwright + network interception."""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.discovered_apis = []
        self.captured_responses = []
    
    def start_browser(self):
        """Launch browser with Thai locale."""
        pw = sync_playwright().start()
        self.browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        self.context = self.browser.new_context(
            locale="th-TH",
            timezone_id="Asia/Bangkok",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        self.pw = pw
    
    def stop_browser(self):
        """Close browser."""
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()
    
    def capture_page_apis(self, url, wait_seconds=10):
        """Navigate to URL and capture all API/data endpoints."""
        page = self.context.new_page()
        captured = {"url": url, "apis": [], "errors": []}
        
        def on_response(response):
            content_type = response.headers.get("content-type", "")
            is_data = any(t in content_type for t in ["json", "javascript", "xml"])
            
            if is_data and response.status == 200:
                try:
                    body = response.text()
                    resp_info = {
                        "url": response.url,
                        "status": response.status,
                        "content_type": content_type,
                        "size": len(body),
                        "body_preview": body[:1000],
                    }
                    
                    if "json" in content_type:
                        try:
                            data = json.loads(body)
                            if isinstance(data, dict):
                                resp_info["json_keys"] = list(data.keys())[:15]
                                # Detect model/price/spec data
                                interesting = [k for k in data.keys() 
                                            if any(t in k.lower() for t in 
                                                ["model", "price", "car", "vehicle", "spec", 
                                                 "grade", "variant", "series", "engine", "power"])]
                                if interesting:
                                    resp_info["data_type"] = interesting
                                    captured["apis"].append(resp_info)
                        except:
                            pass
                except:
                    pass
        
        page.on("response", on_response)
        
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(wait_seconds)
        except Exception as e:
            captured["errors"].append(str(e)[:200])
        
        page.close()
        return captured
    
    def extract_prices_from_dom(self, page):
        """Extract prices from rendered DOM."""
        return page.evaluate("""() => {
            const results = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const text = walker.currentNode.textContent.trim();
                const match = text.match(/([\d,]{6,12})\s*(?:บาท|฿|THB)/);
                if (match && text.length < 200) {
                    results.push({
                        text: text.substring(0, 150),
                        value: parseInt(match[1].replace(/,/g, '')),
                    });
                }
            }
            return results;
        }""")
    
    def extract_specs_from_dom(self, page):
        """Extract specs from rendered DOM using Thai/English patterns."""
        text = page.evaluate("() => document.body.innerText")
        specs = {}
        
        patterns = {
            "power_hp": [r'(\d+\.?\d*)\s*(?:แรงม้า|hp|PS)', r'กำลัง.*?(\d+\.?\d*)\s*(?:แรงม้า|hp|PS)'],
            "torque_nm": [r'(\d+)\s*(?:Nm|นิวตัน)', r'แรงบิด.*?(\d+)\s*Nm'],
            "battery_kwh": [r'(\d+\.?\d*)\s*kWh', r'แบตเตอรี่.*?(\d+\.?\d*)\s*kWh'],
            "range_km": [r'(\d{3,4})\s*(?:กิโลเมตร|km|ระยะทาง)'],
            "length_mm": [r'ยาว\s*([\d,]+)\s*(?:มิลลิเมตร|mm)'],
            "width_mm": [r'กว้าง\s*([\d,]+)\s*(?:มิลลิเมตร|mm)'],
            "height_mm": [r'สูง\s*([\d,]+)\s*(?:มิลลิเมตร|mm)'],
            "wheelbase_mm": [r'ฐานล้อ\s*([\d,]+)\s*(?:มิลลิเมตร|mm)'],
            "engine_cc": [r'(\d{3,4})\s*cc'],
            "displacement_l": [r'(\d\.\d)\s*(?:L|ลิตร|liter)'],
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
    
    def replay_api_request(self, api_url, method="GET", body=None, headers=None):
        """Replay a captured API request."""
        page = self.context.new_page()
        result = {"url": api_url, "method": method, "status": None, "data": None}
        
        try:
            if method == "POST":
                response = page.request.post(api_url, data=json.dumps(body) if body else None,
                                            headers=headers or {"Content-Type": "application/json"})
            else:
                response = page.request.get(api_url, headers=headers)
            
            result["status"] = response.status
            result["data"] = response.json() if "json" in response.headers.get("content-type", "") else response.text()
        except Exception as e:
            result["error"] = str(e)[:200]
        
        page.close()
        return result
    
    def research_brand(self, brand_name, thai_name, official_url, model_path):
        """Complete research loop for one brand."""
        print(f"\n{'='*60}")
        print(f"RESEARCHING: {brand_name} ({thai_name})")
        print(f"{'='*60}")
        
        result = {
            "brand": brand_name,
            "thai_name": thai_name,
            "official_url": official_url,
            "timestamp": datetime.now().isoformat(),
            "discovered_apis": [],
            "models": [],
            "prices": [],
            "specs": [],
            "errors": [],
        }
        
        # Step 1: Discover APIs
        full_url = f"{official_url}{model_path}"
        print(f"1. Discovering APIs from: {full_url}")
        captured = self.capture_page_apis(full_url, wait_seconds=12)
        
        for api in captured.get("apis", []):
            result["discovered_apis"].append(api)
            print(f"   API: {api['url']}")
            if api.get("data_type"):
                print(f"   Data types: {api['data_type']}")
        
        # Step 2: Try to replay discovered APIs
        for api in result["discovered_apis"]:
            if api.get("data_type"):
                print(f"\n2. Replaying API: {api['url']}")
                replayed = self.replay_api_request(api["url"])
                if replayed.get("data"):
                    print(f"   Response keys: {list(replayed['data'].keys())[:10] if isinstance(replayed['data'], dict) else 'array'}")
        
        # Save result
        output_file = OUTPUT_DIR / f"{brand_name.lower().replace(' ', '-')}-api-discovery.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n   Saved to: {output_file}")
        
        return result

def main():
    engine = ThailandAutoResearchEngine()
    engine.start_browser()
    
    try:
        # Research multiple brands
        brands = [
            ("Honda", "ฮอนด้า", "https://www.honda.co.th", "/th/car"),
            ("Toyota", "โตโยต้า", "https://www.toyota.co.th", "/en/model-list"),
            ("Nissan", "นิสสัน", "https://www.nissan.co.th", "/en/vehicles"),
            ("Mazda", "มาสด้า", "https://www.mazda.co.th", "/en/models"),
            ("Mitsubishi", "มิตซูบิชิ", "https://www.mitsubishi-motors.co.th", "/en/model"),
            ("MG", "เอ็มจี", "https://www.mgcars.com", "/th_th/cars"),
        ]
        
        for brand_name, thai_name, url, path in brands:
            try:
                engine.research_brand(brand_name, thai_name, url, path)
            except Exception as e:
                print(f"ERROR: {brand_name}: {e}")
    
    finally:
        engine.stop_browser()

if __name__ == "__main__":
    main()
