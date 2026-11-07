"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type {
  Paginated,
  Product,
  ProductImageCandidate,
  ProductImageCandidateList,
  ProductImageCandidateSearchResult,
} from "@/types/api";

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

  async function loadProducts() {
    try {
      const data = await apiFetch<Paginated<Product>>("/api/admin/products?page=1&page_size=100");
      setProducts(data.items);
    } catch {
      // product dropdown is best-effort
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
      setError("Chọn sản phẩm để tìm ảnh.");
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
          ? `Đã tải ${result.staged} ảnh mới (bỏ qua ${result.skipped}).`
          : `Không tải được ảnh phù hợp (đã bỏ qua ${result.skipped} kết quả).`
      );
      await loadCandidates(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tìm ảnh thất bại.");
    } finally {
      setSearching(false);
    }
  }

  async function approve(candidate: ProductImageCandidate) {
    await apiFetch(`/api/admin/product-image-candidates/${candidate.id}/approve`, { method: "POST" });
    await loadCandidates(page);
  }

  async function reject(candidate: ProductImageCandidate) {
    await apiFetch(`/api/admin/product-image-candidates/${candidate.id}/reject`, { method: "POST" });
    await loadCandidates(page);
  }

  if (authLoading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <section>
      <h1 className="text-3xl font-bold">Ảnh sản phẩm chờ duyệt</h1>

      <form onSubmit={onSearch} className="mt-5 flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm">
          <span>Sản phẩm</span>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="rounded-md border border-black/15 bg-white px-3 py-2"
          >
            <option value="">-- Chọn sản phẩm --</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          <span>Số ảnh tối đa</span>
          <input
            type="number"
            min={1}
            max={5}
            value={maxImages}
            onChange={(e) => setMaxImages(Number(e.target.value))}
            className="rounded-md border border-black/15 bg-white px-3 py-2"
          />
        </label>
        <button
          disabled={searching}
          className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {searching ? "Đang tìm..." : "Tìm ảnh từ Google"}
        </button>
      </form>

      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); loadCandidates(1); }}
          className="rounded-md border border-black/15 bg-white px-3 py-2"
        >
          <option value="PENDING">Chờ duyệt</option>
          <option value="APPROVED">Đã duyệt</option>
          <option value="REJECTED">Đã từ chối</option>
          <option value="">Tất cả</option>
        </select>
        <button onClick={() => loadCandidates(1)} className="rounded-md border border-black/15 bg-white px-3 py-2 font-semibold">
          Làm mới
        </button>
      </div>

      {notice && <p className="mt-4 text-sm text-green-700">{notice}</p>}
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      {loading && <p className="mt-6">Đang tải...</p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {candidates.map((candidate) => (
          <div key={candidate.id} className="overflow-hidden rounded-lg border border-black/10 bg-white">
            {candidate.public_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={apiAssetUrl(candidate.public_url)} alt={candidate.product_name || ""} className="h-44 w-full object-cover" />
            ) : (
              <div className="h-44 w-full bg-stone" />
            )}
            <div className="p-3 text-sm">
              <p className="font-semibold">#{candidate.product_id} {candidate.product_name}</p>
              <p className="mt-1 text-black/60">Nguồn {candidate.source} · {candidate.width}x{candidate.height} · {candidate.file_format}</p>
              <p className="mt-1 text-black/60">Giấy phép: {candidate.license || "-"}</p>
              <p className="mt-1 text-black/50">Tác giả: {candidate.creator || "-"}</p>
              {candidate.source_page_url && (
                <a className="mt-1 block truncate text-clay hover:underline" href={candidate.source_page_url} target="_blank" rel="noreferrer">
                  Nguồn gốc
                </a>
              )}
              <div className="mt-3 flex gap-2">
                {candidate.status === "PENDING" ? (
                  <>
                    <button onClick={() => approve(candidate)} className="rounded-md bg-green-700 px-3 py-1 font-semibold text-white">Duyệt</button>
                    <button onClick={() => reject(candidate)} className="rounded-md bg-red-700 px-3 py-1 font-semibold text-white">Từ chối</button>
                  </>
                ) : (
                  <span className={`font-semibold ${candidate.status === "APPROVED" ? "text-green-700" : "text-red-700"}`}>
                    {candidate.status === "APPROVED" ? "Đã duyệt" : "Đã từ chối"}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {candidates.length === 0 && !loading && <p className="mt-6 text-sm text-black/50">Chưa có ảnh.</p>}

      <div className="mt-6 flex items-center justify-between text-sm">
        <span>Tổng {total} ảnh</span>
        <div className="flex gap-2">
          <button disabled={page <= 1} onClick={() => loadCandidates(page - 1)} className="rounded-md border border-black/15 bg-white px-3 py-2 disabled:opacity-40">Trước</button>
          <button disabled={page * 12 >= total} onClick={() => loadCandidates(page + 1)} className="rounded-md border border-black/15 bg-white px-3 py-2 disabled:opacity-40">Sau</button>
        </div>
      </div>
    </section>
  );
}
