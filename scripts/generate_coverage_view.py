#!/usr/bin/env python3
"""
Generate docs/oem-coverage.md from audit/coverage/oem-registry.json (§93).

The registry JSON is the machine source of truth; this view is generated.
"""
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.join(os.path.dirname(__file__), '..')
REGISTRY = os.path.join(REPO, 'audit', 'coverage', 'oem-registry.json')
VIEW = os.path.join(REPO, 'docs', 'oem-coverage.md')

STATUS_ICON = {
    'REACHABLE': '🟢',
    'BLOCKED_HTTP_403': '⛔',
    'BLOCKED_HTTP_404': '⛔',
    'BLOCKED_DNS': '⛔',
    'BLOCKED_TLS': '⛔',
    'BLOCKED_TIMEOUT': '⏳',
    'ERROR_PAGE': '⚠️',
    'DEALER_REDIRECT': '⚠️',
    'UNKNOWN': '❓',
}


def main():
    with open(REGISTRY) as f:
        reg = json.load(f)

    in_scope = [r for r in reg['brands'] if r['in_scope']]
    counted = [r for r in in_scope
               if r['provenance_status'] == 'ACQUISITION_VERIFIED'
               and r['adapter_status'] == 'PARSED_TESTED']
    coverage = 100.0 * len(counted) / len(in_scope) if in_scope else 0.0
    reachable = [r for r in in_scope if r['access_status'] == 'REACHABLE']
    blocked = [r for r in in_scope if r['access_status'] != 'REACHABLE']

    lines = []
    a = lines.append
    a('# OEM Coverage View')
    a('')
    a('> GENERATED from `audit/coverage/oem-registry.json` by `scripts/generate_coverage_view.py` — do not edit by hand.')
    a(f'> Generated at: {datetime.now(timezone.utc).isoformat()}')
    a('')
    a('## Coverage')
    a('')
    a('```text')
    a(f'coverage = brands(ACQUISITION_VERIFIED AND PARSED_TESTED) / in_scope')
    a(f'         = {len(counted)} / {len(in_scope)} = {coverage:.1f}%')
    a('```')
    a('')
    a(f'- Verified + parsed-tested brands: {", ".join(r["brand"] for r in counted) or "—"}')
    a(f'- Currently reachable endpoints: {len(reachable)} / {len(in_scope)}')
    a(f'- Blocked endpoints: {len(blocked)} / {len(in_scope)}')
    a(f'- Scope candidates unresolved: {len(reg.get("scope_candidates_unresolved", []))}')
    a('')
    a('> Attempt, capture and blocked counts are **operational telemetry, never market coverage** (§93).')
    a('')
    a('## Brands')
    a('')
    a('| Brand | In scope | Access | Adapter | Provenance | Last success (data) | Next retry |')
    a('|---|---|---|---|---|---|---|')
    for r in reg['brands']:
        icon = STATUS_ICON.get(r['access_status'], '❓')
        last = r.get('last_success_at') or ('UNKNOWN' if r.get('last_success_sha256') else '—')
        if last not in ('—', 'UNKNOWN') and 'T' in str(last):
            last = str(last)[:10]
        retry = (r.get('next_retry_at') or '—')[:10]
        a(f"| {r['brand']} | {'yes' if r['in_scope'] else 'no'} | {icon} `{r['access_status']}` "
          f"| {r['adapter_status']} | {r['provenance_status']} | {last} | {retry} |")
    a('')
    a('## Blocked — evidence')
    a('')
    if not blocked:
        a('_No blocked brands._')
    for r in blocked:
        ev = r.get('blocker_evidence') or {}
        a(f"- **{r['brand']}** `{r['access_status']}` — {ev.get('http_status_or_error', '?')} "
          f"at <{ev.get('url', '?')}> (checked {str(ev.get('checked_at', '?'))[:19]}Z); "
          f"retry {str(r.get('next_retry_at', '?'))[:10]}")
        for step in r.get('fallback_ladder', []):
            a(f"  - ladder: {step.get('result')} — {step.get('http_status_or_error')} "
              f"at <{step.get('url')}> ({str(step.get('checked_at', '?'))[:19]})")
    a('')
    cands = reg.get('scope_candidates_unresolved', [])
    if cands:
        a('## Scope candidates — unresolved')
        a('')
        for c in cands:
            a(f"- **{c['candidate']}** — {c['reason']} (evidence: {c.get('evidence', '?')})")
        a('')
    a('## Captured artifacts (brand → endpoints)')
    a('')
    for r in reg['brands']:
        caps = r.get('captured_endpoints') or []
        if not caps:
            continue
        a(f"- **{r['brand']}**")
        for c in caps:
            a(f"  - `{c['artifact']}` ← {c['url']} · {c['provenance_state']}"
              f"{' · parsed' if c.get('parsed') else ' · unparsed'} · {str(c.get('sha256', ''))[:12]}")
    a('')

    os.makedirs(os.path.dirname(VIEW), exist_ok=True)
    with open(VIEW, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Wrote {VIEW} ({len(lines)} lines) — coverage {len(counted)}/{len(in_scope)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
