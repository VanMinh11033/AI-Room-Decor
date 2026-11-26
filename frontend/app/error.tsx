"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RotateCcw } from "lucide-react";
import { LuxuryButton } from "@/components/ui/LuxuryButton";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log minimal safe diagnostic without leaking private data
    if (process.env.NODE_ENV === "development") {
      console.error("Global Error Boundary caught error:", error.message);
    }
  }, [error]);

  return (
    <div className="flex min-h-[65vh] flex-col items-center justify-center px-4 py-16 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-red-50 border border-red-200 text-red-600 shadow-sm">
        <AlertTriangle size={32} />
      </div>

      <div className="mt-6 max-w-md space-y-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-[#8A6B4E]">
          Sự cố kỹ thuật tạm thời
        </span>
        <h1 className="font-serif text-2xl font-bold text-[#242B23] sm:text-3xl">
          Đã có gián đoạn kết nối
        </h1>
        <p className="text-sm leading-relaxed text-[#5A6258]">
          Hệ thống gặp sự cố tạm thời khi xử lý yêu cầu. Dữ liệu và giỏ hàng của quý khách vẫn được bảo toàn an toàn.
        </p>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <LuxuryButton
          variant="primary"
          onClick={() => reset()}
          className="flex items-center gap-2"
        >
          <RotateCcw size={16} />
          <span>Thử lại</span>
        </LuxuryButton>

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
