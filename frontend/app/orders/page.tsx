"use client";

import Link from "next/link";
import {
  Loader2,
  PackageOpen,
  Truck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { Order, OrderListResponse } from "@/types/api";

type OrderFilterTab = "all" | "pending" | "shipping" | "completed" | "cancelled";

export default function OrdersPage() {
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<OrderFilterTab>("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<OrderListResponse>("/api/orders");
      setOrders(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải danh sách đơn hàng.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  const filteredOrders = useMemo(() => {
    if (activeTab === "all") return orders;
    if (activeTab === "pending") {
      return orders.filter((o) => o.status === "PENDING" || o.status === "PROCESSING");
    }
    if (activeTab === "shipping") {
      return orders.filter((o) => o.status === "CONFIRMED" || o.status === "SHIPPED");
    }
    if (activeTab === "completed") {
      return orders.filter((o) => o.status === "DELIVERED" || o.status === "COMPLETED");
    }
    if (activeTab === "cancelled") {
      return orders.filter((o) => o.status === "CANCELLED");
    }
    return orders;
  }, [orders, activeTab]);

  const counts = useMemo(() => {
    return {
      all: orders.length,
      pending: orders.filter((o) => o.status === "PENDING" || o.status === "PROCESSING").length,
      shipping: orders.filter((o) => o.status === "CONFIRMED" || o.status === "SHIPPED").length,
      completed: orders.filter((o) => o.status === "DELIVERED" || o.status === "COMPLETED").length,
      cancelled: orders.filter((o) => o.status === "CANCELLED").length,
    };
  }, [orders]);

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Loader2 size={32} className="animate-spin text-[#8A6B4E]" />
        <p className="font-serif text-sm tracking-wide text-[#5A6258]">Đang tải danh sách đơn hàng...</p>
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-5xl space-y-8 pb-16">
      <EditorialHeading
        eyebrow="Lịch sử mua sắm"
        title="Đơn hàng của tôi"
        subtitle="Theo dõi tiến độ gia công, đóng gói và lộ trình giao nhận của các kiện hàng decor."
      />

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50/90 p-4 text-sm font-semibold text-red-800 shadow-sm"
        >
          {error}
        </div>
      )}

      {/* FILTER TABS */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-[#DDD7CD] pb-2 text-sm">
        {(
          [
            { id: "all", label: "Tất cả", count: counts.all },
            { id: "pending", label: "Chờ xử lý", count: counts.pending },
            { id: "shipping", label: "Đang giao", count: counts.shipping },
            { id: "completed", label: "Hoàn tất", count: counts.completed },
            { id: "cancelled", label: "Đã hủy", count: counts.cancelled },
          ] as const
        ).map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2 text-xs font-bold transition ${
                isActive
                  ? "bg-[#242B23] text-white shadow-sm"
                  : "bg-white text-[#5A6258] hover:bg-[#FBF9F5] hover:text-[#242B23]"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                  isActive ? "bg-white/20 text-white" : "bg-[#DDD7CD]/50 text-[#5A6258]"
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {filteredOrders.length === 0 && !error ? (
        <div className="rounded-3xl border border-[#DDD7CD] bg-white p-12 text-center shadow-card">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#FBF9F5] text-[#5A6258]">
            <PackageOpen size={32} />
          </div>
          <h2 className="mt-4 font-serif text-xl font-bold text-[#242B23]">
            {orders.length === 0 ? "Chưa có đơn hàng nào" : "Không tìm thấy đơn hàng trong mục này"}
          </h2>
          <p className="mt-1 text-sm text-[#5A6258]">
            {orders.length === 0
              ? "Hãy khám phá các tác phẩm nội thất độc bản để bắt đầu làm mới không gian."
              : "Bạn có thể chọn tab 'Tất cả' để xem toàn bộ lịch sử đơn hàng của mình."}
          </p>
          <div className="mt-6">
            <Link href="/products">
              <LuxuryButton variant="primary">Khám phá sản phẩm</LuxuryButton>
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredOrders.map((order) => {
            const isBulkyPending =
              order.shipping_fee_status === "PENDING_CALCULATION" || order.shipping_fee === null;
            const isAwaitingConfirmation =
              order.shipping_fee_status === "AWAITING_CUSTOMER_CONFIRMATION";

            return (
              <div
                key={order.id}
                className="group rounded-3xl border border-[#DDD7CD] bg-white p-5 sm:p-6 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-soft"
              >
                {/* Header card */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DDD7CD]/50 pb-4">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-serif text-base font-bold text-[#242B23]">
                      Đơn hàng #{order.id}
                    </span>
                    <span className="text-xs text-[#5A6258]">
                      • {new Date(order.created_at).toLocaleDateString("vi-VN", {
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>

                  {/* Status badges */}
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Order Status */}
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ${
                        order.status === "DELIVERED" || order.status === "COMPLETED"
                          ? "bg-[#EBF6EE] text-[#1E6B37]"
                          : order.status === "CANCELLED"
                          ? "bg-[#FDF2F1] text-[#B3261E]"
                          : "bg-[#FBF9F5] text-[#8A6B4E] border border-[#8A6B4E]/30"
                      }`}
                    >
                      {displayStatus(order.status)}
                    </span>

                    {/* Shipping fee alert badge if applicable */}
                    {isAwaitingConfirmation && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[#FEF7E6] px-2.5 py-1 text-xs font-bold text-[#9E5600] border border-[#9E5600]/30 animate-pulse">
                        <Truck size={12} />
                        Cần xác nhận phí cồng kềnh
                      </span>
                    )}
                  </div>
                </div>

                {/* Items preview */}
                <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex -space-x-3 overflow-hidden">
                      {order.items.slice(0, 3).map((item) => {
                        const product = item.product;
                        const image =
                          product?.images?.find((img) => img.is_primary)?.image_url ||
                          product?.images?.[0]?.image_url;
                        return (
                          <div
                            key={item.id}
                            className="relative h-14 w-16 overflow-hidden rounded-xl border-2 border-white bg-[#FBF9F5] shadow-sm"
                          >
                            {image ? (
                              <img
                                src={apiAssetUrl(image)}
                                alt={product?.name || "Decor"}
                                className="h-full w-full object-cover"
                              />
                            ) : (
                              <div className="flex h-full w-full items-center justify-center text-[9px] text-[#5A6258]/60">
                                Decor
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-[#242B23]">
                        {order.items.length} mặt hàng decor
                      </p>
                      <p className="text-xs text-[#5A6258] truncate max-w-xs sm:max-w-md">
                        {order.items.map((i) => i.product?.name || `Món #${i.product_id}`).join(", ")}
                      </p>
                    </div>
                  </div>

                  {/* Financial summary & Action */}
                  <div className="flex items-center justify-between gap-4 border-t border-[#DDD7CD]/40 pt-3 sm:border-t-0 sm:pt-0 sm:text-right">
                    <div>
                      <span className="block text-xs text-[#5A6258]">Tổng thanh toán (COD)</span>
                      <span className="font-serif text-lg font-bold text-[#8A6B4E]">
                        {order.total_amount != null
                          ? `${Number(order.total_amount).toLocaleString("vi-VN")} đ`
                          : isBulkyPending
                          ? "Chờ báo phí"
                          : `${Number(order.subtotal_amount || 0).toLocaleString("vi-VN")} đ`}
                      </span>
                    </div>

                    <Link href={`/orders/${order.id}`}>
                      <LuxuryButton variant="secondary" size="sm">
                        Chi tiết đơn
                      </LuxuryButton>
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
