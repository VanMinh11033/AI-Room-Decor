"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, Clock, Download, ImageIcon, ShoppingCart, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
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
  const addingAllInFlight = useRef(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const [projectData, generationData, historyData] = await Promise.all([
        apiFetch<RoomProject>(`/api/room-projects/${params.id}`, { signal }),
        apiFetch<DesignGeneration>(`/api/room-projects/${params.id}/design-generations/${params.generationId}`, { signal }),
        apiFetch<DesignGenerationListResponse>(`/api/room-projects/${params.id}/design-generations`, { signal }),
      ]);
      setProject(projectData);
      setGeneration(generationData);
      setHistory(historyData.items);
    } catch (err) {
      if (signal?.aborted) return;
      setError(err instanceof Error ? err.message : "Không thể tải phương án thiết kế");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [params.generationId, params.id]);

  useEffect(() => {
    const controller = new AbortController();
    if (!authLoading) {
      load(controller.signal);
    }
    return () => controller.abort();
  }, [authLoading, load]);

  async function handleAddOne(productId: number) {
    if (addingIds.includes(productId)) return;
    setAddingIds((ids) => [...ids, productId]);
    setCartMessage("");
    try {
      await addToCart(productId);
      setCartMessage("Đã thêm vào giỏ.");
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Không thêm được vào giỏ.");
    } finally {
      setAddingIds((ids) => ids.filter((id) => id !== productId));
    }
  }

  async function handleAddAll() {
    if (addingAllInFlight.current || !generation || generation.products.length === 0) return;
    addingAllInFlight.current = true;
    setAddingAll(true);
    setCartMessage("");

    // Deduplicate distinct products and count required quantities
    const productMap = new Map<number, number>();
    for (const product of generation.products) {
      productMap.set(product.id, (productMap.get(product.id) || 0) + 1);
    }

    let addedCount = 0;
    let lastError = "";
    try {
      // Safe sequential addition to guarantee backend transaction isolation & avoid unique constraint races
      for (const [productId, quantity] of productMap.entries()) {
        try {
          await addToCart(productId, quantity);
          addedCount++;
        } catch (err) {
          lastError = err instanceof Error ? err.message : "Lỗi thêm sản phẩm";
        }
      }

      if (addedCount === productMap.size) {
        setCartMessage("Đã thêm tất cả vào giỏ.");
      } else if (addedCount > 0) {
        setCartMessage(`Đã thêm ${addedCount}/${productMap.size} sản phẩm vào giỏ.${lastError ? ` (${lastError})` : ""}`);
      } else {
        setCartMessage(lastError || "Không thêm được vào giỏ.");
      }
    } finally {
      addingAllInFlight.current = false;
      setAddingAll(false);
    }
  }

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải phương án thiết kế...</p>;

  if (error || !project || !generation) {
    return (
      <section className="mx-auto max-w-2xl rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5">
        <Link href={`/room-projects/${params.id}/recommendations`} className="inline-flex items-center gap-2 text-sm font-semibold text-black/60">
          <ChevronLeft size={16} /> Quay lại gợi ý
        </Link>
        <h1 className="mt-5 text-3xl font-bold text-ink">Không thể mở phương án</h1>
        <p className="mt-3 text-black/65">{error || "Phương án không tồn tại."}</p>
      </section>
    );
  }

  const isQuotaFallback = generation.verification_status === "COMPOSITE_FALLBACK";

  return (
    <section className="space-y-8">
      {/* 1. Header & Actions */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <Link href={`/room-projects/${params.id}/recommendations`} className="inline-flex items-center gap-2 text-sm font-semibold text-black/60">
            <ChevronLeft size={16} /> Quay lại gợi ý
          </Link>
          <h1 className="mt-4 text-2xl sm:text-3xl md:text-4xl font-bold tracking-normal text-ink break-words">
            {generation.provider === "cloudflare"
              ? "Phương án phối cảnh AI (Cloudflare FLUX)"
              : generation.provider === "composite"
              ? "Phương án phối cảnh Chuẩn Catalog"
              : generation.provider === "gemini_manual_import"
              ? "Phương án phối cảnh Gemini (Nhập thủ công)"
              : "Phương án phối cảnh Concept"}
          </h1>
          <p className="mt-2 text-black/60">{project.title}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <Link
            href={`/room-projects/${params.id}/recommendations`}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-2xl bg-ink px-6 py-3.5 sm:py-3 text-sm font-black text-white hover:bg-black transition-colors shadow-sm"
          >
            <Sparkles size={16} />
            Tạo phương án khác
          </Link>
        </div>
      </div>

      {generation.status === "FAILED" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
          {generation.error_code === "IMAGE_PROVIDER_NOT_CONFIGURED"
            ? "Chưa cấu hình AI image provider cho môi trường này."
            : generation.error_message || generation.error_code || "Tạo ảnh thất bại."}
        </div>
      )}

      {/* 2. Before / After Comparison Grid */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 w-full min-w-0">
        <ImagePanel
          label="Trước khi decor (Ảnh phòng gốc)"
          imageUrl={project.room_image_url}
          alt={project.title}
        />
        <ImagePanel
          label={
            generation.provider === "cloudflare"
              ? "Sau khi decor (Ảnh AI Cloudflare FLUX)"
              : generation.provider === "composite"
              ? "Sau khi decor (Ảnh Chuẩn Catalog)"
              : generation.provider === "gemini_manual_import"
              ? "Sau khi decor (Ảnh Gemini Nhập thủ công)"
              : "Sau khi decor (Ảnh Concept)"
          }
          imageUrl={generation.generated_image_url}
          alt="Phương án decor AI"
          status={
            generation.provider === "cloudflare"
              ? "Cloudflare FLUX"
              : generation.provider === "composite"
              ? "Chuẩn Catalog"
              : generation.provider === "gemini_manual_import"
              ? "Gemini (Thủ công)"
              : "Bản Concept"
          }
          enableDownload
          downloadFilename={`room-design-${project.id}-${generation.id}.png`}
        />
      </div>

      {/* 3. Transparency & Status Banner */}
      {generation.verification_status === "REJECTED" ? (
        <div className="rounded-2xl border border-red-200 bg-red-50/90 p-5 text-sm text-red-950">
          <div className="flex items-center gap-2 font-black text-red-900 text-base">
            <span>❌ Phương án không đạt kiểm định · Trạng thái: REJECTED</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-red-900/90">
            Phương án này bị từ chối do vi phạm Hard Gate độc lập (thay đổi cấu trúc phòng, sai lệch sản phẩm hoặc che khuất lối đi). Vui lòng bấm &quot;Tạo phương án khác&quot; để tạo lại.
          </p>
          {generation.warnings && generation.warnings.length > 0 && (
            <ul className="mt-3 list-disc list-inside space-y-1 text-xs text-red-800">
              {generation.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      ) : isQuotaFallback ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-950">
          <div className="flex items-center gap-2 font-black text-amber-900">
            <span>ℹ️ Thông báo hạn mức AI</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-amber-900/80">
            Hạn mức 10.000 Neurons miễn phí hôm nay của tài khoản Cloudflare Free đã chạm trần (Mã lỗi 4006 từ Cloudflare). Hệ thống tự động chuyển sang Chế độ Composite Catalog 100% để bảo đảm thiết kế không bị gián đoạn.
          </p>
        </div>
      ) : generation.generation_mode === "AI_PHOTOREALISTIC_PREVIEW" || generation.is_ai_preview ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-amber-900">
          <div className="flex items-center gap-2 font-black text-amber-800">
            <Sparkles size={16} />
            <span>Bản xem trước AI · Trạng thái: NEEDS_REVIEW</span>
          </div>
          <p className="mt-1 text-xs text-amber-800/80">
            Ảnh phối cảnh ánh sáng chân thực do AI Cloudflare FLUX tạo. Đồ đạc trong ảnh mang tính chất gợi ý không gian; chi tiết kiểu dáng, chất liệu thực tế của sản phẩm được lưu chính xác trong danh mục mua sắm bên dưới.
          </p>
          {generation.warnings && generation.warnings.length > 0 && (
            <ul className="mt-2 list-disc list-inside space-y-0.5 text-[11px] text-amber-800/90">
              {generation.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 text-sm text-emerald-900">
          <div className="flex items-center gap-2 font-black text-emerald-800">
            <span>✨ Thiết kế Chuẩn Catalog 100% · Trạng thái: VERIFIED</span>
          </div>
          <p className="mt-1 text-xs text-emerald-800/80">
            Sản phẩm được đưa vào phòng chính xác từng pixel từ catalog, bảo đảm không bị biến dạng hay thay thế mẫu mã khi mua hàng.
          </p>
        </div>
      )}

      {/* Quality Score & Component Breakdown Card */}
      {generation.quality_score != null && (
        <div className="rounded-2xl border border-black/10 bg-white p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-black/5 pb-3">
            <div>
              <h3 className="text-sm font-bold text-ink">Kết quả kiểm định chất lượng độc lập (Quality Validation Engine V1.0)</h3>
              <p className="text-xs text-charcoal/60">Đánh giá 6 tiêu chí độc lập theo chuẩn AI Room Decor Skill V1.0 (Ngưỡng đạt: 85/100)</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-charcoal/60">Điểm tổng:</span>
              <span className={`rounded-xl px-3 py-1 text-sm font-black ${
                generation.quality_score >= 85
                  ? "bg-emerald-100 text-emerald-800"
                  : generation.quality_score >= 70
                  ? "bg-amber-100 text-amber-800"
                  : "bg-red-100 text-red-800"
              }`}>
                {generation.quality_score} / 100
              </span>
            </div>
          </div>
          {generation.verification_details?.component_scores && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <ScoreTile label="Chuẩn Catalog (35%)" score={generation.verification_details.component_scores.catalog} />
              <ScoreTile label="Khóa kiến trúc (25%)" score={generation.verification_details.component_scores.architecture} />
              <ScoreTile label="Tỷ lệ đồ đạc (15%)" score={generation.verification_details.component_scores.proportion} />
              <ScoreTile label="Phối cảnh (10%)" score={generation.verification_details.component_scores.perspective} />
              <ScoreTile label="Ánh sáng (10%)" score={generation.verification_details.component_scores.lighting} />
              <ScoreTile label="Chân thực (5%)" score={generation.verification_details.component_scores.realism} />
            </div>
          )}
        </div>
      )}

      {/* 4. Products Used in Design & Design History */}
      <div className="grid gap-5 xl:grid-cols-[1.4fr_0.6fr]">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-black/5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <ImageIcon size={18} /> Sản phẩm catalog tham chiếu trong thiết kế ({generation.products.length})
              </div>
              <p className="mt-1 text-xs text-charcoal/60">
                Sản phẩm được chọn làm mẫu tham chiếu phối cảnh. Hình dáng và chi tiết chuẩn xác được bảo đảm khi đặt mua theo danh mục catalog bên dưới.
              </p>
            </div>
            <button
              type="button"
              onClick={handleAddAll}
              disabled={addingAll || generation.products.length === 0}
              className="inline-flex items-center gap-2 rounded-xl bg-clay px-4 py-2 text-xs font-semibold text-white hover:bg-terracotta disabled:opacity-50 transition shrink-0"
            >
              <ShoppingCart size={15} /> {addingAll ? "Đang thêm..." : "Thêm tất cả vào giỏ"}
            </button>
          </div>
          {cartMessage && <p className="mt-3 text-sm font-semibold text-green-700">{cartMessage}</p>}
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {generation.products.map((product) => (
              <ProductRow key={product.id} product={product} adding={addingIds.includes(product.id)} onAdd={handleAddOne} />
            ))}
          </div>
        </section>

        <aside className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-black/5">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Clock size={18} /> Lịch sử phương án
          </div>
          <div className="mt-4 space-y-2">
            {history.map((item) => (
              <Link
                key={item.id}
                href={`/room-projects/${params.id}/design-generations/${item.id}`}
                className={`block rounded-xl border px-3 py-2 text-sm transition ${
                  item.id === generation.id
                    ? "border-ink bg-ink text-white"
                    : "border-black/10 bg-white text-black/65 hover:border-black/25"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold">#{item.id}</span>
                  <span className="ml-2 text-xs opacity-80">
                    {item.provider === "cloudflare"
                      ? "Cloudflare FLUX"
                      : item.provider === "composite"
                      ? "Chuẩn Catalog"
                      : item.provider === "gemini_manual_import"
                      ? "Gemini (Thủ công)"
                      : "Bản Concept"}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function ImagePanel({
  label,
  imageUrl,
  alt,
  status,
  enableDownload,
  downloadFilename = "room-design.png",
}: {
  label: string;
  imageUrl?: string | null;
  alt: string;
  status?: string;
  enableDownload?: boolean;
  downloadFilename?: string;
}) {
  return (
    <section className="overflow-hidden rounded-3xl bg-white shadow-soft ring-1 ring-black/5">
      <div className="flex items-center justify-between px-5 py-4 border-b border-ink/5">
        <h2 className="text-sm font-bold uppercase text-charcoal/70">{label}</h2>
        <div className="flex items-center gap-2">
          {status && <span className="rounded-full bg-stone px-3 py-1 text-xs font-bold text-ink">{status}</span>}
          {enableDownload && imageUrl && (
            <a
              href={apiAssetUrl(imageUrl)}
              download={downloadFilename}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-clay px-3.5 py-1.5 text-xs font-bold text-white hover:bg-terracotta transition-colors shadow-sm"
            >
              <Download size={14} /> Tải ảnh xuống
            </a>
          )}
        </div>
      </div>
      <div className="relative min-h-[360px] md:min-h-[440px] max-h-[580px] bg-stone/20 flex items-center justify-center overflow-hidden">
        {imageUrl ? (
          <img
            src={apiAssetUrl(imageUrl, { width: 1200 })}
            alt={alt}
            fetchPriority="high"
            decoding="async"
            className="max-h-[580px] w-full object-contain"
          />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-black/45">Chưa có ảnh kết quả.</div>
        )}
      </div>
    </section>
  );
}

function ProductRow({ product, adding, onAdd }: { product: Product; adding: boolean; onAdd: (productId: number) => void }) {
  const primaryImage = product.images.find((image) => image.is_primary)?.image_url || product.images[0]?.image_url;
  return (
    <div className="grid grid-cols-[80px_1fr] gap-3 rounded-2xl border border-black/10 bg-white p-3 shadow-xs">
      <Link href={`/products/${product.id}`} className="aspect-square overflow-hidden rounded-xl bg-ivory">
        {primaryImage ? (
          <img
            src={apiAssetUrl(primaryImage, { width: 160 })}
            alt={product.name}
            loading="lazy"
            decoding="async"
            className="h-full w-full object-cover"
          />
        ) : null}
      </Link>
      <div className="min-w-0 flex flex-col justify-between">
        <div>
          <Link href={`/products/${product.id}`} className="block truncate text-sm font-black text-ink hover:underline">{product.name}</Link>
          <p className="text-[11px] font-bold text-clay">{displayCategory(product.category.name)}</p>
          <p className="mt-1 text-xs font-bold text-ink">{Number(product.price).toLocaleString("vi-VN")} đ</p>
        </div>
        <button
          type="button"
          onClick={() => onAdd(product.id)}
          disabled={adding}
          className="mt-2 inline-flex items-center justify-center gap-1.5 rounded-xl bg-ink px-2.5 py-1.5 text-xs font-bold text-white hover:bg-black disabled:opacity-50 transition"
        >
          <ShoppingCart size={13} /> {adding ? "Đang thêm..." : "Thêm vào giỏ"}
        </button>
      </div>
    </div>
  );
}

function ScoreTile({ label, score }: { label: string; score?: number | null }) {
  const displayVal = score != null ? `${score}` : "--";
  const colorClass =
    score != null && score >= 85
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : score != null && score >= 70
      ? "text-amber-700 bg-amber-50 border-amber-200"
      : "text-ink/60 bg-stone/20 border-black/5";

  return (
    <div className={`rounded-xl border p-2.5 text-center ${colorClass}`}>
      <div className="text-[11px] font-medium opacity-80">{label}</div>
      <div className="mt-1 text-base font-black">{displayVal}</div>
    </div>
  );
}
