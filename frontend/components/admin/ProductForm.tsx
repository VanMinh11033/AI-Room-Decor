"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStatus, displayStyle } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { CatalogItem, Category, Color, Paginated, Product } from "@/types/api";

function selectedIds(form: FormData, key: string) {
  return form.getAll(key).map((value) => Number(value)).filter(Boolean);
}

function isSelected(items: { id: number }[] | undefined, id: number) {
  return Boolean(items?.some((item) => item.id === id));
}

export function ProductForm({ product }: { product?: Product }) {
  const { loading } = useAuth("ADMIN");
  const [categories, setCategories] = useState<Category[]>([]);
  const [materials, setMaterials] = useState<CatalogItem[]>([]);
  const [styles, setStyles] = useState<CatalogItem[]>([]);
  const [roomTypes, setRoomTypes] = useState<CatalogItem[]>([]);
  const [colors, setColors] = useState<Color[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiFetch<Paginated<Category>>("/api/categories?page=1&page_size=100").then((data) => setCategories(data.items)).catch(() => setCategories([]));
    apiFetch<Paginated<CatalogItem>>("/api/materials?page=1&page_size=100").then((data) => setMaterials(data.items)).catch(() => setMaterials([]));
    apiFetch<Paginated<CatalogItem>>("/api/styles?page=1&page_size=100").then((data) => setStyles(data.items)).catch(() => setStyles([]));
    apiFetch<Paginated<CatalogItem>>("/api/room-types?page=1&page_size=100").then((data) => setRoomTypes(data.items)).catch(() => setRoomTypes([]));
    apiFetch<Paginated<Color>>("/api/colors?page=1&page_size=100").then((data) => setColors(data.items)).catch(() => setColors([]));
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const imageUrl = String(form.get("image_url") || "");
    const status = String(form.get("status") || "ACTIVE");
    const payload = {
      category_id: Number(form.get("category_id")),
      name: form.get("name"),
      slug: form.get("slug"),
      description: form.get("description") || null,
      price: form.get("price"),
      stock_quantity: Number(form.get("stock_quantity")),
      width: form.get("width") || null,
      height: form.get("height") || null,
      depth: form.get("depth") || null,
      weight: form.get("weight") || null,
      tags: form.get("tags") || null,
      status,
      is_active: status === "ACTIVE",
      material_ids: selectedIds(form, "material_ids"),
      style_ids: selectedIds(form, "style_ids"),
      room_type_ids: selectedIds(form, "room_type_ids"),
      color_ids: selectedIds(form, "color_ids"),
      images: imageUrl ? [{ image_url: imageUrl, alt_text: form.get("name"), sort_order: 0, is_primary: true }] : product?.images ?? []
    };
    setSaving(true);
    setError("");
    try {
      await apiFetch<Product>(product ? `/api/admin/products/${product.id}` : "/api/admin/products", {
        method: product ? "PUT" : "POST",
        body: JSON.stringify(payload)
      });
      window.location.href = "/admin/products";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được sản phẩm");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <form onSubmit={onSubmit} className="grid gap-4 rounded-lg border border-black/10 bg-white p-6 shadow-sm">
      <select name="category_id" defaultValue={product?.category_id || ""} required className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
        <option value="">Chọn danh mục</option>
        {categories.map((category) => <option key={category.id} value={category.id}>{displayCategory(category.name)}</option>)}
      </select>
      <Input name="name" placeholder="Tên sản phẩm" defaultValue={product?.name || ""} required />
      <Input name="slug" placeholder="slug-san-pham" defaultValue={product?.slug || ""} required />
      <Input name="price" type="number" step="0.01" placeholder="Giá" defaultValue={product?.price || ""} required />
      <Input name="stock_quantity" type="number" placeholder="Tồn kho" defaultValue={product?.stock_quantity ?? 0} required />
      <div className="grid gap-3 sm:grid-cols-4">
        <Input name="width" type="number" step="0.01" placeholder="Rộng" defaultValue={product?.width || ""} />
        <Input name="height" type="number" step="0.01" placeholder="Cao" defaultValue={product?.height || ""} />
        <Input name="depth" type="number" step="0.01" placeholder="Sâu" defaultValue={product?.depth || ""} />
        <Input name="weight" type="number" step="0.01" placeholder="Khối lượng" defaultValue={product?.weight || ""} />
      </div>
      <select name="status" defaultValue={product?.status || "ACTIVE"} className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
        <option value="ACTIVE">{displayStatus("ACTIVE")}</option>
        <option value="INACTIVE">{displayStatus("INACTIVE")}</option>
        <option value="DRAFT">{displayStatus("DRAFT")}</option>
      </select>
      <Input name="tags" placeholder="Tags, cách nhau bằng dấu phẩy" defaultValue={product?.tags || ""} />
      <Input name="image_url" placeholder="URL/path ảnh chính hoặc upload ảnh ở trang edit" defaultValue={product?.images.find((item) => item.is_primary)?.image_url || product?.images[0]?.image_url || ""} />
      <textarea name="description" className="min-h-28 rounded-md border border-black/15 bg-white px-3 py-2 text-sm" placeholder="Mô tả" defaultValue={product?.description || ""} />
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <MultiSelect title="Vật liệu" name="material_ids" items={materials} selected={product?.materials} display={displayMaterial} />
        <MultiSelect title="Phong cách" name="style_ids" items={styles} selected={product?.styles} display={displayStyle} />
        <MultiSelect title="Loại phòng" name="room_type_ids" items={roomTypes} selected={product?.room_types} display={displayRoomType} />
        <MultiSelect title="Màu sắc" name="color_ids" items={colors} selected={product?.colors} display={displayColor} />
      </fieldset>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <Button type="submit" disabled={saving}>{saving ? "Đang lưu..." : "Lưu sản phẩm"}</Button>
    </form>
  );
}

function MultiSelect({ title, name, items, selected, display }: { title: string; name: string; items: { id: number; name: string }[]; selected?: { id: number }[]; display: (value: string) => string }) {
  return (
    <div className="rounded-md border border-black/10 p-3">
      <p className="mb-2 text-sm font-semibold">{title}</p>
      <div className="grid gap-2 text-sm">
        {items.map((item) => (
          <label key={item.id} className="flex items-center gap-2">
            <input name={name} type="checkbox" value={item.id} defaultChecked={isSelected(selected, item.id)} />
            {display(item.name)}
          </label>
        ))}
      </div>
    </div>
  );
}
