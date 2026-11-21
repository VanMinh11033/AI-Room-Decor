"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  Banknote,
  Clock,
  DollarSign,
  Package,
  RotateCcw,
  Search,
  ShoppingCart,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import type { Order, OrderListResponse } from "@/types/api";
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminSearchFilterBar,
  AdminStatMiniCard,
  AdminStatusBadge,
  AdminTable,
  AdminTableCell,
  AdminTableContainer,
  AdminTableHead,
  AdminTableRow,
} from "@/components/admin/AdminPrimitives";

export default function AdminOrdersPage() {
  const { loading: authLoading } = useAuth("ADMIN");
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [paymentFilter, setPaymentFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    apiFetch<OrderListResponse>("/api/admin/orders")
      .then((data) => setOrders(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được đơn hàng."))
      .finally(() => setLoading(false));
  }, []);

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      const matchStatus = !statusFilter || order.status === statusFilter;
      const matchPayment = !paymentFilter || order.payment_status === paymentFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        String(order.id).includes(q) ||
        (order.recipient_name || "").toLowerCase().includes(q) ||
        (order.recipient_phone || "").toLowerCase().includes(q) ||
        (order.customer?.full_name || "").toLowerCase().includes(q) ||
        (order.customer?.email || "").toLowerCase().includes(q);
      return matchStatus && matchPayment && matchSearch;
    });
  }, [orders, statusFilter, paymentFilter, searchQuery]);

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  const pendingCount = orders.filter((o) => o.status === "PENDING").length;
  const completedCount = orders.filter((o) => o.status === "COMPLETED").length;
  const unpaidCount = orders.filter((o) => o.payment_status === "UNPAID").length;
  const completedRevenue = orders
    .filter((o) => o.payment_status === "PAID" || o.status === "COMPLETED")
    .reduce((sum, o) => sum + Number(o.total_amount || o.subtotal_amount || 0), 0);

  const tableColumns = [
    { key: "id", label: "Mã đơn" },
    { key: "customer", label: "Người nhận / SĐT" },
    { key: "items", label: "Sản phẩm", align: "center" as const },
    { key: "payment", label: "Thanh toán (COD)", align: "center" as const },
    { key: "amount", label: "Tổng tiền", align: "right" as const },
    { key: "status", label: "Trạng thái đơn", align: "center" as const },
    { key: "time", label: "Thời gian đặt" },
    { key: "action", label: "Chi tiết", align: "right" as const },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Giao dịch & Thương mại"
        title="Quản lý đơn hàng COD"
        subtitle="Theo dõi chi tiết các giao dịch mua sắm nội thất, địa chỉ giao nhận và tiến độ thu tiền mặt COD."
      />

      {/* 2. Top Summary KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AdminStatMiniCard
          label="Tổng đơn hàng"
          value={orders.length}
          sub="Tất cả các giao dịch hệ thống"
          icon={ShoppingCart}
        />
        <AdminStatMiniCard
          label="Chờ xác nhận"
          value={pendingCount}
          sub="Đơn mới đặt cần duyệt"
          icon={Clock}
          badge={
            pendingCount > 0 ? (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200">
                Cần xử lý
              </span>
            ) : undefined
          }
        />
        <AdminStatMiniCard
          label="Chưa thu tiền COD"
          value={unpaidCount}
          sub="Đang giao hoặc chờ thu tiền"
          icon={Banknote}
        />
        <AdminStatMiniCard
          label="Doanh thu đã thu"
          value={`${completedRevenue.toLocaleString("vi-VN")} đ`}
          sub={`Từ ${completedCount} đơn hoàn thành`}
          icon={DollarSign}
        />
      </div>

      {/* 3. Search & Filter Bar */}
      <AdminSearchFilterBar>
        <div className="relative min-w-[240px] flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] py-2.5 pl-10 pr-4 text-sm text-[#242424] placeholder:text-[#777777] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            placeholder="Tìm theo mã đơn #, người nhận, SĐT, email..."
          />
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[#777777]">Đơn hàng:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-3.5 py-2.5 text-xs font-bold text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="PENDING">Đang chờ (PENDING)</option>
            <option value="CONFIRMED">Đã xác nhận (CONFIRMED)</option>
            <option value="PROCESSING">Đang chuẩn bị (PROCESSING)</option>
            <option value="SHIPPED">Đang giao hàng (SHIPPED)</option>
            <option value="COMPLETED">Đã hoàn thành (COMPLETED)</option>
            <option value="CANCELLED">Đã hủy (CANCELLED)</option>
          </select>
        </div>

        {/* Payment Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[#777777]">Thu tiền:</span>
          <select
            value={paymentFilter}
            onChange={(e) => setPaymentFilter(e.target.value)}
            className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-3.5 py-2.5 text-xs font-bold text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
          >
            <option value="">Tất cả thanh toán</option>
            <option value="UNPAID">Chưa thu tiền (UNPAID)</option>
            <option value="PAID">Đã thu tiền (PAID)</option>
          </select>
        </div>

        {(searchQuery || statusFilter || paymentFilter) && (
          <button
            onClick={() => {
              setSearchQuery("");
              setStatusFilter("");
              setPaymentFilter("");
            }}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#2D332C]/15 bg-white px-3.5 py-2 text-xs font-semibold text-[#777777] transition hover:bg-[#FAF8F5] hover:text-[#242424]"
          >
            <RotateCcw size={13} />
            Đặt lại
          </button>
        )}
      </AdminSearchFilterBar>

      {/* 4. Error Message */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* 5. Orders Table */}
      <AdminTableContainer>
        <AdminTable>
          <AdminTableHead columns={tableColumns} />
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="p-12 text-center text-sm font-medium text-[#777777]">
                  Đang tải danh sách đơn hàng...
                </td>
              </tr>
            ) : filteredOrders.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8">
                  <AdminEmptyState
                    icon={Package}
                    title="Không có đơn hàng nào"
                    description={
                      searchQuery || statusFilter || paymentFilter
                        ? "Không có đơn hàng nào phù hợp với bộ lọc tìm kiếm hiện tại."
                        : "Hệ thống chưa ghi nhận đơn đặt hàng nào."
                    }
                  />
                </td>
              </tr>
            ) : (
              filteredOrders.map((order) => (
                <AdminTableRow key={order.id}>
                  {/* Mã đơn */}
                  <AdminTableCell>
                    <Link
                      href={`/admin/orders/${order.id}`}
                      className="font-bold text-[#2D332C] hover:text-[#A68B6D] hover:underline"
                    >
                      #{order.id}
                    </Link>
                  </AdminTableCell>

                  {/* Người nhận / SĐT */}
                  <AdminTableCell>
                    <div>
                      <p className="font-bold text-[#242424]">
                        {order.recipient_name || order.customer?.full_name || "Khách hàng"}
                      </p>
                      <p className="text-xs font-semibold text-[#A68B6D]">
                        {order.recipient_phone || "Chưa có SĐT"}
                      </p>
                    </div>
                  </AdminTableCell>

                  {/* Số sản phẩm */}
                  <AdminTableCell align="center">
                    <span className="inline-flex items-center gap-1 rounded-md bg-[#FAF8F5] px-2 py-0.5 text-xs font-semibold text-[#242424]">
                      {order.items.length} món
                    </span>
                  </AdminTableCell>

                  {/* Trạng thái thanh toán COD */}
                  <AdminTableCell align="center">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold border ${
                        order.payment_status === "PAID"
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : "bg-amber-50 text-amber-900 border-amber-200"
                      }`}
                    >
                      {order.payment_status === "PAID" ? "Đã thu tiền" : "Chưa thu (COD)"}
                    </span>
                  </AdminTableCell>

                  {/* Tổng tiền */}
                  <AdminTableCell align="right">
                    {order.total_amount ? (
                      <span className="font-bold text-[#242424]">
                        {Number(order.total_amount).toLocaleString("vi-VN")} đ
                      </span>
                    ) : (
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-900">
                        Chờ xác nhận phí
                      </span>
                    )}
                  </AdminTableCell>

                  {/* Trạng thái đơn */}
                  <AdminTableCell align="center">
                    <AdminStatusBadge status={order.status} size="sm" />
                  </AdminTableCell>

                  {/* Thời gian */}
                  <AdminTableCell>
                    <p className="text-xs text-[#242424]">
                      {new Date(order.created_at).toLocaleDateString("vi-VN")}
                    </p>
                    <p className="text-[11px] text-[#777777]">
                      {new Date(order.created_at).toLocaleTimeString("vi-VN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </AdminTableCell>

                  {/* Thao tác */}
                  <AdminTableCell align="right">
                    <Link
                      href={`/admin/orders/${order.id}`}
                      className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#2D332C]/15 bg-white px-3 text-xs font-semibold text-[#242424] shadow-2xs transition hover:border-[#A68B6D] hover:bg-[#FAF8F5]"
                    >
                      Xem đơn
                      <ArrowUpRight size={13} className="text-[#A68B6D]" />
                    </Link>
                  </AdminTableCell>
                </AdminTableRow>
              ))
            )}
          </tbody>
        </AdminTable>
      </AdminTableContainer>
    </div>
  );
}
