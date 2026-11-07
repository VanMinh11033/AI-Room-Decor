"use client";

import Link from "next/link";
import { PackageOpen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { Order, OrderListResponse } from "@/types/api";

export default function OrdersPage() {
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<OrderListResponse>("/api/orders");
      setOrders(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được đơn hàng.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải đơn hàng...</p>;

  return (
    <section className="space-y-7">
      <PageHeader eyebrow="Lịch sử mua hàng" title="Đơn hàng của tôi" description="Theo dõi trạng thái và chi tiết các đơn hàng decor của bạn." />

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{error}</div>}

      {orders.length === 0 && !error ? (
        <SectionCard className="py-16 text-center">
          <PackageOpen size={40} className="mx-auto text-charcoal/30" />
          <p className="mt-4 text-lg font-black text-ink">Chưa có đơn hàng nào</p>
          <Link href="/products" className="primary-cta mt-6">Bắt đầu mua sắm</Link>
        </SectionCard>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <Link key={order.id} href={`/orders/${order.id}`} className="surface-card flex flex-col gap-3 p-5 transition hover:-translate-y-0.5 hover:shadow-soft sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-black text-ink">Đơn hàng #{order.id}</p>
                <p className="mt-1 text-sm text-charcoal/55">{new Date(order.created_at).toLocaleString("vi-VN")}</p>
                <p className="mt-1 text-sm text-charcoal/55">{order.items.length} sản phẩm</p>
              </div>
              <div className="flex items-center gap-4 sm:flex-col sm:items-end">
                <span className="rounded-full bg-ivory px-3 py-1 text-sm font-black text-clay">{displayStatus(order.status)}</span>
                <span className="text-xl font-black text-clay">{Number(order.total_amount).toLocaleString("vi-VN")} đ</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
