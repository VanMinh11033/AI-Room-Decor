"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Check, ChevronLeft, Loader2, ShoppingCart, SlidersHorizontal, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EmptyImagePlaceholder, ScoreBadge, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStyle, joinDisplay } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { DesignGeneration, ProductRecommendation, RecommendationResponse, RoomAnalysis, RoomProject } from "@/types/api";

const MAX_SELECTED_PRODUCTS = 12;

export default function RecommendationsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [project, setProject] = useState<RoomProject | null>(null);
  const [analysis, setAnalysis] = useState<RoomAnalysis | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [sort, setSort] = useState("match");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const generationInFlight = useRef(false);
  const [error, setError] = useState("");
  const [generationError, setGenerationError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [projectData, analysisData, recommendationData] = await Promise.all([
        apiFetch<RoomProject>(`/api/room-projects/${params.id}`),
        apiFetch<RoomAnalysis>(`/api/room-projects/${params.id}/analysis`),
        apiFetch<RecommendationResponse>(`/api/room-projects/${params.id}/recommendations?limit=24`),
      ]);
      setProject(projectData);
      setAnalysis(analysisData);
      setRecommendations(recommendationData);
      setSelectedIds(recommendationData.items.slice(0, 4).map((item) => item.product.id));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Không thể tải gợi ý nội thất";
      if (message === "ROOM_PREFERENCES_REQUIRED") setError("Bạn cần lưu sở thích decor trước khi nhận gợi ý nội thất.");
      else if (message === "ROOM_ANALYSIS_REQUIRED") setError("Bạn cần hoàn tất phân tích ảnh phòng trước khi nhận gợi ý nội thất.");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  const categories = useMemo(() => {
    const map = new Map<number, string>();
    recommendations?.items.forEach((item) => map.set(item.product.category.id, displayCategory(item.product.category.name)));
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [recommendations]);

  const visibleItems = useMemo(() => {
    const items = [...(recommendations?.items || [])];
    const filtered = category ? items.filter((item) => String(item.product.category.id) === category) : items;
    if (sort === "price_asc") return filtered.sort((a, b) => Number(a.product.price) - Number(b.product.price));
    if (sort === "price_desc") return filtered.sort((a, b) => Number(b.product.price) - Number(a.product.price));
    return filtered.sort((a, b) => b.score - a.score || Number(a.product.price) - Number(b.product.price) || a.product.id - b.product.id);
  }, [recommendations, sort, category]);

  const toggleProduct = (productId: number) => {
    setGenerationError("");
    if (selectedIds.includes(productId)) {
      setSelectedIds((current) => current.filter((id) => id !== productId));
      return;
    }
    if (selectedIds.length >= MAX_SELECTED_PRODUCTS) {
      setGenerationError(`Gemini Image hỗ trợ tối đa ${MAX_SELECTED_PRODUCTS} sản phẩm trong một thiết kế. Hãy bỏ chọn sản phẩm trước khi chọn thêm.`);
      return;
    }
    setSelectedIds((current) => [...current, productId]);
  };

  const createGeneration = async () => {
    if (generationInFlight.current) return;
    if (selectedIds.length === 0) {
      setGenerationError("Hãy chọn ít nhất một sản phẩm để tạo thiết kế.");
      return;
    }
    generationInFlight.current = true;
    setGenerating(true);
    setGenerationError("");
    try {
      const generation = await apiFetch<DesignGeneration>(`/api/room-projects/${params.id}/design-generations`, {
        method: "POST",
        body: JSON.stringify({ product_ids: selectedIds }),
      });
      router.push(`/room-projects/${params.id}/design-generations/${generation.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Không thể tạo thiết kế phòng";
      setGenerationError(message.startsWith("IMAGE_PROVIDER_NOT_CONFIGURED") ? "Chưa cấu hình AI image provider cho môi trường này." : message);
    } finally {
      generationInFlight.current = false;
      setGenerating(false);
    }
  };

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải gợi ý nội thất...</p>;

  if (error) {
    return (
      <SectionCard className="mx-auto max-w-2xl">
        <Link href={`/room-projects/${params.id}`} className="inline-flex items-center gap-2 text-sm font-bold text-charcoal/60">
          <ChevronLeft size={16} /> Quay lại dự án
        </Link>
        <h1 className="mt-5 text-3xl font-black text-ink">Chưa thể tạo gợi ý</h1>
        <p className="mt-3 text-charcoal/65">{error}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href={`/room-projects/${params.id}`} className="secondary-cta">Kiểm tra dự án</Link>
          <Link href={`/room-projects/${params.id}/preferences`} className="primary-cta">Chọn sở thích decor</Link>
        </div>
      </SectionCard>
    );
  }

  return (
    <section className="space-y-8">
      <div className="overflow-hidden rounded-3xl border border-ink/10 bg-white shadow-soft">
        <div className="grid lg:grid-cols-[0.78fr_1.22fr]">
          <div className="min-h-80 bg-ivory">
            {project?.room_image_url ? (
              <img src={apiAssetUrl(project.room_image_url)} alt={project.title} className="h-full min-h-80 w-full object-cover" />
            ) : (
              <EmptyImagePlaceholder label="Không có ảnh phòng" />
            )}
          </div>
          <div className="p-6 md:p-8">
            <Link href={`/room-projects/${params.id}`} className="inline-flex items-center gap-2 text-sm font-bold text-charcoal/60">
              <ChevronLeft size={16} /> Quay lại dự án
            </Link>
            <div className="mt-6 inline-flex rounded-full bg-clay/10 px-3 py-1 text-sm font-bold text-clay">Bước 4 · Gợi ý nội thất</div>
            <h1 className="mt-4 text-3xl font-black tracking-tight text-ink md:text-5xl">Gợi ý sản phẩm dành cho căn phòng này</h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-charcoal/65">Dựa trên phân tích AI, ngân sách, phong cách và catalog sản phẩm thật.</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <ContextTile label="Loại phòng" value={displayRoomType(analysis?.room_type || project?.room_type) || "-"} />
              <ContextTile label="Ngân sách" value={budgetLabel(recommendations)} />
              <ContextTile label="Phong cách" value={joinDisplay(recommendations?.preference.styles, (item) => displayStyle(item.name))} />
              <ContextTile label="Màu sắc" value={joinDisplay(recommendations?.preference.colors, (item) => displayColor(item.name))} />
            </div>
          </div>
        </div>
      </div>

      <div className="surface-card flex flex-col gap-4 p-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 text-sm font-black text-ink">
            <SlidersHorizontal size={18} /> {visibleItems.length} sản phẩm phù hợp
          </div>
          <p className="mt-1 text-sm text-charcoal/55">{selectedIds.length}/{MAX_SELECTED_PRODUCTS} sản phẩm đang được chọn cho thiết kế AI.</p>
          <p className="mt-1 text-xs text-charcoal/45">Ảnh sản phẩm đã chọn sẽ được dùng làm ảnh tham chiếu để giữ kiểu dáng, màu sắc và đặc điểm sản phẩm gần nhất có thể.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select value={category} onChange={(event) => setCategory(event.target.value)} className="premium-input py-2">
            <option value="">Tất cả danh mục</option>
            {categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select value={sort} onChange={(event) => setSort(event.target.value)} className="premium-input py-2">
            <option value="match">Phù hợp nhất</option>
            <option value="price_asc">Giá thấp đến cao</option>
            <option value="price_desc">Giá cao đến thấp</option>
          </select>
          <button type="button" onClick={createGeneration} disabled={generating || selectedIds.length === 0} className="primary-cta">
            {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Tạo thiết kế AI
          </button>
        </div>
      </div>

      {generationError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{generationError}</div>}

      {visibleItems.length === 0 ? (
        <SectionCard>Không có sản phẩm phù hợp với điều kiện hiện tại.</SectionCard>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {visibleItems.map((item) => (
            <RecommendationCard key={item.product.id} item={item} selected={selectedIds.includes(item.product.id)} onToggle={toggleProduct} />
          ))}
        </div>
      )}
    </section>
  );
}

function RecommendationCard({ item, selected, onToggle }: { item: ProductRecommendation; selected: boolean; onToggle: (productId: number) => void }) {
  const primaryImage = item.product.images.find((image) => image.is_primary)?.image_url || item.product.images[0]?.image_url;
  const tags = [...item.product.styles, ...item.product.colors, ...item.product.materials].slice(0, 4);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState("");

  async function handleAddToCart() {
    setAdding(true);
    setMessage("");
    try {
      await addToCart(item.product.id);
      setMessage("Đã thêm vào giỏ.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Không thêm được vào giỏ.");
    } finally {
      setAdding(false);
    }
  }

  return (
    <article className={`group overflow-hidden rounded-2xl border bg-white shadow-card transition hover:-translate-y-1 hover:shadow-soft ${selected ? "border-clay" : "border-ink/10"}`}>
      <div className="relative aspect-[4/3] bg-ivory">
        {primaryImage ? (
          <img src={apiAssetUrl(primaryImage)} alt={item.product.name} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.04]" />
        ) : (
          <EmptyImagePlaceholder label="Sản phẩm chưa có ảnh" />
        )}
        <span className="absolute left-3 top-3 rounded-full bg-white/90 px-3 py-1 text-xs font-black text-clay shadow-sm">{displayCategory(item.product.category.name)}</span>
        <span className="absolute right-3 top-3"><ScoreBadge score={item.score} /></span>
        <button
          type="button"
          onClick={() => onToggle(item.product.id)}
          aria-label={selected ? "Bỏ chọn sản phẩm" : "Chọn sản phẩm"}
          className={`absolute bottom-3 right-3 inline-flex h-11 w-11 items-center justify-center rounded-full border text-sm font-black shadow-sm ${
            selected ? "border-ink bg-ink text-white" : "border-ink/10 bg-white text-charcoal/60"
          }`}
        >
          {selected && <Check size={18} />}
        </button>
      </div>
      <div className="p-5">
        <Link href={`/products/${item.product.id}`} className="block text-lg font-black text-ink hover:underline">{item.product.name}</Link>
        <p className="mt-2 text-xl font-black text-clay">{Number(item.product.price).toLocaleString("vi-VN")} đ</p>
        <ul className="mt-4 space-y-2 text-sm text-charcoal/65">
          {item.reasons.slice(0, 3).map((reason) => <li key={reason}>• {reason}</li>)}
        </ul>
        <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold text-charcoal/60">
          {tags.map((tag) => (
            <span key={`${tag.id}-${tag.name}`} className="rounded-full bg-ivory px-2 py-1">
              {"hex_code" in tag ? displayColor(tag.name) : displayStyle(tag.name) !== tag.name ? displayStyle(tag.name) : displayMaterial(tag.name)}
            </span>
          ))}
        </div>
        <button type="button" onClick={handleAddToCart} disabled={adding} className="secondary-cta mt-4 w-full">
          <ShoppingCart size={16} /> {adding ? "Đang thêm..." : "Thêm vào giỏ"}
        </button>
        {message && <p className="mt-2 text-sm font-bold text-green-700">{message}</p>}
      </div>
    </article>
  );
}

function ContextTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-ivory px-4 py-3">
      <p className="text-xs font-black uppercase text-charcoal/45">{label}</p>
      <p className="mt-1 font-bold text-ink">{value}</p>
    </div>
  );
}

function budgetLabel(data: RecommendationResponse | null) {
  if (!data) return "-";
  const min = data.preference.budget_min ? Number(data.preference.budget_min).toLocaleString("vi-VN") : "0";
  const max = data.preference.budget_max ? Number(data.preference.budget_max).toLocaleString("vi-VN") : "không giới hạn";
  return `${min} - ${max} đ`;
}
