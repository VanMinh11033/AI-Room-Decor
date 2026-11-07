"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import type { Product } from "@/types/api";

export function ProductImageUploader({ productId, onUploaded }: { productId: number; onUploaded: (product: Product) => void }) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setLoading(true);
    setError("");
    try {
      const result = await apiFetch<Product>(`/api/admin/products/${productId}/images`, {
        method: "POST",
        body: data
      });
      onUploaded(result);
      form.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không upload được ảnh");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mt-6 rounded-lg border border-black/10 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold">Upload ảnh sản phẩm</h2>
      <div className="mt-4 grid gap-3">
        <input name="file" type="file" accept="image/png,image/jpeg,image/webp" required className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm" />
        <input name="alt_text" placeholder="Alt text" className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm" />
        <label className="flex items-center gap-2 text-sm"><input name="is_primary" type="checkbox" value="true" /> Đặt làm ảnh chính</label>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      <Button type="submit" disabled={loading} className="mt-4">{loading ? "Đang upload..." : "Upload ảnh"}</Button>
    </form>
  );
}

