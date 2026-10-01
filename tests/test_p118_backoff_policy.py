"""
P118-G — Blueprint §94 retry/backoff policy as pure, testable functions.

Red-before: written against 76a242a (+plan commit) where
lib/thai_factory/acquisition/backoff.py does not exist (reproduced gap G-B:
grep BLOCKED_TLS|backoff over lib/ → zero hits; ladder.py is adapter fallback
only). Each test loads the module dynamically so the failure is per-test.
"""
import importlib
from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 9, 29, 6, 0, 0, tzinfo=timezone.utc)


def load_backoff():
    try:
        return importlib.import_module("thai_factory.acquisition.backoff")
    except Exception:
        return None


def _mod():
    m = load_backoff()
    assert m is not None, "lib/thai_factory/acquisition/backoff.py must exist (§94 policy)"
    return m


def test_outcome_classification_matches_policy_table():
    m = _mod()
    cases = {
        "HTTP_403": "BLOCKED_HTTP_403",
        "HTTP_404": "BLOCKED_HTTP_404",
        "DNS_FAILURE": "BLOCKED_DNS",
        "TLS_ERROR": "BLOCKED_TLS",
        "TIMEOUT": "BLOCKED_TIMEOUT",
        "HTTP_500": "TRANSIENT_5XX",
        "HTTP_503": "TRANSIENT_5XX",
        "ERROR_PAGE": "ERROR_PAGE",
        "DEALER_REDIRECT": "DEALER_REDIRECT",
        "HTTP_200": "OK",
    }
    for raw, expected in cases.items():
        assert m.classify_outcome(raw) == expected, f"{raw} → {m.classify_outcome(raw)}"


def test_tls_retry_is_monthly_and_never_disables_certificate_verification():
    m = _mod()
    nxt, state, actions = m.next_retry("BLOCKED_TLS", attempt=1, now=NOW)
    assert state == "RETRY_MONTHLY"
    assert nxt == NOW + timedelta(days=30)
    assert actions.get("disable_cert_verification") is False, "TLS must NEVER disable certificate verification"
    # repeated TLS stays monthly forever
    nxt2, state2, _ = m.next_retry("BLOCKED_TLS", attempt=12, now=NOW)
    assert state2 == "RETRY_MONTHLY" and nxt2 == NOW + timedelta(days=30)


def test_403_is_plus_7d_then_monthly_and_never_rotates_ua_or_bypasses():
    m = _mod()
    nxt1, state1, actions1 = m.next_retry("BLOCKED_HTTP_403", attempt=1, now=NOW)
    assert state1 == "RETRY_7D" and nxt1 == NOW + timedelta(days=7)
    nxt2, state2, actions2 = m.next_retry("BLOCKED_HTTP_403", attempt=2, now=NOW)
    assert state2 == "RETRY_MONTHLY" and nxt2 == NOW + timedelta(days=30)
    for actions in (actions1, actions2):
        assert actions.get("rotate_ua") is False, "403 must never rotate the User-Agent"
        assert actions.get("bypass") is False, "403 must never bypass/bot-mask"


def test_404_is_14d_with_at_most_2_alternates_per_cycle():
    m = _mod()
    nxt, state, actions = m.next_retry("BLOCKED_HTTP_404", attempt=1, now=NOW)
    assert state == "RETRY_14D" and nxt == NOW + timedelta(days=14)
    assert actions.get("max_alternates_per_cycle") == 2
    # alternates never grow with attempts inside a cycle
    _, _, actions2 = m.next_retry("BLOCKED_HTTP_404", attempt=2, now=NOW)
    assert actions2.get("max_alternates_per_cycle") == 2


def test_dns_is_weekly_x4_then_monthly():
    m = _mod()
    for attempt in (1, 2, 3, 4):
        nxt, state, _ = m.next_retry("BLOCKED_DNS", attempt=attempt, now=NOW)
        assert state == "RETRY_WEEKLY" and nxt == NOW + timedelta(days=7), attempt
    nxt, state, _ = m.next_retry("BLOCKED_DNS", attempt=5, now=NOW)
    assert state == "RETRY_MONTHLY" and nxt == NOW + timedelta(days=30)


def test_timeout_backoff_30s_120s_then_cycle_blocked():
    m = _mod()
    assert m.timeout_backoff_delays() == [30.0, 120.0]
    _, state, _ = m.next_retry("BLOCKED_TIMEOUT", attempt=1, now=NOW)
    assert state in ("RETRY_BACKOFF_30S", "RETRY_NEXT_RUN")
    _, state2, _ = m.next_retry("BLOCKED_TIMEOUT", attempt=3, now=NOW)
    assert state2 == "CYCLE_BLOCKED"
    # cycle-blocked exposes no automatic retry time (wait for next cycle)
    nxt, state3, _ = m.next_retry("BLOCKED_TIMEOUT", attempt=4, now=NOW)
    assert state3 == "CYCLE_BLOCKED" and nxt is None


def test_5xx_same_run_retry_30s_120s_then_retry_next_run():
    m = _mod()
    assert m.transient_retry_delays() == [30.0, 120.0]
    _, state, _ = m.next_retry("TRANSIENT_5XX", attempt=1, now=NOW)
    assert state in ("RETRY_30S", "RETRY_120S", "RETRY_NEXT_RUN")
    _, state2, _ = m.next_retry("TRANSIENT_5XX", attempt=3, now=NOW)
    assert state2 == "RETRY_NEXT_RUN"


def test_error_page_and_dealer_redirect_store_blocker_extract_nothing():
    m = _mod()
    for outcome in ("ERROR_PAGE", "DEALER_REDIRECT"):
        _, state, actions = m.next_retry(outcome, attempt=1, now=NOW)
        assert actions.get("extract") is False, f"{outcome} must extract nothing"
        assert state == "URL_TARGET_ISSUE"


def test_per_host_politeness_is_at_least_5_seconds():
    m = _mod()
    # same host, request 200ms ago → the NEXT request must land ≥5s after the
    # last one, so the returned wait must satisfy elapsed + wait ≥ 5000ms
    last = (NOW.timestamp() - 0.2) * 1000
    delay_ms = m.politeness_delay_ms("example.co.th", last_ms=last, now_ms=NOW.timestamp() * 1000)
    assert 200 + delay_ms >= 5000, f"gap {200 + delay_ms}ms < 5000ms (wait={delay_ms})"
    # cold host → no forced wait beyond the floor
    cold = m.politeness_delay_ms("example.co.th", last_ms=0, now_ms=NOW.timestamp() * 1000)
    assert cold >= 0
