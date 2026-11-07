"use client";

import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  Boxes,
  BrainCircuit,
  Clock,
  Cpu,
  DoorOpen,
  ReceiptText,
  ShoppingCart,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import { displayRoomType, displayStatus } from "@/lib/display";
import type { AdminDashboard } from "@/types/api";

export default function AdminPage() {
  const { loading } = useAuth("ADMIN");
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<AdminDashboard>("/api/admin/dashboard")
      .then(setDashboard)
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dashboard."));
  }, []);

  if (loading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        <p>Đang kiểm tra quyền...</p>
      </div>
    );
  }

  const stats = dashboard?.stats;
  const cards = [
    {
      label: "Tổng người dùng",
      value: stats?.total_users,
      sub: "Tài khoản trên hệ thống",
      href: "/admin/users",
      icon: Users,
    },
    {
      label: "Tổng sản phẩm",
      value: stats?.total_products,
      sub: "Danh mục nội thất",
      href: "/admin/products",
      icon: Boxes,
    },
    {
      label: "Sản phẩm đang hoạt động",
      value: stats?.active_products,
      sub: "Đang mở bán trên catalog",
      href: "/admin/products",
      icon: Activity,
    },
    {
      label: "Tổng dự án phòng",
      value: stats?.total_room_projects,
      sub: "Không gian khách hàng tải lên",
      href: "/admin/room-projects",
      icon: DoorOpen,
    },
    {
      label: "Tổng thiết kế AI",
      value: stats?.total_design_generations,
      sub: "Phương án decor đã khởi tạo",
      href: "/admin/room-projects",
      icon: BrainCircuit,
    },
    {
      label: "Tổng đơn hàng",
      value: stats?.total_orders,
      sub: "Toàn bộ đơn đặt hàng",
      href: "/admin/orders",
      icon: ShoppingCart,
    },
    {
      label: "Đơn đang chờ",
      value: stats?.pending_orders,
      sub: "Đơn hàng chờ xác nhận",
      href: "/admin/orders",
      icon: ReceiptText,
    },
    {
      label: "Tổng lượt gọi AI",
      value: stats?.total_ai_calls,
      sub: "Lượt gọi Gemini & Cloudflare",
      href: "/admin/ai-usage",
      icon: Cpu,
    },
  ];

  const activeProductRatio = calcPercent(stats?.active_products, stats?.total_products);
  const completedOrderRatio = calcPercent(stats?.completed_orders, stats?.total_orders);
  const pendingOrderRatio = calcPercent(stats?.pending_orders, stats?.total_orders);

  return (
    <section className="w-full space-y-7">
      {/* SECTION 1: PAGE INTRO & QUICK ACCESS LINKS */}
      <div className="motion-fade-up rounded-[1.75rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
        <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#C9A77A]/45 bg-[#FAF8F5] px-3.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[#2D332C]">
              <Sparkles size={13} className="text-[#C9A77A]" />
              Executive Overview
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#242424] md:text-3xl">
              Tổng quan quản trị
            </h1>
            <p className="max-w-2xl text-sm leading-relaxed text-[#777777]">
              Theo dõi dữ liệu vận hành, đơn hàng, dự án phòng và lượt gọi AI theo thời gian thực từ cơ sở dữ liệu hệ thống.
            </p>
          </div>
          <AdminLinks />
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50/90 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* SECTION 2: REVENUE HERO BANNER & REAL OPERATIONAL RATIOS */}
      <div className="motion-fade-up motion-delay-100 grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        {/* Revenue Card */}
        <div className="relative overflow-hidden rounded-[1.75rem] border border-[#2D332C] bg-[#2D332C] p-6 text-[#FAF8F5] shadow-luxury md:p-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-[#C9A77A]/15 blur-3xl"
          />
          <div className="relative flex h-full flex-col justify-between gap-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <span className="inline-flex items-center gap-2 rounded-full border border-[#C9A77A]/35 bg-white/10 px-3.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[#C9A77A]">
                  <TrendingUp size={13} />
                  Doanh thu thực tế
                </span>
                <p className="text-sm font-medium text-[#FAF8F5]/75">Doanh thu từ đơn hoàn thành</p>
              </div>
              <Link
                href="/admin/orders"
                className="inline-flex items-center gap-1.5 rounded-xl border border-[#C9A77A]/40 bg-white/10 px-3.5 py-2 text-xs font-semibold text-[#FAF8F5] transition hover:border-[#C9A77A] hover:bg-white/15"
              >
                Quản lý đơn hàng
                <ArrowUpRight size={14} className="text-[#C9A77A]" />
              </Link>
            </div>

            <div className="space-y-2">
              <p className="text-3xl font-black tracking-tight text-[#C9A77A] sm:text-4xl lg:text-5xl">
                {money(stats?.completed_order_revenue || "0")}
              </p>
              <p className="text-xs text-[#FAF8F5]/65">
                Không tính đơn đã hủy hoặc chưa hoàn thành.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3 border-t border-white/10 pt-5">
              <div className="rounded-2xl bg-white/5 p-3.5">
                <p className="text-[11px] font-medium text-[#FAF8F5]/65">Đơn hoàn thành</p>
                <p className="mt-1 text-lg font-bold text-[#FAF8F5]">{stats?.completed_orders ?? "-"}</p>
              </div>
              <div className="rounded-2xl bg-white/5 p-3.5">
                <p className="text-[11px] font-medium text-[#FAF8F5]/65">Đơn đang chờ</p>
                <p className="mt-1 text-lg font-bold text-[#C9A77A]">{stats?.pending_orders ?? "-"}</p>
              </div>
              <div className="rounded-2xl bg-white/5 p-3.5">
                <p className="text-[11px] font-medium text-[#FAF8F5]/65">Tổng đơn hàng</p>
                <p className="mt-1 text-lg font-bold text-[#FAF8F5]">{stats?.total_orders ?? "-"}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Real Data Ratios Panel */}
        <div className="admin-surface-card flex flex-col justify-between gap-5">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#A68B6D]">
              Chỉ số tỷ lệ vận hành
            </p>
            <h2 className="mt-1 text-lg font-bold text-[#242424]">
              Phân bổ sản phẩm & đơn hàng thực tế
            </h2>
          </div>

          <div className="space-y-4">
            <RatioRow
              label="Sản phẩm đang mở bán"
              detail={`${stats?.active_products ?? "-"} / ${stats?.total_products ?? "-"} sản phẩm`}
              percent={activeProductRatio}
              barClass="bg-[#2D332C]"
            />
            <RatioRow
              label="Đơn hàng đã hoàn thành"
              detail={`${stats?.completed_orders ?? "-"} / ${stats?.total_orders ?? "-"} đơn hàng`}
              percent={completedOrderRatio}
              barClass="bg-[#C9A77A]"
            />
            <RatioRow
              label="Đơn hàng đang chờ xử lý"
              detail={`${stats?.pending_orders ?? "-"} / ${stats?.total_orders ?? "-"} đơn hàng`}
              percent={pendingOrderRatio}
              barClass="bg-[#A68B6D]"
            />
          </div>

          <div className="flex items-center justify-between border-t border-[#2D332C]/10 pt-4 text-xs text-[#777777]">
            <span>Tổng lượt gọi AI đã ghi nhận</span>
            <span className="font-bold text-[#2D332C]">{stats?.total_ai_calls ?? "-"} lượt</span>
          </div>
        </div>
      </div>

      {/* SECTION 3: 8 KPI CARDS */}
      <div className="motion-fade-up motion-delay-150 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:gap-5">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.label} href={card.href} className="admin-kpi-card group block">
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[#C9A77A]/35 bg-[#FAF8F5] text-[#2D332C] transition-colors duration-200 group-hover:border-[#C9A77A] group-hover:bg-[#2D332C] group-hover:text-[#C9A77A]">
                  <Icon size={20} />
                </span>
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[#FAF8F5] text-[#A68B6D] transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-[#2D332C]">
                  <ArrowUpRight size={14} />
                </span>
              </div>
              <p className="mt-4 text-xs font-semibold uppercase tracking-[0.12em] text-[#777777]">
                {card.label}
              </p>
              <p className="mt-1.5 text-3xl font-bold tracking-tight text-[#242424]">
                {card.value ?? "-"}
              </p>
              <p className="mt-1 text-xs text-[#777777]">{card.sub}</p>
            </Link>
          );
        })}
      </div>

      {/* SECTION 4: 3 RECENT ACTIVITY COLUMNS */}
      <div className="motion-fade-up motion-delay-200 grid gap-6 xl:grid-cols-3">
        {/* Recent Orders */}
        <section className="admin-surface-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-[#2D332C]/10 pb-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#FAF8F5] text-[#2D332C]">
                  <ShoppingCart size={17} />
                </span>
                <div>
                  <h2 className="font-bold text-[#242424]">Đơn hàng gần đây</h2>
                  <p className="text-xs text-[#777777]">Cập nhật giao dịch mới nhất</p>
                </div>
              </div>
              <Link
                href="/admin/orders"
                className="inline-flex items-center gap-1 rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] px-3 py-1.5 text-xs font-semibold text-[#2D332C] transition hover:border-[#C9A77A] hover:bg-white"
              >
                Xem tất cả
                <ArrowUpRight size={13} className="text-[#A68B6D]" />
              </Link>
            </div>

            <div className="mt-4 space-y-3">
              {(dashboard?.recent_orders || []).map((order) => (
                <Link
                  key={order.id}
                  href={`/admin/orders/${order.id}`}
                  className="admin-activity-item"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#242424]">#{order.id}</span>
                      <span className={statusBadgeClass(order.status)}>
                        {displayStatus(order.status)}
                      </span>
                    </div>
                    <span className="text-sm font-bold text-[#A68B6D]">
                      {money(order.total_amount)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-[#242424]/85">
                    {order.customer?.full_name || "Khách hàng"} · {displayStatus(order.status)}
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 text-xs text-[#777777]">
                    <Clock size={12} className="text-[#A68B6D]" />
                    {dateTime(order.created_at)}
                  </p>
                </Link>
              ))}
              {dashboard?.recent_orders.length === 0 && (
                <div className="rounded-2xl border border-dashed border-[#2D332C]/15 bg-[#FAF8F5]/60 p-6 text-center text-sm text-[#777777]">
                  Chưa có đơn hàng.
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Recent Room Projects */}
        <section className="admin-surface-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-[#2D332C]/10 pb-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#FAF8F5] text-[#2D332C]">
                  <DoorOpen size={17} />
                </span>
                <div>
                  <h2 className="font-bold text-[#242424]">Dự án phòng gần đây</h2>
                  <p className="text-xs text-[#777777]">Không gian & tiến độ phân tích</p>
                </div>
              </div>
              <Link
                href="/admin/room-projects"
                className="inline-flex items-center gap-1 rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] px-3 py-1.5 text-xs font-semibold text-[#2D332C] transition hover:border-[#C9A77A] hover:bg-white"
              >
                Xem tất cả
                <ArrowUpRight size={13} className="text-[#A68B6D]" />
              </Link>
            </div>

            <div className="mt-4 space-y-3">
              {(dashboard?.recent_room_projects || []).map((project) => (
                <Link
                  key={project.id}
                  href={`/admin/room-projects/${project.id}`}
                  className="admin-activity-item"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-[#242424]">
                      #{project.id} · {project.title}
                    </p>
                    <span className={statusBadgeClass(project.status)}>
                      {displayStatus(project.status)}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm text-[#242424]/80">
                    {project.customer?.full_name || "Khách hàng"} · {displayStatus(project.status)}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-[#777777]">
                    <span className="rounded-md bg-white px-2 py-0.5 font-medium text-[#2D332C] shadow-sm">
                      {displayRoomType(project.room_type) || "Chưa rõ loại phòng"}
                    </span>
                    <span>·</span>
                    <span>
                      Phân tích:{" "}
                      <strong className="font-semibold text-[#242424]">
                        {project.analysis_status ? displayStatus(project.analysis_status) : "Chưa có"}
                      </strong>
                    </span>
                  </div>
                </Link>
              ))}
              {dashboard?.recent_room_projects.length === 0 && (
                <div className="rounded-2xl border border-dashed border-[#2D332C]/15 bg-[#FAF8F5]/60 p-6 text-center text-sm text-[#777777]">
                  Chưa có dự án phòng.
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Recent AI Usage */}
        <section className="admin-surface-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-[#2D332C]/10 pb-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#FAF8F5] text-[#2D332C]">
                  <BrainCircuit size={17} />
                </span>
                <div>
                  <h2 className="font-bold text-[#242424]">AI gần đây</h2>
                  <p className="text-xs text-[#777777]">Nhật ký gọi model & token</p>
                </div>
              </div>
              <Link
                href="/admin/ai-usage"
                className="inline-flex items-center gap-1 rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] px-3 py-1.5 text-xs font-semibold text-[#2D332C] transition hover:border-[#C9A77A] hover:bg-white"
              >
                Theo dõi AI
                <ArrowUpRight size={13} className="text-[#A68B6D]" />
              </Link>
            </div>

            <div className="mt-4 space-y-3">
              {(dashboard?.recent_ai_usage || []).map((log) => (
                <div key={log.id} className="admin-activity-item">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-[#242424]">
                      {log.provider} · {log.task_type}
                    </p>
                    <span className={statusBadgeClass(log.status)}>
                      {displayStatus(log.status)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm font-medium text-[#A68B6D]">{log.model}</p>
                  <p className="mt-1.5 text-xs text-[#777777]">
                    {displayStatus(log.status)} · {log.total_tokens} token · {dateTime(log.created_at)}
                  </p>
                </div>
              ))}
              {dashboard?.recent_ai_usage.length === 0 && (
                <div className="rounded-2xl border border-dashed border-[#2D332C]/15 bg-[#FAF8F5]/60 p-6 text-center text-sm text-[#777777]">
                  Chưa có log AI.
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

function AdminLinks() {
  const links = [
    ["/admin/users", "Người dùng"],
    ["/admin/products", "Sản phẩm"],
    ["/admin/product-images", "Ảnh chờ duyệt"],
    ["/admin/orders", "Đơn hàng"],
    ["/admin/room-projects", "Dự án phòng"],
    ["/admin/ai-usage", "Theo dõi AI"],
    ["/admin/categories", "Danh mục"],
    ["/admin/materials", "Chất liệu"],
    ["/admin/styles", "Phong cách"],
    ["/admin/room-types", "Loại phòng"],
    ["/admin/colors", "Màu sắc"],
  ];
  return (
    <div className="flex flex-wrap gap-2 text-xs font-semibold">
      {links.map(([href, label]) => (
        <Link
          key={href}
          href={href}
          className="rounded-xl border border-[#2D332C]/12 bg-[#FAF8F5] px-3 py-2 text-[#242424] transition-all duration-200 hover:-translate-y-0.5 hover:border-[#C9A77A] hover:bg-white hover:text-[#2D332C] hover:shadow-sm"
        >
          {label}
        </Link>
      ))}
    </div>
  );
}

function RatioRow({
  label,
  detail,
  percent,
  barClass,
}: {
  label: string;
  detail: string;
  percent: number | null;
  barClass: string;
}) {
  const safeWidth = percent !== null ? Math.min(100, Math.max(0, percent)) : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-[#242424]">{label}</span>
        <span className="text-[#777777]">
          {detail} {percent !== null ? `(${percent}%)` : ""}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[#FAF8F5]">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barClass}`}
          style={{ width: `${safeWidth}%` }}
        />
      </div>
    </div>
  );
}

function calcPercent(part?: number, total?: number): number | null {
  if (typeof part !== "number" || typeof total !== "number" || total <= 0) {
    return null;
  }
  return Math.round((part / total) * 100);
}

function statusBadgeClass(status?: string | null) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "COMPLETED" || normalized === "SUCCESS" || normalized === "ACTIVE" || normalized === "APPROVED") {
    return "inline-flex shrink-0 items-center rounded-full border border-emerald-700/20 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800";
  }
  if (normalized === "PENDING" || normalized === "PROCESSING" || normalized === "CONFIRMED" || normalized === "SHIPPED" || normalized === "ANALYZING" || normalized === "GENERATING") {
    return "inline-flex shrink-0 items-center rounded-full border border-[#C9A77A]/45 bg-[#C9A77A]/15 px-2.5 py-0.5 text-[11px] font-bold text-[#2D332C]";
  }
  if (normalized === "CANCELLED" || normalized === "FAILED" || normalized === "REJECTED") {
    return "inline-flex shrink-0 items-center rounded-full border border-red-300 bg-red-50 px-2.5 py-0.5 text-[11px] font-bold text-red-700";
  }
  return "inline-flex shrink-0 items-center rounded-full border border-[#2D332C]/15 bg-[#FAF8F5] px-2.5 py-0.5 text-[11px] font-bold text-[#2D332C]";
}

function money(value: string | number) {
  return `${Number(value || 0).toLocaleString("vi-VN")} đ`;
}

function dateTime(value: string) {
  return new Date(value).toLocaleString("vi-VN");
}
