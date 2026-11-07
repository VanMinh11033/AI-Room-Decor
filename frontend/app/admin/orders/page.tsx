"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import type { Order, OrderListResponse } from "@/types/api";

export default function AdminOrdersPage() {
  const { loading } = useAuth("ADMIN");
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<OrderListResponse>("/api/admin/orders")
      .then((data) => setOrders(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được đơn hàng."));
  }, []);

  if (loading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <section>
      <h1 className="text-3xl font-bold text-ink">Quản lý đơn hàng</h1>
      <p className="mt-2 text-sm text-black/60">Xem chi tiết và cập nhật trạng thái các đơn hàng.</p>

      {error && <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</p>}

      <div className="mt-6 overflow-hidden rounded-lg border border-black/10 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-black/5">
            <tr>
              <th className="p-3">Mã đơn</th>
              <th className="p-3">Khách hàng</th>
              <th className="p-3">Sản phẩm</th>
              <th className="p-3">Tổng tiền</th>
              <th className="p-3">Trạng thái</th>
              <th className="p-3">Thời gian</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id} className="border-t border-black/10 hover:bg-black/5">
                <td className="p-3"><Link href={`/admin/orders/${order.id}`} className="font-semibold text-clay hover:underline">#{order.id}</Link></td>
                <td className="p-3">
                  <p className="font-semibold text-ink">{order.customer?.full_name || "Khách hàng"}</p>
                  <p className="text-xs text-black/50">{order.customer?.email || `#${order.user_id}`}</p>
                </td>
                <td className="p-3">{order.items.length}</td>
                <td className="p-3 font-semibold">{Number(order.total_amount).toLocaleString("vi-VN")} đ</td>
                <td className="p-3">{displayStatus(order.status)}</td>
                <td className="p-3">{new Date(order.created_at).toLocaleString("vi-VN")}</td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={6} className="p-6 text-center text-black/50">Chưa có đơn hàng nào.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
