"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Edit2, EyeOff, Layers, Save, Search, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { CatalogItem, Color, Paginated } from "@/types/api";
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminPagination,
  AdminStatusBadge,
  AdminSurfaceCard,
} from "@/components/admin/AdminPrimitives";

type LookupItem = CatalogItem | Color;

export function LookupManager({
  title,
  adminPath,
  colorMode = false,
}: {
  title: string;
  publicPath: string;
  adminPath: string;
  colorMode?: boolean;
}) {
  const { loading: authLoading } = useAuth("ADMIN");
  const searchRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<LookupItem[]>([]);
  const [editing, setEditing] = useState<LookupItem | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load(nextPage = 1) {
    const params = new URLSearchParams({ page: String(nextPage), page_size: "10" });
    if (searchRef.current?.value) params.set("search", searchRef.current.value);
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<Paginated<LookupItem>>(`${adminPath}?${params.toString()}`);
      setItems(data.items);
      setPage(data.page);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu danh mục");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = colorMode
      ? {
          name: data.get("name"),
          slug: data.get("slug"),
          hex_code: data.get("hex_code") || null,
          is_active: data.get("is_active") === "on",
        }
      : {
          name: data.get("name"),
          slug: data.get("slug"),
          description: data.get("description") || null,
          is_active: data.get("is_active") === "on",
        };
    setError("");
    setSaving(true);
    try {
      await apiFetch(editing ? `${adminPath}/${editing.id}` : adminPath, {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setEditing(null);
      form.reset();
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được dữ liệu");
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(item: LookupItem) {
    if (!window.confirm(`Bạn có chắc muốn ẩn "${item.name}"?`)) return;
    try {
      await apiFetch(`${adminPath}/${item.id}`, { method: "DELETE" });
      await load(page);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Không thể ẩn danh mục");
    }
  }

  const displayTitle = title.charAt(0).toUpperCase() + title.slice(1);

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <AdminPageHeader
        eyebrow="Hệ thống & Danh mục chuẩn"
        title={`Quản lý ${displayTitle}`}
        subtitle={`Định nghĩa các tiêu chuẩn phân loại ${title.toLowerCase()} trong cơ sở dữ liệu nội thất và AI matching.`}
      />

      {/* 2. Error Notice */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* 3. Main Split: Form (Left) & List (Right) */}
      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        {/* Left Column: Create/Edit Form */}
        <AdminSurfaceCard
          title={editing ? `Chỉnh sửa: ${editing.name}` : `Thêm ${displayTitle} mới`}
          subtitle={editing ? `Cập nhật thuộc tính ID #${editing.id}` : "Khởi tạo mục danh mục mới"}
        >
          <form key={editing?.id ?? "create"} onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
                Tên hiển thị *
              </label>
              <input
                name="name"
                placeholder={`Tên ${title.toLowerCase()}...`}
                defaultValue={editing?.name || ""}
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
                placeholder="slug-khong-dau"
                defaultValue={editing?.slug || ""}
                required
                className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
              />
            </div>

            {colorMode ? (
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
                  Mã màu Hex Code
                </label>
                <div className="flex items-center gap-2">
                  <input
                    name="hex_code"
                    placeholder="#2D332C"
                    defaultValue={(editing as Color | null)?.hex_code || ""}
                    className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
                  />
                  {(editing as Color | null)?.hex_code && (
                    <span
                      className="h-10 w-10 shrink-0 rounded-xl border border-black/10 shadow-xs"
                      style={{ backgroundColor: (editing as Color).hex_code || "#000" }}
                    />
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
                  Mô tả chi tiết
                </label>
                <textarea
                  name="description"
                  rows={3}
                  placeholder={`Mô tả tính chất của ${title.toLowerCase()}...`}
                  defaultValue={(editing as CatalogItem | null)?.description || ""}
                  className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] p-3 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
                />
              </div>
            )}

            <div className="pt-1">
              <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-semibold text-[#242424]">
                <input
                  name="is_active"
                  type="checkbox"
                  defaultChecked={editing?.is_active ?? true}
                  className="h-4 w-4 rounded border-[#2D332C]/20 text-[#2D332C] focus:ring-[#C9A77A]"
                />
                <span>Kích hoạt trong catalog</span>
              </label>
            </div>

            <div className="flex items-center gap-2 pt-3 border-t border-[#2D332C]/10">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-xl bg-[#2D332C] px-5 py-2.5 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:bg-[#3B433A] disabled:opacity-50"
              >
                <Save size={14} className="text-[#C9A77A]" />
                {saving ? "Đang lưu..." : editing ? "Lưu thay đổi" : `Tạo ${title}`}
              </button>

              {editing && (
                <button
                  type="button"
                  onClick={() => setEditing(null)}
                  className="inline-flex items-center gap-1 rounded-xl border border-[#2D332C]/15 bg-white px-4 py-2.5 text-sm font-semibold text-[#777777] hover:bg-[#FAF8F5] hover:text-[#242424]"
                >
                  <X size={14} /> Hủy sửa
                </button>
              )}
            </div>
          </form>
        </AdminSurfaceCard>

        {/* Right Column: Lookup Items List */}
        <AdminSurfaceCard
          title={`Danh sách ${displayTitle}`}
          subtitle={`Tổng số ${total} bản ghi trong hệ thống`}
        >
          <div className="space-y-4">
            {/* Search row */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search
                  size={15}
                  className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
                />
                <input
                  ref={searchRef}
                  className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] py-2 pl-9 pr-3 text-sm text-[#242424] placeholder:text-[#777777] focus:border-[#A68B6D] focus:bg-white focus:outline-none"
                  placeholder={`Tìm kiếm ${title.toLowerCase()}...`}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      load(1);
                    }
                  }}
                />
              </div>
              <button
                type="button"
                onClick={() => load(1)}
                className="inline-flex items-center gap-1 rounded-xl bg-[#2D332C] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#3B433A]"
              >
                Tìm
              </button>
            </div>

            {/* Items List */}
            {loading ? (
              <div className="p-8 text-center text-sm font-medium text-[#777777]">
                Đang tải dữ liệu danh mục...
              </div>
            ) : items.length === 0 ? (
              <AdminEmptyState
                icon={Layers}
                title={`Chưa có ${title.toLowerCase()} nào`}
                description="Sử dụng biểu mẫu bên trái để khởi tạo mục danh mục đầu tiên."
              />
            ) : (
              <div className="divide-y divide-[#2D332C]/5 rounded-2xl border border-[#2D332C]/10 bg-white">
                {items.map((item) => {
                  const hex = (item as Color).hex_code;
                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-3 p-3.5 transition hover:bg-[#FAF8F5]/60"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        {colorMode && (
                          <span
                            className="h-8 w-8 shrink-0 rounded-lg border border-black/10 shadow-2xs"
                            style={{ backgroundColor: hex || "#FAF8F5" }}
                          />
                        )}
                        <div className="min-w-0">
                          <p className="truncate font-bold text-[#242424]">{item.name}</p>
                          <p className="truncate text-xs text-[#777777]">
                            {item.slug} {hex ? `· ${hex}` : ""}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <AdminStatusBadge
                          status={item.is_active ? "ACTIVE" : "INACTIVE"}
                          customLabel={item.is_active ? "Hoạt động" : "Tạm ẩn"}
                          size="sm"
                        />
                        <button
                          type="button"
                          onClick={() => setEditing(item)}
                          className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#2D332C]/15 bg-white px-2.5 text-xs font-semibold text-[#242424] shadow-2xs hover:border-[#A68B6D] hover:bg-[#FAF8F5]"
                        >
                          <Edit2 size={12} className="text-[#A68B6D]" />
                          Sửa
                        </button>
                        {item.is_active && (
                          <button
                            type="button"
                            onClick={() => deactivate(item)}
                            title="Ẩn khỏi catalog"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#2D332C]/10 bg-[#FAF8F5] text-[#777777] hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                          >
                            <EyeOff size={13} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Pagination */}
            {total > 10 && (
              <AdminPagination
                page={page}
                pageSize={10}
                total={total}
                onPageChange={(p) => load(p)}
                loading={loading}
              />
            )}
          </div>
        </AdminSurfaceCard>
      </div>
    </div>
  );
}
