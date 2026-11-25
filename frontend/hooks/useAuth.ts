"use client";

import { useEffect, useState } from "react";
import { clearTokens, getAccessToken, getAuthMe } from "@/lib/api";
import type { User } from "@/types/api";

export function useAuth(requiredRole?: "ADMIN" | "CUSTOMER") {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      if (requiredRole) {
        clearTokens();
        const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
        const loginUrl =
          currentPath && currentPath !== "/" && currentPath !== "/login"
            ? `/login?redirect=${encodeURIComponent(currentPath)}`
            : "/login";
        window.location.href = loginUrl;
      } else {
        setUser(null);
        setLoading(false);
      }
      return;
    }

    getAuthMe()
      .then((me) => {
        // ADMIN can access all areas. Only non-ADMIN is restricted from ADMIN pages.
        if (requiredRole === "ADMIN" && me.role?.name !== "ADMIN") {
          window.location.href = "/";
          return;
        }
        setUser(me);
      })
      .catch(() => {
        clearTokens();
        const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
        const loginUrl =
          currentPath && currentPath !== "/" && currentPath !== "/login"
            ? `/login?redirect=${encodeURIComponent(currentPath)}`
            : "/login";
        window.location.href = loginUrl;
      })
      .finally(() => setLoading(false));
  }, [requiredRole]);

  return { user, loading };
}
