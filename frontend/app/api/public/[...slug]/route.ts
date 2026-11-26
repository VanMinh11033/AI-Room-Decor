import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Allowed public read-only roots
const ALLOWED_ROOT_SLUGS = new Set([
  "products",
  "categories",
  "materials",
  "styles",
  "room-types",
  "colors",
]);

// Resilient in-memory fallback cache (best-effort intra-instance in serverless)
interface FallbackCacheEntry {
  data: unknown;
  status: number;
  timestamp: number;
  rootSlug: string;
}

const fallbackCache = new Map<string, FallbackCacheEntry>();
const MAX_FALLBACK_CACHE_ENTRIES = 200;

// Maximum stale TTL for fallback:
// Products: 30 minutes (catalog changes are infrequent, but prices/status need bounded lifetime)
// Taxonomies: 2 hours (rarely change)
const MAX_PRODUCTS_STALE_TTL_MS = 30 * 60 * 1000;
const MAX_TAXONOMY_STALE_TTL_MS = 2 * 60 * 60 * 1000;

function getBackendBaseUrl(): string {
  const url = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "https://ai-room-decor.onrender.com";
  return url.replace(/\/+$/, "");
}

// Parameter whitelist & sanitization to prevent cache key explosion, origin overload, and parameter pollution
function sanitizeAndNormalizeQuery(rootSlug: string, searchParams: URLSearchParams): { canonicalQuery: string; backendQuery: string } {
  const normalizedParams = new URLSearchParams();

  if (rootSlug === "products") {
    // 1. page: integer, 1 <= page <= 1000
    const rawPage = searchParams.get("page");
    if (rawPage && /^\d+$/.test(rawPage)) {
      const page = Math.min(Math.max(parseInt(rawPage, 10), 1), 1000);
      normalizedParams.set("page", String(page));
    }

    // 2. page_size: integer, 1 <= page_size <= 100
    const rawPageSize = searchParams.get("page_size");
    if (rawPageSize && /^\d+$/.test(rawPageSize)) {
      const pageSize = Math.min(Math.max(parseInt(rawPageSize, 10), 1), 100);
      normalizedParams.set("page_size", String(pageSize));
    }

    // 3. search: string, max 100 chars, trimmed
    const rawSearch = searchParams.get("search");
    if (rawSearch) {
      const cleanSearch = rawSearch.trim().slice(0, 100);
      if (cleanSearch) normalizedParams.set("search", cleanSearch);
    }

    // 4. category_id: positive integer
    const rawCat = searchParams.get("category_id");
    if (rawCat && /^\d+$/.test(rawCat)) {
      normalizedParams.set("category_id", rawCat);
    }

    // 5. material, style, room_type, color: slug format, max 50 chars
    const slugRegex = /^[a-zA-Z0-9_-]{1,50}$/;
    for (const key of ["material", "style", "room_type", "color"] as const) {
      const val = searchParams.get(key);
      if (val && slugRegex.test(val)) {
        normalizedParams.set(key, val);
      }
    }

    // 6. min_price & max_price: numeric, 0 <= price <= 1,000,000,000
    const rawMin = searchParams.get("min_price");
    if (rawMin && /^\d+(\.\d+)?$/.test(rawMin)) {
      const price = Math.min(Math.max(parseFloat(rawMin), 0), 1_000_000_000);
      normalizedParams.set("min_price", String(price));
    }
    const rawMax = searchParams.get("max_price");
    if (rawMax && /^\d+(\.\d+)?$/.test(rawMax)) {
      const price = Math.min(Math.max(parseFloat(rawMax), 0), 1_000_000_000);
      normalizedParams.set("max_price", String(price));
    }

    // 7. sort: restricted enum
    const rawSort = searchParams.get("sort");
    if (rawSort && ["newest", "price_asc", "price_desc", "name_asc"].includes(rawSort)) {
      normalizedParams.set("sort", rawSort);
    }
  } else {
    // Taxonomies only accept bounded page & page_size
    const rawPage = searchParams.get("page");
    if (rawPage && /^\d+$/.test(rawPage)) {
      const page = Math.min(Math.max(parseInt(rawPage, 10), 1), 1000);
      normalizedParams.set("page", String(page));
    }
    const rawPageSize = searchParams.get("page_size");
    if (rawPageSize && /^\d+$/.test(rawPageSize)) {
      const pageSize = Math.min(Math.max(parseInt(rawPageSize, 10), 1), 100);
      normalizedParams.set("page_size", String(pageSize));
    }
  }

  // Sort keys alphabetically for canonical cache key stability
  normalizedParams.sort();
  const canonicalQuery = normalizedParams.toString();
  return {
    canonicalQuery,
    backendQuery: canonicalQuery ? `?${canonicalQuery}` : "",
  };
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  // Method security: Only GET / HEAD are permitted
  if (request.method !== "GET" && request.method !== "HEAD") {
    return NextResponse.json({ detail: "Method not allowed" }, { status: 405 });
  }

  const resolvedParams = await params;
  const slugArray = resolvedParams.slug || [];

  // Path validation: Length must be 1 or 2
  if (slugArray.length === 0 || slugArray.length > 2) {
    return NextResponse.json({ detail: "Invalid public path" }, { status: 400 });
  }

  const rootSlug = slugArray[0];
  if (!ALLOWED_ROOT_SLUGS.has(rootSlug)) {
    return NextResponse.json({ detail: "Endpoint is not accessible publicly" }, { status: 403 });
  }

  // If sub-id is provided (e.g. /products/1), validate identifier format
  if (slugArray.length === 2) {
    const subIdentifier = slugArray[1];
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(subIdentifier) || subIdentifier.includes("..")) {
      return NextResponse.json({ detail: "Invalid resource identifier" }, { status: 400 });
    }
  }

  const subPath = slugArray.join("/");
  const { canonicalQuery, backendQuery } = sanitizeAndNormalizeQuery(rootSlug, request.nextUrl.searchParams);
  const backendUrl = `${getBackendBaseUrl()}/api/${subPath}${backendQuery}`;
  const cacheKey = canonicalQuery ? `${subPath}?${canonicalQuery}` : subPath;

  // Determine bypassCache: header or query parameter
  const bypassCache =
    request.headers.get("Cache-Control") === "no-cache" ||
    request.nextUrl.searchParams.has("bypass_cache") ||
    request.nextUrl.searchParams.has("_bypass");

  // Determine Edge Cache parameters based on resource type
  const isTaxonomy = rootSlug !== "products";
  // Taxonomies: 10 min fresh (s-maxage=600), 1 hour SWR (stale-while-revalidate=3600)
  // Products: 2 min fresh (s-maxage=120), 10 min SWR (stale-while-revalidate=600)
  const sMaxAge = isTaxonomy ? 600 : 120;
  const swr = isTaxonomy ? 3600 : 600;
  const maxFallbackTtl = isTaxonomy ? MAX_TAXONOMY_STALE_TTL_MS : MAX_PRODUCTS_STALE_TTL_MS;

  try {
    const controller = new AbortController();
    // 25s timeout for server-side proxy
    const timeoutId = setTimeout(() => controller.abort(), 25000);

    // Strips any incoming Authorization / Cookie headers to ensure complete session isolation
    const backendResponse = await fetch(backendUrl, {
      method: "GET",
      headers: {
        "Accept": "application/json",
        "User-Agent": "AI-Room-Decor-Nextjs-Edge-Proxy/1.0",
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (backendResponse.ok) {
      const data = await backendResponse.json();

      // Store in resilient fallback cache (LRU eviction if limit reached)
      if (fallbackCache.size >= MAX_FALLBACK_CACHE_ENTRIES) {
        const oldestKey = fallbackCache.keys().next().value;
        if (oldestKey) fallbackCache.delete(oldestKey);
      }
      fallbackCache.set(cacheKey, {
        data,
        status: 200,
        timestamp: Date.now(),
        rootSlug,
      });

      return new NextResponse(JSON.stringify(data), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": bypassCache ? "no-store, max-age=0" : `public, s-maxage=${sMaxAge}, stale-while-revalidate=${swr}`,
          "CDN-Cache-Control": bypassCache ? "no-store" : `public, s-maxage=${sMaxAge}, stale-while-revalidate=${swr}`,
          "Vercel-CDN-Cache-Control": bypassCache ? "no-store" : `public, s-maxage=${sMaxAge}, stale-while-revalidate=${swr}`,
          "X-Edge-Cache": bypassCache ? "BYPASS" : "MISS-POPULATED",
        },
      });
    }

    // Backend returned non-200 (e.g. 502/503/504)
    // Inspect fallback cache for valid entry within maximum stale TTL
    const fallback = fallbackCache.get(cacheKey);
    const isFallbackFreshEnough = fallback && (Date.now() - fallback.timestamp <= maxFallbackTtl);
    if (isFallbackFreshEnough && !bypassCache) {
      return new NextResponse(JSON.stringify(fallback.data), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
          "CDN-Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
          "Vercel-CDN-Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
          "X-Edge-Cache": "STALE-FALLBACK-ON-ERROR",
        },
      });
    }

    // If no fallback and backend returned error
    const errBody = await backendResponse.json().catch(() => ({ detail: "Backend error" }));
    return NextResponse.json(errBody, { status: backendResponse.status });

  } catch {
    // Network failure or timeout contacting backend
    const fallback = fallbackCache.get(cacheKey);
    const isFallbackFreshEnough = fallback && (Date.now() - fallback.timestamp <= maxFallbackTtl);
    if (isFallbackFreshEnough && !bypassCache) {
      return new NextResponse(JSON.stringify(fallback.data), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
          "CDN-Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
          "Vercel-CDN-Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
          "X-Edge-Cache": "STALE-FALLBACK-ON-TIMEOUT",
        },
      });
    }

    // Never return empty items array on error! Return honest gateway timeout
    return NextResponse.json(
      { detail: "Máy chủ phản hồi chậm hoặc đang khởi động. Vui lòng thử lại sau giây lát." },
      { status: 504 }
    );
  }
}
