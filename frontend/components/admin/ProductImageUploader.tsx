"use client";

import { FormEvent, useState } from "react";
import { Image as ImageIcon, Upload, CheckCircle2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { Product } from "@/types/api";

export function ProductImageUploader({
  productId,
  onUploaded,
}: {
  productId: number;
  onUploaded: (product: Product) => void;
}) {
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const result = await apiFetch<Product>(`/api/admin/products/${productId}/images`, {
        method: "POST",
        body: data,
      });
      onUploaded(result);
      form.reset();
      setSelectedFileName("");
      setSuccess("Tải lên và đồng bộ ảnh sản phẩm thành công!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không upload được ảnh");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-8 rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
      <div className="mb-5 border-b border-[#2D332C]/10 pb-4">
        <div className="flex items-center gap-2">
          <ImageIcon size={16} className="text-[#C9A77A]" />
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
            Thư viện hình ảnh
          </p>
        </div>
        <h2 className="mt-1 text-lg font-bold text-[#242424]">Tải lên hình ảnh sản phẩm mới</h2>
        <p className="mt-0.5 text-xs text-[#777777]">
          Hỗ trợ định dạng PNG, JPG, WebP. Nên sử dụng ảnh chụp góc thẳng hoặc ảnh nền trắng để làm tham chiếu AI tốt nhất.
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <div className="relative rounded-2xl border-2 border-dashed border-[#2D332C]/20 bg-[#FAF8F5]/60 p-6 text-center transition hover:border-[#C9A77A] hover:bg-[#FAF8F5]">
          <input
            name="file"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            required
            onChange={(e) => {
              if (e.target.files?.[0]) {
                setSelectedFileName(e.target.files[0].name);
              }
            }}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          />
          <div className="flex flex-col items-center justify-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[#C9A77A]/35 bg-white text-[#2D332C] shadow-sm">
              <Upload size={20} className="text-[#A68B6D]" />
            </span>
            <p className="mt-3 text-sm font-semibold text-[#242424]">
              {selectedFileName ? (
                <span className="text-[#2D332C]">Đã chọn: {selectedFileName}</span>
              ) : (
                "Nhấp để chọn tệp hoặc kéo thả ảnh vào đây"
              )}
            </p>
            <p className="mt-1 text-xs text-[#777777]">PNG, JPG, WebP tối đa 10MB</p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs font-bold uppercase tracking-wider text-[#777777]">
              Mô tả văn bản thay thế (Alt Text)
            </label>
            <input
              name="alt_text"
              placeholder="VD: Sofa da cao cấp màu be góc chính diện"
              className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            />
          </div>

          <div className="flex items-center pt-5">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-[#242424]">
              <input
                name="is_primary"
                type="checkbox"
                value="true"
                className="h-4 w-4 rounded border-[#2D332C]/20 text-[#2D332C] focus:ring-[#C9A77A]"
              />
              <span>Đặt làm hình ảnh đại diện chính (Primary)</span>
            </label>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
            {error}
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800">
            <CheckCircle2 size={16} className="text-emerald-600" />
            {success}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-[#2D332C] px-5 py-2.5 text-sm font-semibold text-white shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#3B433A] disabled:opacity-50"
          >
            <Upload size={14} className="text-[#C9A77A]" />
            {loading ? "Đang tải ảnh lên..." : "Tải lên thư viện"}
          </button>
        </div>
      </form>
    </div>
  );
}
