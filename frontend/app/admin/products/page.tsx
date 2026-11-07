"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { displayCategory, displayStatus } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { Paginated, Product } from "@/types/api";

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

  async function deactivate(product: Product) {
    if (!window.confirm(`Ẩn sản phẩm "${product.name}"?`)) return;
    await apiFetch(`/api/admin/products/${product.id}`, { method: "DELETE" });
    await load(page);
  }

  async function activate(product: Product) {
    if (!window.confirm(`Kích hoạt sản phẩm "${product.name}"?`)) return;
    await apiFetch<Product>(`/api/admin/products/${product.id}`, {
      method: "PUT",
      body: JSON.stringify({ status: "ACTIVE", is_active: true })
    });
    await load(page);
  }

  if (authLoading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <section>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-3xl font-bold">Quản lý sản phẩm</h1>
        <Link className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white" href="/admin/products/create">Thêm sản phẩm</Link>
      </div>
      <form ref={formRef} onSubmit={onSubmit} className="mt-5 grid gap-2 sm:grid-cols-4">
        <input name="search" className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm" placeholder="Tìm sản phẩm" />
        <select name="is_active" className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
          <option value="">Tất cả trạng thái</option>
          <option value="true">Đang bán</option>
          <option value="false">Tạm ẩn</option>
        </select>
        <select name="sort" className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
          <option value="newest">Mới nhất</option>
          <option value="price_asc">Giá tăng</option>
          <option value="price_desc">Giá giảm</option>
          <option value="name_asc">Tên A-Z</option>
        </select>
        <button className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white">Lọc</button>
      </form>
      {loading && <p className="mt-6">Đang tải...</p>}
      {error && <p className="mt-6 text-sm text-red-600">{error}</p>}
      <div className="mt-6 overflow-hidden rounded-lg border border-black/10 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-black/5">
            <tr><th className="p-3">Tên</th><th className="p-3">Danh mục</th><th className="p-3">Giá</th><th className="p-3">Kho</th><th className="p-3">Trạng thái</th><th className="p-3"></th></tr>
          </thead>
          <tbody>
            {products.map((product) => (
              <tr key={product.id} className="border-t border-black/10">
                <td className="p-3 font-semibold">{product.name}</td>
                <td className="p-3">{displayCategory(product.category.name)}</td>
                <td className="p-3">{Number(product.price).toLocaleString("vi-VN")} đ</td>
                <td className="p-3">{product.stock_quantity}</td>
                <td className="p-3">{displayStatus(product.status)}</td>
                <td className="p-3">
                  <div className="flex justify-end gap-3">
                    <Link className="font-semibold" href={`/admin/products/${product.id}/edit`}>Sửa</Link>
                    {product.is_active ? (
                      <button onClick={() => deactivate(product)} className="font-semibold text-red-700">Ẩn</button>
                    ) : (
                      <button onClick={() => activate(product)} className="font-semibold text-green-700">Kích hoạt</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-6 flex items-center justify-between text-sm">
        <span>Tổng {total} sản phẩm</span>
        <div className="flex gap-2">
          <button disabled={page <= 1} onClick={() => load(page - 1)} className="rounded-md border border-black/15 bg-white px-3 py-2 disabled:opacity-40">Trước</button>
          <button disabled={page * 10 >= total} onClick={() => load(page + 1)} className="rounded-md border border-black/15 bg-white px-3 py-2 disabled:opacity-40">Sau</button>
        </div>
      </div>
    </section>
  );
}
