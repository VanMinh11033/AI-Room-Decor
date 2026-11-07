"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, Loader2, MapPin, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { EmptyImagePlaceholder, PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { Order } from "@/types/api";

export default function OrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
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
    if (!window.confirm("Bạn muốn hủy đơn hàng này?")) return;
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

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải đơn hàng...</p>;
  if (error || !order) return <p className="text-red-600">{error || "Không tìm thấy đơn hàng"}</p>;

  return (
    <section className="space-y-7">
      <Link href="/orders" className="inline-flex items-center gap-2 text-sm font-bold text-charcoal/60 hover:text-ink">
        <ChevronLeft size={16} /> Đơn hàng của tôi
      </Link>

      <PageHeader
        eyebrow={displayStatus(order.status)}
        title={`Đơn hàng #${order.id}`}
        description={`Đặt lúc ${new Date(order.created_at).toLocaleString("vi-VN")}`}
      />

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{error}</div>}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <SectionCard title="Sản phẩm">
          <div className="space-y-4">
            {order.items.map((item) => {
              const product = item.product;
              const image = product?.images.find((img) => img.is_primary)?.image_url || product?.images[0]?.image_url;
              return (
                <div key={item.id} className="flex items-center gap-4">
                  <Link href={product ? `/products/${product.id}` : "#"} className="h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-ivory">
                    {image ? <img src={apiAssetUrl(image)} alt={product?.name} className="h-full w-full object-cover" /> : <EmptyImagePlaceholder />}
                  </Link>
                  <div className="min-w-0 flex-1">
                    <Link href={product ? `/products/${product.id}` : "#"} className="block truncate font-bold text-ink hover:underline">
                      {product?.name || "Sản phẩm"}
                    </Link>
                    <p className="mt-0.5 text-sm text-charcoal/55">{Number(item.unit_price).toLocaleString("vi-VN")} đ x{item.quantity}</p>
                  </div>
                  <p className="font-black text-ink">{Number(item.subtotal).toLocaleString("vi-VN")} đ</p>
                </div>
              );
            })}
          </div>
        </SectionCard>

        <aside className="space-y-5">
          <SectionCard title="Thông tin giao hàng">
            <div className="flex items-start gap-3 text-sm text-charcoal/70">
              <MapPin size={18} className="mt-0.5 shrink-0 text-clay" />
              <span>{order.shipping_address || "Chưa cung cấp địa chỉ giao hàng"}</span>
            </div>
          </SectionCard>

          <SectionCard title="Thanh toán">
            <div className="flex items-center justify-between border-b border-ink/10 pb-3">
              <span className="text-sm text-charcoal/60">Trạng thái</span>
              <span className="font-black text-clay">{displayStatus(order.status)}</span>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <span className="font-black text-ink">Tổng cộng</span>
              <span className="text-2xl font-black text-clay">{Number(order.total_amount).toLocaleString("vi-VN")} đ</span>
            </div>
            {order.status === "PENDING" && (
              <button type="button" onClick={cancelOrder} disabled={cancelling} className="secondary-cta mt-5 w-full text-red-600">
                {cancelling ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />} Hủy đơn hàng
              </button>
            )}
          </SectionCard>
        </aside>
      </div>
    </section>
  );
}
