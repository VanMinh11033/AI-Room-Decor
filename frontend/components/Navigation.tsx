"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { apiFetch, clearTokens, getAccessToken } from "@/lib/api";
import type { User } from "@/types/api";

type NavItem = {
  href: string;
  label: string;
};

export function Navigation() {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      setUser(null);
      setChecked(true);
      return;
    }
    apiFetch<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        clearTokens();
        setUser(null);
      })
      .finally(() => setChecked(true));
  }, []);

  function logout() {
    clearTokens();
    setUser(null);
    window.location.href = "/";
  }

  const role = user?.role.name;
  const items: NavItem[] = [
    { href: "/", label: "Trang chủ" },
    { href: "/products", label: "Sản phẩm" },
  ];

  if (checked && role === "CUSTOMER") {
    items.push(
      { href: "/room-projects", label: "Dự án của tôi" },
      { href: "/cart", label: "Giỏ hàng" },
      { href: "/orders", label: "Đơn hàng" },
      { href: "/profile", label: "Hồ sơ" }
    );
  }

  if (checked && role === "ADMIN") {
    items.push(
      { href: "/admin", label: "Tổng quan" },
      { href: "/admin/users", label: "Người dùng" },
      { href: "/admin/products", label: "Sản phẩm" },
      { href: "/admin/product-images", label: "Ảnh chờ duyệt" },
      { href: "/admin/orders", label: "Đơn hàng" },
      { href: "/admin/room-projects", label: "Dự án phòng" },
      { href: "/admin/ai-usage", label: "Theo dõi AI" }
    );
  }

  return (
    <header className="sticky top-0 z-40 border-b border-[#2D332C]/10 bg-[#FAF8F5]/90 shadow-[0_4px_24px_rgba(45,51,44,0.04)] backdrop-blur-xl">
      <nav className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 md:px-6 lg:flex-row lg:items-center lg:justify-between">
        <Link
          href="/"
          className="group flex items-center gap-3.5 rounded-xl transition-transform duration-200 hover:scale-[1.02] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A77A] focus-visible:ring-offset-2"
        >
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[#C9A77A]/35 bg-[#2D332C] text-[#C9A77A] shadow-card transition-all duration-300 group-hover:scale-[1.03] group-hover:border-[#C9A77A] group-hover:shadow-soft">
            <Sparkles size={20} className="transition-transform duration-300 group-hover:rotate-6" />
          </span>
          <span>
            <span className="block text-lg font-bold tracking-tight text-[#242424] transition-colors duration-200 group-hover:text-[#2D332C]">
              AI Room Decor
            </span>
            <span className="block text-[11px] font-semibold uppercase tracking-[0.22em] text-[#A68B6D]">
              Interior AI Studio
            </span>
          </span>
        </Link>

        <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
          {items.map((item) => (
            <Link key={item.href} href={item.href} className={navClass(isActive(pathname, item.href))}>
              {item.label}
            </Link>
          ))}
          {checked && !user && (
            <div className="ml-1 flex flex-wrap items-center gap-2 border-l border-[#2D332C]/10 pl-3">
              <Link href="/login" className={navClass(isActive(pathname, "/login"))}>
                Đăng nhập
              </Link>
              <Link
                href="/register"
                className="rounded-xl border border-[#C9A77A]/40 bg-[#2D332C] px-4 py-2.5 text-sm font-semibold text-[#FAF8F5] shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:bg-[#A68B6D] hover:text-white hover:shadow-card active:translate-y-0 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A77A] focus-visible:ring-offset-2"
              >
                Đăng ký
              </Link>
            </div>
          )}
          {checked && user && (
            <button
              type="button"
              onClick={logout}
              className="ml-1 inline-flex items-center gap-2 rounded-xl border border-[#2D332C]/15 bg-white px-4 py-2.5 text-sm font-semibold text-[#777777] shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-[#A68B6D] hover:bg-[#FAF8F5] hover:text-[#242424] active:translate-y-0 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A77A] focus-visible:ring-offset-2"
            >
              <LogOut size={16} className="text-[#A68B6D] transition-transform duration-200" />
              Đăng xuất
            </button>
          )}
        </div>
      </nav>
    </header>
  );
}

function navClass(active: boolean) {
  return `rounded-xl px-3.5 py-2 transition-all duration-200 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A77A] focus-visible:ring-offset-1 ${
    active
      ? "bg-[#2D332C] font-semibold text-[#FAF8F5] shadow-sm"
      : "text-[#777777] hover:bg-white hover:text-[#242424]"
  }`;
}

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}


