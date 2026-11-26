"use client";

/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Camera,
  Compass,
  Sparkles,
  Wand2,
} from "lucide-react";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayCategory } from "@/lib/display";
import type { Paginated, Product } from "@/types/api";

const FALLBACK_FEATURED_PRODUCTS = [
  {
    id: 1,
    name: "Sofa Góc L-Shape Scandinavian Vải Nỉ Cao Cấp",
    category: { name: "sofa" },
    price: "18500000",
    images: [{ image_url: "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800&q=80", is_primary: true }],
    stock_quantity: 8,
  },
  {
    id: 2,
    name: "Ghế Thư Giãn Lounge Chair Tối Giản Khung Gỗ Sồi",
    category: { name: "armchair" },
    price: "6800000",
    images: [{ image_url: "https://images.unsplash.com/photo-1580481077195-c228c2e646f9?w=800&q=80", is_primary: true }],
    stock_quantity: 12,
  },
  {
    id: 3,
    name: "Bàn Trà Tròn Đôi Phong Cách Bắc Âu Mặt Gỗ",
    category: { name: "coffee_table" },
    price: "4200000",
    images: [{ image_url: "https://images.unsplash.com/photo-1533090161767-e6ffed986b88?w=800&q=80", is_primary: true }],
    stock_quantity: 15,
  },
  {
    id: 4,
    name: "Kệ Sách Gỗ Đứng Minimalist Đa Tầng",
    category: { name: "bookshelf" },
    price: "5500000",
    images: [{ image_url: "https://images.unsplash.com/photo-1594643156337-671222450329?w=800&q=80", is_primary: true }],
    stock_quantity: 6,
  },
];

export default function HomePage() {
  const [featuredProducts, setFeaturedProducts] = useState<Product[]>(FALLBACK_FEATURED_PRODUCTS as unknown as Product[]);

  useEffect(() => {
    apiFetch<Paginated<Product>>("/api/products?page=1&page_size=4")
      .then((data) => {
        if (data?.items && data.items.length > 0) {
          setFeaturedProducts(data.items);
        }
      })
      .catch(() => {
        // Retain verified fallback products
      });
  }, []);

  return (
    <div className="space-y-20 md:space-y-28 w-full max-w-full overflow-hidden">
      {/* =========================================================
          1. ARCHITECTURAL EDITORIAL HERO
      ========================================================= */}
      <section className="relative rounded-[2rem] border border-[#242B23]/10 bg-gradient-to-b from-white via-[#FBF9F5] to-[#F2ECE3]/60 p-6 sm:p-10 md:p-12 lg:p-16 shadow-soft">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-12 lg:gap-12 w-full min-w-0">
          {/* Left Column (7 cols): Editorial Typography */}
          <div className="w-full min-w-0 space-y-6 sm:space-y-8 lg:col-span-7">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#8A6B4E]/30 bg-white/90 px-3.5 py-1.5 shadow-sm">
              <Sparkles size={14} className="text-[#8A6B4E]" />
              <span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">
                Studio Thiết Kế Nội Thất AI
              </span>
            </div>

            <h1 className="font-serif text-3xl sm:text-5xl lg:text-6xl font-normal leading-[1.12] tracking-tight text-[#242B23] break-words">
              Kiến tạo không gian sống chuẩn mực cùng{" "}
              <span className="italic text-[#8A6B4E]">Trí tuệ Nhân tạo</span>
            </h1>

            <p className="max-w-xl text-base sm:text-lg leading-relaxed text-[#5A6258]">
              Tải lên hình ảnh căn phòng của bạn, xác định phong cách và ngân sách. Hệ thống phân tích bố cục không gian, gợi ý chính xác những sản phẩm nội thất thật từ catalog tuyển chọn và dựng phối cảnh trực quan.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 pt-2 w-full">
              <Link href="/room-projects/new" className="w-full sm:w-auto">
                <LuxuryButton variant="primary" size="lg" className="w-full justify-center">
                  <span>Tạo thiết kế AI</span>
                  <ArrowRight size={18} />
                </LuxuryButton>
              </Link>

              <Link href="/products" className="w-full sm:w-auto">
                <LuxuryButton variant="secondary" size="lg" className="w-full justify-center">
                  <span>Khám phá nội thất</span>
                  <ArrowUpRight size={18} className="text-[#8A6B4E]" />
                </LuxuryButton>
              </Link>
            </div>

            {/* Architectural Trust Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 border-t border-[#242B23]/10 pt-8 w-full min-w-0">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">01 · Thị giác AI</p>
                <p className="mt-1 text-sm font-semibold text-[#242B23]">Nhận diện kiến trúc & ánh sáng thực</p>
              </div>
              <div className="sm:border-l sm:border-[#242B23]/10 sm:pl-5">
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">02 · Catalog thật</p>
                <p className="mt-1 text-sm font-semibold text-[#242B23]">100% kích thước & thông số từ kho</p>
              </div>
              <div className="sm:border-l sm:border-[#242B23]/10 sm:pl-5">
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">03 · Độc bản</p>
                <p className="mt-1 text-sm font-semibold text-[#242B23]">Phối cảnh độc quyền theo gu của bạn</p>
              </div>
            </div>
          </div>

          {/* Right Column (5 cols): Architectural Frame */}
          <div className="w-full min-w-0 lg:col-span-5">
            <div className="relative overflow-hidden rounded-3xl border border-[#242B23]/10 bg-white p-3 shadow-luxury">
              <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-[#DDD7CD]/30">
                <img
                  src="https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=85"
                  alt="Không gian phòng khách phong cách Quiet Luxury đương đại"
                  className="h-full w-full object-cover transition-transform duration-700 hover:scale-105"
                  loading="eager"
                />
                <div className="absolute inset-x-3 bottom-3 rounded-xl bg-white/95 p-3.5 shadow-sm backdrop-blur-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">
                        Phòng khách Minimalist
                      </p>
                      <p className="text-xs font-semibold text-[#242B23]">
                        Gỗ sồi tự nhiên × Vải nỉ Scandinavian
                      </p>
                    </div>
                    <StatusBadge variant="verified">Chuẩn Catalog</StatusBadge>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================
          2. THREE ARCHITECTURAL PILLARS (HOW IT WORKS)
      ========================================================= */}
      <section className="space-y-12">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <StatusBadge variant="customer_pick">Quy Trình Kiến Tạo</StatusBadge>
          <EditorialHeading
            title="Thiết kế nội thất trực quan trong ba bước"
            subtitle="Từ bức ảnh hiện trạng đến bản phối cảnh hoàn thiện với sản phẩm thật sẵn sàng mua sắm."
            className="text-center"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full min-w-0">
          {/* Step 1 */}
          <article className="surface-card p-6 sm:p-8 space-y-4 hover:border-[#8A6B4E]/40 transition duration-300">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#242B23] text-white">
              <Camera size={22} />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">Bước 01</p>
            <h3 className="font-serif text-xl sm:text-2xl text-[#242B23]">Chụp hoặc tải ảnh phòng</h3>
            <p className="text-sm leading-relaxed text-[#5A6258]">
              Hệ thống phân tích vị trí cửa sổ, hướng chiếu sáng tự nhiên, góc tường và vật thể hiện có để xây dựng bản đồ không gian chuẩn xác.
            </p>
          </article>

          {/* Step 2 */}
          <article className="surface-card p-6 sm:p-8 space-y-4 hover:border-[#8A6B4E]/40 transition duration-300">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#8A6B4E] text-white">
              <Compass size={22} />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">Bước 02</p>
            <h3 className="font-serif text-xl sm:text-2xl text-[#242B23]">Chọn nội thất từ Catalog</h3>
            <p className="text-sm leading-relaxed text-[#5A6258]">
              Tự do chọn 1–3 món nội thất thật yêu thích, hoặc để thuật toán đa tiêu chí (MCDA) gợi ý các món đồ hài hòa nhất với tỷ lệ phòng của bạn.
            </p>
          </article>

          {/* Step 3 */}
          <article className="surface-card p-6 sm:p-8 space-y-4 hover:border-[#8A6B4E]/40 transition duration-300">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#242B23] text-white">
              <Wand2 size={22} />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">Bước 03</p>
            <h3 className="font-serif text-xl sm:text-2xl text-[#242B23]">Dựng phối cảnh trực quan</h3>
            <p className="text-sm leading-relaxed text-[#5A6258]">
              Ngắm nhìn phương án bài trí nội thất trực quan ngay trong chính căn phòng của mình trước khi quyết định đặt hàng COD thuận tiện.
            </p>
          </article>
        </div>
      </section>

      {/* =========================================================
          3. BEFORE / AFTER CONCEPT DEMONSTRATION (ILLUSTRATIVE)
      ========================================================= */}
      <section className="rounded-3xl border border-[#242B23]/10 bg-white p-6 sm:p-10 md:p-12 shadow-card space-y-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#242B23]/10 pb-6">
          <div className="space-y-2">
            <StatusBadge variant="pending">Mô Phỏng Ý Niệm Kiến Trúc</StatusBadge>
            <h2 className="font-serif text-2xl sm:text-4xl text-[#242B23]">Quy trình trước và sau phối cảnh</h2>
            <p className="text-sm text-[#5A6258] max-w-xl">
              Minh họa nguyên lý giữ nguyên cấu trúc không gian và tích hợp nội thất hài hòa theo tỷ lệ thực tế.
            </p>
          </div>
          <span className="text-xs text-[#5A6258]">Tư liệu ý niệm: Unsplash Architecture</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full min-w-0">
          {/* Before */}
          <div className="group space-y-3">
            <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl border border-[#242B23]/10 bg-[#FBF9F5]">
              <img
                src="https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1200&q=85"
                alt="Minh họa hiện trạng không gian thô trước khi bài trí"
                className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                loading="lazy"
              />
              <span className="absolute left-3.5 top-3.5 rounded-full bg-[#242B23]/80 px-3.5 py-1 text-xs font-semibold text-white backdrop-blur-md">
                Hiện trạng (Ảnh chụp mẫu)
              </span>
            </div>
            <p className="text-sm font-semibold text-[#242B23]">Bước 1: Ảnh chụp thực tế của căn phòng</p>
            <p className="text-xs text-[#5A6258]">
              Hệ thống nhận diện sàn nhà, tường, cửa sổ và góc chiếu sáng để định vị vật thể decor.
            </p>
          </div>

          {/* After */}
          <div className="group space-y-3">
            <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl border border-[#8A6B4E]/40 bg-[#FBF9F5]">
              <img
                src="https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=85"
                alt="Minh họa phương án phối cảnh nội thất sau hoàn thiện"
                className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                loading="lazy"
              />
              <span className="absolute left-3.5 top-3.5 inline-flex items-center gap-1.5 rounded-full bg-[#8A6B4E]/90 px-3.5 py-1 text-xs font-semibold text-white backdrop-blur-md">
                <Sparkles size={13} /> Phối cảnh minh họa
              </span>
            </div>
            <p className="text-sm font-semibold text-[#242B23]">Bước 2: Phương án bài trí cùng nội thất catalog</p>
            <p className="text-xs text-[#5A6258]">
              Đặt các món nội thất thật với vật liệu và kích thước thực tế vào góc nhìn phối cảnh trực quan.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-[#8A6B4E]/25 bg-[#FBF9F5] p-4 text-xs leading-relaxed text-[#5A6258]">
          <strong className="font-semibold text-[#242B23]">Minh bạch tư liệu:</strong> Hai hình ảnh trên là ảnh tư liệu kiến trúc mô phỏng quy trình thiết kế ý niệm. Khi khởi tạo dự án thực tế, AI Room Decor sẽ sử dụng trực tiếp hình ảnh căn phòng bạn tải lên và kết xuất phối cảnh từ chính những sản phẩm thật bạn chọn trong catalog.
        </div>
      </section>

      {/* =========================================================
          4. DYNAMIC FEATURED CATALOG PRODUCTS SHOWCASE
      ========================================================= */}
      <section className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div className="space-y-2">
            <StatusBadge variant="verified">Catalog Tuyển Chọn Thực Tế</StatusBadge>
            <h2 className="font-serif text-2xl sm:text-4xl text-[#242B23]">Nội thất tinh tuyển từ Kho</h2>
            <p className="text-sm text-[#5A6258] max-w-xl">
              Các sản phẩm thật sẵn sàng trong hệ thống kho để đưa vào dự án phối cảnh và mua sắm COD.
            </p>
          </div>
          <Link href="/products">
            <LuxuryButton variant="secondary" size="md">
              <span>Xem toàn bộ catalog</span>
              <ArrowRight size={16} />
            </LuxuryButton>
          </Link>
        </div>

        {/* Live Product Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 w-full min-w-0">
          {featuredProducts.map((item) => {
            const primaryImg = item.images?.find((img) => img.is_primary)?.image_url || item.images?.[0]?.image_url;
            return (
              <Link
                key={item.id}
                href={`/products/${item.id}`}
                className="group block overflow-hidden rounded-2xl border border-[#242B23]/10 bg-white shadow-sm hover:shadow-card hover:border-[#8A6B4E]/40 transition duration-300"
              >
                <div className="relative aspect-[4/3] w-full overflow-hidden bg-[#FBF9F5]">
                  {primaryImg ? (
                    <img
                      src={apiAssetUrl(primaryImg)}
                      alt={item.name}
                      className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                      loading="lazy"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-[#DDD7CD]/30 text-xs text-[#5A6258]">
                      Nội thất catalog
                    </div>
                  )}
                  <span className="absolute left-3 top-3 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-[#8A6B4E] shadow-sm backdrop-blur-sm">
                    {displayCategory(item.category?.name || "Nội thất")}
                  </span>
                  {item.stock_quantity > 0 && (
                    <span className="absolute right-3 top-3 rounded-full bg-[#242B23]/75 px-2.5 py-0.5 text-[11px] font-semibold text-white backdrop-blur-sm">
                      Còn {item.stock_quantity}
                    </span>
                  )}
                </div>
                <div className="p-5 space-y-2">
                  <h3 className="font-serif text-base font-normal text-[#242B23] line-clamp-1 group-hover:text-[#8A6B4E] transition">
                    {item.name}
                  </h3>
                  <div className="flex items-center justify-between pt-2 border-t border-[#242B23]/5">
                    <span className="text-sm font-semibold text-[#242B23]">
                      {Number(item.price).toLocaleString("vi-VN")} đ
                    </span>
                    <span className="text-xs font-semibold text-[#8A6B4E] flex items-center gap-0.5 group-hover:translate-x-0.5 transition">
                      Chi tiết <ArrowUpRight size={14} />
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* =========================================================
          5. QUIET LUXURY EDITORIAL CALL TO ACTION
      ========================================================= */}
      <section className="rounded-3xl border border-[#8A6B4E]/30 bg-gradient-to-br from-[#242B23] to-[#1A2019] p-8 sm:p-12 md:p-16 text-white text-center space-y-6 shadow-luxury">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#DDD7CD]">
          Quiet Luxury Philosophy
        </p>
        <h2 className="font-serif text-3xl sm:text-5xl max-w-2xl mx-auto leading-tight text-[#FBF9F5]">
          Không gian hoàn hảo bắt đầu từ một ý tưởng đúng đắn
        </h2>
        <p className="max-w-xl mx-auto text-sm sm:text-base text-[#DDD7CD]/80 leading-relaxed">
          Tạo dự án phòng mới ngay hôm nay. Trải nghiệm dịch vụ phối cảnh nội thất thông minh với sản phẩm thật và dịch vụ giao hàng COD tận nơi tin cậy.
        </p>
        <div className="pt-2">
          <Link href="/room-projects/new">
            <LuxuryButton variant="bronze" size="lg" className="mx-auto">
              <span>Bắt đầu thiết kế phòng của bạn</span>
              <ArrowRight size={18} />
            </LuxuryButton>
          </Link>
        </div>
      </section>
    </div>
  );
}
