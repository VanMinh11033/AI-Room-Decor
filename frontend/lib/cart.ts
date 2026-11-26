"use client";

import { apiFetch, getAccessToken } from "./api";
import { isValidInternalRedirect } from "./security";
import type { Cart } from "@/types/api";

export interface PendingCartIntent {
  product_id: number;
  quantity: number;
  timestamp: number;
}

const PENDING_CART_STORAGE_KEY = "ai_decor_pending_cart";

/**
 * Saves unauthenticated add-to-cart intent to sessionStorage.
 */
export function setPendingCartIntent(productId: number, quantity = 1): void {
  if (typeof window === "undefined") return;
  try {
    const payload: PendingCartIntent = {
      product_id: productId,
      quantity,
      timestamp: Date.now(),
    };
    sessionStorage.setItem(PENDING_CART_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // sessionStorage quota or security restriction
  }
}

/**
 * Retrieves pending cart intent if it exists and is less than 30 minutes old.
 */
export function getPendingCartIntent(): PendingCartIntent | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PENDING_CART_STORAGE_KEY);
    if (!raw) return null;
    const data: PendingCartIntent = JSON.parse(raw);
    const THIRTY_MINUTES_MS = 30 * 60 * 1000;
    if (Date.now() - data.timestamp > THIRTY_MINUTES_MS) {
      clearPendingCartIntent();
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/**
 * Clears pending cart intent once consumed to prevent duplicate additions.
 */
export function clearPendingCartIntent(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(PENDING_CART_STORAGE_KEY);
  } catch {
    // ignore
  }
}

/**
 * Adds a catalog item to the customer's cart.
 * If unauthenticated, preserves shopping intent and redirects to /login safely.
 */
export async function addToCart(productId: number, quantity = 1, returnPath?: string): Promise<Cart> {
  if (!getAccessToken()) {
    setPendingCartIntent(productId, quantity);

    let destination = `/products/${productId}`;
    if (returnPath && isValidInternalRedirect(returnPath)) {
      destination = returnPath;
    } else if (typeof window !== "undefined") {
      const current = window.location.pathname + window.location.search;
      if (isValidInternalRedirect(current)) {
        destination = current;
      }
    }

    const loginUrl = `/login?redirect=${encodeURIComponent(destination)}&pending_action=add_cart&product_id=${productId}&quantity=${quantity}`;
    if (typeof window !== "undefined") {
      window.location.href = loginUrl;
    }
    throw new Error("Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng.");
  }

  return apiFetch<Cart>("/api/cart/items", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, quantity }),
  });
}
