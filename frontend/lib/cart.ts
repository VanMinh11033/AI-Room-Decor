"use client";

import { apiFetch, getAccessToken } from "./api";
import type { Cart } from "@/types/api";

export async function addToCart(productId: number, quantity = 1): Promise<Cart> {
  if (!getAccessToken()) {
    window.location.href = "/login";
    throw new Error("Vui lòng đăng nhập để thêm vào giỏ hàng.");
  }
  return apiFetch<Cart>("/api/cart/items", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, quantity }),
  });
}
