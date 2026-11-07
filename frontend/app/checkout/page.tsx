"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, Loader2, ShoppingBag } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Cart, Order } from "@/types/api";

export default function CheckoutPage() {
  const router = useRouter();
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [cart, setCart] = useState<Cart | null>(null);
  const [shippingAddress, setShippingAddress] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const order = await apiFetch<Order>("/api/orders", {
        method: "POST",
        body: JSON.stringify({ shipping_address: shippingAddress.trim() || null }),
      });
      router.push(`/orders/${order.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể đặt hàng. Vui lòng thử lại.");
      setSubmitting(false);
    }
  }

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải thông tin thanh toán...</p>;

  const items = cart?.items || [];

  return (
    <section className="space-y-7">
      <PageHeader eyebrow="Thanh toán" title="Xác nhận đơn hàng" description="Kiểm tra lại sản phẩm và địa chỉ giao hàng trước khi hoàn tất đặt hàng." />

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{error}</div>}

      {items.length === 0 && !error ? (
        <SectionCard className="py-16 text-center">
          <p className="text-lg font-black text-ink">Giỏ hàng trống</p>
          <Link href="/products" className="primary-cta mt-6">Xem sản phẩm</Link>
        </SectionCard>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <SectionCard title="Địa chỉ giao hàng">
            <form onSubmit={onSubmit} className="space-y-5">
              <label className="block text-sm font-bold text-ink">
                Địa chỉ nhận hàng
                <textarea value={shippingAddress} onChange={(event) => setShippingAddress(event.target.value)} rows={4} maxLength={500} className="premium-input mt-2 w-full resize-none" placeholder="Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành..." />
              </label>
              <button disabled={submitting} className="primary-cta w-full">
                {submitting ? <Loader2 size={18} className="animate-spin" /> : <ShoppingBag size={18} />}
                {submitting ? "Đang đặt hàng..." : "Xác nhận đặt hàng"}
              </button>
              <Link href="/cart" className="secondary-cta w-full">
                <ChevronLeft size={16} /> Quay lại giỏ hàng
              </Link>
            </form>
          </SectionCard>

          <SectionCard title="Tóm tắt đơn hàng">
            <div className="space-y-3">
              {items.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 flex-1 truncate text-charcoal/70">
                    {item.product?.name || "Sản phẩm"} <span className="text-charcoal/45">x{item.quantity}</span>
                  </span>
                  <span className="font-bold text-ink">{Number(item.subtotal).toLocaleString("vi-VN")} đ</span>
                </div>
              ))}
            </div>
            <div className="mt-5 flex items-center justify-between border-t border-ink/10 pt-4">
              <span className="font-black text-ink">Tổng cộng</span>
              <span className="text-2xl font-black text-clay">{Number(cart?.subtotal ?? 0).toLocaleString("vi-VN")} đ</span>
            </div>
          </SectionCard>
        </div>
      )}
    </section>
  );
}
