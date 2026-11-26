import { Loader2 } from "lucide-react";

export default function GlobalLoading() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="relative flex h-16 w-16 items-center justify-center">
        <div className="absolute h-16 w-16 animate-ping rounded-full bg-[#8A6B4E]/10" />
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FBF9F5] border border-[#DDD7CD] shadow-sm">
          <Loader2 size={24} className="animate-spin text-[#8A6B4E]" />
        </div>
      </div>
      <div className="space-y-1">
        <p className="font-serif text-lg font-bold text-[#242B23]">
          Đang chuẩn bị không gian sống hoàn mỹ...
        </p>
        <p className="text-xs text-[#5A6258]">
          Hệ thống đang nạp dữ liệu kiến trúc và bộ sưu tập nội thất độc bản.
        </p>
      </div>
    </div>
  );
}
