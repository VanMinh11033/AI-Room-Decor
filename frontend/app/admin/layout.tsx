"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Boxes,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  DoorOpen,
  ExternalLink,
  FolderKanban,
  Home,
  Image as ImageIcon,
  Layers,
  LayoutDashboard,
  Palette,
  Plus,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";

type AdminNavItem = {
  href: string;
  label: string;
  shortDesc: string;
  icon: LucideIcon;
};

type AdminNavGroup = {
  groupLabel: string;
  items: AdminNavItem[];
};

const ADMIN_NAV_GROUPS: AdminNavGroup[] = [
  {
    groupLabel: "Điều hành & Thương mại",
    items: [
      {
        href: "/admin",
        label: "Tổng quan",
        shortDesc: "KPIs, doanh thu & hoạt động vận hành",
        icon: LayoutDashboard,
      },
      {
        href: "/admin/orders",
        label: "Đơn hàng",
        shortDesc: "Theo dõi và cập nhật trạng thái đơn",
        icon: ShoppingCart,
      },
      {
        href: "/admin/products",
        label: "Sản phẩm",
        shortDesc: "Quản lý catalog nội thất & tồn kho",
        icon: Boxes,
      },
      {
        href: "/admin/product-images",
        label: "Ảnh chờ duyệt",
        shortDesc: "Tìm kiếm và phê duyệt ảnh sản phẩm",
        icon: ImageIcon,
      },
    ],
  },
  {
    groupLabel: "Không gian & AI Studio",
    items: [
      {
        href: "/admin/room-projects",
        label: "Dự án phòng",
        shortDesc: "Không gian tải lên, sở thích & thiết kế",
        icon: DoorOpen,
      },
      {
        href: "/admin/ai-usage",
        label: "Theo dõi AI",
        shortDesc: "Giám sát Gemini, Cloudflare & token",
        icon: BrainCircuit,
      },
    ],
  },
  {
    groupLabel: "Hệ thống & Danh mục",
    items: [
      {
        href: "/admin/users",
        label: "Người dùng",
        shortDesc: "Tài khoản khách hàng & quản trị viên",
        icon: Users,
      },
      {
        href: "/admin/categories",
        label: "Danh mục",
        shortDesc: "Phân loại sản phẩm nội thất",
        icon: FolderKanban,
      },
      {
        href: "/admin/materials",
        label: "Chất liệu",
        shortDesc: "Danh mục vật liệu chuẩn",
        icon: Layers,
      },
      {
        href: "/admin/styles",
        label: "Phong cách",
        shortDesc: "Danh mục phong cách thiết kế",
        icon: Sparkles,
      },
      {
        href: "/admin/room-types",
        label: "Loại phòng",
        shortDesc: "Danh mục không gian phòng",
        icon: Home,
      },
      {
        href: "/admin/colors",
        label: "Màu sắc",
        shortDesc: "Bảng màu và mã hex nội thất",
        icon: Palette,
      },
    ],
  },
];

const ALL_ADMIN_ITEMS: AdminNavItem[] = ADMIN_NAV_GROUPS.flatMap((group) => group.items);

function isNavItemActive(pathname: string, href: string) {
  if (href === "/admin") {
    return pathname === "/admin";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function resolvePageMeta(pathname: string): { title: string; subtitle: string; group: string } {
  if (pathname === "/admin/products/create") {
    return {
      title: "Thêm sản phẩm mới",
      subtitle: "Khởi tạo sản phẩm nội thất mới trong catalog hệ thống",
      group: "Điều hành & Thương mại",
    };
  }
  if (pathname.startsWith("/admin/products/") && pathname.endsWith("/edit")) {
    return {
      title: "Chỉnh sửa sản phẩm",
      subtitle: "Cập nhật thông số, thuộc tính AI matching và hình ảnh sản phẩm",
      group: "Điều hành & Thương mại",
    };
  }
  if (pathname.startsWith("/admin/orders/")) {
    return {
      title: "Chi tiết đơn hàng",
      subtitle: "Kiểm tra danh mục đặt mua, địa chỉ giao nhận và cập nhật trạng thái",
      group: "Điều hành & Thương mại",
    };
  }
  if (pathname.startsWith("/admin/room-projects/")) {
    return {
      title: "Chi tiết dự án phòng",
      subtitle: "Xem ảnh phòng gốc, kết quả phân tích AI Vision và lịch sử thiết kế",
      group: "Không gian & AI Studio",
    };
  }

  for (const group of ADMIN_NAV_GROUPS) {
    for (const item of group.items) {
      if (isNavItemActive(pathname, item.href)) {
        return {
          title: item.label,
          subtitle: item.shortDesc,
          group: group.groupLabel,
        };
      }
    }
  }

  return {
    title: "Trung tâm Quản trị",
    subtitle: "Hệ thống điều hành AI Room Decor",
    group: "Admin Command Center",
  };
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, loading } = useAuth("ADMIN");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isAuthorizedAdmin = !loading && user?.role?.name === "ADMIN";
  const pageMeta = resolvePageMeta(pathname);

  // Security & Auth Protection:
  // Do not render Sidebar or Admin Header until ADMIN role is verified.
  // Keep {children} mounted so each individual page's own useAuth("ADMIN") hook continues to work untouched.
  if (!isAuthorizedAdmin) {
    return <div className="admin-command-shell">{children}</div>;
  }

  return (
    <div className="admin-command-shell">
      <div className="grid gap-6 lg:grid-cols-[264px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)] xl:gap-8">
        {/* DESKTOP LEFT SIDEBAR */}
        <aside
          aria-label="Điều hướng quản trị"
          className="hidden lg:sticky lg:top-24 lg:flex lg:max-h-[calc(100vh-7.5rem)] lg:flex-col lg:justify-between lg:self-start lg:overflow-y-auto rounded-[1.75rem] border border-[#2D332C]/10 bg-white p-5 shadow-card"
        >
          <div className="space-y-6">
            {/* Brand Header */}
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5] p-3.5">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#C9A77A]/45 bg-[#2D332C] text-[#C9A77A] shadow-sm">
                  <Sparkles size={18} />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold tracking-tight text-[#242424]">AI Room Decor</p>
                  <p className="truncate text-[10px] font-bold uppercase tracking-[0.2em] text-[#A68B6D]">
                    Command Center
                  </p>
                </div>
              </div>
              <span className="rounded-full border border-[#C9A77A]/40 bg-[#C9A77A]/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#2D332C]">
                Admin
              </span>
            </div>

            {/* Navigation Groups */}
            <nav className="space-y-5">
              {ADMIN_NAV_GROUPS.map((group) => (
                <div key={group.groupLabel} className="space-y-1.5">
                  <p className="px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-[#777777]">
                    {group.groupLabel}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((item) => {
                      const Icon = item.icon;
                      const active = isNavItemActive(pathname, item.href);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={`group flex items-center justify-between gap-3 rounded-xl px-3.5 py-2.5 text-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A77A] ${
                            active
                              ? "bg-[#2D332C] font-semibold text-[#FAF8F5] shadow-sm"
                              : "font-medium text-[#242424]/80 hover:bg-[#FAF8F5] hover:text-[#242424]"
                          }`}
                        >
                          <span className="flex min-w-0 items-center gap-3">
                            <span
                              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors duration-200 ${
                                active
                                  ? "bg-[#C9A77A]/20 text-[#C9A77A]"
                                  : "bg-[#FAF8F5] text-[#A68B6D] group-hover:bg-white group-hover:text-[#2D332C]"
                              }`}
                            >
                              <Icon size={16} />
                            </span>
                            <span className="truncate">{item.label}</span>
                          </span>
                          <ChevronRight
                            size={14}
                            className={`shrink-0 transition-transform duration-200 ${
                              active
                                ? "translate-x-0 text-[#C9A77A]"
                                : "-translate-x-1 text-transparent group-hover:translate-x-0 group-hover:text-[#A68B6D]"
                            }`}
                          />
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>
          </div>

          {/* Authenticated Admin Footer Card */}
          <div className="mt-6 border-t border-[#2D332C]/10 pt-4">
            <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-3.5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#2D332C] text-xs font-bold text-[#C9A77A]">
                  <ShieldCheck size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-bold text-[#242424]">{user.full_name}</p>
                  <p className="truncate text-[11px] text-[#777777]">{user.email}</p>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-[#2D332C]/10 pt-2.5 text-[11px]">
                <span className="font-semibold text-[#777777]">Quyền hạn</span>
                <span className="font-bold text-[#2D332C]">{user.role.name}</span>
              </div>
            </div>
          </div>
        </aside>

        {/* RIGHT MAIN WORKSPACE */}
        <div className="min-w-0 space-y-6">
          {/* TOP COMMAND HEADER */}
          <header className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white/95 px-5 py-4 shadow-card backdrop-blur-md md:px-7 md:py-5">
            <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[#A68B6D]">
                  <span className="uppercase tracking-[0.18em]">Admin Command Center</span>
                  <span>/</span>
                  <span className="text-[#777777]">{pageMeta.group}</span>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-xl font-bold tracking-tight text-[#242424] md:text-2xl">
                    {pageMeta.title}
                  </h2>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[#C9A77A]/45 bg-[#FAF8F5] px-3 py-1 text-[11px] font-semibold text-[#2D332C]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#2D332C]" />
                    {pageMeta.subtitle}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <Link
                  href="/admin/products/create"
                  className="inline-flex items-center gap-2 rounded-xl bg-[#2D332C] px-4 py-2.5 text-xs font-semibold text-[#FAF8F5] shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#3B433A] hover:shadow-card"
                >
                  <Plus size={15} className="text-[#C9A77A]" />
                  Thêm sản phẩm
                </Link>
                <Link
                  href="/products"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-3.5 py-2.5 text-xs font-semibold text-[#242424] transition-all duration-200 hover:border-[#C9A77A] hover:bg-white"
                >
                  Xem Catalog
                  <ExternalLink size={13} className="text-[#A68B6D]" />
                </Link>
                <div className="hidden items-center gap-2.5 rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] px-3.5 py-2 sm:flex">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#2D332C] text-[11px] font-bold text-[#C9A77A]">
                    {user.full_name?.charAt(0)?.toUpperCase() || "A"}
                  </span>
                  <div className="text-left leading-tight">
                    <p className="text-xs font-bold text-[#242424]">{user.full_name}</p>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[#A68B6D]">
                      {user.role.name}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* TABLET & MOBILE NON-OVERLAPPING NAVIGATION BAR */}
            <div className="mt-4 border-t border-[#2D332C]/10 pt-3.5 lg:hidden">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                  {ALL_ADMIN_ITEMS.slice(0, 6).map((item) => {
                    const Icon = item.icon;
                    const active = isNavItemActive(pathname, item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`inline-flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
                          active
                            ? "bg-[#2D332C] text-[#FAF8F5] shadow-sm"
                            : "border border-[#2D332C]/10 bg-[#FAF8F5] text-[#242424] hover:border-[#C9A77A]"
                        }`}
                      >
                        <Icon size={14} className={active ? "text-[#C9A77A]" : "text-[#A68B6D]"} />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen((prev) => !prev)}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-3 py-2 text-xs font-semibold text-[#2D332C] transition hover:border-[#C9A77A] hover:bg-white"
                >
                  Danh mục ({ALL_ADMIN_ITEMS.length})
                  <ChevronDown
                    size={14}
                    className={`transition-transform duration-200 ${mobileMenuOpen ? "rotate-180" : ""}`}
                  />
                </button>
              </div>

              {mobileMenuOpen && (
                <div className="mt-3 grid gap-4 rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5] p-4 sm:grid-cols-3">
                  {ADMIN_NAV_GROUPS.map((group) => (
                    <div key={group.groupLabel} className="space-y-1.5">
                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#777777]">
                        {group.groupLabel}
                      </p>
                      <div className="grid gap-1">
                        {group.items.map((item) => {
                          const Icon = item.icon;
                          const active = isNavItemActive(pathname, item.href);
                          return (
                            <Link
                              key={item.href}
                              href={item.href}
                              onClick={() => setMobileMenuOpen(false)}
                              className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition ${
                                active
                                  ? "bg-[#2D332C] text-[#FAF8F5]"
                                  : "bg-white text-[#242424] hover:border-[#C9A77A]"
                              }`}
                            >
                              <Icon size={14} className={active ? "text-[#C9A77A]" : "text-[#A68B6D]"} />
                              {item.label}
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </header>

          {/* PAGE CONTENT */}
          <div className="min-w-0">{children}</div>
        </div>
      </div>
    </div>
  );
}
