"use client";

import { useParams } from "next/navigation";
import {
  Banknote,
  CheckCircle2,
  MapPin,
  Package,
  Phone,
  RefreshCw,
  Save,
  Truck,
  User,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayPaymentMethod, displayPaymentStatus, displayStatus } from "@/lib/display";
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
  const [shippingFeeInput, setShippingFeeInput] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);
  const [savingPayment, setSavingPayment] = useState(false);
  const [savingFee, setSavingFee] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<Order>(`/api/admin/orders/${params.id}`);
      setOrder(data);
      setStatus(data.status);
      if (data.shipping_fee) {
        setShippingFeeInput(String(data.shipping_fee));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được đơn hàng.");
    }
  }, [params.id]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  // Update order status
  async function updateStatus() {
    setSavingStatus(true);
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
      setError(err instanceof Error ? err.message : "Không cập nhật được trạng thái đơn hàng.");
    } finally {
      setSavingStatus(false);
    }
  }

  // Admin confirms COD payment
  async function confirmCodPayment() {
    if (!window.confirm("Xác nhận đã nhận đủ tiền mặt COD cho đơn hàng này? Thao tác này sẽ chuyển PaymentStatus sang PAID.")) {
      return;
    }
    setSavingPayment(true);
    setError("");
    setMessage("");
    try {
      const data = await apiFetch<Order>(`/api/admin/orders/${params.id}/payment-status`, {
        method: "PATCH",
        body: JSON.stringify({ payment_status: "PAID", note: "Admin xác nhận đã nhận tiền mặt COD" }),
      });
      setOrder(data);
      setStatus(data.status);
      setMessage("Đã xác nhận thu tiền mặt COD thành công (PAID)!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xác nhận thanh toán.");
    } finally {
      setSavingPayment(false);
    }
  }

  // Admin quotes shipping fee for bulky items
  async function updateShippingFee() {
    const feeNumber = Number(shippingFeeInput);
    if (isNaN(feeNumber) || feeNumber < 0) {
      setError("Vui lòng nhập số tiền phí vận chuyển hợp lệ.");
      return;
    }
    setSavingFee(true);
    setError("");
    setMessage("");
    try {
      const data = await apiFetch<Order>(`/api/admin/orders/${params.id}/shipping-fee`, {
        method: "PATCH",
        body: JSON.stringify({ shipping_fee: feeNumber }),
      });
      setOrder(data);
      setMessage("Cập nhật phí vận chuyển và chốt tổng thanh toán thành công!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được phí vận chuyển.");
    } finally {
      setSavingFee(false);
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

  const isBulkyPending = order.shipping_fee_status === "PENDING_CALCULATION" || order.shipping_fee === null;

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Chi tiết giao dịch COD"
        title={`Đơn hàng #${order.id}`}
        subtitle={`Đặt lúc ${new Date(order.created_at).toLocaleString("vi-VN")} · Người nhận: ${
          order.recipient_name || order.customer?.full_name || "Khách hàng"
        }`}
        backHref="/admin/orders"
        backLabel="Quay lại danh sách đơn hàng"
        badge={<AdminStatusBadge status={order.status} />}
      />

      {/* Thông báo cập nhật */}
      {message && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-800 shadow-soft">
          <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-soft">
          {error}
        </div>
      )}

      {/* 2. Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        {/* Left Column: Product Items & Recipient Info */}
        <div className="space-y-6">
          {/* Danh mục sản phẩm */}
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

            {/* Bảng tính chi phí */}
            <div className="mt-6 border-t border-[#2D332C]/10 pt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-[#777777]">Tạm tính tiền hàng</span>
                <span className="font-semibold text-[#242424]">
                  {Number(order.subtotal_amount || 0).toLocaleString("vi-VN")} đ
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[#777777]">Phí vận chuyển</span>
                {order.shipping_fee_status === "PENDING_CALCULATION" ? (
                  <span className="rounded-md bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-900 border border-amber-200">
                    Chờ khảo sát báo phí
                  </span>
                ) : order.shipping_fee_status === "AWAITING_CUSTOMER_CONFIRMATION" ? (
                  <span className="rounded-md bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-blue-900 border border-blue-200">
                    Đã báo {Number(order.shipping_fee).toLocaleString("vi-VN")} đ (Chờ khách duyệt)
                  </span>
                ) : order.shipping_fee_status === "CUSTOMER_CONFIRMED" ? (
                  <span className="rounded-md bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-900 border border-emerald-200">
                    Khách đã duyệt {Number(order.shipping_fee).toLocaleString("vi-VN")} đ
                  </span>
                ) : (
                  <span className="font-semibold text-[#242424]">
                    {order.shipping_fee ? `${Number(order.shipping_fee).toLocaleString("vi-VN")} đ` : "Miễn phí"}
                  </span>
                )}
              </div>

              <div className="mt-3 flex items-baseline justify-between border-t border-[#2D332C]/10 pt-3">
                <span className="text-base font-bold text-[#242424]">Tổng thanh toán COD</span>
                {order.total_amount ? (
                  <span className="text-xl font-black text-[#A68B6D]">
                    {Number(order.total_amount).toLocaleString("vi-VN")} đ
                  </span>
                ) : (
                  <div className="text-right">
                    <span className="text-base font-bold text-amber-900">
                      {Number(order.subtotal_amount || 0).toLocaleString("vi-VN")} đ
                    </span>
                    <span className="block text-xs text-[#777777]">(+ Phí vận chuyển cồng kềnh)</span>
                  </div>
                )}
              </div>
            </div>
          </AdminSurfaceCard>

          {/* Cập nhật phí vận chuyển cho hàng cồng kềnh */}
          {(isBulkyPending || order.shipping_fee_status === "AWAITING_CUSTOMER_CONFIRMATION") && order.status !== "CANCELLED" && (
            <AdminSurfaceCard
              title="Khảo sát &amp; Cập nhật phí vận chuyển cồng kềnh"
              subtitle="Đơn hàng chứa sản phẩm cồng kềnh cần báo giá vận chuyển chính xác"
            >
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs text-amber-800 bg-amber-50 p-3 rounded-xl border border-amber-200">
                  <Truck size={16} className="shrink-0 text-amber-700" />
                  <span>
                    Sau khi liên hệ khách hàng và xác nhận cự ly giao hàng, nhập số tiền phí vận chuyển thực tế dưới đây để chốt tổng đơn hàng.
                  </span>
                </div>

                <div className="flex gap-3">
                  <input
                    type="number"
                    min="0"
                    step="1000"
                    value={shippingFeeInput}
                    onChange={(e) => setShippingFeeInput(e.target.value)}
                    placeholder="Ví dụ: 150000"
                    className="flex-1 rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={updateShippingFee}
                    disabled={savingFee || !shippingFeeInput}
                    className="rounded-xl bg-[#A68B6D] px-5 py-2.5 text-xs font-bold text-white shadow-soft transition hover:bg-[#8f755a] disabled:opacity-40"
                  >
                    {savingFee ? "Đang lưu..." : "Chốt phí vận chuyển"}
                  </button>
                </div>
              </div>
            </AdminSurfaceCard>
          )}

          {/* Thông tin nhận hàng & Vận chuyển có cấu trúc */}
          <AdminSurfaceCard
            title="Thông tin nhận hàng &amp; Vận chuyển"
            subtitle="Địa chỉ và thông tin liên lạc được cung cấp lúc checkout"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#A68B6D]">
                  <User size={14} />
                  <span>Người nhận hàng</span>
                </div>
                <p className="mt-2 text-sm font-bold text-[#242424]">
                  {order.recipient_name || order.customer?.full_name || "Chưa cung cấp tên"}
                </p>
                <p className="mt-1 flex items-center gap-1.5 text-xs font-semibold text-emerald-800">
                  <Phone size={12} />
                  <span>{order.recipient_phone || "Chưa có SĐT"}</span>
                </p>
                <p className="mt-1 text-[11px] text-[#777777]">
                  Tài khoản đặt: {order.customer?.email || `ID #${order.user_id}`}
                </p>
              </div>

              <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#A68B6D]">
                  <MapPin size={14} />
                  <span>Địa chỉ giao hàng</span>
                </div>
                <p className="mt-2 text-sm text-[#242424] leading-relaxed">
                  {order.street_address ? (
                    <>
                      <strong>{order.street_address}</strong>, {order.ward}, {order.province}
                    </>
                  ) : (
                    order.shipping_address || "Chưa cung cấp địa chỉ cụ thể"
                  )}
                </p>
                {order.delivery_notes && (
                  <p className="mt-2 text-xs text-[#777777] italic">
                    Ghi chú: &ldquo;{order.delivery_notes}&rdquo;
                  </p>
                )}
              </div>
            </div>
          </AdminSurfaceCard>
        </div>

        {/* Right Column: Status & Operational Controls */}
        <div className="space-y-6">
          {/* Quản lý thu tiền COD */}
          <AdminSurfaceCard
            title="Xác nhận thu tiền COD"
            subtitle="Thanh toán khi nhận hàng tiền mặt"
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#777777]">Phương thức:</span>
                <span className="font-bold text-[#242424]">
                  {displayPaymentMethod(order.payment_method)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-[#777777]">Trạng thái thu tiền:</span>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-black border ${
                    order.payment_status === "PAID"
                      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                      : "bg-amber-50 text-amber-900 border-amber-200"
                  }`}
                >
                  {displayPaymentStatus(order.payment_status)}
                </span>
              </div>

              {order.payment_status === "UNPAID" && order.status !== "CANCELLED" && (
                <button
                  type="button"
                  onClick={confirmCodPayment}
                  disabled={savingPayment}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 py-3 text-xs font-bold text-white shadow-soft transition hover:bg-emerald-800 disabled:opacity-40"
                >
                  {savingPayment ? (
                    <RefreshCw size={15} className="animate-spin" />
                  ) : (
                    <Banknote size={16} />
                  )}
                  {savingPayment ? "Đang xác nhận..." : "Xác nhận đã thu tiền COD (PAID)"}
                </button>
              )}

              {order.payment_status === "PAID" && (
                <div className="flex items-center gap-2 rounded-xl bg-emerald-50/80 border border-emerald-200 p-3 text-xs text-emerald-900 font-semibold">
                  <CheckCircle2 size={16} className="text-emerald-700 shrink-0" />
                  <span>Đã thu tiền mặt COD đầy đủ cho đơn hàng này.</span>
                </div>
              )}
            </div>
          </AdminSurfaceCard>

          {/* Quản lý tiến độ đơn hàng */}
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
                {(order.shipping_fee_status === "PENDING_CALCULATION" || order.shipping_fee_status === "AWAITING_CUSTOMER_CONFIRMATION") && (
                  <p className="mt-2 text-xs font-semibold text-amber-800">
                    * Lưu ý: Không thể chuyển sang trạng thái Giao hàng (SHIPPED) khi khách hàng chưa xác nhận phí vận chuyển hàng cồng kềnh.
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={updateStatus}
                disabled={savingStatus || status === order.status}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#2D332C] px-5 py-3 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:bg-[#3B433A] disabled:opacity-40"
              >
                {savingStatus ? (
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
