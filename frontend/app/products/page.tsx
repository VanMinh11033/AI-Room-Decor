"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Filter, Loader2, PackageSearch, RotateCw, Search } from "lucide-react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { ProductCard } from "@/components/product/ProductCard";
import { apiFetch, cachedApiFetch } from "@/lib/api";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStyle } from "@/lib/display";
import type { CatalogItem, Category, Color, Paginated, Product } from "@/types/api";

type CatalogState = "LOADING" | "RETRYING" | "SUCCESS_WITH_PRODUCTS" | "SUCCESS_EMPTY" | "ERROR";

export default function ProductsPage() {
  const formRef = useRef<HTMLFormElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const latestRequestIdRef = useRef<number>(0);

  const [state, setState] = useState<CatalogState>("LOADING");
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [materials, setMaterials] = useState<CatalogItem[]>([]);
  const [styles, setStyles] = useState<CatalogItem[]>([]);
  const [roomTypes, setRoomTypes] = useState<CatalogItem[]>([]);
  const [colors, setColors] = useState<Color[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Elapsed timer for transparent loading progress feedback
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (state === "LOADING" || state === "RETRYING") {
      timer = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setElapsedSeconds(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [state]);

  const load = useCallback(async (nextPage = 1, isManualRetry = false) => {
    // Increment request ID so only the latest request can commit state
    const currentRequestId = ++latestRequestIdRef.current;

    // Cancel any previous in-flight request on filter change, pagination, or retry
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const params = new URLSearchParams({ page: String(nextPage), page_size: "12" });
    if (formRef.current) {
      new FormData(formRef.current).forEach((value, key) => {
        if (value) params.set(key, String(value));
      });
    }

    setState(isManualRetry ? "RETRYING" : "LOADING");
    setError("");

    try {
      const result = await apiFetch<Paginated<Product>>(`/api/products?${params.toString()}`, {
        signal: controller.signal,
        timeoutMs: 32000,
        retries: 1,
        bypassCache: isManualRetry,
      });

      // Stale check & abort check
      if (currentRequestId !== latestRequestIdRef.current || controller.signal.aborted) {
        return;
      }

      if (result.items && result.items.length > 0) {
        setProducts(result.items);
        setTotal(result.total);
        setPage(result.page);
        setState("SUCCESS_WITH_PRODUCTS");
      } else {
        setProducts([]);
        setTotal(0);
        setPage(1);
        setState("SUCCESS_EMPTY");
      }
    } catch (err: unknown) {
      // Stale check & intentional cancellation check
      if (currentRequestId !== latestRequestIdRef.current || controller.signal.aborted) {
        return;
      }

      const message = err instanceof Error ? err.message : "Không tải được sản phẩm";
      setError(message);
      setProducts([]);
      setTotal(null); // CRITICAL: Never reset total to 0 on error!
      setState("ERROR");
    }
  }, []);

  useEffect(() => {
    load(1);
    cachedApiFetch<Paginated<Category>>("/api/categories?page=1&page_size=100").then((data) => setCategories(data.items)).catch(() => null);
    cachedApiFetch<Paginated<CatalogItem>>("/api/materials?page=1&page_size=100").then((data) => setMaterials(data.items)).catch(() => null);
    cachedApiFetch<Paginated<CatalogItem>>("/api/styles?page=1&page_size=100").then((data) => setStyles(data.items)).catch(() => null);
    cachedApiFetch<Paginated<CatalogItem>>("/api/room-types?page=1&page_size=100").then((data) => setRoomTypes(data.items)).catch(() => null);
    cachedApiFetch<Paginated<Color>>("/api/colors?page=1&page_size=100").then((data) => setColors(data.items)).catch(() => null);

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [load]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load(1);
  }

  // Meaningful loading status text based on elapsed seconds
  let loadingText = "Đang tải danh mục sản phẩm decor...";
  let loadingSubText = "Đang kết nối đến hệ thống máy chủ.";
  if (elapsedSeconds >= 12) {
    loadingText = "Máy chủ đang khởi động từ chế độ ngủ...";
    loadingSubText = `Đã chờ ${elapsedSeconds}s. Quá trình khởi động container miễn phí có thể mất khoảng 25–35 giây.`;
  } else if (elapsedSeconds >= 5) {
    loadingSubText = `Đang kết nối (${elapsedSeconds}s)...`;
  }

  return (
    <section className="space-y-7">
      <PageHeader
        eyebrow="Catalog nội thất"
        title="Sản phẩm decor"
        description="Tìm kiếm và lọc sản phẩm thật từ database theo phong cách, vật liệu, màu sắc, loại phòng và ngân sách."
      />

      <SectionCard>
        <form ref={formRef} onSubmit={onSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 w-full min-w-0">
          <label className="relative sm:col-span-2">
            <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-charcoal/40" />
            <input name="search" className="premium-input w-full pl-10" placeholder="Tìm sản phẩm, tag, mô tả..." />
          </label>
          <Select name="category_id" label="Danh mục" items={categories.map((item) => ({ value: String(item.id), label: displayCategory(item.name) }))} />
          <Select name="sort" label="Sắp xếp" items={[{ value: "newest", label: "Mới nhất" }, { value: "price_asc", label: "Giá tăng dần" }, { value: "price_desc", label: "Giá giảm dần" }, { value: "name_asc", label: "Tên A-Z" }]} />
          <Select name="style" label="Phong cách" items={styles.map((item) => ({ value: item.slug, label: displayStyle(item.name) }))} />
          <Select name="material" label="Vật liệu" items={materials.map((item) => ({ value: item.slug, label: displayMaterial(item.name) }))} />
          <Select name="room_type" label="Loại phòng" items={roomTypes.map((item) => ({ value: item.slug, label: displayRoomType(item.name) }))} />
          <Select name="color" label="Màu sắc" items={colors.map((item) => ({ value: item.slug, label: displayColor(item.name) }))} />
          <input name="min_price" type="number" min="0" className="premium-input" placeholder="Giá từ" />
          <input name="max_price" type="number" min="0" className="premium-input" placeholder="Giá đến" />
          <button className="primary-cta sm:col-span-2">
            <Filter size={17} /> Áp dụng bộ lọc
          </button>
        </form>
      </SectionCard>

      {/* LOADING STATE */}
      {state === "LOADING" && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl border border-[#2D332C]/10 bg-white p-5 shadow-card">
          <div className="flex items-center gap-3">
            <Loader2 size={22} className="animate-spin text-[#C9A77A] shrink-0" />
            <div className="text-sm">
              <p className="font-semibold text-ink">{loadingText}</p>
              <p className="text-xs text-charcoal/60 mt-0.5">{loadingSubText}</p>
            </div>
          </div>
          {elapsedSeconds >= 10 && (
            <button
              type="button"
              onClick={() => load(page, true)}
              className="secondary-cta text-xs px-3 py-1.5 shrink-0 inline-flex items-center gap-1.5"
            >
              <RotateCw size={14} /> Thử lại ngay
            </button>
          )}
        </div>
      )}

      {/* RETRYING STATE */}
      {state === "RETRYING" && (
        <div className="flex items-center gap-3 rounded-2xl border border-[#C9A77A]/40 bg-[#FAF8F5] p-5 shadow-card">
          <Loader2 size={22} className="animate-spin text-[#A68B6D] shrink-0" />
          <div className="text-sm">
            <p className="font-semibold text-ink">Đang thử kết nối lại với máy chủ...</p>
            <p className="text-xs text-charcoal/60 mt-0.5">
              Hệ thống đang hoàn tất tiến trình khởi động dịch vụ.
            </p>
          </div>
        </div>
      )}

      {/* ERROR STATE — WITH RETRY BUTTON, NEVER LABELED EMPTY */}
      {state === "ERROR" && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-soft space-y-4 text-center sm:text-left">
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-3.5">
            <AlertCircle size={24} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="font-bold text-amber-900 text-base">{error}</h3>
              <p className="text-sm text-amber-800/80 leading-relaxed">
                Máy chủ đám mây miễn phí có thể cần thêm thời gian để hoàn tất khởi động dịch vụ. Dữ liệu catalog không bị mất. Vui lòng nhấn nút bên dưới để tải lại.
              </p>
            </div>
          </div>
          <div className="pt-2 flex justify-center sm:justify-start">
            <button
              type="button"
              onClick={() => load(1, true)}
              className="inline-flex items-center gap-2 rounded-xl border border-[#C9A77A]/40 bg-[#2D332C] px-5 py-2.5 text-sm font-semibold text-[#FAF8F5] shadow-sm transition-all hover:bg-[#A68B6D] active:scale-[0.98]"
            >
              <RotateCw size={16} /> Thử tải lại danh mục
            </button>
          </div>
        </div>
      )}

      {/* SUCCESS_EMPTY STATE — ONLY UPON GENUINE ZERO-ITEM RESULT FROM BACKEND */}
      {state === "SUCCESS_EMPTY" && (
        <SectionCard className="text-center py-14">
          <PackageSearch size={44} className="mx-auto text-charcoal/30" />
          <h3 className="mt-3 text-lg font-bold text-ink">Không tìm thấy sản phẩm phù hợp</h3>
          <p className="mt-1 text-sm text-charcoal/60 max-w-md mx-auto">
            Không có sản phẩm nào khớp với tiêu chí tìm kiếm hoặc bộ lọc hiện tại. Vui lòng thử thay đổi từ khóa hoặc xóa bớt tiêu chí lọc.
          </p>
          <button
            type="button"
            onClick={() => {
              if (formRef.current) formRef.current.reset();
              load(1);
            }}
            className="secondary-cta mt-5 inline-flex items-center gap-2 px-4 py-2 text-sm"
          >
            Đặt lại bộ lọc
          </button>
        </SectionCard>
      )}

      {/* SUCCESS_WITH_PRODUCTS STATE — PRODUCT GRID */}
      {state === "SUCCESS_WITH_PRODUCTS" && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 w-full min-w-0">
          {products.map((product, idx) => (
            <ProductCard key={product.id} product={product} priority={idx < 3} />
          ))}
        </div>
      )}

      {/* PAGINATION FOOTER — ONLY RENDERED ON SUCCESS (NEVER ON ERROR OR LOADING) */}
      {(state === "SUCCESS_WITH_PRODUCTS" || state === "SUCCESS_EMPTY") && total !== null && (
        <div className="flex items-center justify-between rounded-2xl bg-white/80 p-3 text-sm font-bold text-charcoal/65 shadow-sm">
          <span>Tổng {total} sản phẩm</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => load(page - 1)} className="secondary-cta px-4 py-2 disabled:opacity-40">Trước</button>
            <button disabled={page * 12 >= total} onClick={() => load(page + 1)} className="secondary-cta px-4 py-2 disabled:opacity-40">Sau</button>
          </div>
        </div>
      )}
    </section>
  );
}

function Select({ name, label, items }: { name: string; label: string; items: { value: string; label: string }[] }) {
  return (
    <select name={name} className="premium-input">
      <option value="">{label}</option>
      {items.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
    </select>
  );
}
