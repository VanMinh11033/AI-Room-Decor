"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Check, ChevronLeft, DollarSign, Palette, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayCategory, displayColor, displayMaterial, displayStyle } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import { StudioNavHeader } from "@/components/studio/StudioNavHeader";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { CatalogItem, Category, Color, Paginated, RoomAnalysis, RoomPreference, RoomProject } from "@/types/api";

const purposes = [
  "Nghỉ ngơi & Thư giãn",
  "Làm việc tại nhà",
  "Học tập & Nghiên cứu",
  "Tiếp đón khách quý",
  "Giải trí gia đình",
  "Đọc sách tĩnh tại",
  "Không gian đa chức năng",
];

const budgetPresets = [
  { label: "Dưới 5 triệu", min: "0", max: "5000000" },
  { label: "5 – 10 triệu", min: "5000000", max: "10000000" },
  { label: "10 – 20 triệu", min: "10000000", max: "20000000" },
  { label: "20 – 50 triệu", min: "20000000", max: "50000000" },
  { label: "Trên 50 triệu", min: "50000000", max: "" },
];

export default function RoomPreferencesPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [project, setProject] = useState<RoomProject | null>(null);
  const [analysis, setAnalysis] = useState<RoomAnalysis | null>(null);
  const [styles, setStyles] = useState<CatalogItem[]>([]);
  const [colors, setColors] = useState<Color[]>([]);
  const [materials, setMaterials] = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [styleIds, setStyleIds] = useState<number[]>([]);
  const [colorIds, setColorIds] = useState<number[]>([]);
  const [materialIds, setMaterialIds] = useState<number[]>([]);
  const [categoryIds, setCategoryIds] = useState<number[]>([]);
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [purpose, setPurpose] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [projectData, styleData, colorData, materialData, categoryData] = await Promise.all([
        apiFetch<RoomProject>(`/api/room-projects/${params.id}`),
        apiFetch<Paginated<CatalogItem>>("/api/styles?page=1&page_size=100"),
        apiFetch<Paginated<Color>>("/api/colors?page=1&page_size=100"),
        apiFetch<Paginated<CatalogItem>>("/api/materials?page=1&page_size=100"),
        apiFetch<Paginated<Category>>("/api/categories?page=1&page_size=100"),
      ]);
      setProject(projectData);
      setStyles(styleData.items);
      setColors(colorData.items);
      setMaterials(materialData.items);
      setCategories(categoryData.items);
      try {
        const storedPreference = await apiFetch<RoomPreference>(`/api/room-projects/${params.id}/preferences`);
        hydrateForm(storedPreference);
        setSaved(true);
      } catch {
        setSaved(false);
      }
      try {
        setAnalysis(await apiFetch<RoomAnalysis>(`/api/room-projects/${params.id}/analysis`));
      } catch {
        setAnalysis(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải dữ liệu. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  function hydrateForm(preference: RoomPreference) {
    setBudgetMin(preference.budget_min ? String(Number(preference.budget_min)) : "");
    setBudgetMax(preference.budget_max ? String(Number(preference.budget_max)) : "");
    setPurpose(preference.purpose || "");
    setNotes(preference.notes || "");
    setStyleIds(preference.styles.map((item) => item.id));
    setColorIds(preference.colors.map((item) => item.id));
    setMaterialIds(preference.materials.map((item) => item.id));
    setCategoryIds(preference.categories.map((item) => item.id));
  }

  function toggle(setter: (value: number[]) => void, values: number[], id: number) {
    setter(values.includes(id) ? values.filter((item) => item !== id) : [...values, id]);
    setSaved(false);
  }

  async function savePreferences() {
    setSaving(true);
    setError("");
    try {
      await apiFetch<RoomPreference>(`/api/room-projects/${params.id}/preferences`, {
        method: "PUT",
        body: JSON.stringify({
          budget_min: budgetMin ? Number(budgetMin) : null,
          budget_max: budgetMax ? Number(budgetMax) : null,
          currency: "VND",
          purpose: purpose || null,
          notes: notes || null,
          style_ids: styleIds,
          color_ids: colorIds,
          material_ids: materialIds,
          category_ids: categoryIds,
        }),
      });
      setSaved(true);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể lưu sở thích. Vui lòng thử lại.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveAndContinue() {
    await savePreferences();
    router.push(`/room-projects/${params.id}/recommendations`);
  }

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  const budgetPreview = useMemo(() => {
    const min = budgetMin ? formatVnd(Number(budgetMin)) : "0 ₫";
    const max = budgetMax ? formatVnd(Number(budgetMax)) : "Không giới hạn";
    return `${min} — ${max}`;
  }, [budgetMin, budgetMax]);

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#8A6B4E] border-t-transparent" />
        <p className="text-sm font-medium text-[#5A6258]">Đang tải hồ sơ phong cách kiến trúc...</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50/50 p-6 text-center">
        <p className="font-medium text-red-700">{error || "Không tìm thấy dự án phòng."}</p>
        <Link href="/room-projects" className="mt-4 inline-block text-sm font-semibold text-[#8A6B4E] underline">
          Quay lại danh sách dự án
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20">
      {/* 1. Cohesive Studio Navigation Stepper */}
      <StudioNavHeader
        projectId={project.id}
        projectTitle={project.title}
        roomImageUrl={project.room_image_url}
        currentStep={2}
        hasRoomImage={Boolean(project.room_image_url)}
        hasPreferences={saved}
        saveState={saving ? "saving" : error ? "error" : saved ? "saved" : "unsaved"}
        isSaving={saving}
      />

      {/* 2. Editorial Header */}
      <EditorialHeading
        eyebrow="BƯỚC 02 · GU THẨM MỸ & CÁ NHÂN HÓA"
        title="Định hình không gian sống của bạn"
        subtitle="Lựa chọn phong cách kiến trúc, bảng màu và hạn mức ngân sách để AI Studio đề xuất giải pháp nội thất tinh tuyển từ catalog."
      />

      {/* 3. Main Form Grid */}
      <div className="grid gap-8 lg:grid-cols-12 items-start">
        {/* Left Column: Context, Budget & Purpose (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Room Context Card */}
          <div className="overflow-hidden rounded-2xl border border-[#242B23]/10 bg-white shadow-sm">
            <div className="relative aspect-[16/10] bg-[#F7F4EE]">
              {project.room_image_url ? (
                <img
                  src={apiAssetUrl(project.room_image_url)}
                  alt={project.title}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center p-6 text-center text-xs text-[#5A6258]">
                  Chưa có ảnh phòng
                </div>
              )}
              <div className="absolute top-3 left-3">
                <StatusBadge variant="neutral">Không gian hiện tại</StatusBadge>
              </div>
            </div>
            <div className="p-4 sm:p-5">
              <h3 className="font-serif text-lg font-bold text-[#242B23]">{project.title}</h3>
              <p className="mt-1 text-xs text-[#5A6258]">
                {analysis?.status === "COMPLETED"
                  ? `Đã phân tích: ${analysis.existing_objects?.length || 0} đặc trưng kiến trúc nhận diện`
                  : "Chưa hoàn tất phân tích chi tiết"}
              </p>
            </div>
          </div>

          {/* Budget Setting Card */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-5">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#8A6B4E]/10 text-[#8A6B4E]">
                <DollarSign size={16} />
              </span>
              <div>
                <h3 className="text-sm font-bold text-[#242B23]">Ngân sách dự kiến</h3>
                <p className="text-xs text-[#5A6258]">Định hướng mức đầu tư cho toàn bộ nội thất phòng</p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-xs font-semibold text-[#242B23]">
                Tối thiểu (VND)
                <input
                  type="number"
                  min="0"
                  step="500000"
                  value={budgetMin}
                  onChange={(e) => {
                    setBudgetMin(e.target.value);
                    setSaved(false);
                  }}
                  placeholder="0"
                  className="mt-1.5 w-full rounded-xl border border-[#242B23]/10 bg-[#F7F4EE] px-3.5 py-2.5 text-sm text-[#242B23] outline-none transition focus:border-[#8A6B4E] focus:bg-white"
                />
              </label>
              <label className="block text-xs font-semibold text-[#242B23]">
                Tối đa (VND)
                <input
                  type="number"
                  min="0"
                  step="500000"
                  value={budgetMax}
                  onChange={(e) => {
                    setBudgetMax(e.target.value);
                    setSaved(false);
                  }}
                  placeholder="Không giới hạn"
                  className="mt-1.5 w-full rounded-xl border border-[#242B23]/10 bg-[#F7F4EE] px-3.5 py-2.5 text-sm text-[#242B23] outline-none transition focus:border-[#8A6B4E] focus:bg-white"
                />
              </label>
            </div>

            {/* Budget Presets */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#5A6258]/70">Gợi ý nhanh</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {budgetPresets.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => {
                      setBudgetMin(preset.min);
                      setBudgetMax(preset.max);
                      setSaved(false);
                    }}
                    className="rounded-full border border-[#242B23]/10 bg-[#F7F4EE] px-3 py-1.5 text-xs font-medium text-[#242B23] transition hover:border-[#8A6B4E] hover:bg-white"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Formatted Preview */}
            <div className="rounded-xl border border-[#8A6B4E]/15 bg-[#8A6B4E]/5 px-4 py-3">
              <span className="text-[11px] font-medium text-[#8A6B4E] uppercase tracking-wider">Hạn mức áp dụng</span>
              <p className="mt-0.5 text-sm font-bold text-[#242B23] font-serif">{budgetPreview}</p>
            </div>
          </div>

          {/* Primary Purpose Card */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-[#242B23]">Mục đích sử dụng chính</h3>
            <p className="text-xs text-[#5A6258]">Giúp AI tối ưu hóa tỷ lệ không gian và công năng sử dụng</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {purposes.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setPurpose(item);
                    setSaved(false);
                  }}
                  className={`rounded-xl border px-3.5 py-2.5 text-left text-xs font-semibold transition ${
                    purpose === item
                      ? "border-[#242B23] bg-[#242B23] text-white shadow-sm"
                      : "border-[#242B23]/10 bg-[#F7F4EE] text-[#242B23] hover:border-[#8A6B4E] hover:bg-white"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          {/* Additional Notes Card */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#242B23]">Yêu cầu đặc biệt</h3>
              <span className="text-[11px] text-[#5A6258]">{notes.length}/1000</span>
            </div>
            <textarea
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                setSaved(false);
              }}
              maxLength={1000}
              rows={4}
              placeholder="Ví dụ: Ưu tiên ánh sáng ấm cúng, vật liệu gỗ tự nhiên tông sồi, phong cách gọn gàng tối giản..."
              className="w-full resize-none rounded-xl border border-[#242B23]/10 bg-[#F7F4EE] p-3 text-xs text-[#242B23] outline-none transition focus:border-[#8A6B4E] focus:bg-white"
            />
          </div>
        </div>

        {/* Right Column: Aesthetic Selections (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Styles Selection */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#242B23]">Phong cách thiết kế</h3>
                <p className="text-xs text-[#5A6258]">Có thể chọn một hoặc nhiều phong cách yêu thích</p>
              </div>
              <span className="text-xs font-semibold text-[#8A6B4E]">{styleIds.length} đã chọn</span>
            </div>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {styles.map((style) => {
                const isSelected = styleIds.includes(style.id);
                return (
                  <button
                    key={style.id}
                    type="button"
                    onClick={() => toggle(setStyleIds, styleIds, style.id)}
                    className={`flex items-center justify-between rounded-xl border px-4 py-3 text-left transition ${
                      isSelected
                        ? "border-[#242B23] bg-[#242B23] text-white shadow-sm"
                        : "border-[#242B23]/10 bg-[#F7F4EE] text-[#242B23] hover:border-[#8A6B4E] hover:bg-white"
                    }`}
                  >
                    <span className="text-xs font-semibold">{displayStyle(style.name)}</span>
                    {isSelected && <Check size={16} className="text-[#8A6B4E]" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Color Palette Selection */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#242B23]">Bảng màu ưu tiên</h3>
                <p className="text-xs text-[#5A6258]">Màu sắc chủ đạo bạn muốn phối trong không gian</p>
              </div>
              <span className="text-xs font-semibold text-[#8A6B4E]">{colorIds.length} đã chọn</span>
            </div>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {colors.map((color) => {
                const isSelected = colorIds.includes(color.id);
                return (
                  <button
                    key={color.id}
                    type="button"
                    onClick={() => toggle(setColorIds, colorIds, color.id)}
                    className={`flex items-center justify-between rounded-xl border px-3.5 py-2.5 text-left transition ${
                      isSelected
                        ? "border-[#242B23] bg-[#242B23] text-white shadow-sm"
                        : "border-[#242B23]/10 bg-[#F7F4EE] text-[#242B23] hover:border-[#8A6B4E] hover:bg-white"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span
                        className="h-5 w-5 shrink-0 rounded-full border border-[#242B23]/20 shadow-xs"
                        style={{ backgroundColor: color.hex_code || "#ffffff" }}
                      />
                      <span className="truncate text-xs font-semibold">{displayColor(color.name)}</span>
                    </div>
                    {isSelected && <Check size={16} className="text-[#8A6B4E] shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Materials Selection */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#242B23]">Chất liệu mong muốn</h3>
                <p className="text-xs text-[#5A6258]">Vật liệu bề mặt tự nhiên tăng tính sang trọng</p>
              </div>
              <span className="text-xs font-semibold text-[#8A6B4E]">{materialIds.length} đã chọn</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {materials.map((material) => {
                const isSelected = materialIds.includes(material.id);
                return (
                  <button
                    key={material.id}
                    type="button"
                    onClick={() => toggle(setMaterialIds, materialIds, material.id)}
                    className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                      isSelected
                        ? "border-[#8A6B4E] bg-[#8A6B4E] text-white shadow-xs"
                        : "border-[#242B23]/10 bg-[#F7F4EE] text-[#242B23] hover:border-[#8A6B4E] hover:bg-white"
                    }`}
                  >
                    {displayMaterial(material.name)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Catalog Categories of Interest */}
          <div className="rounded-2xl border border-[#242B23]/10 bg-white p-5 sm:p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#242B23]">Nội thất cần bổ sung</h3>
                <p className="text-xs text-[#5A6258]">Chọn các nhóm sản phẩm bạn đang tìm kiếm</p>
              </div>
              <span className="text-xs font-semibold text-[#8A6B4E]">{categoryIds.length} đã chọn</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {categories.map((category) => {
                const isSelected = categoryIds.includes(category.id);
                return (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() => toggle(setCategoryIds, categoryIds, category.id)}
                    className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                      isSelected
                        ? "border-[#242B23] bg-[#242B23] text-white shadow-xs"
                        : "border-[#242B23]/10 bg-[#F7F4EE] text-[#242B23] hover:border-[#8A6B4E] hover:bg-white"
                    }`}
                  >
                    {displayCategory(category.name)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Sticky Bottom Action Bar */}
      <div className="sticky bottom-4 z-20 rounded-2xl border border-[#242B23]/10 bg-white/95 p-4 shadow-xl backdrop-blur-md">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${saved ? "bg-emerald-500" : "bg-amber-400"}`}
            />
            <p className="text-xs sm:text-sm font-medium text-[#242B23]">
              {saved
                ? "Hồ sơ gu thẩm mỹ đã được lưu an toàn."
                : "Có thay đổi chưa lưu trong hồ sơ phong cách."}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-3 w-full sm:w-auto">
            <LuxuryButton
              variant="secondary"
              size="sm"
              loading={saving}
              onClick={savePreferences}
              className="w-full sm:w-auto"
            >
              Lưu hồ sơ phong cách
            </LuxuryButton>
            <LuxuryButton
              variant="primary"
              size="sm"
              onClick={handleSaveAndContinue}
              className="w-full sm:w-auto group"
            >
              <span>Xem gợi ý nội thất</span>
              <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
            </LuxuryButton>
          </div>
        </div>
        {error && <p className="mt-2 text-xs font-semibold text-red-600">{error}</p>}
      </div>
    </div>
  );
}

function formatVnd(value: number) {
  return value.toLocaleString("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
}
