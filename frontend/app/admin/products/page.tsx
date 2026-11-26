"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Boxes,
  CheckCircle2,
  Edit3,
  Eye,
  EyeOff,
  Filter,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
} from "lucide-react";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayCategory } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { Paginated, Product } from "@/types/api";
import {
  AdminBadge,
  AdminEmptyState,
  AdminPageHeader,
  AdminPagination,
  AdminSearchFilterBar,
  AdminStatMiniCard,
  AdminStatusBadge,
  AdminTable,
  AdminTableCell,
  AdminTableContainer,
  AdminTableHead,
  AdminTableRow,
} from "@/components/admin/AdminPrimitives";

export default function AdminProductsPage() {
  const { loading: authLoading } = useAuth("ADMIN");
  const formRef = useRef<HTMLFormElement>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(nextPage = 1) {
    const params = new URLSearchParams({ page: String(nextPage), page_size: "10" });
    if (formRef.current) {
      new FormData(formRef.current).forEach((value, key) => {
        if (value) params.set(key, String(value));
      });
    }
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<Paginated<Product>>(`/api/admin/products?${params.toString()}`);
      setProducts(data.items);
      setPage(data.page);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được sản phẩm");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load(1);
  }

  function onReset() {
    if (formRef.current) {
      formRef.current.reset();
      load(1);
    }
  }

  async function deactivate(product: Product) {
    if (!window.confirm(`Ẩn sản phẩm "${product.name}" khỏi danh mục bán?`)) return;
    try {
      await apiFetch(`/api/admin/products/${product.id}`, { method: "DELETE" });
      await load(page);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Không thể ẩn sản phẩm");
    }
  }

  async function activate(product: Product) {
    if (!window.confirm(`Kích hoạt sản phẩm "${product.name}"?`)) return;
    try {
      await apiFetch<Product>(`/api/admin/products/${product.id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "ACTIVE", is_active: true }),
      });
      await load(page);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Không thể kích hoạt sản phẩm");
    }
  }

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  const activeCount = products.filter((p) => p.is_active || p.status === "ACTIVE").length;
  const readyCount = products.filter((p) => p.is_reference_ready).length;

  const tableColumns = [
    { key: "product", label: "Sản phẩm & Hình ảnh" },
    { key: "category", label: "Phân loại" },
    { key: "price", label: "Đơn giá", align: "right" as const },
    { key: "stock", label: "Kho", align: "center" as const },
    { key: "status", label: "Trạng thái", align: "center" as const },
    { key: "ai_readiness", label: "Chuẩn tham chiếu AI", align: "center" as const },
    { key: "actions", label: "Thao tác", align: "right" as const },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Catalog & Thương mại"
        title="Quản lý sản phẩm"
        subtitle="Quản trị 30+ sản phẩm catalog nội thất, hình ảnh tham chiếu AI chuẩn và trạng thái kinh doanh."
        actions={
          <Link
            href="/admin/products/create"
            className="inline-flex items-center gap-2 rounded-xl bg-[#2D332C] px-5 py-3 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#3B433A] hover:shadow-soft"
          >
            <Plus size={16} className="text-[#C9A77A]" />
            Thêm sản phẩm mới
          </Link>
        }
      />

      {/* 2. Top Summary KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AdminStatMiniCard
          label="Tổng sản phẩm"
          value={total}
          sub="Toàn bộ danh mục catalog"
          icon={Boxes}
        />
        <AdminStatMiniCard
          label="Đang mở bán"
          value={activeCount}
          sub="Hiển thị trên website khách hàng"
          icon={CheckCircle2}
        />
        <AdminStatMiniCard
          label="Sẵn sàng AI Ref"
          value={readyCount}
          sub="Có ảnh sạch chuẩn tham chiếu AI"
          icon={Sparkles}
        />
        <AdminStatMiniCard
          label="Tạm ẩn / Đang xử lý"
          value={Math.max(0, products.length - activeCount)}
          sub="Cần kiểm tra hoặc kích hoạt"
          icon={EyeOff}
        />
      </div>

      {/* 3. Search & Filter Bar */}
      <AdminSearchFilterBar formRef={formRef} onSubmit={onSubmit}>
        <div className="relative min-w-[240px] flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            name="search"
            className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] py-2.5 pl-10 pr-4 text-sm text-[#242424] placeholder:text-[#777777] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            placeholder="Tìm theo tên sản phẩm, slug..."
          />
        </div>

        <select
          name="is_active"
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả trạng thái</option>
          <option value="true">Đang bán (Active)</option>
          <option value="false">Tạm ẩn (Inactive)</option>
        </select>

        <select
          name="sort"
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="newest">Mới nhất trước</option>
          <option value="price_asc">Giá tăng dần</option>
          <option value="price_desc">Giá giảm dần</option>
          <option value="name_asc">Tên sản phẩm A-Z</option>
        </select>

        <div className="flex items-center gap-2">
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#2D332C] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#3B433A]"
          >
            <Filter size={14} className="text-[#C9A77A]" />
            Lọc
          </button>
          <button
            type="button"
            onClick={onReset}
            title="Đặt lại bộ lọc"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] text-[#777777] transition hover:border-[#A68B6D] hover:bg-white hover:text-[#242424]"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </AdminSearchFilterBar>

      {/* 4. Error Message */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* 5. Products Data Table */}
      <AdminTableContainer>
        <AdminTable>
          <AdminTableHead columns={tableColumns} />
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="p-12 text-center text-sm font-medium text-[#777777]">
                  Đang tải dữ liệu sản phẩm...
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8">
                  <AdminEmptyState
                    icon={Boxes}
                    title="Không tìm thấy sản phẩm nào"
                    description="Thử thay đổi từ khóa tìm kiếm hoặc bỏ bớt các bộ lọc đang chọn."
                    action={
                      <button
                        type="button"
                        onClick={onReset}
                        className="rounded-xl border border-[#2D332C]/15 bg-white px-4 py-2 text-xs font-semibold text-[#242424] shadow-sm hover:bg-[#FAF8F5]"
                      >
                        Đặt lại bộ lọc
                      </button>
                    }
                  />
                </td>
              </tr>
            ) : (
              products.map((product) => {
                const primaryImage =
                  product.images.find((img) => img.is_primary)?.image_url ||
                  product.images[0]?.image_url;

                const isLowStock = product.stock_quantity <= 3;
                const isOutOfStock = product.stock_quantity <= 0;

                return (
                  <AdminTableRow key={product.id}>
                    {/* Column 1: Product Thumbnail & Name */}
                    <AdminTableCell>
                      <div className="flex items-center gap-3.5">
                        <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] shadow-2xs">
                          {primaryImage ? (
                            <img
                              src={apiAssetUrl(primaryImage, { width: 100 })}
                              alt={product.name}
                              loading="lazy"
                              decoding="async"
                              className="h-full w-full object-cover transition duration-300 hover:scale-105"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-xs font-bold text-[#A68B6D]">
                              N/A
                            </div>
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-bold text-[#242424] hover:text-[#2D332C]">
                            <Link href={`/admin/products/${product.id}/edit`}>
                              {product.name}
                            </Link>
                          </p>
                          <p className="truncate text-xs text-[#777777]">
                            #{product.id} · {product.slug}
                          </p>
                        </div>
                      </div>
                    </AdminTableCell>

                    {/* Column 2: Category & Tags */}
                    <AdminTableCell>
                      <div className="space-y-1">
                        <AdminBadge variant="gold" size="sm">
                          {displayCategory(product.category?.name || "Khác")}
                        </AdminBadge>
                        {product.styles && product.styles.length > 0 && (
                          <p className="text-[11px] text-[#777777]">
                            {product.styles.map((s) => s.name).join(", ")}
                          </p>
                        )}
                      </div>
                    </AdminTableCell>

                    {/* Column 3: Price */}
                    <AdminTableCell align="right">
                      <span className="font-bold text-[#242424]">
                        {Number(product.price).toLocaleString("vi-VN")} đ
                      </span>
                    </AdminTableCell>

                    {/* Column 4: Stock */}
                    <AdminTableCell align="center">
                      <div className="inline-flex flex-col items-center">
                        <span
                          className={`font-semibold ${
                            isOutOfStock
                              ? "text-rose-600"
                              : isLowStock
                              ? "text-amber-600"
                              : "text-[#242424]"
                          }`}
                        >
                          {product.stock_quantity}
                        </span>
                        {isOutOfStock ? (
                          <span className="text-[10px] font-bold text-rose-500">Hết hàng</span>
                        ) : isLowStock ? (
                          <span className="text-[10px] font-bold text-amber-500">Sắp hết</span>
                        ) : null}
                      </div>
                    </AdminTableCell>

                    {/* Column 5: Status */}
                    <AdminTableCell align="center">
                      <AdminStatusBadge status={product.status || (product.is_active ? "ACTIVE" : "INACTIVE")} size="sm" />
                    </AdminTableCell>

                    {/* Column 6: AI Reference Readiness */}
                    <AdminTableCell align="center">
                      {product.is_reference_ready ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800 shadow-2xs">
                          <Sparkles size={11} className="text-emerald-600" />
                          Sẵn sàng AI
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-[#2D332C]/10 bg-[#FAF8F5] px-2.5 py-0.5 text-[11px] font-medium text-[#777777]">
                          Chưa có ảnh chuẩn
                        </span>
                      )}
                    </AdminTableCell>

                    {/* Column 7: Actions */}
                    <AdminTableCell align="right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link
                          href={`/admin/products/${product.id}/edit`}
                          className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#2D332C]/15 bg-white px-2.5 text-xs font-semibold text-[#242424] shadow-2xs transition hover:border-[#A68B6D] hover:bg-[#FAF8F5]"
                        >
                          <Edit3 size={13} className="text-[#A68B6D]" />
                          Sửa
                        </Link>
                        {product.is_active || product.status === "ACTIVE" ? (
                          <button
                            type="button"
                            onClick={() => deactivate(product)}
                            title="Ẩn sản phẩm"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#2D332C]/10 bg-[#FAF8F5] text-[#777777] transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                          >
                            <EyeOff size={14} />
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => activate(product)}
                            title="Kích hoạt bán"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 transition hover:bg-emerald-100"
                          >
                            <Eye size={14} />
                          </button>
                        )}
                      </div>
                    </AdminTableCell>
                  </AdminTableRow>
                );
              })
            )}
          </tbody>
        </AdminTable>

        {/* 6. Pagination */}
        {total > 0 && (
          <AdminPagination
            page={page}
            pageSize={10}
            total={total}
            onPageChange={(p) => load(p)}
            loading={loading}
          />
        )}
      </AdminTableContainer>
    </div>
  );
}
