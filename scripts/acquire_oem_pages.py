#!/usr/bin/env python3
"""
Horizontal OEM acquisition using AcquisitionWriter (sidecar path).

Captures new artifacts with provenance sidecars (.prov.json) from same acquisition event.
"""
import sys
import os
import asyncio
import json
from datetime import datetime, timezone

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from thai_factory.acquisition.provenance import AcquisitionWriter
from playwright.async_api import async_playwright

FIXTURE_DIR = "tests/fixtures/oem-artifacts"
SESSION_ID = f"acquisition_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"


async def capture_page(url: str, filename: str, wait_selector: str = None, timeout_ms: int = 45000):
    """
    Capture a page with AcquisitionWriter (creates artifact + sidecar).
    
    Returns:
        dict with success, filename, provenance, or error/blocker
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()
        
        try:
            print(f"  Fetching {url}...")
            response = await page.goto(url, timeout=timeout_ms, wait_until='domcontentloaded')
            
            if response and response.status >= 400:
                await browser.close()
                return {
                    'success': False,
                    'blocker': f'HTTP_{response.status}',
                    'url': url,
                    'filename': filename,
                }
            
            # Wait for selector if specified
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=15000)
                except Exception as e:
                    print(f"  Warning: selector wait failed: {e}")
            
            # Get final URL (after redirects)
            final_url = page.url
            
            # Get content
            content = await page.content()
            
            await browser.close()
            
            # Write with AcquisitionWriter (creates artifact + sidecar)
            provenance = AcquisitionWriter.write(
                content=content,
                source_url=final_url,
                acquisition_method="playwright",
                output_dir=FIXTURE_DIR,
                filename=filename,
                session_id=SESSION_ID,
            )
            
            print(f"  ✓ Captured: {filename} ({len(content)} bytes)")
            print(f"    SHA-256: {provenance['sha256'][:16]}...")
            print(f"    captured_at: {provenance['captured_at']}")
            
            return {
                'success': True,
                'filename': filename,
                'provenance': provenance,
                'size': len(content),
                'final_url': final_url,
            }
            
        except Exception as e:
            await browser.close()
            return {
                'success': False,
                'blocker': f'FETCH_ERROR: {str(e)[:100]}',
                'url': url,
                'filename': filename,
            }


async def main():
    """Capture multiple OEM pages with AcquisitionWriter."""
    print(f"=== HORIZONTAL ACQUISITION (session: {SESSION_ID}) ===\n")
    
    # OEM targets - accessible official pages
    targets = [
        # Toyota pricelist renders client-side → wait for the JSON-LD payload
        ('https://www.toyota.co.th/en/pricelist', 'toyota_pricelist_page.html',
         'script[type="application/ld+json"]'),
        # GWM alternate #2: official mall (products publish prices)
        ('https://mall.gwm.co.th/', 'gwm_mall_home.html', None),
    ]
    
    results = []
    blockers = []
    
    for url, filename, selector in targets:
        print(f"\n[{len(results)+len(blockers)+1}/{len(targets)}] {filename}")
        result = await capture_page(url, filename, wait_selector=selector)
        
        if result['success']:
            results.append(result)
        else:
            blockers.append(result)
            print(f"  ✗ BLOCKED: {result['blocker']}")
    
    # Summary
    print(f"\n=== ACQUISITION SUMMARY ===")
    print(f"Session: {SESSION_ID}")
    print(f"Captured: {len(results)}/{len(targets)}")
    print(f"Blocked: {len(blockers)}")
    
    if results:
        print(f"\n✓ Successfully captured:")
        for r in results:
            print(f"  - {r['filename']} ({r['size']:,} bytes) SHA={r['provenance']['sha256'][:16]}...")
    
    if blockers:
        print(f"\n✗ Blocked:")
        for b in blockers:
            print(f"  - {b['filename']}: {b['blocker']} ({b['url']})")
    
    # Save results for reference
    results_file = f"audit/data-staging/acquisition_{SESSION_ID}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'session_id': SESSION_ID,
            'captured': results,
            'blocked': blockers,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {results_file}")


if __name__ == '__main__':
    asyncio.run(main())
