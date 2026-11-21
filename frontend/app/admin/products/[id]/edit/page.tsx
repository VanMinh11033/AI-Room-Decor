"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProductForm } from "@/components/admin/ProductForm";
import { ProductImageUploader } from "@/components/admin/ProductImageUploader";
import { AdminBadge, AdminPageHeader, AdminStatusBadge } from "@/components/admin/AdminPrimitives";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import type { Product } from "@/types/api";

export default function EditProductPage() {
  const params = useParams<{ id: string }>();
  const { loading } = useAuth("ADMIN");
  const [product, setProduct] = useState<Product | null>(null);

  useEffect(() => {
    apiFetch<Product>(`/api/admin/products/${params.id}`)
      .then(setProduct)
      .catch(() => setProduct(null));
  }, [params.id]);

  if (loading || !product) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang tải thông tin sản phẩm #{params.id}...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Cập nhật catalog"
        title={`Chỉnh sửa: ${product.name}`}
        subtitle={`Mã sản phẩm: #${product.id} · Slug: ${product.slug}`}
        backHref="/admin/products"
        backLabel="Quay lại danh mục sản phẩm"
        badge={
          <div className="flex items-center gap-2">
            <AdminStatusBadge status={product.status || (product.is_active ? "ACTIVE" : "INACTIVE")} />
            {product.is_reference_ready ? (
              <AdminBadge variant="emerald">Sẵn sàng AI Ref</AdminBadge>
            ) : (
              <AdminBadge variant="stone">Chưa có ảnh chuẩn</AdminBadge>
            )}
          </div>
        }
      />

      {/* Existing Images Gallery Preview */}
      {product.images && product.images.length > 0 && (
        <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
          <div className="mb-4">
            <h3 className="text-base font-bold text-[#242424]">Hình ảnh hiện tại ({product.images.length})</h3>
            <p className="text-xs text-[#777777]">Hình ảnh đại diện và các góc phối cảnh trong catalog</p>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 md:grid-cols-6">
            {product.images.map((img) => (
              <div
                key={img.id}
                className={`relative overflow-hidden rounded-xl border bg-[#FAF8F5] p-1 shadow-2xs ${
                  img.is_primary ? "border-[#C9A77A] ring-2 ring-[#C9A77A]/25" : "border-[#2D332C]/10"
                }`}
              >
                <img
                  src={apiAssetUrl(img.image_url)}
                  alt={img.alt_text || product.name}
                  className="aspect-square w-full rounded-lg object-cover"
                />
                {img.is_primary && (
                  <span className="absolute bottom-2 left-2 rounded-md bg-[#2D332C] px-1.5 py-0.5 text-[9px] font-bold text-[#C9A77A]">
                    Ảnh chính
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mx-auto max-w-4xl space-y-6">
        <ProductForm product={product} />
        <ProductImageUploader productId={product.id} onUploaded={setProduct} />
      </div>
    </div>
  );
}
