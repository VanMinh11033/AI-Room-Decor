/**
 * AI Room Studio Preselected Product State Helper
 * AI Room Decor - Luxury V3
 */

export interface PreselectedProduct {
  id: number;
  name: string;
  image_url?: string;
  timestamp: number;
}

const PRESELECTED_PRODUCT_KEY = "ai_decor_preselected_product";

export function setPreselectedProduct(product: { id: number; name: string; image_url?: string }): void {
  if (typeof window === "undefined") return;
  try {
    const payload: PreselectedProduct = {
      id: product.id,
      name: product.name,
      image_url: product.image_url,
      timestamp: Date.now(),
    };
    sessionStorage.setItem(PRESELECTED_PRODUCT_KEY, JSON.stringify(payload));
  } catch {
    // sessionStorage quota or restriction
  }
}

export function getPreselectedProduct(): PreselectedProduct | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PRESELECTED_PRODUCT_KEY);
    if (!raw) return null;
    const data: PreselectedProduct = JSON.parse(raw);
    const ONE_HOUR_MS = 60 * 60 * 1000;
    if (Date.now() - data.timestamp > ONE_HOUR_MS) {
      clearPreselectedProduct();
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

export function clearPreselectedProduct(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(PRESELECTED_PRODUCT_KEY);
  } catch {
    // ignore
  }
}
