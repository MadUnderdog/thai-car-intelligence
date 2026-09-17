import { validateUrl, type UrlPolicyOptions } from "./url-policy";

export interface SafeFetchOptions extends UrlPolicyOptions {
  /** Injected fetch implementation for deterministic tests. */
  fetch?: typeof fetch;
  maxRedirects?: number;
  timeoutMs?: number;
  maxResponseBytes?: number;
}

const DEFAULT_MAX_REDIRECTS = 3;
const DEFAULT_TIMEOUT_MS = 10_000;
const DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024;

function isRedirect(status: number): boolean {
  return status >= 300 && status < 400 && status !== 304;
}

async function readBoundedResponse(response: Response, maxBytes: number): Promise<Response> {
  const contentLength = response.headers.get("content-length");
  if (contentLength !== null && /^\d+$/.test(contentLength) && Number(contentLength) > maxBytes) {
    throw new Error("Response size exceeds the configured response size limit.");
  }
  if (!response.body) return response;

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      const chunk = new Uint8Array(result.value);
      total += chunk.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        throw new Error("Response size exceeds the configured response size limit.");
      }
      chunks.push(chunk);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

/** Fetch an HTTP resource while enforcing URL policy across every redirect. */
export async function safeFetch(
  input: string | URL,
  init: RequestInit = {},
  options: SafeFetchOptions = {},
): Promise<Response> {
  const fetchImpl = options.fetch ?? globalThis.fetch;
  const maxRedirects = options.maxRedirects ?? DEFAULT_MAX_REDIRECTS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const maxResponseBytes = options.maxResponseBytes ?? DEFAULT_MAX_RESPONSE_BYTES;
  if (!Number.isInteger(maxRedirects) || maxRedirects < 0) throw new Error("Invalid redirect limit.");
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error("Invalid timeout.");
  if (!Number.isInteger(maxResponseBytes) || maxResponseBytes <= 0) throw new Error("Invalid response size limit.");

  let current = typeof input === "string" ? input : input.toString();
  for (let redirects = 0; ; redirects += 1) {
    const validation = await validateUrl(current, options);
    if (!validation.ok) throw new Error(validation.message);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const abortCaller = (): void => controller.abort();
    if (init.signal) init.signal.addEventListener("abort", abortCaller, { once: true });
    try {
      const response = await fetchImpl(current, { ...init, redirect: "manual", signal: controller.signal });
      if (!isRedirect(response.status)) return await readBoundedResponse(response, maxResponseBytes);
      if (redirects >= maxRedirects) throw new Error("Maximum redirect limit exceeded.");
      const location = response.headers.get("location");
      if (!location) throw new Error("Redirect response has no Location header.");
      current = new URL(location, validation.url).toString();
    } finally {
      clearTimeout(timer);
      if (init.signal) init.signal.removeEventListener("abort", abortCaller);
    }
  }
}
