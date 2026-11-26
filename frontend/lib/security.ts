/**
 * Security and Navigation Utilities
 * AI Room Decor - Luxury V3
 */

/**
 * Validates that a URL is a safe internal application path to prevent Open Redirect (CWE-601).
 * 
 * Rules:
 * - Must be a string
 * - Must start with a single forward slash '/'
 * - Must NOT start with '//' (protocol-relative URL bypass)
 * - Must NOT start with '/\\' (Windows backslash path evasion)
 * - Must NOT contain control characters (\r, \n, \t, \0)
 * - Must resolve to the current origin when parsed against a dummy base
 */
export function isValidInternalRedirect(url: unknown): boolean {
  if (typeof url !== "string") return false;
  const trimmed = url.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//") || trimmed.startsWith("/\\")) {
    return false;
  }
  // Reject control characters that might confuse URL parsers
  if (/[\r\n\t\0]/.test(trimmed)) {
    return false;
  }
  try {
    const parsed = new URL(trimmed, "http://localhost");
    if (parsed.origin !== "http://localhost") {
      return false;
    }
    return parsed.pathname.startsWith("/") && !parsed.pathname.startsWith("//");
  } catch {
    return false;
  }
}

/**
 * Returns a sanitized redirect destination, falling back to a safe default.
 */
export function sanitizeRedirect(url: unknown, fallback = "/room-projects"): string {
  if (isValidInternalRedirect(url)) {
    return (url as string).trim();
  }
  return fallback;
}
