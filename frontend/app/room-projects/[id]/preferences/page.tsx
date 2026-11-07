"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Check, ChevronLeft, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayCategory, displayColor, displayMaterial, displayStyle } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { CatalogItem, Category, Color, Paginated, RoomAnalysis, RoomPreference, RoomProject } from "@/types/api";

const purposes = [
  "Nghỉ ngơi",
  "Làm việc",
  "Học tập",
  "Tiếp khách",
  "Giải trí",
  "Đọc sách",
  "Đa chức năng",
];

const budgetPresets = [
  { label: "Dưới 5 triệu", min: "0", max: "5000000" },
  { label: "5-10 triệu", min: "5000000", max: "10000000" },
  { label: "10-20 triệu", min: "10000000", max: "20000000" },
  { label: "20-50 triệu", min: "20000000", max: "50000000" },
  { label: "Trên 50 triệu", min: "50000000", max: "" },
];

export default function RoomPreferencesPage() {
  const params = useParams<{ id: string }>();
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

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  const budgetPreview = useMemo(() => {
    const min = budgetMin ? formatVnd(Number(budgetMin)) : "Chưa chọn";
    const max = budgetMax ? formatVnd(Number(budgetMax)) : "Không giới hạn";
    return `${min} - ${max}`;
  }, [budgetMin, budgetMax]);

  if (authLoading || loading) return <p>Đang tải sở thích decor...</p>;
  if (!project) return <p className="text-red-600">{error || "Không tìm thấy dự án."}</p>;

  return (
    <section className="space-y-8">
      <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-black/5">
        <div className="grid gap-0 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="p-6 md:p-8">
            <Link href={`/room-projects/${project.id}`} className="inline-flex items-center gap-2 text-sm font-semibold text-black/60">
              <ChevronLeft size={16} /> Quay lại dự án
            </Link>
            <div className="mt-8 inline-flex items-center gap-2 rounded-full bg-stone px-3 py-1 text-sm font-semibold text-clay">
              <Sparkles size={16} /> Cá nhân hóa decor
            </div>
            <h1 className="mt-4 text-4xl font-bold tracking-normal text-ink">Cá nhân hóa không gian của bạn</h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-black/65">
              Cho AI Room Decor biết phong cách, ngân sách và những món nội thất bạn mong muốn.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-4">
              <Step label="Ảnh phòng" state={project.room_image_url ? "done" : "pending"} />
              <Step label="Phân tích AI" state={analysis?.status === "COMPLETED" ? "done" : "pending"} />
              <Step label="Sở thích decor" state="current" />
              <Step label="Gợi ý nội thất" state="soon" />
            </div>
          </div>
          <div className="min-h-72 bg-stone">
            {project.room_image_url ? (
              <img src={apiAssetUrl(project.room_image_url)} alt={project.title} className="h-full min-h-72 w-full object-cover" />
            ) : (
              <div className="flex h-full min-h-72 items-center justify-center px-6 text-center text-black/50">Upload ảnh phòng để xem preview tại đây.</div>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <Section title="Ngân sách" subtitle="Dữ liệu lưu dạng số, giao diện hiển thị VND rõ ràng.">
            <div className="grid gap-3 sm:grid-cols-2">
              <BudgetInput label="Ngân sách tối thiểu" value={budgetMin} onChange={setBudgetMin} />
              <BudgetInput label="Ngân sách tối đa" value={budgetMax} onChange={setBudgetMax} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {budgetPresets.map((preset) => (
                <button key={preset.label} onClick={() => { setBudgetMin(preset.min); setBudgetMax(preset.max); setSaved(false); }} className="rounded-full bg-stone px-3 py-2 text-sm font-semibold text-ink hover:bg-clay/15">
                  {preset.label}
                </button>
              ))}
            </div>
            <p className="mt-4 rounded-lg bg-clay/10 px-4 py-3 text-sm font-semibold text-ink">{budgetPreview}</p>
          </Section>

          <Section title="Mục đích chính của không gian">
            <div className="grid gap-2 sm:grid-cols-2">
              {purposes.map((item) => (
                <button key={item} onClick={() => { setPurpose(item); setSaved(false); }} className={`rounded-xl px-4 py-3 text-left text-sm font-semibold transition ${purpose === item ? "bg-ink text-white shadow-sm" : "bg-stone text-ink hover:bg-clay/15"}`}>
                  {item}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Yêu cầu thêm">
            <textarea
              value={notes}
              onChange={(event) => { setNotes(event.target.value); setSaved(false); }}
              maxLength={1000}
              rows={6}
              className="w-full resize-none rounded-xl border border-black/10 bg-stone px-4 py-3 text-sm outline-none transition focus:border-clay focus:bg-white"
              placeholder="Ví dụ: Tôi muốn căn phòng sáng, gọn gàng, ít đồ và ưu tiên nội thất dễ vệ sinh..."
            />
            <p className="mt-2 text-right text-xs text-black/45">{notes.length}/1000</p>
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Phong cách yêu thích" subtitle="Có thể chọn nhiều phong cách từ dữ liệu catalog.">
            <div className="grid gap-3 sm:grid-cols-2">
              {styles.map((style) => <SelectableCard key={style.id} selected={styleIds.includes(style.id)} label={displayStyle(style.name)} onClick={() => toggle(setStyleIds, styleIds, style.id)} />)}
            </div>
          </Section>

          <Section title="Màu sắc ưu tiên">
            <div className="grid gap-3 sm:grid-cols-2">
              {colors.map((color) => (
                <SelectableCard key={color.id} selected={colorIds.includes(color.id)} label={displayColor(color.name)} onClick={() => toggle(setColorIds, colorIds, color.id)}>
                  <span className="h-6 w-6 rounded-full border border-black/10" style={{ backgroundColor: color.hex_code || "#ffffff" }} />
                </SelectableCard>
              ))}
            </div>
          </Section>

          <Section title="Vật liệu mong muốn">
            <div className="flex flex-wrap gap-2">
              {materials.map((material) => <Chip key={material.id} selected={materialIds.includes(material.id)} label={displayMaterial(material.name)} onClick={() => toggle(setMaterialIds, materialIds, material.id)} />)}
            </div>
          </Section>

          <Section title="Bạn muốn bổ sung gì cho căn phòng?">
            <div className="flex flex-wrap gap-2">
              {categories.map((category) => <Chip key={category.id} selected={categoryIds.includes(category.id)} label={displayCategory(category.name)} onClick={() => toggle(setCategoryIds, categoryIds, category.id)} />)}
            </div>
          </Section>
        </div>
      </div>

      <div className="sticky bottom-4 rounded-2xl bg-white/95 p-4 shadow-lg ring-1 ring-black/10 backdrop-blur">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {saved ? <p className="font-semibold text-green-700">Bạn đã hoàn tất thông tin cá nhân hóa.</p> : <p className="font-semibold text-ink">Thông tin cá nhân hóa đã sẵn sàng để lưu.</p>}
            <p className="text-sm text-black/55">Bước tiếp theo: Nhận gợi ý nội thất phù hợp từ catalog thật.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href={`/room-projects/${project.id}/recommendations`} className={`rounded-md border border-black/10 px-4 py-2 text-sm font-semibold ${saved ? "bg-white text-ink" : "pointer-events-none bg-stone text-black/40"}`}>
              Nhận gợi ý nội thất
            </Link>
            <button disabled={saving} onClick={savePreferences} className="rounded-md bg-ink px-5 py-2 text-sm font-semibold text-white transition hover:bg-black disabled:opacity-50">
              {saving ? "Đang lưu..." : "Lưu sở thích decor"}
            </button>
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    </section>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-black/5">
      <h2 className="text-xl font-bold text-ink">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-black/55">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Step({ label, state }: { label: string; state: "done" | "current" | "pending" | "soon" }) {
  const text = state === "done" ? "Hoàn tất" : state === "current" ? "Hiện tại" : state === "soon" ? "Sắp có" : "Đang chờ";
  return (
    <div className={`rounded-xl px-3 py-3 text-sm ${state === "current" ? "bg-ink text-white" : state === "done" ? "bg-green-50 text-green-800" : "bg-stone text-black/55"}`}>
      <p className="font-semibold">{label}</p>
      <p className="mt-1 text-xs opacity-75">{text}</p>
    </div>
  );
}

function BudgetInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm font-semibold text-ink">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} type="number" min="0" className="mt-2 w-full rounded-xl border border-black/10 bg-stone px-4 py-3 outline-none transition focus:border-clay focus:bg-white" />
      <span className="mt-2 block text-xs font-medium text-black/45">{value ? formatVnd(Number(value)) : "Chưa nhập"}</span>
    </label>
  );
}

function SelectableCard({ selected, label, onClick, children }: { selected: boolean; label: string; onClick: () => void; children?: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`flex min-h-16 items-center justify-between rounded-xl px-4 py-3 text-left transition ${selected ? "bg-ink text-white shadow-md" : "bg-stone text-ink hover:bg-clay/15"}`}>
      <span className="flex items-center gap-3 font-semibold">{children}{label}</span>
      {selected && <Check size={18} />}
    </button>
  );
}

function Chip({ selected, label, onClick }: { selected: boolean; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`rounded-full px-4 py-2 text-sm font-semibold transition ${selected ? "bg-clay text-white shadow-sm" : "bg-stone text-ink hover:bg-clay/15"}`}>
      {label}
    </button>
  );
}

function formatVnd(value: number) {
  return value.toLocaleString("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
}
