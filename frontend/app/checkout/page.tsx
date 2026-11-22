"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Banknote,
  ChevronLeft,
  CreditCard,
  Loader2,
  Package,
  ShieldCheck,
  ShoppingBag,
  Truck,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Cart, Order, ShippingPreviewResponse } from "@/types/api";

const VIETNAM_PHONE_REGEX = /^(?:0|\+84)[35789]\d{8}$/;

export default function CheckoutPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth("CUSTOMER");

  const [cart, setCart] = useState<Cart | null>(null);
  const [shippingPreview, setShippingPreview] = useState<ShippingPreviewResponse | null>(null);

  // Form states
  const [recipientName, setRecipientName] = useState("");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [province, setProvince] = useState("");
  const [ward, setWard] = useState("");
  const [streetAddress, setStreetAddress] = useState("");
  const [deliveryNotes, setDeliveryNotes] = useState("");
  const [paymentMethod] = useState<"COD">("COD");

  // UI status
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Auto-fill user profile name if available
  useEffect(() => {
    if (user?.full_name && !recipientName) {
      setRecipientName(user.full_name);
    }
  }, [user, recipientName]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [cartData, previewData] = await Promise.all([
        apiFetch<Cart>("/api/cart"),
        apiFetch<ShippingPreviewResponse>("/api/orders/shipping-preview").catch(() => null),
      ]);
      setCart(cartData);
      setShippingPreview(previewData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được giỏ hàng.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) loadData();
  }, [authLoading, loadData]);

  // Client validation
  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!recipientName.trim() || recipientName.trim().length < 2) {
      errors.recipientName = "Vui lòng nhập họ và tên người nhận (tối thiểu 2 ký tự).";
    }

    const cleanPhone = recipientPhone.trim().replace(/[\s.-]/g, "");
    if (!cleanPhone) {
      errors.recipientPhone = "Vui lòng nhập số điện thoại người nhận.";
    } else if (!VIETNAM_PHONE_REGEX.test(cleanPhone)) {
      errors.recipientPhone = "Số điện thoại không đúng định dạng di động Việt Nam (ví dụ: 0912345678).";
    }

    if (!province.trim()) {
      errors.province = "Vui lòng nhập tỉnh hoặc thành phố.";
    }

    if (!ward.trim()) {
      errors.ward = "Vui lòng nhập phường hoặc xã.";
    }

    if (!streetAddress.trim() || streetAddress.trim().length < 3) {
      errors.streetAddress = "Vui lòng nhập số nhà, tên đường chi tiết.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return; // Prevent double submit
    if (!validateForm()) {
      setError("Vui lòng kiểm tra và điền đầy đủ các thông tin nhận hàng bắt buộc.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const payload = {
        recipient_name: recipientName.trim(),
        recipient_phone: recipientPhone.trim().replace(/[\s.-]/g, ""),
        province: province.trim(),
        ward: ward.trim(),
        street_address: streetAddress.trim(),
        delivery_notes: deliveryNotes.trim() || null,
        payment_method: "COD",
      };

      const order = await apiFetch<Order>("/api/orders", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      router.push(`/orders/${order.id}?checkout_success=1`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể đặt hàng. Vui lòng thử lại.");
      setSubmitting(false);
    }
  }

  const items = useMemo(() => cart?.items || [], [cart]);
  const isBulky = shippingPreview?.is_bulky ?? false;

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Loader2 size={32} className="animate-spin text-clay" />
        <p className="font-semibold text-charcoal/70">Đang chuẩn bị trang thanh toán...</p>
      </div>
    );
  }

  return (
    <section className="space-y-8 pb-12">
      <PageHeader
        eyebrow="Thanh toán an toàn"
        title="Xác nhận đơn hàng nội thất"
        description="Kiểm tra lại sản phẩm decor đã chọn, cung cấp thông tin nhận hàng và chọn phương thức thanh toán."
      />

      {error && (
        <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700 shadow-soft">
          <AlertCircle size={20} className="shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {items.length === 0 && !error ? (
        <SectionCard className="py-16 text-center">
          <Package size={44} className="mx-auto text-charcoal/30" />
          <p className="mt-4 text-lg font-black text-ink">Giỏ hàng của bạn đang trống</p>
          <p className="mt-1 text-sm text-charcoal/60">Hãy quay lại danh mục để chọn các sản phẩm decor yêu thích.</p>
          <Link href="/products" className="primary-cta mt-6 inline-flex">
            Khám phá sản phẩm
          </Link>
        </SectionCard>
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.2fr_0.8fr] w-full min-w-0">
          {/* CỘT TRÁI: FORM THÔNG TIN NHẬN HÀNG & PHƯƠNG THỨC THANH TOÁN */}
          <div className="space-y-6">
            {/* 1. THÔNG TIN NGƯỜI NHẬN */}
            <SectionCard title="1. Thông tin giao nhận hàng">
              <form id="checkout-form" onSubmit={onSubmit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-xs font-black uppercase tracking-wider text-charcoal/70">
                      Họ và tên người nhận <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={recipientName}
                      onChange={(e) => {
                        setRecipientName(e.target.value);
                        if (fieldErrors.recipientName) setFieldErrors((prev) => ({ ...prev, recipientName: "" }));
                      }}
                      placeholder="Nguyễn Văn A"
                      className={`premium-input mt-1.5 w-full ${fieldErrors.recipientName ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    {fieldErrors.recipientName && (
                      <p className="mt-1 text-xs font-medium text-red-600">{fieldErrors.recipientName}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-black uppercase tracking-wider text-charcoal/70">
                      Số điện thoại di động <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="tel"
                      required
                      value={recipientPhone}
                      onChange={(e) => {
                        setRecipientPhone(e.target.value);
                        if (fieldErrors.recipientPhone) setFieldErrors((prev) => ({ ...prev, recipientPhone: "" }));
                      }}
                      placeholder="0912345678"
                      className={`premium-input mt-1.5 w-full ${fieldErrors.recipientPhone ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    {fieldErrors.recipientPhone && (
                      <p className="mt-1 text-xs font-medium text-red-600">{fieldErrors.recipientPhone}</p>
                    )}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-xs font-black uppercase tracking-wider text-charcoal/70">
                      Tỉnh / Thành phố <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={province}
                      onChange={(e) => {
                        setProvince(e.target.value);
                        if (fieldErrors.province) setFieldErrors((prev) => ({ ...prev, province: "" }));
                      }}
                      placeholder="Hà Nội, TP. Hồ Chí Minh, Đà Nẵng..."
                      className={`premium-input mt-1.5 w-full ${fieldErrors.province ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    {fieldErrors.province && (
                      <p className="mt-1 text-xs font-medium text-red-600">{fieldErrors.province}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-black uppercase tracking-wider text-charcoal/70">
                      Phường / Xã <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={ward}
                      onChange={(e) => {
                        setWard(e.target.value);
                        if (fieldErrors.ward) setFieldErrors((prev) => ({ ...prev, ward: "" }));
                      }}
                      placeholder="Phường Bến Nghé, Phường Dịch Vọng..."
                      className={`premium-input mt-1.5 w-full ${fieldErrors.ward ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    {fieldErrors.ward && (
                      <p className="mt-1 text-xs font-medium text-red-600">{fieldErrors.ward}</p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-black uppercase tracking-wider text-charcoal/70">
                    Số nhà, tên đường, tòa nhà <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={streetAddress}
                    onChange={(e) => {
                      setStreetAddress(e.target.value);
                      if (fieldErrors.streetAddress) setFieldErrors((prev) => ({ ...prev, streetAddress: "" }));
                    }}
                    placeholder="Số 45/2 đường Nguyễn Thị Minh Khai, Tòa nhà Landmark..."
                    className={`premium-input mt-1.5 w-full ${fieldErrors.streetAddress ? "border-red-500 focus:border-red-500" : ""}`}
                  />
                  {fieldErrors.streetAddress && (
                    <p className="mt-1 text-xs font-medium text-red-600">{fieldErrors.streetAddress}</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-black uppercase tracking-wider text-charcoal/70">
                    Ghi chú giao hàng (không bắt buộc)
                  </label>
                  <textarea
                    rows={2}
                    maxLength={500}
                    value={deliveryNotes}
                    onChange={(e) => setDeliveryNotes(e.target.value)}
                    placeholder="Ví dụ: Giao giờ hành chính, gọi trước khi đến 15 phút, gửi lễ tân..."
                    className="premium-input mt-1.5 w-full resize-none text-sm"
                  />
                </div>
              </form>
            </SectionCard>

            {/* 2. CHỌN PHƯƠNG THỨC THANH TOÁN (CHỈ COD) */}
            <SectionCard title="2. Phương thức thanh toán">
              <div className="space-y-3">
                {/* Option 1: COD (Active) */}
                <label className="flex cursor-pointer items-start gap-3.5 rounded-2xl border-2 border-clay bg-ivory/60 p-4 shadow-soft transition hover:border-clay/90">
                  <input
                    type="radio"
                    name="paymentMethod"
                    value="COD"
                    checked={paymentMethod === "COD"}
                    readOnly
                    className="mt-1 h-4 w-4 accent-clay"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Banknote size={18} className="text-clay" />
                      <span className="font-bold text-ink">Thanh toán khi nhận hàng (COD)</span>
                      <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-black text-emerald-800">
                        Khuyên dùng
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-charcoal/70">
                      Quý khách thanh toán bằng tiền mặt trực tiếp cho nhân viên giao hàng sau khi nhận và kiểm tra kiện hàng decor.
                    </p>
                  </div>
                </label>

                {/* Option 2: VNPAY & Ví điện tử (Sắp ra mắt - Disabled) */}
                <div className="flex cursor-not-allowed items-start gap-3.5 rounded-2xl border border-ink/10 bg-[#FAF8F5]/40 p-4 opacity-60">
                  <input
                    type="radio"
                    name="paymentMethod"
                    disabled
                    className="mt-1 h-4 w-4 text-charcoal/30 cursor-not-allowed"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <CreditCard size={18} className="text-charcoal/40" />
                      <span className="font-bold text-charcoal/70">VNPAY &amp; Ví điện tử</span>
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-black text-amber-800">
                        Sắp ra mắt
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-charcoal/50">
                      Cổng thanh toán trực tuyến qua VNPAY-QR, thẻ ATM nội địa và thẻ quốc tế (Visa/Mastercard) đang trong quá trình thử nghiệm.
                    </p>
                  </div>
                </div>
              </div>
            </SectionCard>
          </div>

          {/* CỘT PHẢI: TÓM TẮT ĐƠN HÀNG & NÚT ĐẶT HÀNG */}
          <div className="space-y-6">
            <SectionCard title="Tóm tắt đơn hàng">
              {/* Danh sách mặt hàng */}
              <div className="max-h-80 divide-y divide-ink/10 overflow-y-auto pr-1">
                {items.map((item) => {
                  const product = item.product;
                  const image = product?.images?.find((img) => img.is_primary)?.image_url || product?.images?.[0]?.image_url;
                  return (
                    <div key={item.id} className="flex items-center gap-3.5 py-3 first:pt-0 last:pb-0">
                      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-ink/10 bg-ivory">
                        {image ? (
                          <img src={apiAssetUrl(image)} alt={product?.name} className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-xs text-charcoal/40">Decor</div>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-bold text-ink">{product?.name || "Sản phẩm decor"}</p>
                        <p className="mt-0.5 text-xs text-charcoal/60">
                          {Number(item.unit_price).toLocaleString("vi-VN")} đ x{" "}
                          <strong className="text-ink">{item.quantity}</strong>
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-black text-ink">
                          {Number(item.subtotal).toLocaleString("vi-VN")} đ
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Cảnh báo hàng cồng kềnh nếu có */}
              {isBulky && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/80 p-3.5 text-xs text-amber-900">
                  <div className="flex items-center gap-1.5 font-bold text-amber-900">
                    <Truck size={16} className="shrink-0 text-amber-700" />
                    <span>Đơn hàng có sản phẩm cồng kềnh</span>
                  </div>
                  <p className="mt-1 text-amber-800">
                    Sản phẩm: <strong>{shippingPreview?.bulky_items?.join(", ")}</strong> cần vận chuyển chuyên dụng. Phí giao hàng sẽ được nhân viên liên hệ khảo sát và xác nhận trực tiếp trước khi giao.
                  </p>
                </div>
              )}

              {/* Chi tiết tính toán chi phí */}
              <div className="mt-5 space-y-2.5 border-t border-ink/10 pt-4 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-charcoal/70">Tạm tính tiền hàng:</span>
                  <span className="font-bold text-ink">
                    {Number(cart?.subtotal || 0).toLocaleString("vi-VN")} đ
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-charcoal/70">Phí vận chuyển:</span>
                  {isBulky ? (
                    <span className="rounded-lg bg-amber-100 px-2 py-0.5 text-xs font-black text-amber-900">
                      Chờ xác nhận phí
                    </span>
                  ) : (
                    <span className="font-bold text-ink">
                      {shippingPreview?.shipping_fee
                        ? `${Number(shippingPreview.shipping_fee).toLocaleString("vi-VN")} đ`
                        : "30.000 đ"}
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-baseline justify-between border-t border-ink/10 pt-3">
                  <div>
                    <span className="text-base font-black text-ink">Tổng thanh toán (COD):</span>
                    {isBulky && (
                      <p className="text-[11px] font-medium text-amber-800">
                        * Tạm tính hàng, chưa bao gồm phí vận chuyển cồng kềnh
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    {isBulky ? (
                      <div>
                        <span className="text-xl font-black text-clay">
                          {Number(cart?.subtotal || 0).toLocaleString("vi-VN")} đ
                        </span>
                        <span className="block text-[11px] font-bold text-charcoal/50">+ Phí vận chuyển</span>
                      </div>
                    ) : (
                      <span className="text-2xl font-black text-clay">
                        {Number(shippingPreview?.total_amount || (Number(cart?.subtotal || 0) + 30000)).toLocaleString("vi-VN")} đ
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Nút Đặt hàng */}
              <div className="mt-6 space-y-3">
                <button
                  type="submit"
                  form="checkout-form"
                  disabled={submitting}
                  className="primary-cta w-full py-3.5 text-base shadow-soft"
                >
                  {submitting ? <Loader2 size={20} className="animate-spin" /> : <ShoppingBag size={20} />}
                  {submitting ? "Đang xử lý đặt hàng..." : "Xác nhận đặt hàng (COD)"}
                </button>

                <div className="flex items-center justify-center gap-1.5 text-center text-xs text-charcoal/60">
                  <ShieldCheck size={14} className="text-emerald-600" />
                  <span>Cam kết bảo mật thông tin &amp; kiểm tra hàng trước khi thanh toán</span>
                </div>

                <Link
                  href="/cart"
                  className="secondary-cta w-full text-xs font-bold text-charcoal/70 hover:text-ink"
                >
                  <ChevronLeft size={16} /> Quay lại giỏ hàng
                </Link>
              </div>
            </SectionCard>
          </div>
        </div>
      )}
    </section>
  );
}
