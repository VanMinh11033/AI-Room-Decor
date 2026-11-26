"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, FolderPlus, Sparkles } from "lucide-react";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { FormField } from "@/components/ui/FormField";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StudioNavHeader } from "@/components/studio/StudioNavHeader";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { clearPreselectedProduct, getPreselectedProduct, setPreselectedProduct } from "@/lib/studio";
import type { Product, RoomProject } from "@/types/api";

function NewRoomProjectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { loading: authLoading } = useAuth("CUSTOMER");

  const [title, setTitle] = useState("");
  const [roomType, setRoomType] = useState("Phòng khách");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [preselectedName, setPreselectedName] = useState<string | null>(null);

  const preselectId = searchParams.get("preselect_product_id");

  useEffect(() => {
    const product = getPreselectedProduct();
    if (product && (preselectId === String(product.id) || !preselectId)) {
      setPreselectedName(product.name);
      if (!title) {
        setTitle(`Phòng thiết kế cùng ${product.name}`);
      }
    } else if (preselectId) {
      apiFetch<Product>(`/api/products/${preselectId}`)
        .then((p) => {
          if (p) {
            setPreselectedProduct({ id: p.id, name: p.name, image_url: p.images?.[0]?.image_url });
            setPreselectedName(p.name);
            if (!title) {
              setTitle(`Phòng thiết kế cùng ${p.name}`);
            }
          }
        })
        .catch(() => {});
    }
  }, [preselectId, title]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const project = await apiFetch<RoomProject>("/api/room-projects", {
        method: "POST",
        body: JSON.stringify({ title, room_type: roomType || null }),
      });
      const query = preselectId ? `?preselect_product_id=${preselectId}` : "";
      router.push(`/room-projects/${project.id}${query}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được dự án phòng");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="font-serif text-lg text-[#242B23]">Đang kiểm tra quyền truy cập Studio...</p>
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-4xl space-y-8 w-full max-w-full">
      {/* Studio Navigation Header */}
      <StudioNavHeader
        projectTitle={title || "Khởi tạo không gian phòng mới"}
        currentStep={1}
        hasRoomImage={false}
        hasPreferences={false}
        selectedProductsCount={preselectedName ? 1 : 0}
        saveState={saving ? "saving" : "unsaved"}
        isSaving={saving}
      />

      <div className="rounded-3xl border border-[#242B23]/10 bg-white p-6 sm:p-10 shadow-card space-y-8">
        <div className="space-y-2 border-b border-[#242B23]/10 pb-6">
          <StatusBadge variant="verified">Bước 01 · Thiết Lập Không Gian</StatusBadge>
          <EditorialHeading
            title="Đặt tên & chọn loại phòng"
            subtitle="Khởi tạo không gian để bắt đầu tải ảnh phòng hiện trạng và tiến hành phân tích ánh sáng."
          />
        </div>

        {preselectedName && (
          <div className="flex items-center gap-3.5 rounded-2xl border border-[#8A6B4E]/30 bg-[#FBF9F5] p-4 text-xs text-[#242B23]">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#242B23] text-white">
              <Sparkles size={18} />
            </div>
            <div>
              <p className="font-semibold text-[#8A6B4E] uppercase tracking-wider text-[11px]">
                Sản phẩm đồng hành
              </p>
              <p className="font-semibold text-sm text-[#242B23]">{preselectedName}</p>
              <p className="text-[#5A6258] mt-0.5">
                Món đồ này đã được ghi nhớ và sẽ xuất hiện tự động trong danh sách phối cảnh sau khi bạn tải ảnh phòng.
              </p>
            </div>
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-6">
          <FormField
            id="project-title"
            label="Tên dự án thiết kế"
            helperText="Đặt tên gợi nhớ để phân biệt các phòng khác nhau trong ngôi nhà của bạn."
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            minLength={2}
            maxLength={255}
            className="text-base"
            placeholder="Ví dụ: Phòng khách Penthouse Thảo Điền"
            error={error ? "Vui lòng nhập tên dự án hợp lệ" : undefined}
          />

          <div className="space-y-1.5 w-full">
            <label className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
              Loại không gian phòng <span className="text-[#B3261E]">*</span>
            </label>
            <p className="text-xs text-[#5A6258]">
              Chọn loại phòng để thuật toán đề xuất nội thất chuẩn xác với công năng sử dụng.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
              {[
                "Phòng khách",
                "Phòng ngủ master",
                "Góc làm việc",
                "Phòng ăn & bếp",
                "Phòng đọc sách",
                "Phòng em bé",
                "Ban công / Hiên",
                "Không gian mở",
              ].map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setRoomType(type)}
                  className={`rounded-xl border p-3 text-xs font-semibold text-left transition ${
                    roomType === type
                      ? "border-[#8A6B4E] bg-[#8A6B4E]/10 text-[#242B23] ring-1 ring-[#8A6B4E]/30"
                      : "border-[#242B23]/10 bg-white text-[#5A6258] hover:border-[#8A6B4E]/40"
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end pt-4 border-t border-[#242B23]/10">
            <LuxuryButton
              type="submit"
              variant="primary"
              size="lg"
              loading={saving}
              disabled={saving || !title.trim()}
              className="w-full sm:w-auto"
            >
              <span>Tiếp tục tải ảnh phòng</span>
              <ArrowRight size={18} />
            </LuxuryButton>
          </div>
        </form>
      </div>
    </section>
  );
}

export default function NewRoomProjectPage() {
  return (
    <Suspense
      fallback={
        <div className="py-16 text-center space-y-3">
          <p className="font-serif text-lg text-[#242B23]">Đang chuẩn bị Studio...</p>
        </div>
      }
    >
      <NewRoomProjectContent />
    </Suspense>
  );
}
