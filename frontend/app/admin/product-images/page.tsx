"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Check,
  CheckCircle2,
  ExternalLink,
  Globe,
  Image as ImageIcon,
  Maximize2,
  RefreshCw,
  X,
} from "lucide-react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type {
  Paginated,
  Product,
  ProductImageCandidate,
  ProductImageCandidateList,
  ProductImageCandidateSearchResult,
} from "@/types/api";
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminPagination,
  AdminSearchFilterBar,
  AdminStatusBadge,
  AdminSurfaceCard,
} from "@/components/admin/AdminPrimitives";

export default function AdminProductImagesPage() {
  const { loading: authLoading } = useAuth("ADMIN");
  const [products, setProducts] = useState<Product[]>([]);
  const [candidates, setCandidates] = useState<ProductImageCandidate[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [productId, setProductId] = useState("");
  const [status, setStatus] = useState("PENDING");
  const [maxImages, setMaxImages] = useState(3);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  async function loadProducts() {
    try {
      const data = await apiFetch<Paginated<Product>>("/api/admin/products?page=1&page_size=100");
      setProducts(data.items);
    } catch {
      // best-effort
    }
  }

  async function loadCandidates(nextPage = 1) {
    const params = new URLSearchParams({ page: String(nextPage), page_size: "12" });
    if (productId) params.set("product_id", productId);
    if (status) params.set("status", status);
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<ProductImageCandidateList>(
        `/api/admin/product-image-candidates?${params.toString()}`
      );
      setCandidates(data.items);
      setPage(data.page);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách ảnh.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProducts();
    loadCandidates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!productId) {
      setError("Vui lòng chọn một sản phẩm để tìm kiếm hình ảnh phù hợp.");
      return;
    }
    setSearching(true);
    setError("");
    setNotice("");
    try {
      const result = await apiFetch<ProductImageCandidateSearchResult>(
        "/api/admin/product-image-candidates/search",
        {
          method: "POST",
          body: JSON.stringify({ product_id: Number(productId), max_images: maxImages }),
        }
      );
      setNotice(
        result.staged > 0
          ? `Đã tìm thấy và lưu tạm ${result.staged} ảnh mới (bỏ qua ${result.skipped} ảnh trùng).`
          : `Không tìm thấy ảnh mới phù hợp (đã bỏ qua ${result.skipped} kết quả).`
      );
      await loadCandidates(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tìm kiếm ảnh thất bại.");
    } finally {
      setSearching(false);
    }
  }

  async function approve(candidate: ProductImageCandidate) {
    try {
      await apiFetch(`/api/admin/product-image-candidates/${candidate.id}/approve`, {
        method: "POST",
      });
      await loadCandidates(page);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Không thể duyệt ảnh");
    }
  }

  async function reject(candidate: ProductImageCandidate) {
    try {
      await apiFetch(`/api/admin/product-image-candidates/${candidate.id}/reject`, {
        method: "POST",
      });
      await loadCandidates(page);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Không thể từ chối ảnh");
    }
  }

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Catalog & Hình ảnh"
        title="Ảnh sản phẩm chờ duyệt"
        subtitle="Tìm kiếm ảnh catalog chất lượng cao từ nguồn mở và phê duyệt ảnh chính thức vào catalog hệ thống."
      />

      {/* 2. Candidate Discovery Search Form */}
      <AdminSurfaceCard
        title="Tìm kiếm ứng viên ảnh từ web"
        subtitle="Thu thập ảnh tham chiếu từ nguồn uy tín cho sản phẩm catalog"
      >
        <form onSubmit={onSearch} className="flex flex-wrap items-end gap-4">
          <div className="min-w-[260px] flex-1 space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Chọn sản phẩm cần tìm ảnh *
            </label>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            >
              <option value="">-- Chọn sản phẩm trong catalog --</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  #{p.id} · {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="w-32 space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Số lượng ảnh
            </label>
            <input
              type="number"
              min={1}
              max={5}
              value={maxImages}
              onChange={(e) => setMaxImages(Number(e.target.value))}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <button
            type="submit"
            disabled={searching}
            className="inline-flex items-center gap-2 rounded-xl bg-[#2D332C] px-6 py-2.5 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:bg-[#3B433A] disabled:opacity-50"
          >
            {searching ? (
              <>
                <RefreshCw size={15} className="animate-spin text-[#C9A77A]" />
                Đang tìm ảnh...
              </>
            ) : (
              <>
                <Globe size={15} className="text-[#C9A77A]" />
                Tìm ảnh từ Google
              </>
            )}
          </button>
        </form>
      </AdminSurfaceCard>

      {/* 3. Filter Bar */}
      <AdminSearchFilterBar>
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-[#777777]">
            Trạng thái duyệt:
          </span>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              loadCandidates(1);
            }}
            className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
          >
            <option value="PENDING">Chờ duyệt (Pending)</option>
            <option value="APPROVED">Đã duyệt (Approved)</option>
            <option value="REJECTED">Đã từ chối (Rejected)</option>
            <option value="">Tất cả trạng thái</option>
          </select>
        </div>

        <button
          type="button"
          onClick={() => loadCandidates(1)}
          className="inline-flex items-center gap-1.5 rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2 text-xs font-semibold text-[#242424] transition hover:bg-white"
        >
          <RefreshCw size={13} className="text-[#A68B6D]" />
          Làm mới danh sách
        </button>

        <span className="ml-auto text-xs text-[#777777]">
          Tổng cộng <strong className="text-[#242424]">{total}</strong> ảnh ứng viên
        </span>
      </AdminSearchFilterBar>

      {/* Notices & Alerts */}
      {notice && (
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-xs font-semibold text-emerald-800 shadow-sm">
          <CheckCircle2 size={16} className="text-emerald-600" />
          <span>{notice}</span>
        </div>
      )}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* 4. Candidate Grid */}
      {loading ? (
        <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-12 text-center text-sm font-medium text-[#777777] shadow-card">
          Đang tải danh sách ảnh ứng viên...
        </div>
      ) : candidates.length === 0 ? (
        <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 shadow-card">
          <AdminEmptyState
            icon={ImageIcon}
            title="Chưa có ảnh ứng viên nào"
            description="Hãy chọn sản phẩm ở ô phía trên và bấm 'Tìm ảnh từ Google' để quét thêm ảnh mới."
          />
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {candidates.map((candidate) => {
            const hasUrl = Boolean(candidate.public_url);
            const isApproved = candidate.status === "APPROVED";

            return (
              <div
                key={candidate.id}
                className="flex flex-col justify-between overflow-hidden rounded-2xl border border-[#2D332C]/10 bg-white shadow-card transition hover:shadow-soft"
              >
                <div>
                  {/* Image Frame */}
                  <div className="relative aspect-4/3 w-full overflow-hidden border-b border-[#2D332C]/10 bg-[#FAF8F5]">
                    {hasUrl ? (
                      <>
                        <img
                          src={apiAssetUrl(candidate.public_url!, { width: 400 })}
                          alt={candidate.product_name || "Ứng viên ảnh"}
                          loading="lazy"
                          decoding="async"
                          className="h-full w-full object-cover transition duration-300 hover:scale-105"
                        />
                        <button
                          type="button"
                          onClick={() => setPreviewUrl(apiAssetUrl(candidate.public_url!))}
                          className="absolute bottom-2 right-2 rounded-lg bg-black/60 p-1.5 text-white backdrop-blur-sm hover:bg-black"
                        >
                          <Maximize2 size={13} />
                        </button>
                      </>
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-[#777777]">
                        Không có URL ảnh
                      </div>
                    )}
                    <span className="absolute left-2 top-2">
                      <AdminStatusBadge status={candidate.status} size="sm" />
                    </span>
                  </div>

                  {/* Metadata Content */}
                  <div className="space-y-2 p-4 text-xs">
                    <p className="truncate font-bold text-[#242424]">
                      #{candidate.product_id} · {candidate.product_name || "Sản phẩm"}
                    </p>
                    <p className="text-[#777777]">
                      Nguồn: <strong className="text-[#242424]">{candidate.source}</strong> ·{" "}
                      {candidate.width}x{candidate.height} ({candidate.file_format})
                    </p>
                    <p className="truncate text-[#777777]">
                      Giấy phép: {candidate.license || "Chưa xác định"}
                    </p>
                    <p className="truncate text-[#777777]">Tác giả: {candidate.creator || "-"}</p>

                    {candidate.source_page_url && (
                      <a
                        href={candidate.source_page_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-semibold text-[#A68B6D] hover:text-[#2D332C] hover:underline"
                      >
                        Xem trang gốc
                        <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                </div>

                {/* Bottom Action Footer */}
                <div className="border-t border-[#2D332C]/10 p-3 bg-[#FAF8F5]/50">
                  {candidate.status === "PENDING" ? (
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => approve(candidate)}
                        className="inline-flex items-center justify-center gap-1 rounded-xl bg-emerald-700 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-800"
                      >
                        <Check size={13} /> Duyệt
                      </button>
                      <button
                        type="button"
                        onClick={() => reject(candidate)}
                        className="inline-flex items-center justify-center gap-1 rounded-xl bg-rose-700 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-rose-800"
                      >
                        <X size={13} /> Từ chối
                      </button>
                    </div>
                  ) : (
                    <div className="text-center text-xs font-bold text-[#777777]">
                      {isApproved ? (
                        <span className="text-emerald-700">✓ Đã duyệt vào catalog</span>
                      ) : (
                        <span className="text-rose-700">✕ Đã từ chối ảnh này</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 5. Pagination */}
      {total > 12 && (
        <AdminPagination
          page={page}
          pageSize={12}
          total={total}
          onPageChange={(p) => loadCandidates(p)}
          loading={loading}
        />
      )}

      {/* Preview Lightbox */}
      {previewUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
          onClick={() => setPreviewUrl(null)}
        >
          <div
            className="relative max-h-[90vh] max-w-[90vw] overflow-hidden rounded-2xl bg-white p-2"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={previewUrl}
              alt="Ảnh phóng to"
              className="max-h-[85vh] w-auto max-w-full rounded-xl object-contain"
            />
            <button
              type="button"
              onClick={() => setPreviewUrl(null)}
              className="absolute right-4 top-4 rounded-full bg-black/70 px-3 py-1 text-xs font-bold text-white hover:bg-black"
            >
              Đóng (ESC)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
