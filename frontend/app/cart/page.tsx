"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Minus,
  Package,
  Plus,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Trash2,
  Truck,
} from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiAssetUrl, apiFetch, getAccessToken } from "@/lib/api";
import { displayCategory } from "@/lib/display";
import type { Cart, CartItem } from "@/types/api";

function CartContent() {
  const searchParams = useSearchParams();
  const [isGuest, setIsGuest] = useState(false);
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  // Dialog state
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [itemToRemove, setItemToRemove] = useState<CartItem | null>(null);
  const [removingAction, setRemovingAction] = useState(false);

  const justAdded = searchParams.get("added") === "1" || searchParams.get("added") === "true";

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setIsGuest(true);
      setLoading(false);
      return;
    }

    setIsGuest(false);
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
    load();
  }, [load]);

  async function updateQuantity(itemId: number, quantity: number) {
    if (quantity < 1) return;
    setBusy(itemId);
    setError("");
    try {
      setCart(
        await apiFetch<Cart>(`/api/cart/items/${itemId}`, {
          method: "PATCH",
          body: JSON.stringify({ quantity }),
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được số lượng.");
    } finally {
      setBusy(null);
    }
  }

  async function handleConfirmRemoveItem() {
    if (!itemToRemove) return;
    setRemovingAction(true);
    setError("");
    try {
      setCart(await apiFetch<Cart>(`/api/cart/items/${itemToRemove.id}`, { method: "DELETE" }));
      setItemToRemove(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xóa được sản phẩm.");
    } finally {
      setRemovingAction(false);
    }
  }

  async function handleConfirmClearCart() {
    setRemovingAction(true);
    setError("");
    try {
      setCart(await apiFetch<Cart>("/api/cart", { method: "DELETE" }));
      setConfirmClearOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xóa được giỏ hàng.");
    } finally {
      setRemovingAction(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#8A6B4E] border-t-transparent" />
        <p className="text-sm font-medium text-[#5A6258]">Đang tải giỏ hàng của bạn...</p>
      </div>
    );
  }

  // 1. Dedicated Guest Cart Guidance View
  if (isGuest) {
    return (
      <div className="space-y-8 pb-16">
        <EditorialHeading
          eyebrow="GIỎ HÀNG NỘI THẤT"
          title="Giỏ hàng của bạn"
          subtitle="Đăng nhập để đồng bộ các sản phẩm catalog bạn đã lựa chọn và tiến hành đặt hàng COD."
        />

        <div className="mx-auto max-w-xl rounded-2xl border border-[#242B23]/10 bg-white p-8 sm:p-12 text-center shadow-card space-y-6">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#F7F4EE] text-[#8A6B4E] border border-[#8A6B4E]/20 shadow-xs">
            <ShoppingCart size={28} />
          </div>

          <div className="space-y-2">
            <h2 className="font-serif text-2xl font-bold text-[#242B23]">
              Bạn đang duyệt với tư cách Khách
            </h2>
            <p className="text-sm leading-relaxed text-[#5A6258] max-w-md mx-auto">
              Giỏ hàng trực tuyến được đồng bộ an toàn theo tài khoản để bảo đảm số lượng tồn kho thực tế, bảo lưu ưu đãi thiết kế và hỗ trợ thanh toán tận nơi COD.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link href="/login?redirect=/cart" className="w-full sm:w-auto">
              <LuxuryButton variant="primary" size="md" className="w-full">
                <span>Đăng nhập ngay</span>
                <ArrowRight size={16} />
              </LuxuryButton>
            </Link>
            <Link href="/products" className="w-full sm:w-auto">
              <LuxuryButton variant="secondary" size="md" className="w-full">
                Khám phá bộ sưu tập
              </LuxuryButton>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const items = cart?.items || [];
  const isEmpty = items.length === 0;

  return (
    <div className="space-y-8 pb-16 w-full min-w-0">
      {/* Editorial Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <EditorialHeading
          eyebrow="GIỎ HÀNG & THANH TOÁN"
          title="Giỏ hàng nội thất"
          subtitle={
            isEmpty
              ? "Chưa có sản phẩm nào trong giỏ hàng."
              : `Bạn đang có ${items.length} món đồ nội thất sẵn sàng đặt hàng COD.`
          }
        />
        {!isEmpty && (
          <button
            type="button"
            onClick={() => setConfirmClearOpen(true)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#5A6258] hover:text-[#B3261E] transition self-start sm:self-auto"
          >
            <Trash2 size={14} />
            <span>Xóa toàn bộ giỏ hàng</span>
          </button>
        )}
      </div>

      {/* Just added confirmation banner */}
      {justAdded && (
        <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 text-xs font-semibold text-emerald-800">
          <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
          <span>Sản phẩm catalog đã được thêm vào giỏ hàng thành công.</span>
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50/80 p-4 text-xs font-semibold text-red-700">
          {error}
        </div>
      )}

      {/* 2. Empty State */}
      {isEmpty ? (
        <div className="rounded-2xl border border-[#242B23]/10 bg-white p-10 sm:p-16 text-center shadow-card space-y-6">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#F7F4EE] text-[#5A6258]/60">
            <ShoppingBag size={30} />
          </div>
          <div className="space-y-2">
            <h2 className="font-serif text-2xl font-bold text-[#242B23]">
              Giỏ hàng của bạn đang trống
            </h2>
            <p className="text-sm text-[#5A6258] max-w-md mx-auto">
              Hãy khám phá các tuyệt tác nội thất từ catalog chuẩn hoặc bắt đầu phối cảnh AI để tìm những món đồ hoàn hảo nhất cho căn phòng của bạn.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-3 pt-2">
            <Link href="/products">
              <LuxuryButton variant="primary" size="md">
                Khám phá bộ sưu tập nội thất
              </LuxuryButton>
            </Link>
            <Link href="/room-projects">
              <LuxuryButton variant="secondary" size="md">
                Vào Studio thiết kế phòng
              </LuxuryButton>
            </Link>
          </div>
        </div>
      ) : (
        /* 3. Populated Cart Grid (8 cols items + 4 cols summary) */
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 items-start w-full min-w-0">
          {/* Left Column: Cart Items List */}
          <div className="w-full min-w-0 lg:col-span-8 space-y-4">
            {items.map((item) => {
              const product = item.product;
              const primaryImage =
                product?.images?.find((img) => img.is_primary)?.image_url ||
                product?.images?.[0]?.image_url;
              const isItemBusy = busy === item.id;
              const stock = product?.stock_quantity ?? 0;
              const isOutOfStock = stock <= 0;
              const isLowStock = stock > 0 && stock <= 3;

              return (
                <div
                  key={item.id}
                  className="flex flex-col sm:flex-row gap-4 sm:gap-5 rounded-2xl border border-[#242B23]/10 bg-white p-4 sm:p-5 shadow-sm transition hover:border-[#8A6B4E]/30"
                >
                  {/* Thumbnail */}
                  <Link
                    href={`/products/${item.product_id}`}
                    className="relative aspect-[4/3] w-full sm:w-36 shrink-0 overflow-hidden rounded-xl bg-[#F7F4EE]"
                  >
                    {primaryImage ? (
                      <img
                        src={apiAssetUrl(primaryImage)}
                        alt={product?.name || "Sản phẩm nội thất"}
                        className="h-full w-full object-cover transition duration-300 hover:scale-105"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-[#5A6258]">
                        Chưa có ảnh
                      </div>
                    )}
                  </Link>

                  {/* Details */}
                  <div className="flex flex-1 flex-col justify-between min-w-0">
                    <div>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          {product?.category && (
                            <span className="text-[10px] font-bold uppercase tracking-wider text-[#8A6B4E]">
                              {displayCategory(product.category.name)}
                            </span>
                          )}
                          <Link
                            href={`/products/${item.product_id}`}
                            className="block font-serif text-base sm:text-lg font-bold text-[#242B23] hover:text-[#8A6B4E] transition truncate"
                          >
                            {product?.name || `Sản phẩm #${item.product_id}`}
                          </Link>
                        </div>
                        <button
                          type="button"
                          onClick={() => setItemToRemove(item)}
                          disabled={isItemBusy}
                          aria-label={`Xóa ${product?.name || "sản phẩm"} khỏi giỏ`}
                          className="rounded-lg p-1.5 text-[#5A6258] transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50 shrink-0"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>

                      {/* Stock Badge */}
                      <div className="mt-2 flex items-center gap-2">
                        {isOutOfStock ? (
                          <StatusBadge variant="rejected" label="Tạm hết hàng" />
                        ) : isLowStock ? (
                          <StatusBadge variant="fallback" label={`Chỉ còn ${stock} món`} />
                        ) : (
                          <StatusBadge variant="verified" label="Còn hàng sẵn" />
                        )}
                      </div>
                    </div>

                    {/* Price & Quantity Controls */}
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-[#242B23]/5 pt-3">
                      {/* Quantity Selector */}
                      <div className="flex items-center gap-1.5 rounded-xl border border-[#242B23]/10 bg-[#F7F4EE] p-1">
                        <button
                          type="button"
                          onClick={() => updateQuantity(item.id, item.quantity - 1)}
                          disabled={isItemBusy || item.quantity <= 1}
                          aria-label="Giảm số lượng"
                          className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-[#242B23] shadow-xs transition hover:bg-[#8A6B4E] hover:text-white disabled:opacity-40 disabled:hover:bg-white disabled:hover:text-[#242B23]"
                        >
                          <Minus size={14} />
                        </button>
                        <span className="w-9 text-center font-serif text-sm font-bold text-[#242B23]">
                          {isItemBusy ? "..." : item.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => updateQuantity(item.id, item.quantity + 1)}
                          disabled={isItemBusy || (stock > 0 && item.quantity >= stock)}
                          aria-label="Tăng số lượng"
                          className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-[#242B23] shadow-xs transition hover:bg-[#8A6B4E] hover:text-white disabled:opacity-40 disabled:hover:bg-white disabled:hover:text-[#242B23]"
                        >
                          <Plus size={14} />
                        </button>
                      </div>

                      {/* Line Item Subtotal */}
                      <div className="text-right">
                        <span className="text-[10px] text-[#5A6258] block">Thành tiền</span>
                        <span className="font-serif text-base sm:text-lg font-bold text-[#8A6B4E]">
                          {Number(item.subtotal).toLocaleString("vi-VN")} ₫
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Order Summary Card */}
          <aside className="w-full min-w-0 lg:col-span-4 sticky top-6 space-y-4">
            <div className="rounded-2xl border border-[#242B23]/10 bg-white p-6 shadow-card space-y-5">
              <h3 className="font-serif text-lg font-bold text-[#242B23] border-b border-[#242B23]/10 pb-3">
                Tóm tắt đơn hàng
              </h3>

              <div className="space-y-3 text-xs text-[#5A6258]">
                <div className="flex items-center justify-between">
                  <span>Tạm tính ({items.length} món)</span>
                  <span className="font-bold text-[#242B23]">
                    {Number(cart?.subtotal || 0).toLocaleString("vi-VN")} ₫
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Phí vận chuyển tiêu chuẩn</span>
                  <span className="font-bold text-emerald-700">Miễn phí toàn quốc</span>
                </div>
                <div className="rounded-xl border border-[#8A6B4E]/15 bg-[#F7F4EE] p-3 text-[11px] text-[#5A6258] leading-relaxed">
                  <div className="flex items-center gap-1.5 font-bold text-[#242B23]">
                    <Truck size={14} className="text-[#8A6B4E]" />
                    <span>Chính sách giao hàng nội thất</span>
                  </div>
                  <p className="mt-1">
                    Giao hàng COD tận nơi toàn quốc. Với các món đồ kích thước lớn (sofa lớn, tủ kệ), chuyên viên điều phối sẽ liên hệ để xác nhận phương án và hỗ trợ lắp đặt.
                  </p>
                </div>
              </div>

              <div className="border-t border-[#242B23]/10 pt-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm font-bold text-[#242B23]">Tổng thanh toán dự kiến</span>
                  <span className="font-serif text-xl sm:text-2xl font-bold text-[#8A6B4E]">
                    {Number(cart?.subtotal || 0).toLocaleString("vi-VN")} ₫
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-[#5A6258]">
                  Thanh toán bằng tiền mặt khi nhận hàng (COD).
                </p>
              </div>

              <Link href="/checkout" className="block w-full pt-1">
                <LuxuryButton variant="primary" size="lg" className="w-full shadow-lg group">
                  <span>Tiến hành đặt hàng COD</span>
                  <ChevronRight size={18} className="transition-transform group-hover:translate-x-0.5" />
                </LuxuryButton>
              </Link>

              {/* Guarantees */}
              <div className="pt-2 border-t border-[#242B23]/5 space-y-2 text-[11px] text-[#5A6258]">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={14} className="text-[#8A6B4E] shrink-0" />
                  <span>Cam kết chất lượng 100% chuẩn catalog độc bản</span>
                </div>
                <div className="flex items-center gap-2">
                  <Package size={14} className="text-[#8A6B4E] shrink-0" />
                  <span>Kiểm tra hàng trước khi thanh toán tiền mặt</span>
                </div>
              </div>
            </div>
          </aside>
        </div>
      )}

      {/* Accessible Confirm Dialog: Remove Single Item */}
      <ConfirmDialog
        isOpen={Boolean(itemToRemove)}
        onClose={() => setItemToRemove(null)}
        onConfirm={handleConfirmRemoveItem}
        title="Xóa sản phẩm khỏi giỏ hàng?"
        description={`Bạn có chắc chắn muốn bỏ "${itemToRemove?.product?.name || "sản phẩm này"}" ra khỏi giỏ hàng?`}
        confirmLabel="Xóa sản phẩm"
        cancelLabel="Giữ lại"
        variant="danger"
        loading={removingAction}
      />

      {/* Accessible Confirm Dialog: Clear Entire Cart */}
      <ConfirmDialog
        isOpen={confirmClearOpen}
        onClose={() => setConfirmClearOpen(false)}
        onConfirm={handleConfirmClearCart}
        title="Xóa toàn bộ giỏ hàng?"
        description="Thao tác này sẽ dọn sạch tất cả sản phẩm trong giỏ hàng của bạn. Bạn sẽ cần chọn lại sản phẩm từ catalog."
        confirmLabel="Xóa tất cả"
        cancelLabel="Hủy bỏ"
        variant="danger"
        loading={removingAction}
      />
    </div>
  );
}

export default function CartPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#8A6B4E] border-t-transparent" />
          <p className="text-sm font-medium text-[#5A6258]">Đang tải giỏ hàng...</p>
        </div>
      }
    >
      <CartContent />
    </Suspense>
  );
}
