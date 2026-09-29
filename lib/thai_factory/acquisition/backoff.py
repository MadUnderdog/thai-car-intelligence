"""
Blueprint §94 retry / backoff / source-failure policy — pure, deterministic.

Every transition returns (next_retry_at | None, retry_state, actions) where
actions carry the EXPLICIT safety flags the policy guarantees:

  - BLOCKED_HTTP_403  → never rotate the User-Agent, never bypass/bot-mask
  - BLOCKED_TLS       → never disable certificate verification
  - ERROR_PAGE / DEALER_REDIRECT → store evidence, extract nothing
  - per-host politeness gap ≥ 5 s between requests

No I/O, no clock reads (the caller injects `now`) — testable offline.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

POLITENESS_MIN_GAP_MS = 5000
DNS_WEEKLY_ATTEMPTS = 4

RETRY_DAYS = {"monthly": 30, "weekly": 7, "403_first": 7, "404": 14}


def classify_outcome(raw: str) -> str:
    """Map a fetch outcome marker to the §94 state name."""
    key = (raw or "").strip().upper()
    if key in ("HTTP_200", "OK", "SUCCESS"):
        return "OK"
    if key in ("HTTP_403", "403"):
        return "BLOCKED_HTTP_403"
    if key in ("HTTP_404", "404"):
        return "BLOCKED_HTTP_404"
    if key.startswith("DNS") or key in ("NXDOMAIN", "EAI_AGAIN"):
        return "BLOCKED_DNS"
    if key.startswith("TLS") or key in ("CERT_ERROR", "SSL_ERROR"):
        return "BLOCKED_TLS"
    if "TIMEOUT" in key or key in ("ETIMEDOUT", "TIMED_OUT"):
        return "BLOCKED_TIMEOUT"
    if key.startswith("HTTP_5") or key in ("5XX", "TRANSIENT"):
        return "TRANSIENT_5XX"
    if key == "ERROR_PAGE":
        return "ERROR_PAGE"
    if key == "DEALER_REDIRECT":
        return "DEALER_REDIRECT"
    return key


def timeout_backoff_delays() -> list:
    return [30.0, 120.0]


def transient_retry_delays() -> list:
    return [30.0, 120.0]


def next_retry(state: str, attempt: int, now: datetime) -> Tuple[Optional[datetime], str, Dict]:
    """
    §94 table. `attempt` = consecutive attempts in the current cycle (1-based).
    Returns (next_retry_at | None, retry_state, actions).
    """
    state = classify_outcome(state)

    if state == "BLOCKED_HTTP_403":
        if attempt <= 1:
            return now + timedelta(days=RETRY_DAYS["403_first"]), "RETRY_7D", {
                "rotate_ua": False, "bypass": False,
            }
        return now + timedelta(days=RETRY_DAYS["monthly"]), "RETRY_MONTHLY", {
            "rotate_ua": False, "bypass": False,
        }

    if state == "BLOCKED_HTTP_404":
        return now + timedelta(days=RETRY_DAYS["404"]), "RETRY_14D", {
            "max_alternates_per_cycle": 2,
        }

    if state == "BLOCKED_DNS":
        if attempt <= DNS_WEEKLY_ATTEMPTS:
            return now + timedelta(days=RETRY_DAYS["weekly"]), "RETRY_WEEKLY", {}
        return now + timedelta(days=RETRY_DAYS["monthly"]), "RETRY_MONTHLY", {}

    if state == "BLOCKED_TLS":
        return now + timedelta(days=RETRY_DAYS["monthly"]), "RETRY_MONTHLY", {
            "disable_cert_verification": False,
        }

    if state == "BLOCKED_TIMEOUT":
        delays = timeout_backoff_delays()
        if attempt <= len(delays):
            return now + timedelta(seconds=delays[attempt - 1]), f"RETRY_BACKOFF_{int(delays[attempt - 1])}S", {}
        return None, "CYCLE_BLOCKED", {}

    if state == "TRANSIENT_5XX":
        delays = transient_retry_delays()
        if attempt <= len(delays):
            return now + timedelta(seconds=delays[attempt - 1]), f"RETRY_{int(delays[attempt - 1])}S", {}
        return None, "RETRY_NEXT_RUN", {}

    if state in ("ERROR_PAGE", "DEALER_REDIRECT"):
        return None, "URL_TARGET_ISSUE", {"extract": False}

    # OK / unknown → no backoff scheduled
    return None, "NO_BACKOFF", {}


def politeness_delay_ms(domain: str, last_ms: Optional[float], now_ms: float) -> int:
    """
    Per-host politeness: the next request must land ≥ 5 s after the previous
    one on the same host. Returns the milliseconds the caller must wait.
    """
    if not last_ms or last_ms <= 0:
        return 0
    elapsed = now_ms - last_ms
    remaining = POLITENESS_MIN_GAP_MS - elapsed
    return int(remaining) if remaining > 0 else 0


def host_of(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")
