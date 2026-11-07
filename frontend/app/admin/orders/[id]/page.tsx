"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import type { Order } from "@/types/api";

const STATUS_OPTIONS = ["PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "COMPLETED", "CANCELLED"];

export default function AdminOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { loading } = useAuth("ADMIN");
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
    if (!loading) load();
  }, [loading, load]);

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
      setMessage("Đã cập nhật trạng thái.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được trạng thái.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Đang kiểm tra quyền...</p>;
  if (error && !order) return <p className="text-red-600">{error}</p>;
  if (!order) return <p className="text-black/50">Đang tải...</p>;

  return (
    <section>
      <Link href="/admin/orders" className="inline-flex items-center gap-2 text-sm font-semibold text-black/60 hover:text-ink">
        <ChevronLeft size={16} /> Quản lý đơn hàng
      </Link>

      <div className="mt-4 flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold text-ink">Đơn hàng #{order.id}</h1>
          <p className="mt-2 text-sm text-black/60">
            {order.customer?.full_name || "Khách hàng"} · {order.customer?.email || `#${order.user_id}`} · {new Date(order.created_at).toLocaleString("vi-VN")}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-ink">Sản phẩm</h2>
          <div className="mt-4 space-y-3">
            {order.items.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-3 border-b border-black/5 pb-3 text-sm">
                <div className="flex min-w-0 items-center gap-3">
                  {item.product?.images?.[0]?.image_url && (
                    <img src={apiAssetUrl(item.product.images[0].image_url)} alt={item.product.name} className="h-14 w-14 rounded-md object-cover" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-ink">{item.product?.name || "Sản phẩm"}</p>
                    <p className="mt-0.5 text-black/50">{Number(item.unit_price).toLocaleString("vi-VN")} đ x{item.quantity}</p>
                  </div>
                </div>
                <p className="font-semibold text-ink">{Number(item.subtotal).toLocaleString("vi-VN")} đ</p>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
            <p className="text-sm text-black/50">Tổng tiền</p>
            <p className="mt-1 text-2xl font-bold text-clay">{Number(order.total_amount).toLocaleString("vi-VN")} đ</p>
            <p className="mt-4 text-sm text-black/50">Địa chỉ giao hàng</p>
            <p className="mt-1 text-sm text-ink">{order.shipping_address || "Chưa cung cấp"}</p>
          </div>

          <div className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
            <p className="text-sm text-black/50">Trạng thái hiện tại</p>
            <p className="mt-1 font-semibold text-ink">{displayStatus(order.status)}</p>
            <label className="mt-4 block text-sm font-semibold text-ink">
              Cập nhật trạng thái
              <select value={status} onChange={(event) => setStatus(event.target.value)} className="mt-2 w-full rounded-md border border-black/10 bg-white px-3 py-2 text-sm">
                {STATUS_OPTIONS.map((option) => <option key={option} value={option}>{displayStatus(option)}</option>)}
              </select>
            </label>
            {message && <p className="mt-3 text-sm font-semibold text-green-700">{message}</p>}
            {error && <p className="mt-3 text-sm font-semibold text-red-700">{error}</p>}
            <button onClick={updateStatus} disabled={saving} className="mt-4 w-full rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-black disabled:opacity-50">
              {saving ? "Đang lưu..." : "Lưu trạng thái"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
