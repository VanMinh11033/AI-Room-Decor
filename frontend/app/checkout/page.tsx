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
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import {
  VIETNAM_34_PROVINCES,
  getCanonicalProvinceName,
  getWardsForProvince,
  isHistoricalProvince,
  loadWardsForProvince,
  resolveProvince,
  validateProvinceWardMatch,
} from "@/lib/addressData";
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

  // Dynamic detection of historical vs current 2025 province
  const historicalInfo = useMemo(() => isHistoricalProvince(province), [province]);

  // Idempotency key per checkout attempt
  const [idempotencyKey] = useState<string>(() => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `ord_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  });

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

  const [availableWards, setAvailableWards] = useState<string[]>([]);

  useEffect(() => {
    let isMounted = true;
    if (province.trim()) {
      // 1. Nạp danh mục cơ sở đồng bộ
      const syncWards = getWardsForProvince(province);
      setAvailableWards(syncWards);

      // 2. Tải lười (lazy load) toàn bộ danh mục cấp xã/phường phân vùng theo tỉnh chuẩn NQ 202/2025
      loadWardsForProvince(province).then((fullWards) => {
        if (isMounted && fullWards && fullWards.length > 0) {
          setAvailableWards(fullWards);
        }
      });
    } else {
      setAvailableWards([]);
    }
    return () => {
      isMounted = false;
    };
  }, [province]);

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
      errors.recipientPhone = "Số điện thoại di động không hợp lệ (ví dụ: 0912345678 hoặc +84912345678).";
    }

    if (!province.trim()) {
      errors.province = "Vui lòng chọn hoặc nhập Tỉnh / Thành phố.";
    } else {
      const resolved = resolveProvince(province);
      if (!resolved && province.trim().length < 2) {
        errors.province = "Tên Tỉnh / Thành phố không hợp lệ.";
      }
    }

    if (!ward.trim()) {
      errors.ward = "Vui lòng chọn hoặc nhập Phường / Xã.";
    } else if (province.trim() && !validateProvinceWardMatch(province, ward, availableWards)) {
      errors.ward = "Phường / Xã không thuộc địa bàn Tỉnh / Thành phố đã chọn.";
    }

    if (!streetAddress.trim() || streetAddress.trim().length < 3) {
      errors.streetAddress = "Vui lòng nhập số nhà, tên đường chi tiết (tối thiểu 3 ký tự).";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return; // Prevent double submit
    if (!validateForm()) {
      setError("Vui lòng kiểm tra và điền đầy đủ các thông tin giao nhận bắt buộc bên dưới.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const resolved = resolveProvince(province);
      const canonicalProvince = resolved ? resolved.name : getCanonicalProvinceName(province) || province.trim();
      let finalNotes = deliveryNotes.trim();
      if (resolved && resolved.name.toLowerCase() !== province.trim().toLowerCase()) {
        const histNote = `Địa chỉ lịch sử: ${province.trim()}`;
        finalNotes = finalNotes ? `${finalNotes} (${histNote})` : histNote;
      }

      const payload = {
        recipient_name: recipientName.trim(),
        recipient_phone: recipientPhone.trim().replace(/[\s.-]/g, ""),
        province: canonicalProvince,
        ward: ward.trim(),
        street_address: streetAddress.trim(),
        delivery_notes: finalNotes || null,
        payment_method: "COD",
        idempotency_key: idempotencyKey,
      };

      const order = await apiFetch<Order>("/api/orders", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      router.push(`/orders/${order.id}?checkout_success=1`);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "";
      if (errMsg.toLowerCase().includes("cart is empty") || errMsg.toLowerCase().includes("giỏ hàng trống")) {
        setError("Giỏ hàng hiện tại trống hoặc đơn hàng vừa được xử lý thành công. Quý khách vui lòng kiểm tra danh sách 'Đơn hàng của tôi' để xác nhận trạng thái.");
      } else {
        setError(errMsg || "Không thể tạo đơn hàng do gián đoạn kết nối. Quý khách vui lòng kiểm tra kết nối mạng và thử lại.");
      }
      setSubmitting(false);
    }
  }

  const items = useMemo(() => cart?.items || [], [cart]);
  const isBulky = shippingPreview?.is_bulky ?? false;
  const subtotal = Number(cart?.subtotal || 0);

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[55vh] flex-col items-center justify-center gap-3">
        <Loader2 size={32} className="animate-spin text-[#8A6B4E]" />
        <p className="font-serif text-sm tracking-wide text-[#5A6258]">Đang chuẩn bị trang thanh toán...</p>
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-6xl space-y-8 pb-16">
      <EditorialHeading
        eyebrow="Thanh toán COD an toàn"
        title="Xác nhận đơn hàng nội thất"
        subtitle="Kiểm tra danh mục sản phẩm, cung cấp thông tin nhận hàng và chọn phương thức thanh toán tận nơi."
      />

      {error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50/90 p-4 text-sm font-semibold text-red-800 shadow-sm"
        >
          <AlertCircle size={20} className="shrink-0 text-red-600 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {items.length === 0 && !error ? (
        <div className="rounded-3xl border border-[#DDD7CD] bg-white p-12 text-center shadow-card">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#FBF9F5] text-[#5A6258]">
            <Package size={32} />
          </div>
          <h2 className="mt-4 font-serif text-xl font-bold text-[#242B23]">Giỏ hàng của bạn đang trống</h2>
          <p className="mt-1 text-sm text-[#5A6258]">Hãy khám phá bộ sưu tập nội thất độc bản để chọn món đồ yêu thích.</p>
          <div className="mt-6">
            <Link href="/products">
              <LuxuryButton variant="primary">Khám phá sản phẩm</LuxuryButton>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.3fr_0.9fr] w-full min-w-0">
          {/* CỘT TRÁI: FORM GIAO NHẬN VÀ PHƯƠNG THỨC THANH TOÁN */}
          <div className="space-y-6">
            {/* 1. THÔNG TIN NGƯỜI NHẬN */}
            <div className="rounded-3xl border border-[#DDD7CD] bg-white p-6 sm:p-7 shadow-card">
              <div className="flex items-center gap-2 border-b border-[#DDD7CD]/60 pb-4">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#242B23] text-xs font-bold text-white">
                  1
                </span>
                <h2 className="font-serif text-lg font-bold text-[#242B23]">Thông tin giao nhận hàng</h2>
              </div>

              <form id="checkout-form" onSubmit={onSubmit} className="mt-6 space-y-5">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label htmlFor="recipient-name" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
                      Họ và tên người nhận <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="recipient-name"
                      type="text"
                      required
                      value={recipientName}
                      onChange={(e) => {
                        setRecipientName(e.target.value);
                        if (fieldErrors.recipientName) setFieldErrors((prev) => ({ ...prev, recipientName: "" }));
                      }}
                      placeholder="Nguyễn Văn A"
                      className={`premium-input w-full ${fieldErrors.recipientName ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    {fieldErrors.recipientName && (
                      <p className="text-xs font-semibold text-red-600">{fieldErrors.recipientName}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="recipient-phone" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
                      Số điện thoại di động <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="recipient-phone"
                      type="tel"
                      required
                      value={recipientPhone}
                      onChange={(e) => {
                        setRecipientPhone(e.target.value);
                        if (fieldErrors.recipientPhone) setFieldErrors((prev) => ({ ...prev, recipientPhone: "" }));
                      }}
                      placeholder="0912 345 678"
                      className={`premium-input w-full ${fieldErrors.recipientPhone ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    {fieldErrors.recipientPhone && (
                      <p className="text-xs font-semibold text-red-600">{fieldErrors.recipientPhone}</p>
                    )}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label htmlFor="province-input" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
                        Tỉnh / Thành phố <span className="text-red-500">*</span>
                      </label>
                      <span className="text-[10px] text-[#8A6B4E] font-medium">Chuẩn 34 Tỉnh / TP (2025)</span>
                    </div>
                    <input
                      id="province-input"
                      list="vietnam-provinces"
                      type="text"
                      required
                      value={province}
                      onChange={(e) => {
                        const newProv = e.target.value;
                        setProvince(newProv);
                        if (fieldErrors.province) setFieldErrors((prev) => ({ ...prev, province: "" }));
                      }}
                      placeholder="Chọn hoặc nhập Tỉnh / Thành phố"
                      className={`premium-input w-full ${fieldErrors.province ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    <datalist id="vietnam-provinces">
                      {VIETNAM_34_PROVINCES.map((prov) => (
                        <option key={prov.id} value={prov.name}>
                          {prov.name} ({prov.code}) {prov.mergedFrom.length > 1 ? `— gồm ${prov.mergedFrom.join(", ")} cũ` : ""}
                        </option>
                      ))}
                      {/* Danh mục tra cứu nhanh địa danh lịch sử sáp nhập */}
                      {VIETNAM_34_PROVINCES.flatMap((p) =>
                        p.mergedFrom
                          .filter((m) => m.toLowerCase() !== p.shortName.toLowerCase())
                          .map((m) => (
                            <option key={`${p.id}-${m}`} value={m}>
                              {m} (nay thuộc {p.name})
                            </option>
                          ))
                      )}
                    </datalist>
                    {historicalInfo.isHistorical && historicalInfo.currentProvince && (
                      <p className="text-[11px] font-medium text-[#8A6B4E] bg-[#FBF9F5] p-2 rounded-lg border border-[#8A6B4E]/30">
                        💡 {historicalInfo.message} Đơn hàng sẽ được tự động chuyển tới {historicalInfo.currentProvince.name}.
                      </p>
                    )}
                    {fieldErrors.province && (
                      <p className="text-xs font-semibold text-red-600">{fieldErrors.province}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="ward-input" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
                      Phường / Xã <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="ward-input"
                      list="vietnam-wards"
                      type="text"
                      required
                      value={ward}
                      onChange={(e) => {
                        setWard(e.target.value);
                        if (fieldErrors.ward) setFieldErrors((prev) => ({ ...prev, ward: "" }));
                      }}
                      placeholder={availableWards.length > 0 ? "Chọn hoặc nhập Phường / Xã" : "Nhập Phường / Xã"}
                      className={`premium-input w-full ${fieldErrors.ward ? "border-red-500 focus:border-red-500" : ""}`}
                    />
                    <datalist id="vietnam-wards">
                      {availableWards.map((w) => (
                        <option key={w} value={w} />
                      ))}
                    </datalist>
                    {fieldErrors.ward && (
                      <p className="text-xs font-semibold text-red-600">{fieldErrors.ward}</p>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="street-address" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
                    Số nhà, tên đường, khu căn hộ <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="street-address"
                    type="text"
                    required
                    value={streetAddress}
                    onChange={(e) => {
                      setStreetAddress(e.target.value);
                      if (fieldErrors.streetAddress) setFieldErrors((prev) => ({ ...prev, streetAddress: "" }));
                    }}
                    placeholder="Số 45/2 Nguyễn Thị Minh Khai, Tòa Landmark 2..."
                    className={`premium-input w-full ${fieldErrors.streetAddress ? "border-red-500 focus:border-red-500" : ""}`}
                  />
                  {fieldErrors.streetAddress && (
                    <p className="text-xs font-semibold text-red-600">{fieldErrors.streetAddress}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="delivery-notes" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
                      Ghi chú giao hàng (không bắt buộc)
                    </label>
                    <span className="text-[11px] text-[#5A6258]">{deliveryNotes.length}/500</span>
                  </div>
                  <textarea
                    id="delivery-notes"
                    rows={2}
                    maxLength={500}
                    value={deliveryNotes}
                    onChange={(e) => setDeliveryNotes(e.target.value)}
                    placeholder="Ví dụ: Giao giờ hành chính, gọi trước khi đến 15 phút, gửi sảnh lễ tân..."
                    className="premium-input w-full resize-none text-sm"
                  />
                </div>
              </form>
            </div>

            {/* 2. PHƯƠNG THỨC THANH TOÁN (CHỈ COD HOẠT ĐỘNG) */}
            <div className="rounded-3xl border border-[#DDD7CD] bg-white p-6 sm:p-7 shadow-card">
              <div className="flex items-center gap-2 border-b border-[#DDD7CD]/60 pb-4">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#242B23] text-xs font-bold text-white">
                  2
                </span>
                <h2 className="font-serif text-lg font-bold text-[#242B23]">Phương thức thanh toán</h2>
              </div>

              <div className="mt-5 space-y-3">
                {/* Phương thức 1: COD (Khuyên dùng & Active) */}
                <label className="flex cursor-pointer items-start gap-4 rounded-2xl border-2 border-[#8A6B4E] bg-[#FBF9F5] p-4.5 shadow-sm transition hover:border-[#8A6B4E]/80">
                  <input
                    type="radio"
                    name="paymentMethod"
                    value="COD"
                    checked={paymentMethod === "COD"}
                    readOnly
                    className="mt-1 h-4 w-4 accent-[#8A6B4E]"
                  />
                  <div className="flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Banknote size={18} className="text-[#8A6B4E]" />
                      <span className="font-bold text-[#242B23]">Thanh toán khi nhận hàng (COD)</span>
                      <span className="rounded-full bg-[#EBF6EE] px-2.5 py-0.5 text-[11px] font-bold text-[#1E6B37]">
                        Khuyên dùng
                      </span>
                    </div>
                    <p className="text-xs text-[#5A6258] leading-relaxed">
                      Quý khách kiểm tra sản phẩm nội thất cùng nhân viên giao hàng trước khi thanh toán tiền mặt trực tiếp.
                    </p>
                  </div>
                </label>

                {/* Phương thức 2: VNPAY & Thẻ trực tuyến (Disabled - Sắp ra mắt) */}
                <div className="flex cursor-not-allowed items-start gap-4 rounded-2xl border border-[#DDD7CD]/70 bg-[#FBF9F5]/40 p-4.5 opacity-60">
                  <input
                    type="radio"
                    name="paymentMethod"
                    disabled
                    className="mt-1 h-4 w-4 text-[#5A6258]/30 cursor-not-allowed"
                  />
                  <div className="flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <CreditCard size={18} className="text-[#5A6258]" />
                      <span className="font-bold text-[#5A6258]">VNPAY &amp; Thẻ ngân hàng / Ví điện tử</span>
                      <span className="rounded-full bg-[#FEF7E6] px-2.5 py-0.5 text-[10px] font-bold text-[#9E5600]">
                        Sắp ra mắt
                      </span>
                    </div>
                    <p className="text-xs text-[#5A6258]/80 leading-relaxed">
                      Cổng thanh toán trực tuyến qua VNPAY-QR, thẻ ATM nội địa và thẻ quốc tế (Visa/Mastercard) đang trong quá trình tích hợp bảo mật.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* CỘT PHẢI: TÓM TẮT ĐƠN HÀNG & NÚT ĐẶT HÀNG */}
          <div className="space-y-6">
            <div className="rounded-3xl border border-[#DDD7CD] bg-white p-6 sm:p-7 shadow-card">
              <div className="flex items-center justify-between border-b border-[#DDD7CD]/60 pb-4">
                <h2 className="font-serif text-lg font-bold text-[#242B23]">Tóm tắt kiện hàng</h2>
                <span className="text-xs font-semibold text-[#8A6B4E]">
                  {items.reduce((sum, item) => sum + item.quantity, 0)} món đồ
                </span>
              </div>

              {/* Danh sách mặt hàng */}
              <div className="max-h-80 divide-y divide-[#DDD7CD]/60 overflow-y-auto pr-1">
                {items.map((item) => {
                  const product = item.product;
                  const image = product?.images?.find((img) => img.is_primary)?.image_url || product?.images?.[0]?.image_url;
                  return (
                    <div key={item.id} className="flex items-center gap-3.5 py-3.5 first:pt-3 last:pb-0">
                      <div className="h-16 w-20 shrink-0 overflow-hidden rounded-xl border border-[#DDD7CD]/70 bg-[#FBF9F5]">
                        {image ? (
                          <img
                            src={apiAssetUrl(image)}
                            alt={product?.name || "Sản phẩm"}
                            className="h-full w-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-[10px] text-[#5A6258]/60">
                            Decor
                          </div>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-[#242B23]">{product?.name || "Sản phẩm decor"}</p>
                        <p className="mt-0.5 text-xs text-[#5A6258]">
                          {Number(item.unit_price).toLocaleString("vi-VN")} đ ×{" "}
                          <strong className="text-[#242B23]">{item.quantity}</strong>
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold text-[#242B23]">
                          {Number(item.subtotal).toLocaleString("vi-VN")} đ
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Thông báo vận chuyển hàng cồng kềnh */}
              {isBulky && (
                <div className="mt-5 rounded-2xl border border-amber-300 bg-amber-50/90 p-4 text-xs text-amber-950">
                  <div className="flex items-center gap-2 font-bold text-amber-900">
                    <Truck size={17} className="shrink-0 text-amber-700" />
                    <span>Đơn hàng có sản phẩm cồng kềnh</span>
                  </div>
                  <p className="mt-1.5 leading-relaxed text-amber-900">
                    Sản phẩm: <strong>{shippingPreview?.bulky_items?.join(", ")}</strong> cần xe chuyên dụng và đội ngũ khuân vác. Phí vận chuyển sẽ được chuyên viên CSKH liên hệ khảo sát lộ trình và báo phí trực tiếp trước khi giao.
                  </p>
                </div>
              )}

              {/* Chi tiết tài chính */}
              <div className="mt-5 space-y-2.5 border-t border-[#DDD7CD]/60 pt-4 text-sm">
                <div className="flex items-center justify-between text-[#5A6258]">
                  <span>Tạm tính tiền hàng:</span>
                  <span className="font-semibold text-[#242B23]">
                    {subtotal.toLocaleString("vi-VN")} đ
                  </span>
                </div>

                <div className="flex items-center justify-between text-[#5A6258]">
                  <span>Phí vận chuyển:</span>
                  {isBulky ? (
                    <span className="rounded-lg bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-900">
                      Chờ CSKH báo phí
                    </span>
                  ) : (
                    <span className="font-semibold text-[#242B23]">
                      {shippingPreview?.shipping_fee
                        ? `${Number(shippingPreview.shipping_fee).toLocaleString("vi-VN")} đ`
                        : "30.000 đ"}
                    </span>
                  )}
                </div>

                <div className="mt-4 flex items-baseline justify-between border-t border-[#DDD7CD]/60 pt-3">
                  <div>
                    <span className="font-serif text-base font-bold text-[#242B23]">Tổng thanh toán COD:</span>
                    {isBulky && (
                      <p className="text-[11px] font-medium text-amber-800">
                        * Tạm tính tiền hàng, chưa gồm phí vận chuyển cồng kềnh
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    {isBulky ? (
                      <div>
                        <span className="font-serif text-xl font-bold text-[#8A6B4E]">
                          {subtotal.toLocaleString("vi-VN")} đ
                        </span>
                        <span className="block text-[11px] font-medium text-[#5A6258]">+ Phí vận chuyển</span>
                      </div>
                    ) : (
                      <span className="font-serif text-2xl font-bold text-[#8A6B4E]">
                        {Number(shippingPreview?.total_amount || (subtotal + 30000)).toLocaleString("vi-VN")} đ
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Nút đặt hàng */}
              <div className="mt-6 space-y-3">
                <LuxuryButton
                  type="submit"
                  form="checkout-form"
                  variant="bronze"
                  size="lg"
                  loading={submitting}
                  className="w-full text-base font-bold"
                  icon={<ShoppingBag size={20} />}
                >
                  {submitting ? "Đang xử lý đơn hàng..." : "Xác nhận đặt hàng (COD)"}
                </LuxuryButton>

                <div className="flex items-center justify-center gap-1.5 text-center text-xs text-[#5A6258]">
                  <ShieldCheck size={14} className="text-[#1E6B37]" />
                  <span>Cam kết bảo mật thông tin &amp; đồng kiểm tra hàng trước khi thanh toán</span>
                </div>

                <div className="pt-2">
                  <Link
                    href="/cart"
                    className="flex items-center justify-center gap-1 text-xs font-semibold text-[#5A6258] hover:text-[#242B23] transition-colors"
                  >
                    <ChevronLeft size={16} /> Quay lại kiểm tra giỏ hàng
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
