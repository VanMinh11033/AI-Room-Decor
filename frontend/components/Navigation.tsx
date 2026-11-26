"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Menu, Sparkles, X } from "lucide-react";
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
  const [mobileOpen, setMobileOpen] = useState(false);

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

  // Auto-close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function logout() {
    clearTokens();
    setUser(null);
    setMobileOpen(false);
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
  } else if (!user) {
    // Unauthenticated visitors have access to Giỏ hàng (AUD-P1-005)
    items.push({ href: "/cart", label: "Giỏ hàng" });
  }

  if (checked && role === "ADMIN") {
    items.push({ href: "/admin", label: "Quản trị" });
  }

  return (
    <header className="sticky top-0 z-40 border-b border-[#DDD7CD] bg-[#FBF9F5]/95 shadow-[0_4px_24px_rgba(45,51,44,0.04)] backdrop-blur-xl">
      <nav className="mx-auto max-w-7xl px-4 py-3 sm:py-4 md:px-6">
        {/* TOP BAR: Logo left, Desktop nav right, Mobile hamburger right */}
        <div className="flex items-center justify-between">
          <Link
            href="/"
            onClick={() => setMobileOpen(false)}
            className="group flex items-center gap-2.5 sm:gap-3.5 rounded-xl transition-transform duration-200 hover:scale-[1.02] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8A6B4E] focus-visible:ring-offset-2"
          >
            <span className="flex h-9 w-9 sm:h-11 sm:w-11 shrink-0 items-center justify-center rounded-2xl border border-[#8A6B4E]/40 bg-[#242B23] text-[#C9A77A] shadow-card transition-all duration-300 group-hover:scale-[1.03] group-hover:border-[#C9A77A] group-hover:shadow-soft">
              <Sparkles size={18} className="sm:hidden transition-transform duration-300 group-hover:rotate-6" />
              <Sparkles size={20} className="hidden sm:block transition-transform duration-300 group-hover:rotate-6" />
            </span>
            <span className="min-w-0">
              <span className="block text-base sm:text-lg font-bold tracking-tight text-[#242424] transition-colors duration-200 group-hover:text-[#242B23]">
                AI Room Decor
              </span>
              <span className="block text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.18em] sm:tracking-[0.22em] text-[#8A6B4E]">
                Interior AI Studio
              </span>
            </span>
          </Link>

          {/* DESKTOP NAVIGATION (100% PRESERVED FOR lg: SCREEN AND ABOVE) */}
          <div className="hidden lg:flex lg:items-center lg:gap-1.5 text-sm font-medium">
            {items.map((item) => (
              <Link key={item.href} href={item.href} className={navClass(isActive(pathname, item.href))}>
                {item.label}
              </Link>
            ))}
            {checked && !user && (
              <div className="ml-1 flex items-center gap-2 border-l border-[#DDD7CD] pl-3">
                <Link href="/login" className={navClass(isActive(pathname, "/login"))}>
                  Đăng nhập
                </Link>
                <Link
                  href="/register"
                  className="rounded-xl border border-[#8A6B4E]/40 bg-[#242B23] px-4 py-2.5 text-sm font-semibold text-[#FBF9F5] shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:bg-[#8A6B4E] hover:text-white hover:shadow-card active:translate-y-0 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8A6B4E] focus-visible:ring-offset-2"
                >
                  Đăng ký
                </Link>
              </div>
            )}
            {checked && user && (
              <button
                type="button"
                onClick={logout}
                className="ml-1 inline-flex items-center gap-2 rounded-xl border border-[#DDD7CD] bg-white px-4 py-2.5 text-sm font-semibold text-[#5A6258] shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-[#8A6B4E] hover:bg-[#FBF9F5] hover:text-[#242424] active:translate-y-0 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8A6B4E] focus-visible:ring-offset-2"
              >
                <LogOut size={16} className="text-[#8A6B4E] transition-transform duration-200" />
                Đăng xuất
              </button>
            )}
          </div>

          {/* MOBILE HAMBURGER BUTTON (< lg) */}
          <div className="flex items-center gap-2 lg:hidden">
            <button
              type="button"
              onClick={() => setMobileOpen((prev) => !prev)}
              aria-label={mobileOpen ? "Đóng menu điều hướng" : "Mở menu điều hướng"}
              aria-expanded={mobileOpen}
              className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-[#DDD7CD] bg-white text-[#242424] shadow-sm transition-all hover:bg-[#FBF9F5] hover:text-[#242B23] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8A6B4E] focus-visible:ring-offset-1 active:scale-95"
            >
              {mobileOpen ? <X size={22} className="text-[#2D332C]" /> : <Menu size={22} className="text-[#2D332C]" />}
            </button>
          </div>
        </div>

        {/* MOBILE COLLAPSIBLE DRAWER (< lg) */}
        {mobileOpen && (
          <div className="mt-3 divide-y divide-[#2D332C]/10 rounded-2xl border border-[#DDD7CD] bg-white/95 p-3 shadow-luxury backdrop-blur-xl lg:hidden motion-fade-up">
            {/* Nav Links */}
            <div className="flex flex-col gap-1 pb-3">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex min-h-[44px] items-center justify-between rounded-xl px-4 py-2.5 text-sm font-semibold transition-all ${
                      active
                        ? "bg-[#242B23] text-[#FBF9F5] shadow-sm"
                        : "text-[#242424] hover:bg-[#FBF9F5] active:bg-[#F2ECE3]"
                    }`}
                  >
                    <span>{item.label}</span>
                    {active && <span className="h-1.5 w-1.5 rounded-full bg-[#C9A77A]" />}
                  </Link>
                );
              })}
            </div>

            {/* Auth Actions */}
            <div className="pt-3">
              {checked && !user && (
                <div className="grid grid-cols-2 gap-2">
                  <Link
                    href="/login"
                    onClick={() => setMobileOpen(false)}
                    className="flex min-h-[44px] items-center justify-center rounded-xl border border-[#DDD7CD] bg-white px-4 py-2.5 text-center text-sm font-semibold text-[#242424] shadow-sm transition-all hover:bg-[#FBF9F5] active:scale-[0.98]"
                  >
                    Đăng nhập
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileOpen(false)}
                    className="flex min-h-[44px] items-center justify-center rounded-xl border border-[#8A6B4E]/40 bg-[#242B23] px-4 py-2.5 text-center text-sm font-semibold text-[#FBF9F5] shadow-sm transition-all hover:bg-[#8A6B4E] active:scale-[0.98]"
                  >
                    Đăng ký
                  </Link>
                </div>
              )}

              {checked && user && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between px-2 py-1 text-xs text-[#5A6258]">
                    <span className="truncate font-medium">{user.email}</span>
                    <span className="shrink-0 rounded-full bg-[#C9A77A]/20 px-2 py-0.5 font-bold text-[#2D332C]">
                      {user.role.name}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={logout}
                    className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-[#DDD7CD] bg-white px-4 py-2.5 text-sm font-semibold text-[#5A6258] shadow-sm transition-all hover:border-red-200 hover:bg-red-50 hover:text-red-600 active:scale-[0.98]"
                  >
                    <LogOut size={16} className="text-[#8A6B4E]" />
                    Đăng xuất
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}

function navClass(active: boolean) {
  return `rounded-xl px-3.5 py-2 transition-all duration-200 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8A6B4E] focus-visible:ring-offset-1 ${
    active
      ? "bg-[#242B23] font-semibold text-[#FBF9F5] shadow-sm"
      : "text-[#5A6258] hover:bg-white hover:text-[#242424]"
  }`;
}

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}


