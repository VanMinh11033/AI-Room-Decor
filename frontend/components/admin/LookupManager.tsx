"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { displayStatus } from "@/lib/display";
import type { CatalogItem, Color, Paginated } from "@/types/api";

type LookupItem = CatalogItem | Color;

export function LookupManager({ title, adminPath, colorMode = false }: { title: string; publicPath: string; adminPath: string; colorMode?: boolean }) {
  const { loading: authLoading } = useAuth("ADMIN");
  const searchRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<LookupItem[]>([]);
  const [editing, setEditing] = useState<LookupItem | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = colorMode
      ? { name: data.get("name"), slug: data.get("slug"), hex_code: data.get("hex_code") || null, is_active: data.get("is_active") === "on" }
      : { name: data.get("name"), slug: data.get("slug"), description: data.get("description") || null, is_active: data.get("is_active") === "on" };
    setError("");
    try {
      await apiFetch(editing ? `${adminPath}/${editing.id}` : adminPath, {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload)
      });
      setEditing(null);
      form.reset();
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được dữ liệu");
    }
  }

  async function deactivate(item: LookupItem) {
    if (!window.confirm(`Ẩn "${item.name}"?`)) return;
    await apiFetch(`${adminPath}/${item.id}`, { method: "DELETE" });
    await load(page);
  }

  if (authLoading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <section className="grid gap-6 md:grid-cols-[0.8fr_1.2fr]">
      <form key={editing?.id ?? "create"} onSubmit={onSubmit} className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold">{editing ? `Sửa ${title}` : `Thêm ${title}`}</h1>
        <div className="mt-5 grid gap-3">
          <Input name="name" placeholder="Tên" defaultValue={editing?.name || ""} required />
          <Input name="slug" placeholder="slug" defaultValue={editing?.slug || ""} required />
          {colorMode ? (
            <Input name="hex_code" placeholder="#ffffff" defaultValue={(editing as Color | null)?.hex_code || ""} />
          ) : (
            <Input name="description" placeholder="Mô tả" defaultValue={(editing as CatalogItem | null)?.description || ""} />
          )}
          <label className="flex items-center gap-2 text-sm"><input name="is_active" type="checkbox" defaultChecked={editing?.is_active ?? true} /> Đang hoạt động</label>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <div className="mt-5 flex gap-2">
          <Button type="submit">Lưu</Button>
          {editing && <button type="button" onClick={() => setEditing(null)} className="rounded-md border border-black/15 bg-white px-4 py-2 text-sm font-semibold">Hủy</button>}
        </div>
      </form>
      <div className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold">Danh sách {title}</h2>
        <div className="mt-4 flex gap-2">
          <input ref={searchRef} className="w-full rounded-md border border-black/15 bg-white px-3 py-2 text-sm" placeholder="Tìm kiếm" />
          <button onClick={() => load(1)} className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white">Tìm</button>
        </div>
        {loading && <p className="mt-4">Đang tải...</p>}
        <div className="mt-4 divide-y divide-black/10">
          {items.map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="font-semibold">{item.name}</p>
                <p className="text-sm text-black/50">{item.slug} · {displayStatus(item.is_active ? "ACTIVE" : "INACTIVE")}</p>
              </div>
              <div className="flex gap-3 text-sm font-semibold">
                <button onClick={() => setEditing(item)}>Sửa</button>
                <button onClick={() => deactivate(item)} className="text-red-700">Ẩn</button>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 flex items-center justify-between text-sm">
          <span>Tổng {total}</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => load(page - 1)} className="rounded-md border border-black/15 bg-white px-3 py-2 disabled:opacity-40">Trước</button>
            <button disabled={page * 10 >= total} onClick={() => load(page + 1)} className="rounded-md border border-black/15 bg-white px-3 py-2 disabled:opacity-40">Sau</button>
          </div>
        </div>
      </div>
    </section>
  );
}
