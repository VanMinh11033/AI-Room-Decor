"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, Clock, ImageIcon, ShoppingCart, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory, displayStatus } from "@/lib/display";
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
      setCartMessage("Đã thêm vào giỏ.");
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Không thêm được vào giỏ.");
    } finally {
      setAddingIds((ids) => ids.filter((id) => id !== productId));
    }
  }

  async function handleAddAll() {
    if (!generation) return;
    setAddingAll(true);
    setCartMessage("");
    try {
      for (const product of generation.products) {
        await addToCart(product.id);
      }
      setCartMessage("Đã thêm tất cả vào giỏ.");
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Không thêm được vào giỏ.");
    } finally {
      setAddingAll(false);
    }
  }

  if (authLoading || loading) return <p>Đang tải phương án thiết kế...</p>;

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

  return (
    <section className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <Link href={`/room-projects/${params.id}/recommendations`} className="inline-flex items-center gap-2 text-sm font-semibold text-black/60">
            <ChevronLeft size={16} /> Quay lại gợi ý
          </Link>
          <h1 className="mt-4 text-4xl font-bold tracking-normal text-ink">Phương án thiết kế AI</h1>
          <p className="mt-2 text-black/60">{project.title}</p>
        </div>
        <Link
          href={`/room-projects/${params.id}/recommendations`}
          className="inline-flex items-center justify-center gap-2 rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white"
        >
          <Sparkles size={16} />
          Tạo phương án khác
        </Link>
      </div>

      {generation.status === "FAILED" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
          {generation.error_code === "IMAGE_PROVIDER_NOT_CONFIGURED"
            ? "Chưa cấu hình AI image provider cho môi trường này."
            : generation.error_message || generation.error_code || "Tạo ảnh thất bại."}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <ImagePanel label="Ảnh phòng gốc" imageUrl={project.room_image_url} alt={project.title} />
        <ImagePanel label="Ảnh decor AI" imageUrl={generation.generated_image_url} alt="Phương án decor AI" status={generation.status} />
      </div>

      <p className="rounded-2xl bg-ivory px-5 py-3 text-sm text-charcoal/65">
        AI sử dụng ảnh sản phẩm đã chọn làm ảnh tham chiếu để giữ kiểu dáng, màu sắc và đặc điểm sản phẩm gần nhất có thể.
      </p>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_0.6fr]">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-black/5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <ImageIcon size={18} /> Sản phẩm đã dùng trong thiết kế
            </div>
            <button type="button" onClick={handleAddAll} disabled={addingAll} className="inline-flex items-center gap-2 rounded-md bg-clay px-3 py-2 text-xs font-semibold text-white hover:bg-terracotta disabled:opacity-50">
              <ShoppingCart size={15} /> {addingAll ? "Đang thêm..." : "Thêm tất cả vào giỏ"}
            </button>
          </div>
          {cartMessage && <p className="mt-3 text-sm font-semibold text-green-700">{cartMessage}</p>}
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {generation.products.map((product) => <ProductRow key={product.id} product={product} adding={addingIds.includes(product.id)} onAdd={handleAddOne} />)}
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
                className={`block rounded-lg border px-3 py-2 text-sm ${
                  item.id === generation.id ? "border-ink bg-ink text-white" : "border-black/10 bg-white text-black/65 hover:border-black/25"
                }`}
              >
                <span className="font-semibold">#{item.id}</span>
                <span className="ml-2">{displayStatus(item.status)}</span>
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function ImagePanel({ label, imageUrl, alt, status }: { label: string; imageUrl?: string | null; alt: string; status?: string }) {
  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-black/5">
      <div className="flex items-center justify-between px-5 py-4">
        <h2 className="text-sm font-bold uppercase text-black/55">{label}</h2>
        {status && <span className="rounded-full bg-stone px-3 py-1 text-xs font-bold text-ink">{displayStatus(status)}</span>}
      </div>
      <div className="aspect-[4/3] bg-stone">
        {imageUrl ? (
          <img src={apiAssetUrl(imageUrl)} alt={alt} className="h-full w-full object-cover" />
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
    <div className="grid grid-cols-[96px_1fr] gap-4 rounded-xl border border-black/10 bg-white p-3">
      <Link href={`/products/${product.id}`} className="aspect-square overflow-hidden rounded-lg bg-stone">
        {primaryImage ? <img src={apiAssetUrl(primaryImage)} alt={product.name} className="h-full w-full object-cover" /> : null}
      </Link>
      <div className="min-w-0">
        <Link href={`/products/${product.id}`} className="block truncate text-sm font-bold text-ink hover:underline">{product.name}</Link>
        <p className="mt-1 text-xs font-semibold text-clay">{displayCategory(product.category.name)}</p>
        <p className="mt-2 text-sm font-bold">{Number(product.price).toLocaleString("vi-VN")} đ</p>
        <button type="button" onClick={() => onAdd(product.id)} disabled={adding} className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-ink px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-black disabled:opacity-50">
          <ShoppingCart size={13} /> {adding ? "Đang thêm..." : "Thêm vào giỏ"}
        </button>
      </div>
    </div>
  );
}
