"use client";

const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const API_URL = rawApiUrl;

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

export function setTokens(accessToken: string, refreshToken: string) {
  window.localStorage.setItem("access_token", accessToken);
  window.localStorage.setItem("refresh_token", refreshToken);
}

export function clearTokens() {
  window.localStorage.removeItem("access_token");
  window.localStorage.removeItem("refresh_token");
}

export function apiAssetUrl(path?: string | null) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_URL}${normalizedPath}`;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  let response: Response;
  try {
    response = await fetch(`${API_URL}${normalizedPath}`, { ...options, headers });
  } catch {
    throw new Error("Không thể kết nối đến máy chủ.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(mapApiError(typeof body.detail === "string" ? body.detail : "Request failed"));
  }
  return response.json();
}

function mapApiError(detail: string) {
  if (detail === "Email already registered") return "Email này đã được đăng ký.";
  if (detail === "Invalid credentials" || detail === "Invalid email or password") return "Email hoặc mật khẩu không đúng.";
  if (detail === "Inactive user" || detail === "User is inactive") return "Tài khoản đã bị khóa.";
  if (detail === "Request failed") return "Yêu cầu không thành công. Vui lòng thử lại.";
  return detail;
}
