"use client";

import { useParams } from "next/navigation";
import { CheckCircle2, MapPin, Package, RefreshCw, Save, User } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import type { Order } from "@/types/api";
import {
  AdminPageHeader,
  AdminStatusBadge,
  AdminSurfaceCard,
} from "@/components/admin/AdminPrimitives";

const STATUS_OPTIONS = [
  "PENDING",
  "CONFIRMED",
  "PROCESSING",
  "SHIPPED",
  "COMPLETED",
  "CANCELLED",
];

export default function AdminOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { loading: authLoading } = useAuth("ADMIN");
  const [order, setOrder] = useState<Order | null>(null);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<Order>(`/api/admin/orders/${params.id}`);
      setOrder(data);
      setStatus(data.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được đơn hàng.");
    }
  }, [params.id]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  async function updateStatus() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const data = await apiFetch<Order>(`/api/admin/orders/${params.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setOrder(data);
      setStatus(data.status);
      setMessage("Cập nhật trạng thái đơn hàng thành công!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được trạng thái.");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  if (error && !order) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm font-semibold text-red-700 shadow-sm">
        {error}
      </div>
    );
  }

  if (!order) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang tải chi tiết đơn hàng #{params.id}...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Chi tiết giao dịch"
        title={`Đơn hàng #${order.id}`}
        subtitle={`Đặt lúc ${new Date(order.created_at).toLocaleString("vi-VN")} · Khách hàng: ${
          order.customer?.full_name || "Khách vãng lai"
        }`}
        backHref="/admin/orders"
        backLabel="Quay lại danh sách đơn hàng"
        badge={<AdminStatusBadge status={order.status} />}
      />

      {/* 2. Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        {/* Left Column: Product Items in Order */}
        <div className="space-y-6">
          <AdminSurfaceCard
            title="Danh mục sản phẩm đặt mua"
            subtitle={`${order.items.length} mặt hàng trong kiện hàng này`}
          >
            <div className="divide-y divide-[#2D332C]/5">
              {order.items.map((item) => {
                const primaryImage =
                  item.product?.images?.find((img) => img.is_primary)?.image_url ||
                  item.product?.images?.[0]?.image_url;

                return (
                  <div
                    key={item.id}
                    className="flex flex-col justify-between gap-4 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center"
                  >
                    <div className="flex min-w-0 items-center gap-4">
                      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5]">
                        {primaryImage ? (
                          <img
                            src={apiAssetUrl(primaryImage)}
                            alt={item.product?.name || "Sản phẩm"}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-xs text-[#777777]">
                            <Package size={20} />
                          </div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate font-bold text-[#242424]">
                          {item.product?.name || `Sản phẩm #${item.product_id}`}
                        </p>
                        <p className="mt-1 text-xs text-[#777777]">
                          Đơn giá: {Number(item.unit_price).toLocaleString("vi-VN")} đ · Số lượng:{" "}
                          <strong className="text-[#242424]">x{item.quantity}</strong>
                        </p>
                      </div>
                    </div>

                    <div className="text-right sm:shrink-0">
                      <p className="text-sm font-bold text-[#2D332C]">
                        {Number(item.subtotal).toLocaleString("vi-VN")} đ
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Total Calculation Row */}
            <div className="mt-6 border-t border-[#2D332C]/10 pt-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#777777]">Tạm tính sản phẩm</span>
                <span className="font-semibold text-[#242424]">
                  {Number(order.total_amount).toLocaleString("vi-VN")} đ
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between text-sm">
                <span className="text-[#777777]">Phí vận chuyển nội thất</span>
                <span className="font-semibold text-emerald-700">Miễn phí giao hàng</span>
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-[#2D332C]/10 pt-3">
                <span className="text-base font-bold text-[#242424]">Tổng thanh toán</span>
                <span className="text-xl font-black text-[#A68B6D]">
                  {Number(order.total_amount).toLocaleString("vi-VN")} đ
                </span>
              </div>
            </div>
          </AdminSurfaceCard>

          {/* Shipping & Recipient Card */}
          <AdminSurfaceCard
            title="Thông tin nhận hàng & Vận chuyển"
            subtitle="Địa chỉ và thông tin liên lạc được cung cấp lúc checkout"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#A68B6D]">
                  <User size={14} />
                  <span>Khách hàng nhận</span>
                </div>
                <p className="mt-2 text-sm font-bold text-[#242424]">
                  {order.customer?.full_name || "Chưa cung cấp tên"}
                </p>
                <p className="mt-0.5 text-xs text-[#777777]">
                  {order.customer?.email || `Tài khoản ID #${order.user_id}`}
                </p>
              </div>

              <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#A68B6D]">
                  <MapPin size={14} />
                  <span>Địa chỉ giao hàng</span>
                </div>
                <p className="mt-2 text-sm text-[#242424]">
                  {order.shipping_address || "Chưa cung cấp địa chỉ cụ thể"}
                </p>
              </div>
            </div>
          </AdminSurfaceCard>
        </div>

        {/* Right Column: Status & Operational Controls */}
        <div className="space-y-6">
          <AdminSurfaceCard
            title="Quản lý tiến độ đơn hàng"
            subtitle="Cập nhật trạng thái xử lý cho đơn hàng"
          >
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                  Trạng thái hiện tại
                </p>
                <div className="mt-2">
                  <AdminStatusBadge status={order.status} />
                </div>
              </div>

              <div className="border-t border-[#2D332C]/10 pt-4">
                <label className="text-xs font-bold uppercase tracking-wider text-[#242424]">
                  Chuyển trạng thái sang:
                </label>
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {displayStatus(option)} ({option})
                    </option>
                  ))}
                </select>
              </div>

              {message && (
                <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800">
                  <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
                  <span>{message}</span>
                </div>
              )}

              {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
                  {error}
                </div>
              )}

              <button
                type="button"
                onClick={updateStatus}
                disabled={saving || status === order.status}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#2D332C] px-5 py-3 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:bg-[#3B433A] disabled:opacity-40"
              >
                {saving ? (
                  <>
                    <RefreshCw size={15} className="animate-spin text-[#C9A77A]" />
                    Đang lưu cập nhật...
                  </>
                ) : (
                  <>
                    <Save size={15} className="text-[#C9A77A]" />
                    Lưu trạng thái mới
                  </>
                )}
              </button>
            </div>
          </AdminSurfaceCard>

          {/* Quick Info Summary */}
          <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-5">
            <h4 className="text-xs font-bold uppercase tracking-[0.14em] text-[#A68B6D]">
              Nhật ký thời gian
            </h4>
            <div className="mt-3 space-y-2 text-xs text-[#777777]">
              <div className="flex justify-between">
                <span>Khởi tạo đơn:</span>
                <span className="font-semibold text-[#242424]">
                  {new Date(order.created_at).toLocaleString("vi-VN")}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Cập nhật gần nhất:</span>
                <span className="font-semibold text-[#242424]">
                  {new Date(order.updated_at || order.created_at).toLocaleString("vi-VN")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
