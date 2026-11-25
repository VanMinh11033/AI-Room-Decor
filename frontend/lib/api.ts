"use client";

import type { User } from "@/types/api";

const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const API_URL = rawApiUrl;

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  try {
    const urlToken = new URLSearchParams(window.location.search).get("token");
    if (urlToken) {
      window.localStorage.setItem("access_token", urlToken);
      return urlToken;
    }
  } catch {
    // ignore
  }
  return window.localStorage.getItem("access_token");
}

// In-memory cache for the current authenticated user, strictly tied to the active access token
let cachedToken: string | null = null;
let cachedUser: User | null = null;
let cachedUserTimestamp = 0;
let inFlightAuthPromise: Promise<User> | null = null;
let inFlightToken: string | null = null;

export function setTokens(accessToken: string, refreshToken: string) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("access_token", accessToken);
    window.localStorage.setItem("refresh_token", refreshToken);
  }
  // Invalidate any existing auth cache so the new user session is fetched fresh
  cachedToken = null;
  cachedUser = null;
  cachedUserTimestamp = 0;
  inFlightAuthPromise = null;
  inFlightToken = null;
}

export function clearTokens() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("refresh_token");
  }
  cachedToken = null;
  cachedUser = null;
  cachedUserTimestamp = 0;
  inFlightAuthPromise = null;
  inFlightToken = null;
}

export function apiAssetUrl(path?: string | null, options?: { width?: number }) {
  if (!path) return "";
  if (path.includes("res.cloudinary.com") && path.includes("/upload/")) {
    const width = options?.width || 600;
    // Don't duplicate transformations if format, width or quality are already specified
    if (!path.includes("f_auto") && !path.includes("w_") && !path.includes("q_")) {
      return path.replace("/upload/", `/upload/f_auto,q_auto,w_${width}/`);
    }
    return path;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_URL}${normalizedPath}`;
}

export interface ApiFetchOptions extends RequestInit {
  timeoutMs?: number;
  retries?: number;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const isOrderCreation = method === "POST" && path.includes("/api/orders");
  const isSafeRead = method === "GET";

  // First attempt timeout: 32s (matches Render Free boot); retry timeout: 15s; order creation: 45s
  const defaultTimeout = isOrderCreation ? 45000 : 32000;
  const timeoutMs = options.timeoutMs ?? defaultTimeout;

  // Safe read requests allow 1 bounded retry; non-idempotent operations strictly enforce 0 retries
  const maxRetries = isSafeRead ? (options.retries ?? 1) : 0;
  const callerSignal = options.signal;

  const fetchOptions: RequestInit = { ...options };
  delete (fetchOptions as ApiFetchOptions).timeoutMs;
  delete (fetchOptions as ApiFetchOptions).retries;

  const headers = new Headers(fetchOptions.headers);
  if (!(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  let attempt = 0;
  while (attempt <= maxRetries) {
    attempt++;
    const currentTimeoutMs = attempt === 1 ? timeoutMs : 15000;
    const timeoutController = new AbortController();
    const timeoutId = setTimeout(() => timeoutController.abort(), currentTimeoutMs);

    let combinedSignal = timeoutController.signal;
    let cleanupListeners: (() => void) | null = null;

    if (callerSignal) {
      if (callerSignal.aborted) {
        clearTimeout(timeoutId);
        throw new Error("AbortError");
      }
      const combinedController = new AbortController();
      const onCallerAbort = () => combinedController.abort();
      const onTimeoutAbort = () => combinedController.abort();
      callerSignal.addEventListener("abort", onCallerAbort, { once: true });
      timeoutController.signal.addEventListener("abort", onTimeoutAbort, { once: true });
      cleanupListeners = () => {
        callerSignal.removeEventListener("abort", onCallerAbort);
        timeoutController.signal.removeEventListener("abort", onTimeoutAbort);
      };
      combinedSignal = combinedController.signal;
    }

    try {
      const response = await fetch(`${API_URL}${normalizedPath}`, {
        ...fetchOptions,
        headers,
        signal: combinedSignal,
      });
      clearTimeout(timeoutId);
      if (cleanupListeners) cleanupListeners();

      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(mapApiError(typeof body.detail === "string" ? body.detail : "Request failed"));
      }
      return await response.json();
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      if (cleanupListeners) cleanupListeners();

      // 1. INTENTIONAL CALLER CANCELLATION (filter change, unmount, navigation):
      if (callerSignal?.aborted) {
        // Never retry intentional cancellations! Rethrow immediately.
        throw err;
      }

      const isTimeout = timeoutController.signal.aborted;
      const isNetwork = err instanceof Error && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError"));

      // 2. Only safe reads (GET) with retry budget can retry upon internal timeout or network error:
      if (isSafeRead && attempt <= maxRetries && (isTimeout || isNetwork)) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        continue;
      }

      if (isTimeout) {
        if (isOrderCreation) {
          throw new Error(
            "Yêu cầu tạo đơn hàng quá thời gian phản hồi. Đơn hàng có thể đang được hệ thống xử lý. Vui lòng kiểm tra trang 'Đơn hàng' trước khi thử lại để tránh đặt trùng lặp."
          );
        }
        throw new Error("Máy chủ phản hồi chậm hoặc đang khởi động. Vui lòng thử lại sau giây lát.");
      }

      if (err instanceof Error && err.message && err.message !== "Failed to fetch") {
        throw err;
      }
      throw new Error("Không thể kết nối đến máy chủ.");
    }
  }

  throw new Error("Không thể kết nối đến máy chủ.");
}

/**
 * Deduplicated & cached auth fetch for /api/auth/me
 * Strictly tied to the active access token to prevent session leakages or stale promise resurrection.
 */
export async function getAuthMe(options?: { forceRefresh?: boolean }): Promise<User> {
  const currentToken = getAccessToken();
  if (!currentToken) {
    cachedUser = null;
    cachedToken = null;
    cachedUserTimestamp = 0;
    inFlightAuthPromise = null;
    inFlightToken = null;
    throw new Error("Không có phiên đăng nhập.");
  }

  const now = Date.now();
  if (
    !options?.forceRefresh &&
    cachedUser &&
    cachedToken === currentToken &&
    now - cachedUserTimestamp < 30000
  ) {
    return cachedUser;
  }

  if (!options?.forceRefresh && inFlightAuthPromise && inFlightToken === currentToken) {
    return inFlightAuthPromise;
  }

  inFlightToken = currentToken;
  inFlightAuthPromise = apiFetch<User>("/api/auth/me", { timeoutMs: 32000, retries: 1 })
    .then((user) => {
      // CRITICAL: Only cache if the active token STILL matches the token when this request started!
      if (getAccessToken() === currentToken) {
        cachedUser = user;
        cachedToken = currentToken;
        cachedUserTimestamp = Date.now();
      }
      return user;
    })
    .catch((err) => {
      if (getAccessToken() === currentToken) {
        cachedUser = null;
        cachedToken = null;
        cachedUserTimestamp = 0;
      }
      throw err;
    })
    .finally(() => {
      if (inFlightToken === currentToken) {
        inFlightAuthPromise = null;
        inFlightToken = null;
      }
    });

  return inFlightAuthPromise;
}

/**
 * In-memory client cache for lookup tables and public catalog
 */
const lookupCache = new Map<string, { data: unknown; timestamp: number }>();
const inFlightLookups = new Map<string, Promise<unknown>>();

export async function cachedApiFetch<T>(path: string, ttlMs = 5 * 60 * 1000): Promise<T> {
  const cached = lookupCache.get(path);
  if (cached && Date.now() - cached.timestamp < ttlMs) {
    return cached.data as T;
  }

  const inFlight = inFlightLookups.get(path);
  if (inFlight) {
    return inFlight as Promise<T>;
  }

  const promise = apiFetch<T>(path, { timeoutMs: 32000, retries: 1 })
    .then((data) => {
      lookupCache.set(path, { data, timestamp: Date.now() });
      return data;
    })
    .finally(() => {
      inFlightLookups.delete(path);
    });

  inFlightLookups.set(path, promise);
  return promise;
}

function mapApiError(detail: string) {
  if (detail === "Email already registered") return "Email này đã được đăng ký.";
  if (detail === "Invalid credentials" || detail === "Invalid email or password") return "Email hoặc mật khẩu không đúng.";
  if (detail === "Inactive user" || detail === "User is inactive") return "Tài khoản đã bị khóa.";
  if (detail === "Request failed") return "Yêu cầu không thành công. Vui lòng thử lại.";
  return detail;
}
