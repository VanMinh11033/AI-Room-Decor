"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  Banknote,
  CheckCircle2,
  ChevronLeft,
  Info,
  Loader2,
  MapPin,
  Phone,
  Truck,
  User,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { EmptyImagePlaceholder, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayPaymentMethod, displayPaymentStatus, displayStatus } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { Order } from "@/types/api";

export default function OrderDetailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const isJustCheckedOut = searchParams.get("checkout_success") === "1";

  const { loading: authLoading } = useAuth("CUSTOMER");
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [confirmingFee, setConfirmingFee] = useState(false);
  const [feeNotice, setFeeNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOrder(await apiFetch<Order>(`/api/orders/${params.id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được đơn hàng.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  async function cancelOrder() {
    if (!window.confirm("Bạn muốn hủy đơn hàng này? Thao tác này sẽ hoàn trả số lượng sản phẩm về kho.")) return;
    setCancelling(true);
    setError("");
    try {
      setOrder(await apiFetch<Order>(`/api/orders/${params.id}/cancel`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể hủy đơn hàng.");
    } finally {
      setCancelling(false);
    }
  }

  async function confirmShippingFee() {
    setConfirmingFee(true);
    setError("");
    setFeeNotice("");
    try {
      const updated = await apiFetch<Order>(`/api/orders/${params.id}/confirm-shipping-fee`, { method: "POST" });
      setOrder(updated);
      setFeeNotice("Quý khách đã xác nhận đồng ý mức phí vận chuyển. Đơn hàng đang được điều phối giao.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xác nhận phí vận chuyển.");
    } finally {
      setConfirmingFee(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Loader2 size={32} className="animate-spin text-clay" />
        <p className="font-semibold text-charcoal/60">Đang tải thông tin đơn hàng #{params.id}...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm font-semibold text-red-700">
        <p>{error || "Không tìm thấy đơn hàng yêu cầu."}</p>
        <Link href="/orders" className="secondary-cta mt-4 inline-flex">
          Quay lại danh sách đơn hàng
        </Link>
      </div>
    );
  }

  const isBulkyPending = order.shipping_fee_status === "PENDING_CALCULATION" || order.shipping_fee === null;

  return (
    <section className="space-y-7 pb-12">
      <Link href="/orders" className="inline-flex items-center gap-2 text-sm font-bold text-charcoal/60 hover:text-ink">
        <ChevronLeft size={16} /> Đơn hàng của tôi
      </Link>

      {/* Thông báo đặt hàng thành công */}
      {isJustCheckedOut && (
        <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/90 p-5 shadow-soft">
          <CheckCircle2 size={24} className="mt-0.5 shrink-0 text-emerald-600" />
          <div className="space-y-1">
            <h3 className="font-black text-emerald-950">Đặt hàng thành công!</h3>
            <p className="text-sm text-emerald-800">
              Cảm ơn quý khách đã tin chọn AI Room Decor. Đơn hàng <strong>#{order.id}</strong> đang ở trạng thái <strong>Chờ xác nhận</strong>. Chúng tôi sẽ liên hệ qua số điện thoại <strong>{order.recipient_phone}</strong> để xác nhận chi tiết trước khi điều phối giao hàng.
            </p>
          </div>
        </div>
      )}

      {/* Header đơn hàng */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <span className="text-xs font-black uppercase tracking-wider text-clay">Chi tiết đơn hàng decor</span>
          <h1 className="mt-1 text-2xl font-black text-ink sm:text-3xl">Đơn hàng #{order.id}</h1>
          <p className="mt-1 text-sm text-charcoal/60">
            Đặt lúc {new Date(order.created_at).toLocaleString("vi-VN")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Badge Order Status */}
          <span className="rounded-full bg-ivory px-3.5 py-1.5 text-xs font-black text-clay border border-ink/10 shadow-soft">
            {displayStatus(order.status)}
          </span>
          {/* Badge Payment Status */}
          <span
            className={`rounded-full px-3.5 py-1.5 text-xs font-black border shadow-soft ${
              order.payment_status === "PAID"
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-amber-50 text-amber-900 border-amber-200"
            }`}
          >
            {displayPaymentStatus(order.payment_status)}
          </span>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">
          {error}
        </div>
      )}

      {/* Thông báo cập nhật phí */}
      {feeNotice && (
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-800 shadow-soft">
          <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
          <span>{feeNotice}</span>
        </div>
      )}

      {/* Cảnh báo & Xác nhận phí vận chuyển hàng cồng kềnh */}
      {order.shipping_fee_status === "AWAITING_CUSTOMER_CONFIRMATION" && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50/95 p-5 shadow-soft">
          <div className="flex items-start gap-3.5">
            <Truck size={24} className="mt-0.5 shrink-0 text-amber-700" />
            <div className="space-y-2.5 flex-1">
              <div>
                <h3 className="font-black text-amber-950 text-base">Xác nhận mức phí vận chuyển hàng cồng kềnh</h3>
                <p className="mt-1 text-sm text-amber-900 leading-relaxed">
                  Quản trị viên đã khảo sát tuyến đường và cập nhật cước phí vận chuyển cho kiện hàng cồng kềnh này là:{" "}
                  <strong className="text-clay font-black text-base">{Number(order.shipping_fee || 0).toLocaleString("vi-VN")} đ</strong>.
                </p>
                <p className="text-xs text-amber-800">
                  Tổng số tiền thanh toán khi nhận hàng (COD):{" "}
                  <strong className="text-ink font-black text-sm">{Number(order.total_amount || 0).toLocaleString("vi-VN")} đ</strong>.
                </p>
              </div>
              <div className="pt-1 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={confirmShippingFee}
                  disabled={confirmingFee}
                  className="rounded-xl bg-[#2D332C] px-5 py-2.5 text-xs font-bold text-white shadow-soft transition hover:bg-[#3B433A] disabled:opacity-50"
                >
                  {confirmingFee ? "Đang xác nhận..." : "Đồng ý mức phí & Tiếp tục giao hàng"}
                </button>
                {order.status === "PENDING" && (
                  <button
                    type="button"
                    onClick={cancelOrder}
                    disabled={cancelling}
                    className="rounded-xl border border-red-200 bg-white px-4 py-2.5 text-xs font-bold text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    Không đồng ý phí &amp; Hủy đơn
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {order.shipping_fee_status === "CUSTOMER_CONFIRMED" && (
        <div className="flex items-center gap-2.5 rounded-2xl border border-emerald-200 bg-emerald-50/90 p-4 text-xs font-semibold text-emerald-900 shadow-soft">
          <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
          <span>
            Quý khách đã xác nhận đồng ý mức phí vận chuyển ({Number(order.shipping_fee || 0).toLocaleString("vi-VN")} đ). Đơn hàng đang được chuẩn bị để giao tới địa chỉ của quý khách.
          </span>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        {/* Cột trái: Danh sách sản phẩm */}
        <div className="space-y-6">
          <SectionCard title={`Sản phẩm trong kiện hàng (${order.items.length})`}>
            <div className="divide-y divide-ink/10">
              {order.items.map((item) => {
                const product = item.product;
                const image = product?.images?.find((img) => img.is_primary)?.image_url || product?.images?.[0]?.image_url;
                return (
                  <div key={item.id} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0">
                    <Link
                      href={product ? `/products/${product.id}` : "#"}
                      className="h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-ivory border border-ink/10"
                    >
                      {image ? (
                        <img src={apiAssetUrl(image)} alt={product?.name} className="h-full w-full object-cover" />
                      ) : (
                        <EmptyImagePlaceholder />
                      )}
                    </Link>
                    <div className="min-w-0 flex-1">
                      <Link
                        href={product ? `/products/${product.id}` : "#"}
                        className="block truncate font-bold text-ink hover:underline"
                      >
                        {product?.name || `Sản phẩm #${item.product_id}`}
                      </Link>
                      <p className="mt-0.5 text-xs text-charcoal/60">
                        {Number(item.unit_price).toLocaleString("vi-VN")} đ x{" "}
                        <strong className="text-ink">{item.quantity}</strong>
                      </p>
                    </div>
                    <p className="font-black text-ink">{Number(item.subtotal).toLocaleString("vi-VN")} đ</p>
                  </div>
                );
              })}
            </div>
          </SectionCard>

          {/* Thông tin hỗ trợ */}
          <div className="rounded-2xl border border-ink/10 bg-ivory/60 p-5 text-xs text-charcoal/70">
            <div className="flex items-center gap-2 font-bold text-ink">
              <Info size={16} className="text-clay" />
              <span>Chính sách kiểm tra &amp; nhận hàng</span>
            </div>
            <p className="mt-1.5 leading-relaxed">
              Quý khách được quyền đồng kiểm cùng nhân viên giao hàng trước khi thanh toán. Nếu sản phẩm không đúng mẫu mã, màu sắc hoặc bị lỗi do vận chuyển, quý khách có quyền từ chối nhận hàng mà không mất phí.
            </p>
          </div>
        </div>

        {/* Cột phải: Thông tin nhận hàng & Thanh toán */}
        <aside className="space-y-6">
          {/* Thông tin nhận hàng có cấu trúc */}
          <SectionCard title="Thông tin người nhận">
            <div className="space-y-3.5 text-sm">
              <div className="flex items-start gap-2.5">
                <User size={16} className="mt-0.5 shrink-0 text-clay" />
                <div>
                  <span className="block text-xs text-charcoal/60">Người nhận hàng</span>
                  <span className="font-bold text-ink">{order.recipient_name || "N/A"}</span>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Phone size={16} className="mt-0.5 shrink-0 text-clay" />
                <div>
                  <span className="block text-xs text-charcoal/60">Số điện thoại liên hệ</span>
                  <span className="font-bold text-ink">{order.recipient_phone || "N/A"}</span>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <MapPin size={16} className="mt-0.5 shrink-0 text-clay" />
                <div>
                  <span className="block text-xs text-charcoal/60">Địa chỉ giao hàng</span>
                  <span className="text-ink leading-relaxed">
                    {order.street_address ? (
                      <>
                        {order.street_address}, {order.ward}, {order.province}
                      </>
                    ) : (
                      order.shipping_address || "Chưa cung cấp địa chỉ"
                    )}
                  </span>
                </div>
              </div>

              {order.delivery_notes && (
                <div className="rounded-xl border border-ink/5 bg-white/70 p-3 text-xs">
                  <span className="font-bold text-charcoal/70">Ghi chú giao hàng: </span>
                  <span className="text-charcoal/80">{order.delivery_notes}</span>
                </div>
              )}
            </div>
          </SectionCard>

          {/* Thanh toán & Chi phí */}
          <SectionCard title="Thanh toán COD">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-charcoal/60">Phương thức:</span>
                <div className="flex items-center gap-1.5 font-bold text-ink">
                  <Banknote size={15} className="text-clay" />
                  <span>{displayPaymentMethod(order.payment_method)}</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-charcoal/60">Trạng thái thu tiền:</span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-black ${
                    order.payment_status === "PAID"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-amber-100 text-amber-900"
                  }`}
                >
                  {displayPaymentStatus(order.payment_status)}
                </span>
              </div>

              <div className="border-t border-ink/10 pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-charcoal/60">Tạm tính tiền hàng:</span>
                  <span className="font-bold text-ink">
                    {Number(order.subtotal_amount || 0).toLocaleString("vi-VN")} đ
                  </span>
                </div>

                <div className="mt-2 flex items-center justify-between">
                  <span className="text-charcoal/60">Phí vận chuyển:</span>
                  {order.shipping_fee_status === "PENDING_CALCULATION" || order.shipping_fee === null ? (
                    <span className="rounded-md bg-amber-100 px-2 py-0.5 text-[11px] font-black text-amber-900">
                      Chờ khảo sát báo phí
                    </span>
                  ) : order.shipping_fee_status === "AWAITING_CUSTOMER_CONFIRMATION" ? (
                    <div className="text-right">
                      <span className="font-bold text-ink">
                        {Number(order.shipping_fee).toLocaleString("vi-VN")} đ
                      </span>
                      <span className="block text-[10px] font-bold text-amber-800">Chờ bạn xác nhận</span>
                    </div>
                  ) : order.shipping_fee_status === "CUSTOMER_CONFIRMED" ? (
                    <div className="text-right">
                      <span className="font-bold text-ink">
                        {Number(order.shipping_fee).toLocaleString("vi-VN")} đ
                      </span>
                      <span className="block text-[10px] font-bold text-emerald-800">Đã xác nhận</span>
                    </div>
                  ) : (
                    <span className="font-bold text-ink">
                      {order.shipping_fee ? `${Number(order.shipping_fee).toLocaleString("vi-VN")} đ` : "Miễn phí"}
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-baseline justify-between border-t border-ink/10 pt-3">
                  <div>
                    <span className="font-black text-ink">Tổng thanh toán:</span>
                    {isBulkyPending && (
                      <p className="text-[10px] text-amber-800">* Chưa bao gồm phí cồng kềnh</p>
                    )}
                  </div>
                  <div className="text-right">
                    {order.total_amount ? (
                      <span className="text-xl font-black text-clay">
                        {Number(order.total_amount).toLocaleString("vi-VN")} đ
                      </span>
                    ) : (
                      <span className="text-base font-black text-clay">
                        {Number(order.subtotal_amount || 0).toLocaleString("vi-VN")} đ
                        <span className="block text-[11px] text-charcoal/50">+ Phí vận chuyển</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Hủy đơn hàng */}
            {order.status === "PENDING" && (
              <button
                type="button"
                onClick={cancelOrder}
                disabled={cancelling}
                className="secondary-cta mt-6 w-full text-xs text-red-600 hover:border-red-300 hover:bg-red-50"
              >
                {cancelling ? <Loader2 size={15} className="animate-spin" /> : <XCircle size={15} />} Hủy đơn hàng này
              </button>
            )}
          </SectionCard>
        </aside>
      </div>
    </section>
  );
}
