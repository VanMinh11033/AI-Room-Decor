"use client";

import { useEffect, useState } from "react";
import { apiFetch, clearTokens } from "@/lib/api";
import type { User } from "@/types/api";

export function useAuth(requiredRole?: "ADMIN" | "CUSTOMER") {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<User>("/api/auth/me")
      .then((me) => {
        if (requiredRole && me.role.name !== requiredRole) {
          window.location.href = "/";
          return;
        }
        setUser(me);
      })
      .catch(() => {
        clearTokens();
        window.location.href = "/login";
      })
      .finally(() => setLoading(false));
  }, [requiredRole]);

  return { user, loading };
}

