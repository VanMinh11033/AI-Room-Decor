"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Check,
  ChevronLeft,
  Heart,
  Loader2,
  Package,
  ShoppingCart,
  SlidersHorizontal,
  Sparkles,
  Wallet,
} from "lucide-react";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getPreselectedProduct } from "@/lib/studio";
import { EmptyImagePlaceholder, ScoreBadge } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStyle, joinDisplay } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import { StudioNavHeader } from "@/components/studio/StudioNavHeader";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
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

function RecommendationsContent() {
  const searchParams = useSearchParams();
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

      // V1.5 PRO: Ưu tiên bộ sản phẩm đã được tối ưu hóa ngân sách hoặc sản phẩm preselected từ Catalog (AUD-P1-002)
      const bundleIds = recommendationData.bundle?.product_ids;
      const preselected = getPreselectedProduct();
      const preselectParam = searchParams.get("preselect_product_id");
      const preselectedId = preselectParam ? Number(preselectParam) : preselected ? preselected.id : null;

      let initialSelected: number[] = [];
      if (bundleIds && bundleIds.length > 0) {
        initialSelected = [...bundleIds];
      } else {
        initialSelected = autoSelectTopProducts(recommendationData.items);
      }

      if (preselectedId && preselectedId > 0) {
        const existingItem = recommendationData.items.find((it) => it.product.id === preselectedId);
        if (existingItem) {
          existingItem.role = "CUSTOMER_PRESELECTED";
        }
        const existsInItems = Boolean(existingItem);
        if (!existsInItems) {
          try {
            const singleProduct = await apiFetch<Product>(`/api/products/${preselectedId}`);
            if (singleProduct) {
              recommendationData.items.unshift({
                product: singleProduct,
                score: 99,
                reasons: ["Sản phẩm do bạn chủ động chọn từ Catalog để đưa vào không gian này."],
                breakdown: {},
                role: "CUSTOMER_PRESELECTED",
              });
            }
          } catch {
            // non-fatal
          }
        }
        initialSelected = Array.from(new Set([preselectedId, ...initialSelected])).slice(0, MAX_SELECTED_PRODUCTS);
      }

      setSelectedIds(initialSelected);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Không thể tải gợi ý nội thất";
      if (message === "ROOM_PREFERENCES_REQUIRED") setError("Bạn cần lưu sở thích decor trước khi nhận gợi ý nội thất.");
      else if (message === "ROOM_ANALYSIS_REQUIRED") setError("Bạn cần hoàn tất phân tích ảnh phòng trước khi nhận gợi ý nội thất.");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, [params.id, searchParams]);

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

  const isAIBundle = useMemo(() => {
    const bundleIds = recommendations?.bundle?.product_ids || [];
    if (!bundleIds.length || selectedIds.length !== bundleIds.length) return false;
    const sortedSelected = [...selectedIds].sort((a, b) => a - b);
    const sortedBundle = [...bundleIds].sort((a, b) => a - b);
    return sortedSelected.every((id, idx) => id === sortedBundle[idx]);
  }, [recommendations, selectedIds]);

  const toggleProduct = (productId: number) => {
    setGenerationError("");
    if (selectedIds.includes(productId)) {
      setSelectedIds((current) => current.filter((id) => id !== productId));
      return;
    }
    if (selectedIds.length >= MAX_SELECTED_PRODUCTS) {
      setGenerationError("Bạn đã chọn tối đa 3 sản phẩm tham chiếu cho AI. Vui lòng bỏ bớt 1 món để chọn món mới.");
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
      // Log diagnostic technical details internally (AUD-P1-004)
      const sanitizedMsg = typeof message === "string" ? message.replace(/Bearer\s+[A-Za-z0-9-_.]+/gi, "Bearer ***").replace(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g, "***@***.***") : "Unknown Error";
      console.error("AI Studio Generation Diagnostic:", sanitizedMsg);

      if (message.includes("CLOUDFLARE_IMAGE_DAILY_QUOTA_EXCEEDED") || message.includes("4006")) {
        setGenerationError("Studio hiện đang có lượng yêu cầu thiết kế cao trong ngày. Để đảm bảo chất lượng thẩm mỹ cao nhất, hệ thống sẽ mở thêm lượt tạo phối cảnh mới vào 07:00 sáng mai (giờ Việt Nam). Bạn vẫn có thể xem lại các phương án đã lưu hoặc tiếp tục chọn sản phẩm catalog.");
      } else if (message.includes("CLOUDFLARE_IMAGE_RATE_LIMIT_OR_BUSY") || message.includes("3040")) {
        setGenerationError("Hệ thống đang đồng thời xử lý phối cảnh cho nhiều khách hàng. Không gian của bạn đang được ưu tiên hàng đợi, vui lòng bấm thử lại sau 30–60 giây.");
      } else if (message.includes("CLOUDFLARE_IMAGE_LOCK_BUSY")) {
        setGenerationError("Hệ thống đang hoàn tất xử lý không gian trước đó. Vui lòng bấm thử lại sau giây lát.");
      } else if (message.includes("CLOUDFLARE_IMAGE_QUOTA_ERROR") || message.includes("quota")) {
        setGenerationError("Studio hiện đang điều phối hàng đợi tạo ảnh. Vui lòng thử lại sau giây lát hoặc vào khung giờ tiếp theo.");
      } else if (message.includes("CLOUDFLARE_IMAGE_SERVER_ERROR") || message.includes("3043")) {
        setGenerationError("Dịch vụ AI tạo phối cảnh tạm thời bận. Đội ngũ kỹ thuật đang tự động tối ưu đường truyền, vui lòng thử lại sau giây lát.");
      } else if (message.includes("CLOUDFLARE_IMAGE_AUTH_ERROR")) {
        setGenerationError("Không thể kết nối dịch vụ tạo phối cảnh. Vui lòng liên hệ quản trị viên để kiểm tra cấu hình.");
      } else if (message.includes("FLOOR_PLANE_NOT_RELIABLE") || message.includes("FLOOR_NOT_DETECTED")) {
        setGenerationError("Góc chụp hiện tại chưa hiển thị rõ mặt sàn để bố trí nội thất chính xác. Bạn vui lòng tải lên ảnh chụp bao quát không gian sàn phòng rõ hơn.");
      } else if (message.includes("NO_COMPOSITIBLE_PRODUCT_IMAGES")) {
        setGenerationError("Các sản phẩm đã chọn chưa có ảnh tham chiếu chất lượng cao để phối cảnh. Vui lòng chọn sản phẩm khác từ danh mục.");
      } else if (message.startsWith("IMAGE_PROVIDER_NOT_CONFIGURED")) {
        setGenerationError("Dịch vụ AI tạo phối cảnh chưa được kích hoạt cho không gian này.");
      } else {
        setGenerationError(message.includes("status 5") ? "Hệ thống tạm thời bận. Vui lòng thử lại sau giây lát." : message);
      }
    } finally {
      generationInFlight.current = false;
      setGenerating(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#8A6B4E] border-t-transparent" />
        <p className="text-sm font-medium text-[#5A6258]">Đang phân tích độ tương thích và chuẩn bị danh mục gợi ý...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-white p-6 sm:p-8 shadow-sm text-center">
        <h2 className="font-serif text-2xl font-bold text-[#242B23]">Chưa thể tải gợi ý nội thất</h2>
        <p className="mt-3 text-sm text-[#5A6258] leading-relaxed">{error}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href={`/room-projects/${params.id}`}>
            <LuxuryButton variant="secondary" size="sm">Kiểm tra dự án</LuxuryButton>
          </Link>
          <Link href={`/room-projects/${params.id}/preferences`}>
            <LuxuryButton variant="primary" size="sm">Cài đặt sở thích decor</LuxuryButton>
          </Link>
        </div>
      </div>
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
    <div className="space-y-8 pb-20">
      {/* 1. Cohesive Studio Navigation Stepper */}
      <StudioNavHeader
        projectId={params.id}
        projectTitle={project?.title || "Dự án thiết kế phòng"}
        roomImageUrl={project?.room_image_url}
        currentStep={generating ? 4 : 3}
        hasRoomImage={Boolean(project?.room_image_url)}
        hasPreferences={true}
        selectedProductsCount={selectedIds.length}
        saveState="saved"
      />

      {/* 2. Editorial Header */}
      <EditorialHeading
        eyebrow="BƯỚC 03 · TUYỂN CHỌN NỘI THẤT CATALOG"
        title="Gợi ý nội thất tương thích không gian"
        subtitle="Hệ thống MCDA phân tích độ tương thích kiến trúc từ phong cách, màu sắc và ngân sách đã thiết lập. Chọn từ 1 đến 3 sản phẩm catalog thật để AI tiến hành phối cảnh."
      />

      {/* 3. Project Context Summary Strip */}
      <div className="overflow-hidden rounded-2xl border border-[#242B23]/10 bg-white shadow-sm">
        <div className="grid lg:grid-cols-[0.8fr_1.2fr]">
          <div className="relative aspect-[16/10] lg:aspect-auto bg-[#F7F4EE] flex items-center justify-center overflow-hidden">
            {project?.room_image_url ? (
              <img
                src={apiAssetUrl(project.room_image_url)}
                alt={project.title}
                className="h-full w-full object-cover"
              />
            ) : (
              <EmptyImagePlaceholder label="Không có ảnh phòng" />
            )}
            <div className="absolute top-3 left-3">
              <StatusBadge variant="neutral">Không gian thiết kế</StatusBadge>
            </div>
          </div>
          <div className="p-5 sm:p-6 lg:p-8 flex flex-col justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge variant="customer_pick">MCDA PRO Engine</StatusBadge>
                {recommendations?.recommendation_version && (
                  <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800 border border-emerald-200">
                    V{recommendations.recommendation_version.toUpperCase()}
                  </span>
                )}
              </div>
              <h3 className="mt-3 font-serif text-xl sm:text-2xl font-bold text-[#242B23]">{project?.title}</h3>
              <p className="mt-2 text-xs sm:text-sm text-[#5A6258] leading-relaxed">
                Tổ hợp nội thất được tuyển chọn kỹ lưỡng để tôn vinh cấu trúc kiến trúc gốc, tạo điểm nhấn và cân bằng thẩm mỹ tổng thể.
              </p>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-[#242B23]/10 pt-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A6258]/70">Loại phòng</span>
                <p className="mt-0.5 text-xs font-bold text-[#242B23] truncate">
                  {displayRoomType(effPref?.room_type || analysis?.room_type || project?.room_type) || "Phòng khách"}
                </p>
              </div>
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A6258]/70">Ngân sách</span>
                <p className="mt-0.5 text-xs font-bold text-[#8A6B4E] truncate">{budgetLabel(recommendations)}</p>
              </div>
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A6258]/70">Phong cách</span>
                <p className="mt-0.5 text-xs font-bold text-[#242B23] truncate">{stylesDisplay || "Hiện đại tự nhiên"}</p>
              </div>
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A6258]/70">Bảng màu</span>
                <p className="mt-0.5 text-xs font-bold text-[#242B23] truncate">{colorsDisplay || "Hài hòa tự nhiên"}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Signature AI Studio Generation Card */}
      <div className="overflow-hidden rounded-2xl border-2 border-[#8A6B4E]/30 bg-gradient-to-br from-[#F7F4EE] via-white to-[#F7F4EE]/60 p-5 sm:p-7 shadow-md">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-4 flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#8A6B4E] px-3 py-1 text-xs font-bold uppercase tracking-wider text-white shadow-xs">
                <Sparkles size={13} />
                {isAIBundle ? "Tổ hợp tối ưu tự động" : "Bộ sưu tập tùy chỉnh"}
              </span>
              <span className="text-xs font-semibold text-[#5A6258]">
                {selectedProducts.length}/3 sản phẩm được chọn
              </span>
            </div>

            <div>
              <h2 className="font-serif text-xl sm:text-2xl md:text-3xl font-bold text-[#242B23]">
                Khởi tạo phối cảnh kiến trúc AI
              </h2>
              <p className="mt-1 max-w-xl text-xs sm:text-sm text-[#5A6258] leading-relaxed">
                {selectedProducts.length > 0
                  ? isAIBundle
                    ? "Tổ hợp 3 món cân bằng theo công năng (Chính - Tiện ích - Điểm nhấn) khớp với hạn mức ngân sách của bạn."
                    : `Bạn đã chọn ${selectedProducts.length} sản phẩm từ catalog để AI tính toán tỷ lệ đặt vào không gian.`
                  : "Vui lòng chọn từ 1 đến 3 sản phẩm catalog bên dưới trước khi khởi tạo phối cảnh."}
              </p>
            </div>

            {/* Selected Products Thumbnails */}
            {selectedProducts.length > 0 && (
              <div className="flex flex-wrap gap-2.5 pt-1">
                {selectedProducts.map((item) => {
                  const img = item.product.images.find((i) => i.is_primary)?.image_url || item.product.images[0]?.image_url;
                  return (
                    <div
                      key={item.product.id}
                      className="flex items-center gap-2.5 rounded-xl border border-[#8A6B4E]/20 bg-white p-2 shadow-xs"
                    >
                      <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-[#F7F4EE]">
                        {img ? (
                          <img src={apiAssetUrl(img)} alt={item.product.name} className="h-full w-full object-cover" />
                        ) : (
                          <div className="h-full w-full bg-[#ECE7DE]" />
                        )}
                      </div>
                      <div className="min-w-0 pr-1 max-w-[160px]">
                        <div className="truncate text-xs font-bold text-[#242B23]">{item.product.name}</div>
                        <div className="text-[11px] font-semibold text-[#8A6B4E]">
                          {Number(item.product.price).toLocaleString("vi-VN")} ₫
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Budget Analytics Bar */}
            <div className="flex flex-wrap items-center gap-3 sm:gap-5 rounded-xl border border-[#242B23]/10 bg-white/80 p-3 text-xs text-[#5A6258]">
              <div className="flex items-center gap-1.5">
                <Wallet size={15} className="text-[#8A6B4E] shrink-0" />
                <span>
                  Tổng giá trị: <strong className="font-bold text-[#242B23]">{totalSelectedPrice.toLocaleString("vi-VN")} ₫</strong>
                </span>
              </div>
              {userBudgetMax !== null && (
                <div>
                  Hạn mức: <strong className="font-bold text-[#242B23]">{userBudgetMax.toLocaleString("vi-VN")} ₫</strong>
                </div>
              )}
              {remainingBudget !== null && (
                <div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                      remainingBudget >= 0
                        ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                        : "bg-red-50 text-red-800 border border-red-200"
                    }`}
                  >
                    {remainingBudget >= 0
                      ? `Còn lại ${remainingBudget.toLocaleString("vi-VN")} ₫`
                      : `Vượt ${Math.abs(remainingBudget).toLocaleString("vi-VN")} ₫`}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Action Trigger Button */}
          <div className="flex flex-col items-stretch lg:items-end gap-2 shrink-0 w-full lg:w-auto">
            <LuxuryButton
              variant="primary"
              size="lg"
              loading={generating}
              disabled={generating || selectedIds.length === 0}
              onClick={handleCreateAIDesign}
              className="w-full lg:w-auto shadow-lg"
            >
              <Sparkles size={18} className="text-[#F7F4EE]" />
              <span>{generating ? "Đang xử lý phối cảnh AI..." : "Tạo thiết kế AI Studio"}</span>
            </LuxuryButton>
            <span className="text-[11px] text-center lg:text-right text-[#5A6258]">
              Mô phỏng ánh sáng tự nhiên và chất liệu nội thất chân thực
            </span>
          </div>
        </div>

        {generationError && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50/80 p-4 text-xs font-semibold text-red-700 leading-relaxed">
            {generationError}
          </div>
        )}
      </div>

      {/* 5. Filter & Sorting Controls */}
      <div className="flex flex-col gap-4 rounded-2xl border border-[#242B23]/10 bg-white p-4 sm:flex-row sm:items-center sm:justify-between shadow-sm">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={17} className="text-[#8A6B4E]" />
          <h3 className="text-sm font-bold text-[#242B23]">
            Danh mục đề xuất ({visibleItems.length} sản phẩm)
          </h3>
        </div>
        <div className="flex flex-col sm:flex-row gap-2.5 w-full sm:w-auto">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-xl border border-[#242B23]/10 bg-[#F7F4EE] px-3 py-2 text-xs font-medium text-[#242B23] outline-none transition focus:border-[#8A6B4E] focus:bg-white w-full sm:w-auto"
          >
            <option value="">Tất cả phân loại</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="rounded-xl border border-[#242B23]/10 bg-[#F7F4EE] px-3 py-2 text-xs font-medium text-[#242B23] outline-none transition focus:border-[#8A6B4E] focus:bg-white w-full sm:w-auto"
          >
            <option value="match">Độ phù hợp cao nhất (MCDA)</option>
            <option value="price_asc">Giá tăng dần</option>
            <option value="price_desc">Giá giảm dần</option>
          </select>
        </div>
      </div>

      {/* 6. Products Recommendation Grid */}
      {visibleItems.length === 0 ? (
        <div className="rounded-2xl border border-[#242B23]/10 bg-white p-12 text-center">
          <Package size={32} className="mx-auto text-[#5A6258]/50" />
          <p className="mt-3 text-sm font-medium text-[#5A6258]">
            Không tìm thấy sản phẩm phù hợp với bộ lọc đã chọn.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
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
    </div>
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
  const tags = [...item.product.styles, ...item.product.colors, ...item.product.materials].slice(0, 3);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState("");

  const roleLabel =
    item.role === "CUSTOMER_PRESELECTED"
      ? "Lựa chọn từ Catalog"
      : item.role === "ANCHOR"
      ? "Nội thất chính"
      : item.role === "FUNCTIONAL"
      ? "Công năng phụ trợ"
      : "Chi tiết điểm nhấn";

  const roleBadgeVariant =
    item.role === "CUSTOMER_PRESELECTED"
      ? "customer_pick"
      : item.role === "ANCHOR"
      ? "neutral"
      : item.role === "FUNCTIONAL"
      ? "neutral"
      : "neutral";

  async function handleAddToCart() {
    setAdding(true);
    setMessage("");
    try {
      await addToCart(item.product.id);
      setMessage("Đã thêm vào giỏ hàng");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Chưa thể thêm vào giỏ");
    } finally {
      setAdding(false);
    }
  }

  return (
    <article
      className={`group flex flex-col justify-between overflow-hidden rounded-2xl border bg-white transition duration-200 ${
        selected
          ? "border-[#8A6B4E] ring-2 ring-[#8A6B4E]/20 shadow-md"
          : "border-[#242B23]/10 hover:border-[#8A6B4E]/40 hover:shadow-sm"
      }`}
    >
      <div>
        {/* Product Image */}
        <div className="relative aspect-[4/3] bg-[#F7F4EE] overflow-hidden">
          {primaryImage ? (
            <img
              src={apiAssetUrl(primaryImage)}
              alt={item.product.name}
              className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
            />
          ) : (
            <EmptyImagePlaceholder label="Sản phẩm chưa có ảnh" />
          )}

          {/* Badges Overlay */}
          <div className="absolute left-3 top-3 flex flex-col items-start gap-1.5">
            <span className="rounded-full bg-white/90 px-2.5 py-0.5 text-[11px] font-bold text-[#242B23] shadow-xs backdrop-blur-sm">
              {displayCategory(item.product.category.name)}
            </span>
            <StatusBadge variant={roleBadgeVariant}>{roleLabel}</StatusBadge>
          </div>

          <div className="absolute right-3 top-3">
            <ScoreBadge score={item.score} />
          </div>

          {/* Selection Toggle CTA */}
          <button
            type="button"
            onClick={() => onToggle(item.product.id)}
            className={`absolute bottom-3 right-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold transition shadow-sm ${
              selected
                ? "bg-[#242B23] text-white"
                : "bg-white/95 text-[#242B23] hover:bg-white"
            }`}
          >
            {selected ? (
              <>
                <Check size={14} className="text-[#8A6B4E]" />
                <span>Đang chọn cho AI</span>
              </>
            ) : (
              <span>Chọn món này</span>
            )}
          </button>
        </div>

        {/* Content Details */}
        <div className="p-4 sm:p-5">
          <Link
            href={`/products/${item.product.id}`}
            className="block font-serif text-base font-bold text-[#242B23] hover:text-[#8A6B4E] transition line-clamp-1"
          >
            {item.product.name}
          </Link>
          <p className="mt-1 font-serif text-lg font-bold text-[#8A6B4E]">
            {Number(item.product.price).toLocaleString("vi-VN")} ₫
          </p>

          {/* Reasoning */}
          <ul className="mt-3 space-y-1 text-xs text-[#5A6258]">
            {item.reasons.slice(0, 2).map((reason, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="text-[#8A6B4E] font-bold">✓</span>
                <span className="line-clamp-1">{reason}</span>
              </li>
            ))}
          </ul>

          {/* Tags */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={`${tag.id}-${tag.name}`}
                className="rounded-full bg-[#F7F4EE] px-2.5 py-0.5 text-[10px] font-medium text-[#5A6258]"
              >
                {"hex_code" in tag
                  ? displayColor(tag.name)
                  : displayStyle(tag.name) !== tag.name
                  ? displayStyle(tag.name)
                  : displayMaterial(tag.name)}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Card Footer Actions */}
      <div className="border-t border-[#242B23]/5 p-4 pt-3">
        <LuxuryButton
          variant="secondary"
          size="sm"
          loading={adding}
          onClick={handleAddToCart}
          className="w-full text-xs"
        >
          <ShoppingCart size={14} />
          <span>Thêm vào giỏ</span>
        </LuxuryButton>
        {message && (
          <p className="mt-1.5 text-center text-[11px] font-semibold text-emerald-700">
            {message}
          </p>
        )}
      </div>
    </article>
  );
}

function budgetLabel(recommendations: RecommendationResponse | null) {
  const eff = recommendations?.effective_preference?.budget_max;
  if (typeof eff === "number") return `Tối đa ${Number(eff).toLocaleString("vi-VN")} ₫`;
  const pref = recommendations?.preference;
  if (!pref) return "—";
  if (pref.budget_max) return `${Number(pref.budget_max).toLocaleString("vi-VN")} ₫`;
  if (pref.budget_min) return `Từ ${Number(pref.budget_min).toLocaleString("vi-VN")} ₫`;
  return "Không giới hạn";
}

export default function RecommendationsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#8A6B4E] border-t-transparent" />
          <p className="text-sm font-medium text-[#5A6258]">Đang tải gợi ý nội thất...</p>
        </div>
      }
    >
      <RecommendationsContent />
    </Suspense>
  );
}
