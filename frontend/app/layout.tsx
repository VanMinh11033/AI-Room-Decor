import type { Metadata } from "next";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Navigation } from "@/components/Navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Room Decor",
  description: "Personalized AI room decor platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="flex min-h-screen flex-col">
        <Navigation />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-6 md:py-12">{children}</main>
        <footer className="mt-16 border-t border-[#2D332C]/10 bg-white/80 backdrop-blur-sm">
          <div className="mx-auto max-w-7xl px-4 py-12 md:px-6">
            <div className="grid gap-10 md:grid-cols-[1.4fr_0.8fr_0.8fr]">
              <div className="space-y-4">
                <Link
                  href="/"
                  className="group inline-flex items-center gap-3 rounded-xl transition-transform duration-200 hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C9A77A]"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#C9A77A]/35 bg-[#2D332C] text-[#C9A77A] shadow-sm transition-all duration-300 group-hover:border-[#C9A77A]">
                    <Sparkles size={18} className="transition-transform duration-300 group-hover:rotate-6" />
                  </span>
                  <span>
                    <span className="block text-base font-bold tracking-tight text-[#242424]">AI Room Decor</span>
                    <span className="block text-[10px] font-semibold uppercase tracking-[0.22em] text-[#A68B6D]">
                      Interior AI Studio
                    </span>
                  </span>
                </Link>
                <p className="max-w-md text-sm leading-6 text-[#777777]">
                  Nền tảng tư vấn và thiết kế nội thất cá nhân hóa bằng AI. Phân tích không gian thực tế, gợi ý sản phẩm từ catalog thật và trực quan hóa phương án decor cho căn phòng của bạn.
                </p>
              </div>

              <div>
                <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-[#2D332C]">Khám phá</h2>
                <ul className="mt-4 space-y-2.5 text-sm text-[#777777]">
                  <li>
                    <Link href="/" className="luxury-footer-link">
                      Trang chủ
                    </Link>
                  </li>
                  <li>
                    <Link href="/products" className="luxury-footer-link">
                      Catalog sản phẩm
                    </Link>
                  </li>
                  <li>
                    <Link href="/room-projects/new" className="luxury-footer-link">
                      Tạo dự án phòng mới
                    </Link>
                  </li>
                  <li>
                    <Link href="/room-projects" className="luxury-footer-link">
                      Dự án của tôi
                    </Link>
                  </li>
                </ul>
              </div>

              <div>
                <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-[#2D332C]">Tài khoản & Mua sắm</h2>
                <ul className="mt-4 space-y-2.5 text-sm text-[#777777]">
                  <li>
                    <Link href="/cart" className="luxury-footer-link">
                      Giỏ hàng
                    </Link>
                  </li>
                  <li>
                    <Link href="/orders" className="luxury-footer-link">
                      Đơn hàng của tôi
                    </Link>
                  </li>
                  <li>
                    <Link href="/login" className="luxury-footer-link">
                      Đăng nhập
                    </Link>
                  </li>
                  <li>
                    <Link href="/register" className="luxury-footer-link">
                      Đăng ký tài khoản
                    </Link>
                  </li>
                </ul>
              </div>
            </div>

            <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t border-[#2D332C]/10 pt-6 text-xs text-[#777777] sm:flex-row sm:items-center">
              <p>© AI Room Decor — Modern Luxury Interior AI Studio.</p>
              <p className="text-[#A68B6D]">AI Vision · Rule-based Matching · AI Interior Visualization</p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}

