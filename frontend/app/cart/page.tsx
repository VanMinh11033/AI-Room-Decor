"use client";

import Link from "next/link";
import { Minus, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { EmptyImagePlaceholder, PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Cart } from "@/types/api";

export default function CartPage() {
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setCart(await apiFetch<Cart>("/api/cart"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được giỏ hàng.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  async function updateQuantity(itemId: number, quantity: number) {
    setBusy(itemId);
    setError("");
    try {
      setCart(await apiFetch<Cart>(`/api/cart/items/${itemId}`, { method: "PATCH", body: JSON.stringify({ quantity }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được số lượng.");
    } finally {
      setBusy(null);
    }
  }

  async function removeItem(itemId: number) {
    setBusy(itemId);
    setError("");
    try {
      setCart(await apiFetch<Cart>(`/api/cart/items/${itemId}`, { method: "DELETE" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xóa được sản phẩm.");
    } finally {
      setBusy(null);
    }
  }

  async function clearCart() {
    if (!window.confirm("Bạn muốn xóa toàn bộ giỏ hàng?")) return;
    setError("");
    try {
      setCart(await apiFetch<Cart>("/api/cart", { method: "DELETE" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xóa được giỏ hàng.");
    }
  }

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải giỏ hàng...</p>;

  const items = cart?.items || [];

  return (
    <section className="space-y-7">
      <PageHeader eyebrow="Giỏ hàng" title="Giỏ hàng của bạn" description="Kiểm tra số lượng và tiến hành thanh toán các sản phẩm decor đã chọn." />

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{error}</div>}

      {items.length === 0 ? (
        <SectionCard className="py-16 text-center">
          <ShoppingCart size={40} className="mx-auto text-charcoal/30" />
          <p className="mt-4 text-lg font-black text-ink">Giỏ hàng trống</p>
          <p className="mt-2 text-sm text-charcoal/60">Khám phá sản phẩm decor và thêm vào giỏ để bắt đầu.</p>
          <Link href="/products" className="primary-cta mt-6">Xem sản phẩm</Link>
        </SectionCard>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
          <div className="space-y-4">
            {items.map((item) => {
              const product = item.product;
              const image = product?.images.find((img) => img.is_primary)?.image_url || product?.images[0]?.image_url;
              return (
                <article key={item.id} className="surface-card flex gap-4 p-4">
                  <Link href={product ? `/products/${product.id}` : "#"} className="h-24 w-24 shrink-0 overflow-hidden rounded-xl bg-ivory">
                    {image ? (
                      <img src={apiAssetUrl(image)} alt={product?.name} className="h-full w-full object-cover" />
                    ) : (
                      <EmptyImagePlaceholder />
                    )}
                  </Link>
                  <div className="flex min-w-0 flex-1 flex-col justify-between">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Link href={product ? `/products/${product.id}` : "#"} className="block truncate font-black text-ink hover:underline">
                          {product?.name || "Sản phẩm"}
                        </Link>
                        <p className="mt-1 text-sm text-charcoal/55">{Number(item.unit_price).toLocaleString("vi-VN")} đ</p>
                      </div>
                      <button type="button" onClick={() => removeItem(item.id)} disabled={busy === item.id} className="text-red-500 hover:text-red-700" aria-label="Xóa sản phẩm">
                        <Trash2 size={18} />
                      </button>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3">
                      <div className="inline-flex items-center gap-1 rounded-xl border border-ink/10 bg-ivory">
                        <button type="button" onClick={() => updateQuantity(item.id, Math.max(1, item.quantity - 1))} disabled={busy === item.id || item.quantity <= 1} className="px-3 py-2 text-charcoal/60 hover:text-ink" aria-label="Giảm số lượng">
                          <Minus size={15} />
                        </button>
                        <span className="min-w-8 text-center text-sm font-black text-ink">{item.quantity}</span>
                        <button type="button" onClick={() => updateQuantity(item.id, item.quantity + 1)} disabled={busy === item.id} className="px-3 py-2 text-charcoal/60 hover:text-ink" aria-label="Tăng số lượng">
                          <Plus size={15} />
                        </button>
                      </div>
                      <p className="text-lg font-black text-clay">{Number(item.subtotal).toLocaleString("vi-VN")} đ</p>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          <aside className="surface-card h-fit p-6">
            <h2 className="text-xl font-black text-ink">Tổng giỏ hàng</h2>
            <dl className="mt-5 space-y-3 text-sm">
              <div className="flex justify-between"><dt className="text-charcoal/60">Số lượng sản phẩm</dt><dd className="font-bold text-ink">{cart?.total_items ?? 0}</dd></div>
              <div className="flex justify-between"><dt className="text-charcoal/60">Tạm tính</dt><dd className="font-bold text-ink">{Number(cart?.subtotal ?? 0).toLocaleString("vi-VN")} đ</dd></div>
            </dl>
            <Link href="/checkout" className="primary-cta mt-6 w-full">Tiến hành thanh toán</Link>
            <button type="button" onClick={clearCart} className="secondary-cta mt-3 w-full text-red-600">Xóa giỏ hàng</button>
          </aside>
        </div>
      )}
    </section>
  );
}
