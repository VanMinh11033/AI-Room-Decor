"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Filter, Search } from "lucide-react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { ProductCard } from "@/components/product/ProductCard";
import { apiFetch } from "@/lib/api";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStyle } from "@/lib/display";
import type { CatalogItem, Category, Color, Paginated, Product } from "@/types/api";

export default function ProductsPage() {
  const formRef = useRef<HTMLFormElement>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [materials, setMaterials] = useState<CatalogItem[]>([]);
  const [styles, setStyles] = useState<CatalogItem[]>([]);
  const [roomTypes, setRoomTypes] = useState<CatalogItem[]>([]);
  const [colors, setColors] = useState<Color[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(nextPage = 1) {
    const params = new URLSearchParams({ page: String(nextPage), page_size: "12" });
    if (formRef.current) {
      new FormData(formRef.current).forEach((value, key) => {
        if (value) params.set(key, String(value));
      });
    }
    setLoading(true);
    setError("");
    try {
      const result = await apiFetch<Paginated<Product>>(`/api/products?${params.toString()}`);
      setProducts(result.items);
      setTotal(result.total);
      setPage(result.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được sản phẩm");
      setProducts([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    apiFetch<Paginated<Category>>("/api/categories?page=1&page_size=100").then((data) => setCategories(data.items)).catch(() => null);
    apiFetch<Paginated<CatalogItem>>("/api/materials?page=1&page_size=100").then((data) => setMaterials(data.items)).catch(() => null);
    apiFetch<Paginated<CatalogItem>>("/api/styles?page=1&page_size=100").then((data) => setStyles(data.items)).catch(() => null);
    apiFetch<Paginated<CatalogItem>>("/api/room-types?page=1&page_size=100").then((data) => setRoomTypes(data.items)).catch(() => null);
    apiFetch<Paginated<Color>>("/api/colors?page=1&page_size=100").then((data) => setColors(data.items)).catch(() => null);
  }, []);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load(1);
  }

  return (
    <section className="space-y-7">
      <PageHeader
        eyebrow="Catalog nội thất"
        title="Sản phẩm decor"
        description="Tìm kiếm và lọc sản phẩm thật từ database theo phong cách, vật liệu, màu sắc, loại phòng và ngân sách."
      />

      <SectionCard>
        <form ref={formRef} onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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

      {loading && <p className="font-semibold text-charcoal/60">Đang tải sản phẩm...</p>}
      {error && <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</p>}

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((product) => <ProductCard key={product.id} product={product} />)}
      </div>

      {!loading && products.length === 0 && !error && <SectionCard>Không tìm thấy sản phẩm phù hợp.</SectionCard>}

      <div className="flex items-center justify-between rounded-2xl bg-white/80 p-3 text-sm font-bold text-charcoal/65 shadow-sm">
        <span>Tổng {total} sản phẩm</span>
        <div className="flex gap-2">
          <button disabled={page <= 1} onClick={() => load(page - 1)} className="secondary-cta px-4 py-2 disabled:opacity-40">Trước</button>
          <button disabled={page * 12 >= total} onClick={() => load(page + 1)} className="secondary-cta px-4 py-2 disabled:opacity-40">Sau</button>
        </div>
      </div>
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
