/**
 * Minimal in-memory sliding-window rate limiter.
 * Suitable for single-host / single-process deployments only.
 * NOT suitable for multi-instance / serverless deployments.
 */

type RateLimitEntry = { count: number; windowStart: number };

const store = new Map<string, RateLimitEntry>();

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  retryAfterMs: number;
}

/**
 * Check and increment rate limit for a given key.
 * @param key — unique identifier (e.g. IP address)
 * @param maxRequests — max requests allowed per window
 * @param windowMs — window duration in milliseconds
 */
export function checkRateLimit(
  key: string,
  maxRequests: number,
  windowMs: number,
): RateLimitResult {
  const now = Date.now();
  const entry = store.get(key);

  if (!entry || now - entry.windowStart > windowMs) {
    // New window
    store.set(key, { count: 1, windowStart: now });
    return { allowed: true, remaining: maxRequests - 1, retryAfterMs: 0 };
  }

  if (entry.count >= maxRequests) {
    const retryAfterMs = windowMs - (now - entry.windowStart);
    return { allowed: false, remaining: 0, retryAfterMs };
  }

  entry.count++;
  return { allowed: true, remaining: maxRequests - entry.count, retryAfterMs: 0 };
}

/** Expose for testing only — resets internal state. */
export function _resetRateLimitStore(): void {
  store.clear();
}
