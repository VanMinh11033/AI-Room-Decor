"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Clock,
  Download,
  History,
  ImageIcon,
  Layers,
  RotateCcw,
  ShoppingCart,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import { StudioNavHeader } from "@/components/studio/StudioNavHeader";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { DesignGeneration, DesignGenerationListResponse, Product, RoomProject } from "@/types/api";

export default function DesignGenerationPage() {
  const params = useParams<{ id: string; generationId: string }>();
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [project, setProject] = useState<RoomProject | null>(null);
  const [generation, setGeneration] = useState<DesignGeneration | null>(null);
  const [history, setHistory] = useState<DesignGeneration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addingIds, setAddingIds] = useState<number[]>([]);
  const [addingAll, setAddingAll] = useState(false);
  const [cartMessage, setCartMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [projectData, generationData, historyData] = await Promise.all([
        apiFetch<RoomProject>(`/api/room-projects/${params.id}`),
        apiFetch<DesignGeneration>(`/api/room-projects/${params.id}/design-generations/${params.generationId}`),
        apiFetch<DesignGenerationListResponse>(`/api/room-projects/${params.id}/design-generations`),
      ]);
      setProject(projectData);
      setGeneration(generationData);
      setHistory(historyData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải phương án thiết kế");
    } finally {
      setLoading(false);
    }
  }, [params.generationId, params.id]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  async function handleAddOne(productId: number) {
    setAddingIds((ids) => [...ids, productId]);
    setCartMessage("");
    try {
      await addToCart(productId);
      setCartMessage("Đã thêm vào giỏ hàng");
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Chưa thể thêm vào giỏ");
    } finally {
      setAddingIds((ids) => ids.filter((id) => id !== productId));
    }
  }

  async function handleAddAll() {
    if (!generation || addingAll) return;
    setAddingAll(true);
    setCartMessage("");
    try {
      // Deduplicate product IDs to prevent duplicate calls (AUD-P1-002)
      const uniqueProducts = Array.from(new Map(generation.products.map((p) => [p.id, p])).values());
      let successCount = 0;
      let failureCount = 0;
      for (const product of uniqueProducts) {
        if (!product.is_active || (product.stock_quantity !== undefined && product.stock_quantity <= 0)) {
          failureCount++;
          continue;
        }
        try {
          await addToCart(product.id);
          successCount++;
        } catch {
          failureCount++;
        }
      }
      if (failureCount === 0 && successCount > 0) {
        setCartMessage("Đã thêm toàn bộ bộ sưu tập vào giỏ hàng!");
      } else if (successCount > 0) {
        setCartMessage(`Đã thêm ${successCount} sản phẩm vào giỏ hàng (${failureCount} sản phẩm tạm hết hoặc lỗi).`);
      } else if (failureCount > 0) {
        setCartMessage("Sản phẩm trong phương án này tạm thời hết hàng.");
      } else {
        setCartMessage("Không có sản phẩm khả dụng để thêm vào giỏ.");
      }
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Chưa thể thêm toàn bộ vào giỏ");
    } finally {
      setAddingAll(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#8A6B4E] border-t-transparent" />
        <p className="text-sm font-medium text-[#5A6258]">Đang tải phương án thiết kế kiến trúc...</p>
      </div>
    );
  }

  if (error || !project || !generation) {
    return (
      <div className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-white p-6 sm:p-8 text-center shadow-sm">
        <h2 className="font-serif text-2xl font-bold text-[#242B23]">Không thể mở phương án phối cảnh</h2>
        <p className="mt-3 text-sm text-[#5A6258] leading-relaxed">{error || "Phương án không tồn tại hoặc đã bị xóa."}</p>
        <div className="mt-6 flex justify-center">
          <Link href={`/room-projects/${params.id}/recommendations`}>
            <LuxuryButton variant="primary" size="sm">
              Quay lại danh mục gợi ý
            </LuxuryButton>
          </Link>
        </div>
      </div>
    );
  }

  const isQuotaFallback = generation.verification_status === "COMPOSITE_FALLBACK";
  const headingTitle =
    generation.provider === "cloudflare"
      ? "Phương án phối cảnh AI Studio"
      : generation.provider === "composite"
      ? "Phương án phối cảnh Chuẩn Catalog"
      : generation.provider === "gemini_manual_import"
      ? "Phương án phối cảnh Studio Cao cấp"
      : "Phương án phối cảnh Concept";

  return (
    <div className="space-y-8 pb-20 w-full min-w-0 max-w-full">
      {/* 1. Cohesive Studio Navigation Stepper */}
      <StudioNavHeader
        projectId={params.id}
        projectTitle={project.title}
        roomImageUrl={project.room_image_url}
        currentStep={5}
        hasRoomImage={Boolean(project.room_image_url)}
        hasPreferences={true}
        selectedProductsCount={generation.products.length}
        latestGenerationId={generation.id}
      />

      {/* 2. Top Header & Primary Action */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <EditorialHeading
          eyebrow="BƯỚC 05 · KẾT QUẢ PHỐI CẢNH AI STUDIO"
          title={headingTitle}
          subtitle={`Dự án: ${project.title} · Phiên bản #${generation.id}`}
        />
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <Link href={`/room-projects/${params.id}/recommendations`}>
            <LuxuryButton variant="secondary" size="sm">
              <RotateCcw size={15} />
              <span>Tạo phương án khác</span>
            </LuxuryButton>
          </Link>
        </div>
      </div>

      {generation.status === "FAILED" && (
        <div className="rounded-2xl border border-red-200 bg-red-50/90 p-5 text-sm font-semibold text-red-800">
          {generation.error_code === "IMAGE_PROVIDER_NOT_CONFIGURED"
            ? "Chưa cấu hình AI image provider cho môi trường này."
            : generation.error_message || generation.error_code || "Tạo ảnh phối cảnh thất bại."}
        </div>
      )}

      {/* 3. Before / After Comparison Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 w-full min-w-0">
        {/* Left: Original Room */}
        <div className="overflow-hidden rounded-2xl border border-[#242B23]/10 bg-white shadow-sm flex flex-col justify-between w-full min-w-0">
          <div className="flex items-center justify-between border-b border-[#242B23]/10 px-4 sm:px-5 py-3.5">
            <h3 className="font-serif text-sm font-bold text-[#242B23]">Trước khi decor (Hiện trạng phòng)</h3>
            <StatusBadge variant="neutral">Ảnh gốc</StatusBadge>
          </div>
          <div className="relative min-h-[300px] sm:min-h-[340px] md:min-h-[440px] bg-[#F7F4EE] flex items-center justify-center overflow-hidden">
            {project.room_image_url ? (
              <img
                src={apiAssetUrl(project.room_image_url)}
                alt={project.title}
                className="max-h-[540px] w-full object-contain"
              />
            ) : (
              <div className="text-xs text-[#5A6258]">Chưa có ảnh phòng gốc</div>
            )}
          </div>
        </div>

        {/* Right: AI Studio Output */}
        <div className="overflow-hidden rounded-2xl border border-[#8A6B4E]/30 bg-white shadow-sm flex flex-col justify-between w-full min-w-0">
          <div className="flex items-center justify-between border-b border-[#242B23]/10 px-4 sm:px-5 py-3.5">
            <div className="flex items-center gap-2 min-w-0">
              <h3 className="font-serif text-sm font-bold text-[#242B23] truncate">Sau khi decor (Phối cảnh AI)</h3>
              <StatusBadge variant="customer_pick">
                {generation.provider === "cloudflare"
                  ? "AI Studio"
                  : generation.provider === "composite"
                  ? "Chuẩn Catalog"
                  : "Studio"}
              </StatusBadge>
            </div>
            {generation.generated_image_url && (
              <a
                href={apiAssetUrl(generation.generated_image_url)}
                download={`room-design-${project.id}-${generation.id}.png`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl border border-[#8A6B4E]/20 bg-[#F7F4EE] px-2.5 sm:px-3 py-1.5 text-xs font-bold text-[#8A6B4E] transition hover:bg-white hover:shadow-xs shrink-0"
              >
                <Download size={13} />
                <span>Tải ảnh</span>
              </a>
            )}
          </div>
          <div className="relative min-h-[300px] sm:min-h-[340px] md:min-h-[440px] bg-[#F7F4EE] flex items-center justify-center overflow-hidden">
            {generation.generated_image_url ? (
              <img
                src={apiAssetUrl(generation.generated_image_url)}
                alt="Phương án decor AI"
                className="max-h-[540px] w-full object-contain"
              />
            ) : (
              <div className="text-xs text-[#5A6258]">Chưa có kết quả phối cảnh</div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Transparency & Quality Standards Banner */}
      {generation.verification_status === "REJECTED" ? (
        <div className="rounded-2xl border border-red-200 bg-red-50/90 p-4 sm:p-5 text-xs text-red-950 w-full min-w-0">
          <p className="font-bold text-red-900 text-sm">Tiêu chuẩn kiến trúc chưa đạt yêu cầu khắt khe</p>
          <p className="mt-1 leading-relaxed text-red-900/80">
            Phương án này chưa đáp ứng tối đa tiêu chuẩn về tỷ lệ hoặc giữ nguyên kết cấu sàn tường gốc. Bạn nên bấm &quot;Tạo phương án khác&quot; để AI phối cảnh hoàn thiện hơn.
          </p>
          {generation.warnings && generation.warnings.length > 0 && (
            <ul className="mt-2.5 list-disc list-inside space-y-0.5 text-red-800">
              {generation.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      ) : isQuotaFallback ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 sm:p-5 text-xs text-amber-950 w-full min-w-0">
          <p className="font-bold text-amber-900 text-sm">Phương án phối cảnh chuẩn Catalog</p>
          <p className="mt-1 leading-relaxed text-amber-900/80">
            Để đảm bảo trải nghiệm liên tục, Studio hiển thị ảnh bố cục trực tiếp từ catalog thật 100% của bộ sưu tập nội thất.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-[#8A6B4E]/20 bg-[#F7F4EE]/60 p-4 sm:p-5 text-xs text-[#5A6258] space-y-1.5 w-full min-w-0">
          <div className="flex items-center gap-2 font-serif text-sm font-bold text-[#242B23]">
            <Sparkles size={16} className="text-[#8A6B4E] shrink-0" />
            <span>Minh bạch thiết kế & Cam kết chất lượng bàn giao</span>
          </div>
          <p className="leading-relaxed">
            Ảnh phối cảnh AI thể hiện mô phỏng tương quan thẩm mỹ, ánh sáng tự nhiên và bố cục không gian. Từng sản phẩm thi công thực tế tuân thủ tuyệt đối thông số catalog, kích thước và chất liệu được liệt kê bên dưới.
          </p>
        </div>
      )}

      {/* 5. Architectural Quality Scorecard */}
      {generation.quality_score != null && (
        <div className="rounded-2xl border border-[#242B23]/10 bg-white p-4 sm:p-6 shadow-sm space-y-4 w-full min-w-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#242B23]/10 pb-3.5">
            <div>
              <h3 className="font-serif text-base font-bold text-[#242B23]">
                Báo cáo tiêu chuẩn thẩm mỹ & kiến trúc
              </h3>
              <p className="text-xs text-[#5A6258]">
                Đánh giá 6 tiêu chuẩn khắt khe về tỷ lệ không gian, chất liệu và phối cảnh ánh sáng (Chuẩn bàn giao: ≥ 85/100)
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs font-semibold text-[#5A6258]">Điểm thẩm định:</span>
              <span
                className={`rounded-xl px-3 py-1 text-sm font-bold ${
                  generation.quality_score >= 85
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : generation.quality_score >= 70
                    ? "bg-amber-50 text-amber-800 border border-amber-200"
                    : "bg-red-50 text-red-800 border border-red-200"
                }`}
              >
                {generation.quality_score} / 100
              </span>
            </div>
          </div>

          {(() => {
            const scores = generation.verification_details?.component_scores;
            if (!scores) return null;
            return (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-2.5 w-full min-w-0">
                <ScoreTile label="Chuẩn Catalog (35%)" score={scores.catalog} />
                <ScoreTile label="Bảo toàn kiến trúc (25%)" score={scores.architecture} />
                <ScoreTile label="Tỷ lệ không gian (15%)" score={scores.proportion} />
                <ScoreTile label="Phối cảnh góc nhìn (10%)" score={scores.perspective} />
                <ScoreTile label="Ánh sáng tự nhiên (10%)" score={scores.lighting} />
                <ScoreTile label="Độ tự nhiên (5%)" score={scores.realism} />
              </div>
            );
          })()}
        </div>
      )}

      {/* 6. Products Collection & Design History */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start w-full min-w-0">
        {/* Applied Products (8 cols) */}
        <div className="w-full min-w-0 lg:col-span-8 rounded-2xl border border-[#242B23]/10 bg-white p-4 sm:p-6 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#242B23]/10 pb-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-serif text-sm sm:text-base font-bold text-[#242B23]">
                <Layers size={18} className="text-[#8A6B4E] shrink-0" />
                <span className="break-words">Nội thất catalog tham chiếu ({generation.products.length} sản phẩm)</span>
              </div>
              <p className="text-xs text-[#5A6258] mt-0.5">
                Các sản phẩm thực tế được AI phối cảnh chính xác vào không gian
              </p>
            </div>
            <LuxuryButton
              variant="primary"
              size="sm"
              loading={addingAll}
              disabled={addingAll || generation.products.length === 0}
              onClick={handleAddAll}
              className="w-full sm:w-auto shrink-0"
            >
              <ShoppingCart size={15} />
              <span>Thêm toàn bộ vào giỏ</span>
            </LuxuryButton>
          </div>

          {cartMessage && (
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-xs font-semibold text-emerald-800">
              {cartMessage}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 w-full min-w-0">
            {generation.products.map((product) => (
              <ProductCardItem
                key={product.id}
                product={product}
                isAdding={addingIds.includes(product.id)}
                onAdd={() => handleAddOne(product.id)}
              />
            ))}
          </div>
        </div>

        {/* Design History Sidebar (4 cols) */}
        <div className="w-full min-w-0 lg:col-span-4 rounded-2xl border border-[#242B23]/10 bg-white p-4 sm:p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 font-serif text-sm font-bold text-[#242B23]">
            <History size={16} className="text-[#8A6B4E] shrink-0" />
            <span>Lịch sử phương án ({history.length})</span>
          </div>
          <div className="space-y-2">
            {history.map((item) => {
              const isCurrent = item.id === generation.id;
              return (
                <Link
                  key={item.id}
                  href={`/room-projects/${params.id}/design-generations/${item.id}`}
                  className={`flex items-center justify-between rounded-xl border p-3 text-xs transition ${
                    isCurrent
                      ? "border-[#242B23] bg-[#242B23] text-white shadow-xs"
                      : "border-[#242B23]/10 bg-[#F7F4EE] text-[#242B23] hover:border-[#8A6B4E] hover:bg-white"
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    <p className="font-bold">Phương án #{item.id}</p>
                    <p className={`text-[10px] truncate ${isCurrent ? "text-[#ECE7DE]" : "text-[#5A6258]"}`}>
                      {item.provider === "cloudflare"
                        ? "Cloudflare FLUX.2 Dev"
                        : item.provider === "composite"
                        ? "Phối cảnh Chuẩn Catalog"
                        : "Studio"}
                    </p>
                  </div>
                  {isCurrent && (
                    <span className="shrink-0 rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-bold text-white">
                      Đang xem
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProductCardItem({
  product,
  isAdding,
  onAdd,
}: {
  product: Product;
  isAdding: boolean;
  onAdd: () => void;
}) {
  const primaryImage = product.images.find((image) => image.is_primary)?.image_url || product.images[0]?.image_url;

  return (
    <div className="flex gap-3 rounded-xl border border-[#242B23]/10 bg-[#F7F4EE]/40 p-3 min-w-0">
      <Link
        href={`/products/${product.id}`}
        className="h-16 w-16 sm:h-20 sm:w-20 shrink-0 overflow-hidden rounded-lg bg-[#F7F4EE]"
      >
        {primaryImage ? (
          <img src={apiAssetUrl(primaryImage)} alt={product.name} className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full bg-[#ECE7DE]" />
        )}
      </Link>
      <div className="flex flex-col justify-between min-w-0 flex-1">
        <div className="min-w-0">
          <Link
            href={`/products/${product.id}`}
            className="block font-serif text-xs font-bold text-[#242B23] hover:text-[#8A6B4E] truncate"
          >
            {product.name}
          </Link>
          <p className="text-[10px] font-medium text-[#5A6258] truncate">{displayCategory(product.category.name)}</p>
          <p className="mt-0.5 text-xs font-bold text-[#8A6B4E]">
            {Number(product.price).toLocaleString("vi-VN")} ₫
          </p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          disabled={isAdding}
          className="mt-2 inline-flex items-center gap-1.5 self-start rounded-lg border border-[#242B23]/10 bg-white px-2.5 py-1 text-[11px] font-bold text-[#242B23] transition hover:border-[#8A6B4E] hover:text-[#8A6B4E] disabled:opacity-50"
        >
          <ShoppingCart size={12} />
          <span>{isAdding ? "Đang thêm..." : "Thêm vào giỏ"}</span>
        </button>
      </div>
    </div>
  );
}

function ScoreTile({ label, score }: { label: string; score?: number | null }) {
  const displayVal = score != null ? `${score}` : "—";
  const colorClass =
    score != null && score >= 85
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : score != null && score >= 70
      ? "text-amber-700 bg-amber-50 border-amber-200"
      : "text-[#5A6258] bg-[#F7F4EE] border-[#242B23]/10";

  return (
    <div className={`rounded-xl border p-2 text-center ${colorClass}`}>
      <div className="text-[10px] font-medium opacity-80 truncate">{label}</div>
      <div className="mt-0.5 font-serif text-sm font-bold">{displayVal}</div>
    </div>
  );
}
