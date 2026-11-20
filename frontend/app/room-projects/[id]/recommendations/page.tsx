"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Check, ChevronLeft, Heart, Loader2, ShoppingCart, SlidersHorizontal, Sparkles, Wallet } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EmptyImagePlaceholder, ScoreBadge, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStyle, joinDisplay } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { DesignGeneration, Product, ProductRecommendation, RecommendationResponse, RoomAnalysis, RoomProject } from "@/types/api";

const MAX_SELECTED_PRODUCTS = 3;

/**
 * Kiểm tra xem một sản phẩm catalog đã có ảnh tham chiếu chuẩn để tạo ảnh AI hay chưa.
 * Dữ liệu được xác thực đồng bộ từ backend (is_reference_ready).
 */
function isProductEligible(product: Product): boolean {
  if (typeof product.is_reference_ready === "boolean") {
    return product.is_reference_ready;
  }
  return true;
}

/**
 * Tự động chọn 1-3 sản phẩm catalog phù hợp nhất cho phòng.
 * CHỈ chọn từ các sản phẩm đã sẵn sàng ảnh tham chiếu (isProductEligible).
 * Ưu tiên chọn từ các danh mục công năng khác nhau (VD: 1 Sofa, 1 Bàn, 1 Thảm/Đèn).
 */
function autoSelectTopProducts(items: ProductRecommendation[]): number[] {
  if (!items || items.length === 0) return [];
  const selected: number[] = [];
  const seenCategories = new Set<number>();

  // 1. Chỉ xem xét các sản phẩm đã có ảnh catalog chuẩn
  const eligibleItems = items.filter((item) => isProductEligible(item.product));

  // 2. Ưu tiên chọn từ các danh mục khác nhau
  for (const item of eligibleItems) {
    if (selected.length >= MAX_SELECTED_PRODUCTS) break;
    const catId = item.product.category_id || item.product.category?.id;
    if (catId && !seenCategories.has(catId)) {
      seenCategories.add(catId);
      selected.push(item.product.id);
    }
  }

  // 3. Nếu chưa đủ 3 món, điền thêm từ các sản phẩm hợp lệ còn lại
  if (selected.length < MAX_SELECTED_PRODUCTS) {
    for (const item of eligibleItems) {
      if (selected.length >= MAX_SELECTED_PRODUCTS) break;
      if (!selected.includes(item.product.id)) {
        selected.push(item.product.id);
      }
    }
  }
  return selected;
}

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
        apiFetch<RecommendationResponse>(`/api/room-projects/${params.id}/recommendations?limit=50`),
      ]);
      setProject(projectData);
      setAnalysis(analysisData);
      setRecommendations(recommendationData);

      // V1.5 PRO: Ưu tiên bộ sản phẩm đã được tối ưu hóa ngân sách (Bundle Optimizer)
      const bundleIds = recommendationData.bundle?.product_ids;
      if (bundleIds && bundleIds.length > 0) {
        setSelectedIds(bundleIds);
      } else {
        const topSelected = autoSelectTopProducts(recommendationData.items);
        setSelectedIds(topSelected);
      }
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

  const selectedProducts = useMemo(() => {
    if (!recommendations) return [];
    return selectedIds
      .map((id) => recommendations.items.find((item) => item.product.id === id))
      .filter((item): item is ProductRecommendation => Boolean(item));
  }, [recommendations, selectedIds]);

  // V1.5 PRO Budget Bundle Totals
  const totalSelectedPrice = useMemo(() => {
    return selectedProducts.reduce((sum, item) => sum + Number(item.product.price || 0), 0);
  }, [selectedProducts]);

  const userBudgetMax = useMemo(() => {
    const eff = recommendations?.effective_preference?.budget_max;
    if (typeof eff === "number") return eff;
    const pref = recommendations?.preference?.budget_max;
    if (typeof pref === "number") return pref;
    return null;
  }, [recommendations]);

  const remainingBudget = useMemo(() => {
    if (userBudgetMax === null) return null;
    return userBudgetMax - totalSelectedPrice;
  }, [userBudgetMax, totalSelectedPrice]);

  const toggleProduct = (productId: number) => {
    setGenerationError("");
    if (selectedIds.includes(productId)) {
      setSelectedIds((current) => current.filter((id) => id !== productId));
      return;
    }
    if (selectedIds.length >= MAX_SELECTED_PRODUCTS) {
      setGenerationError(`Hệ thống tự động phối cảnh tối đa ${MAX_SELECTED_PRODUCTS} sản phẩm để bảo đảm chất lượng bố cục phòng. Vui lòng bỏ chọn một món trước khi thêm món khác.`);
      return;
    }
    setSelectedIds((current) => [...current, productId]);
  };

  /**
   * Nút bấm duy nhất: Tạo thiết kế AI với Cloudflare FLUX.2 Dev
   */
  const handleCreateAIDesign = async () => {
    if (generationInFlight.current) return;
    if (selectedIds.length === 0) {
      setGenerationError("Vui lòng chọn từ 1 đến 3 sản phẩm catalog để tạo thiết kế.");
      return;
    }
    generationInFlight.current = true;
    setGenerating(true);
    setGenerationError("");

    try {
      const generation = await apiFetch<DesignGeneration>(`/api/room-projects/${params.id}/design-generations`, {
        method: "POST",
        body: JSON.stringify({
          product_ids: selectedIds,
          selection_mode: "MANUAL",
          generation_mode: "AI_PHOTOREALISTIC_PREVIEW",
          force: true,
        }),
      });
      router.push(`/room-projects/${params.id}/design-generations/${generation.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Không thể tạo thiết kế phòng";
      if (message.includes("CLOUDFLARE_IMAGE_DAILY_QUOTA_EXCEEDED")) {
        setGenerationError("Hạn mức 10.000 Neurons miễn phí hôm nay của tài khoản Cloudflare Free đã chạm trần (Mã lỗi 4006 từ Cloudflare). Hạn mức sẽ tự động được làm mới (reset) lúc 00:00 UTC (tương đương 07:00 sáng mai giờ Việt Nam).");
      } else if (message.includes("CLOUDFLARE_IMAGE_RATE_LIMIT_OR_BUSY") || message.includes("3040")) {
        setGenerationError("Máy chủ Cloudflare AI đang xử lý quá nhiều yêu cầu đồng thời (Mã lỗi 3040 - Rate Limit). Hạn mức ngày vẫn còn, vui lòng đợi 30 - 60 giây rồi thử lại.");
      } else if (message.includes("CLOUDFLARE_IMAGE_LOCK_BUSY")) {
        setGenerationError("Hệ thống đang bận điều phối quota hoặc xử lý tác vụ khác. Vui lòng thử lại sau vài giây.");
      } else if (message.includes("CLOUDFLARE_IMAGE_QUOTA_ERROR") || message.includes("quota")) {
        const detailPart = message.split(":").slice(1).join(":").trim();
        setGenerationError(detailPart || "Hạn mức tạo ảnh Cloudflare AI hôm nay đã hết. Vui lòng thử lại vào 07:00 sáng mai (giờ Việt Nam).");
      } else if (message.includes("CLOUDFLARE_IMAGE_SERVER_ERROR") || message.includes("3043")) {
        setGenerationError("Máy chủ Cloudflare AI hiện đang quá tải hoặc gặp sự cố. Vui lòng thử lại sau giây lát.");
      } else if (message.includes("CLOUDFLARE_IMAGE_AUTH_ERROR")) {
        setGenerationError("Lỗi xác thực token Cloudflare AI. Vui lòng kiểm tra lại cấu hình hệ thống.");
      } else if (message.includes("FLOOR_PLANE_NOT_RELIABLE") || message.includes("FLOOR_NOT_DETECTED")) {
        setGenerationError("Không thể xác định mặt sàn an toàn từ ảnh phòng để bố trí nội thất tự động. Vui lòng chụp lại ảnh với góc nhìn bao quát rõ mặt sàn.");
      } else if (message.includes("NO_COMPOSITIBLE_PRODUCT_IMAGES")) {
        setGenerationError("Các sản phẩm đã chọn chưa có ảnh tham chiếu hợp lệ trong catalog.");
      } else if (message.startsWith("IMAGE_PROVIDER_NOT_CONFIGURED")) {
        setGenerationError("Chưa cấu hình dịch vụ AI tạo ảnh cho hệ thống.");
      } else {
        setGenerationError(message);
      }
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

  const effPref = recommendations?.effective_preference;
  const stylesDisplay = effPref?.styles && effPref.styles.length > 0 
    ? effPref.styles.join(", ") 
    : joinDisplay(recommendations?.preference.styles, (item) => displayStyle(item.name));
  const colorsDisplay = effPref?.colors && effPref.colors.length > 0
    ? effPref.colors.join(", ")
    : joinDisplay(recommendations?.preference.colors, (item) => displayColor(item.name));

  return (
    <section className="space-y-8">
      {/* 1. Project Info Header with Provenance */}
      <div className="overflow-hidden rounded-3xl border border-ink/10 bg-white shadow-soft">
        <div className="grid lg:grid-cols-[0.78fr_1.22fr]">
          <div className="min-h-80 bg-stone/20 flex items-center justify-center">
            {project?.room_image_url ? (
              <img src={apiAssetUrl(project.room_image_url)} alt={project.title} className="h-full min-h-80 w-full object-contain" />
            ) : (
              <EmptyImagePlaceholder label="Không có ảnh phòng" />
            )}
          </div>
          <div className="p-6 md:p-8">
            <Link href={`/room-projects/${params.id}`} className="inline-flex items-center gap-2 text-sm font-bold text-charcoal/60">
              <ChevronLeft size={16} /> Quay lại dự án
            </Link>
            <div className="mt-6 flex flex-wrap items-center gap-2">
              <span className="inline-flex rounded-full bg-clay/10 px-3 py-1 text-sm font-bold text-clay">Bước 4 · Gợi ý & Tạo thiết kế AI</span>
              {recommendations?.recommendation_version && (
                <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-black text-emerald-800">
                  Engine {recommendations.recommendation_version.toUpperCase()} PRO
                </span>
              )}
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight text-ink md:text-5xl">Gợi ý sản phẩm dành cho căn phòng này</h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-charcoal/65">
              Hệ thống đã phân tích không gian, kết hợp sở thích cá nhân và ngân sách để tính toán tổ hợp nội thất hài hòa nhất. Bạn có thể xem giải thích lý do bên dưới hoặc bấm nút để tạo ảnh phối cảnh ngay.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <ContextTile 
                label="Loại phòng" 
                value={displayRoomType(effPref?.room_type || analysis?.room_type || project?.room_type) || "-"} 
                provenance={effPref?.provenance?.room_type}
              />
              <ContextTile 
                label="Ngân sách dự kiến" 
                value={budgetLabel(recommendations)} 
                provenance={effPref?.provenance?.budget}
              />
              <ContextTile 
                label="Phong cách" 
                value={stylesDisplay || "Hiện đại tự nhiên"} 
                provenance={effPref?.provenance?.styles}
              />
              <ContextTile 
                label="Màu sắc chủ đạo" 
                value={colorsDisplay || "Hài hòa theo phòng"} 
                provenance={effPref?.provenance?.colors}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Hero Action Card & Budget Bundle Optimizer */}
      <div className="overflow-hidden rounded-3xl border-2 border-clay bg-gradient-to-r from-clay/5 via-white to-ivory p-6 shadow-md md:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3 flex-1">
            <div className="inline-flex items-center gap-2 rounded-full bg-clay px-3 py-1 text-xs font-black uppercase tracking-wider text-white">
              <Sparkles size={14} /> Tự động 100% · Một chạm tạo thiết kế
            </div>
            <h2 className="text-2xl font-black text-ink md:text-3xl">Tạo phương án thiết kế phòng với AI</h2>
            <p className="max-w-xl text-sm leading-relaxed text-charcoal/70">
              {selectedProducts.length > 0 ? (
                <>
                  Hệ thống đã chọn <strong>{selectedProducts.length}</strong> sản phẩm tối ưu công năng (Anchor, Functional, Accent) theo ngân sách của bạn:
                </>
              ) : (
                <>
                  Vui lòng chọn từ 1 đến 3 sản phẩm catalog bên dưới để tạo thiết kế:
                </>
              )}
            </p>

            {/* Showcase các sản phẩm được chọn */}
            {selectedProducts.length > 0 && (
              <div className="flex flex-wrap gap-3 pt-1">
                {selectedProducts.map((item) => {
                  const img = item.product.images.find((i) => i.is_primary)?.image_url || item.product.images[0]?.image_url;
                  return (
                    <div key={item.product.id} className="flex items-center gap-3 rounded-2xl border border-clay/20 bg-white/90 p-2.5 shadow-sm">
                      <div className="h-12 w-12 flex-shrink-0 overflow-hidden rounded-xl bg-ivory">
                        {img ? (
                          <img src={apiAssetUrl(img)} alt={item.product.name} className="h-full w-full object-cover" />
                        ) : (
                          <div className="h-full w-full bg-stone" />
                        )}
                      </div>
                      <div className="pr-2">
                        <div className="text-xs font-black text-ink line-clamp-1">{item.product.name}</div>
                        <div className="text-[11px] font-bold text-clay">{Number(item.product.price).toLocaleString("vi-VN")} đ</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* V1.5 PRO: Budget Bundle Summary & Explanation */}
            <div className="mt-4 flex flex-wrap items-center gap-4 rounded-2xl border border-ink/10 bg-white/80 p-3.5 text-xs text-charcoal/75">
              <div className="flex items-center gap-2">
                <Wallet size={16} className="text-clay" />
                <span>Tổng giá bộ nội thất: <strong className="text-ink font-black">{totalSelectedPrice.toLocaleString("vi-VN")} đ</strong></span>
              </div>
              {userBudgetMax !== null && (
                <div className="flex items-center gap-2">
                  <span>Hạn mức: <strong className="text-ink font-black">{userBudgetMax.toLocaleString("vi-VN")} đ</strong></span>
                </div>
              )}
              {remainingBudget !== null && (
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 font-black text-[11px] ${
                    remainingBudget >= 0 ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
                  }`}>
                    {remainingBudget >= 0 
                      ? `Còn lại ${remainingBudget.toLocaleString("vi-VN")} đ` 
                      : `Vượt ${Math.abs(remainingBudget).toLocaleString("vi-VN")} đ`}
                  </span>
                </div>
              )}
            </div>

            {recommendations?.bundle?.bundle_explanation && (
              <p className="text-xs font-medium italic text-charcoal/60">
                💡 {recommendations.bundle.bundle_explanation}
              </p>
            )}
          </div>

          {/* Nút bấm DUY NHẤT */}
          <div className="flex flex-col items-stretch lg:items-end gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={handleCreateAIDesign}
              disabled={generating || selectedIds.length === 0}
              className="primary-cta inline-flex items-center justify-center gap-3 rounded-2xl px-10 py-5 text-lg font-black shadow-xl transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:hover:scale-100"
            >
              {generating ? <Loader2 size={24} className="animate-spin" /> : <Sparkles size={24} />}
              <span>{generating ? "Đang tạo thiết kế nội thất AI..." : "✨ TẠO THIẾT KẾ AI"}</span>
            </button>
            <span className="text-[11px] text-center lg:text-right font-medium text-charcoal/50">
              Tạo ảnh phối cảnh ánh sáng tự nhiên qua Cloudflare FLUX
            </span>
          </div>
        </div>

        {generationError && (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">
            {generationError}
          </div>
        )}
      </div>

      {/* 3. Catalog Showcase Header */}
      <div className="surface-card flex flex-col gap-4 p-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 text-sm font-black text-ink">
            <SlidersHorizontal size={18} /> Danh mục sản phẩm đề xuất ({visibleItems.length})
          </div>
          <p className="mt-1 text-sm text-charcoal/55">
            Điểm phù hợp (0–100) được tính dựa trên 8 tiêu chí MCDA (phong cách, loại phòng, màu sắc, vật liệu, ngân sách, công năng, không gian).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select value={category} onChange={(event) => setCategory(event.target.value)} className="premium-input py-2">
            <option value="">Tất cả danh mục</option>
            {categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select value={sort} onChange={(event) => setSort(event.target.value)} className="premium-input py-2">
            <option value="match">Độ phù hợp cao nhất</option>
            <option value="price_asc">Giá thấp đến cao</option>
            <option value="price_desc">Giá cao đến thấp</option>
          </select>
        </div>
      </div>

      {/* 4. Products Grid */}
      {visibleItems.length === 0 ? (
        <SectionCard>Chưa có sản phẩm catalog phù hợp với điều kiện hiện tại.</SectionCard>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {visibleItems.map((item) => (
            <RecommendationCard
              key={item.product.id}
              item={item}
              selected={selectedIds.includes(item.product.id)}
              onToggle={toggleProduct}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function RecommendationCard({
  item,
  selected,
  onToggle,
}: {
  item: ProductRecommendation;
  selected: boolean;
  onToggle: (productId: number) => void;
}) {
  const primaryImage = item.product.images.find((image) => image.is_primary)?.image_url || item.product.images[0]?.image_url;
  const tags = [...item.product.styles, ...item.product.colors, ...item.product.materials].slice(0, 4);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState("");

  const roleLabel = item.role === "ANCHOR" ? "Món chính" : item.role === "FUNCTIONAL" ? "Tiện ích" : "Trang trí";
  const roleColor = item.role === "ANCHOR" ? "bg-amber-100 text-amber-900 border-amber-300" : item.role === "FUNCTIONAL" ? "bg-blue-100 text-blue-900 border-blue-300" : "bg-purple-100 text-purple-900 border-purple-300";

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
    <article className={`group overflow-hidden rounded-2xl border bg-white shadow-card transition hover:-translate-y-1 hover:shadow-soft ${selected ? "border-clay ring-2 ring-clay/20" : "border-ink/10"}`}>
      <div className="relative aspect-[4/3] bg-ivory">
        {primaryImage ? (
          <img src={apiAssetUrl(primaryImage)} alt={item.product.name} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.04]" />
        ) : (
          <EmptyImagePlaceholder label="Sản phẩm chưa có ảnh" />
        )}
        <div className="absolute left-3 top-3 flex flex-col gap-1 items-start">
          <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-black text-clay shadow-sm">{displayCategory(item.product.category.name)}</span>
          <div className="flex items-center gap-1">
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold shadow-xs ${roleColor}`}>
              {roleLabel}
            </span>
            {item.boost && item.boost >= 10.0 && (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-rose-600 text-white px-2 py-0.5 text-[10px] font-bold shadow-xs">
                <Heart size={10} fill="currentColor" /> Yêu thích (+10)
              </span>
            )}
          </div>
          <span className="rounded-full bg-emerald-600/90 text-white px-2 py-0.5 text-[10px] font-bold shadow-xs">✓ Sẵn sàng tạo ảnh AI</span>
        </div>
        <span className="absolute right-3 top-3" title={`Điểm phù hợp: ${item.score}/100`}><ScoreBadge score={item.score} /></span>

        {/* Badge trạng thái chọn */}
        <button
          type="button"
          onClick={() => onToggle(item.product.id)}
          className={`absolute bottom-3 right-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-black shadow-sm transition ${
            selected
              ? "bg-ink text-white"
              : "bg-white/90 text-charcoal/70 hover:bg-white hover:text-ink"
          }`}
        >
          {selected ? (
            <>
              <Check size={14} className="text-emerald-400" />
              <span>Đang dùng trong AI</span>
            </>
          ) : (
            <span>Chọn món này</span>
          )}
        </button>
      </div>
      <div className="p-5">
        <Link href={`/products/${item.product.id}`} className="block text-lg font-black text-ink hover:underline">{item.product.name}</Link>
        <p className="mt-2 text-xl font-black text-clay">{Number(item.product.price).toLocaleString("vi-VN")} đ</p>
        
        {/* Reasons explainability */}
        <ul className="mt-4 space-y-1.5 text-sm text-charcoal/70">
          {item.reasons.slice(0, 3).map((reason) => (
            <li key={reason} className="flex items-start gap-1.5 text-xs">
              <span className="text-emerald-600 font-bold">✓</span>
              <span>{reason}</span>
            </li>
          ))}
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

function ContextTile({ label, value, provenance }: { label: string; value: string; provenance?: string }) {
  let provBadge = null;
  if (provenance === "INHERITED_PROFILE") {
    provBadge = <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-bold text-sky-800">Từ tài khoản</span>;
  } else if (provenance === "ROOM_PREFERENCE" || provenance === "EXPLICIT_OVERRIDE") {
    provBadge = <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">Theo phòng</span>;
  } else if (provenance === "ROOM_ANALYSIS") {
    provBadge = <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">Từ ảnh phòng</span>;
  }

  return (
    <div className="rounded-2xl border border-ink/10 bg-ivory/60 p-4">
      <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-charcoal/50">
        <span>{label}</span>
        {provBadge}
      </div>
      <div className="mt-1 text-sm font-black text-ink">{value}</div>
    </div>
  );
}

function budgetLabel(recommendations: RecommendationResponse | null) {
  const eff = recommendations?.effective_preference?.budget_max;
  if (typeof eff === "number") return `Tối đa ${Number(eff).toLocaleString("vi-VN")} đ`;
  const pref = recommendations?.preference;
  if (!pref) return "-";
  if (pref.budget_max) return `${Number(pref.budget_max).toLocaleString("vi-VN")} đ`;
  if (pref.budget_min) return `Từ ${Number(pref.budget_min).toLocaleString("vi-VN")} đ`;
  return "Không giới hạn";
}
