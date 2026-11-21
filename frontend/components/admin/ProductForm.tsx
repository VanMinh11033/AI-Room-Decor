"use client";

import { FormEvent, useEffect, useState } from "react";
import React from "react";
import { Layers, Palette, Save, Sparkles } from "lucide-react";
import { apiFetch } from "@/lib/api";
import {
  displayCategory,
  displayColor,
  displayMaterial,
  displayRoomType,
  displayStatus,
  displayStyle,
} from "@/lib/display";
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
    apiFetch<Paginated<Category>>("/api/categories?page=1&page_size=100")
      .then((data) => setCategories(data.items))
      .catch(() => setCategories([]));
    apiFetch<Paginated<CatalogItem>>("/api/materials?page=1&page_size=100")
      .then((data) => setMaterials(data.items))
      .catch(() => setMaterials([]));
    apiFetch<Paginated<CatalogItem>>("/api/styles?page=1&page_size=100")
      .then((data) => setStyles(data.items))
      .catch(() => setStyles([]));
    apiFetch<Paginated<CatalogItem>>("/api/room-types?page=1&page_size=100")
      .then((data) => setRoomTypes(data.items))
      .catch(() => setRoomTypes([]));
    apiFetch<Paginated<Color>>("/api/colors?page=1&page_size=100")
      .then((data) => setColors(data.items))
      .catch(() => setColors([]));
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
      images: imageUrl
        ? [{ image_url: imageUrl, alt_text: form.get("name"), sort_order: 0, is_primary: true }]
        : product?.images ?? [],
    };
    setSaving(true);
    setError("");
    try {
      await apiFetch<Product>(
        product ? `/api/admin/products/${product.id}` : "/api/admin/products",
        {
          method: product ? "PUT" : "POST",
          body: JSON.stringify(payload),
        }
      );
      window.location.href = "/admin/products";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được sản phẩm");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-2xl border border-[#2D332C]/10 bg-white p-6 text-sm text-[#777777]">
        Đang kiểm tra quyền...
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      {/* SECTION 1: Core Information */}
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
        <div className="mb-5 border-b border-[#2D332C]/10 pb-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
            Khối thông tin chính
          </p>
          <h2 className="text-lg font-bold text-[#242424]">Thông tin định danh sản phẩm</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Tên sản phẩm *
            </label>
            <input
              name="name"
              placeholder="VD: Ghế bành gỗ sồi Scandinavian..."
              defaultValue={product?.name || ""}
              required
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Slug định danh *
            </label>
            <input
              name="slug"
              placeholder="ghe-banh-scandinavian"
              defaultValue={product?.slug || ""}
              required
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Danh mục nội thất *
            </label>
            <select
              name="category_id"
              defaultValue={product?.category_id || ""}
              required
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            >
              <option value="">Chọn danh mục phù hợp</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {displayCategory(category.name)}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Đơn giá (VNĐ) *
            </label>
            <input
              name="price"
              type="number"
              step="1000"
              placeholder="12000000"
              defaultValue={product?.price || ""}
              required
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Số lượng tồn kho *
            </label>
            <input
              name="stock_quantity"
              type="number"
              placeholder="10"
              defaultValue={product?.stock_quantity ?? 0}
              required
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Trạng thái kinh doanh
            </label>
            <select
              name="status"
              defaultValue={product?.status || "ACTIVE"}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            >
              <option value="ACTIVE">{displayStatus("ACTIVE")} (Công khai mở bán)</option>
              <option value="INACTIVE">{displayStatus("INACTIVE")} (Tạm ẩn khỏi catalog)</option>
              <option value="DRAFT">{displayStatus("DRAFT")} (Bản nháp nội bộ)</option>
            </select>
          </div>
        </div>
      </div>

      {/* SECTION 2: Dimensions & Specifications */}
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
        <div className="mb-5 border-b border-[#2D332C]/10 pb-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
            Thông số kỹ thuật
          </p>
          <h2 className="text-lg font-bold text-[#242424]">Kích thước & Quy cách</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Chiều rộng (cm)
            </label>
            <input
              name="width"
              type="number"
              step="0.01"
              placeholder="85"
              defaultValue={product?.width || ""}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Chiều cao (cm)
            </label>
            <input
              name="height"
              type="number"
              step="0.01"
              placeholder="95"
              defaultValue={product?.height || ""}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Chiều sâu (cm)
            </label>
            <input
              name="depth"
              type="number"
              step="0.01"
              placeholder="90"
              defaultValue={product?.depth || ""}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Khối lượng (kg)
            </label>
            <input
              name="weight"
              type="number"
              step="0.01"
              placeholder="18"
              defaultValue={product?.weight || ""}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5 sm:col-span-4">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Tags nhận diện (ngăn cách bằng dấu phẩy)
            </label>
            <input
              name="tags"
              placeholder="sofa, scandinavian, sang-trong, phong-khach"
              defaultValue={product?.tags || ""}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>
        </div>
      </div>

      {/* SECTION 3: Visual & Description */}
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
        <div className="mb-5 border-b border-[#2D332C]/10 pb-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
            Mô tả & Hình ảnh
          </p>
          <h2 className="text-lg font-bold text-[#242424]">Nội dung giới thiệu sản phẩm</h2>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              URL ảnh chính (hoặc tải trực tiếp tại trang chỉnh sửa)
            </label>
            <input
              name="image_url"
              placeholder="https://... hoặc /products/sofa-japandi.jpg"
              defaultValue={
                product?.images.find((item) => item.is_primary)?.image_url ||
                product?.images[0]?.image_url ||
                ""
              }
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Mô tả chi tiết sản phẩm
            </label>
            <textarea
              name="description"
              rows={4}
              placeholder="Mô tả phong cách, chất liệu hoàn thiện, cảm hứng thiết kế..."
              defaultValue={product?.description || ""}
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] p-4 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>
        </div>
      </div>

      {/* SECTION 4: AI Matching & Decor Taxonomy Attributes */}
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
        <div className="mb-5 border-b border-[#2D332C]/10 pb-4">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-[#C9A77A]" />
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
              Thuộc tính AI Decor
            </p>
          </div>
          <h2 className="mt-1 text-lg font-bold text-[#242424]">
            Phân loại tương thích gợi ý AI & Khách hàng
          </h2>
        </div>

        <fieldset className="grid gap-5 md:grid-cols-2">
          <MultiSelect
            title="Vật liệu & Chất liệu"
            name="material_ids"
            items={materials}
            selected={product?.materials}
            display={displayMaterial}
            icon={Layers}
          />
          <MultiSelect
            title="Phong cách thiết kế"
            name="style_ids"
            items={styles}
            selected={product?.styles}
            display={displayStyle}
            icon={Sparkles}
          />
          <MultiSelect
            title="Không gian phòng phù hợp"
            name="room_type_ids"
            items={roomTypes}
            selected={product?.room_types}
            display={displayRoomType}
          />
          <MultiSelect
            title="Bảng màu sắc phối hợp"
            name="color_ids"
            items={colors}
            selected={product?.colors}
            display={displayColor}
            icon={Palette}
          />
        </fieldset>
      </div>

      {/* Error Notice */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* Submit Action */}
      <div className="flex items-center justify-end gap-3 pt-2">
        <a
          href="/admin/products"
          className="rounded-xl border border-[#2D332C]/15 bg-white px-5 py-3 text-sm font-semibold text-[#242424] shadow-sm transition hover:bg-[#FAF8F5]"
        >
          Hủy bỏ
        </a>
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-xl bg-[#2D332C] px-6 py-3 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#3B433A] hover:shadow-soft disabled:opacity-50"
        >
          <Save size={16} className="text-[#C9A77A]" />
          {saving ? "Đang lưu thông tin..." : product ? "Lưu cập nhật sản phẩm" : "Khởi tạo sản phẩm"}
        </button>
      </div>
    </form>
  );
}

function MultiSelect({
  title,
  name,
  items,
  selected,
  display,
  icon: Icon,
}: {
  title: string;
  name: string;
  items: { id: number; name: string }[];
  selected?: { id: number }[];
  display: (value: string) => string;
  icon?: React.ComponentType<{ size?: number; className?: string }>;
}) {
  return (
    <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
      <div className="mb-3 flex items-center gap-2 border-b border-[#2D332C]/10 pb-2">
        {Icon && <Icon size={14} className="text-[#A68B6D]" />}
        <p className="text-xs font-bold uppercase tracking-wider text-[#242424]">{title}</p>
      </div>
      <div className="grid max-h-48 gap-2 overflow-y-auto pr-1 text-sm sm:grid-cols-2">
        {items.map((item) => {
          const checked = isSelected(selected, item.id);
          return (
            <label
              key={item.id}
              className={`flex cursor-pointer items-center gap-2 rounded-xl border p-2 text-xs font-medium transition ${
                checked
                  ? "border-[#C9A77A] bg-white font-semibold text-[#2D332C] shadow-2xs"
                  : "border-transparent bg-white/60 text-[#777777] hover:bg-white hover:text-[#242424]"
              }`}
            >
              <input
                name={name}
                type="checkbox"
                value={item.id}
                defaultChecked={checked}
                className="rounded border-[#2D332C]/20 text-[#2D332C] focus:ring-[#C9A77A]"
              />
              <span className="truncate">{display(item.name)}</span>
            </label>
          );
        })}
        {items.length === 0 && (
          <p className="col-span-2 text-xs italic text-[#777777]">Chưa có dữ liệu danh mục</p>
        )}
      </div>
    </div>
  );
}
