import Link from "next/link";
import { Compass, Home, ShoppingBag } from "lucide-react";
import { LuxuryButton } from "@/components/ui/LuxuryButton";

export default function NotFound() {
  return (
    <div className="flex min-h-[65vh] flex-col items-center justify-center px-4 py-16 text-center">
      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-[#FBF9F5] border border-[#DDD7CD] text-[#8A6B4E] shadow-card">
        <Compass size={40} className="animate-pulse" />
      </div>

      <div className="mt-6 max-w-lg space-y-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-[#8A6B4E]">
          404 — Không tìm thấy trang
        </span>
        <h1 className="font-serif text-3xl font-bold text-[#242B23] sm:text-4xl">
          Không gian này chưa tồn tại
        </h1>
        <p className="text-sm leading-relaxed text-[#5A6258]">
          Đường dẫn quý khách đang tìm kiếm không tồn tại, đã được thay đổi hoặc bộ sưu tập nội thất đã được chuyển sang danh mục mới.
        </p>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link href="/products">
          <LuxuryButton variant="primary" className="flex items-center gap-2">
            <ShoppingBag size={16} />
            <span>Khám phá bộ sưu tập</span>
          </LuxuryButton>
        </Link>

        <Link href="/">
          <LuxuryButton variant="secondary" className="flex items-center gap-2">
            <Home size={16} />
            <span>Về trang chủ</span>
          </LuxuryButton>
        </Link>
      </div>
    </div>
  );
}
