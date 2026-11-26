"use client";

import { useEffect, useState } from "react";
import { apiFetch, clearTokens, getAccessToken } from "@/lib/api";
import { isValidInternalRedirect } from "@/lib/security";
import type { User } from "@/types/api";

export function useAuth(requiredRole?: "ADMIN" | "CUSTOMER") {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();

    // Pre-flight check (AUD-P2-005): If no access token exists, redirect immediately.
    // Keep loading true during redirection to prevent mounting protected child effects
    // from firing secondary 401 requests before page navigation completes.
    if (!token) {
      if (typeof window !== "undefined") {
        const currentPath = window.location.pathname + window.location.search;
        const safePath = isValidInternalRedirect(currentPath) ? currentPath : "";
        const loginUrl =
          safePath && safePath !== "/" && !safePath.startsWith("/login")
            ? `/login?redirect=${encodeURIComponent(safePath)}`
            : "/login";
        window.location.href = loginUrl;
      }
      return;
    }

    apiFetch<User>("/api/auth/me")
      .then((me) => {
        // ADMIN can access all areas. Only non-ADMIN is restricted from ADMIN pages.
        if (requiredRole === "ADMIN" && me.role?.name !== "ADMIN") {
          window.location.href = "/";
          return;
        }
        setUser(me);
        setLoading(false);
      })
      .catch(() => {
        clearTokens();
        if (typeof window !== "undefined") {
          const currentPath = window.location.pathname + window.location.search;
          const safePath = isValidInternalRedirect(currentPath) ? currentPath : "";
          const loginUrl =
            safePath && safePath !== "/" && !safePath.startsWith("/login")
              ? `/login?redirect=${encodeURIComponent(safePath)}`
              : "/login";
          window.location.href = loginUrl;
        }
      });
  }, [requiredRole]);

  return { user, loading };
}
