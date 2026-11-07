"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProductForm } from "@/components/admin/ProductForm";
import { ProductImageUploader } from "@/components/admin/ProductImageUploader";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import type { Product } from "@/types/api";

export default function EditProductPage() {
  const params = useParams<{ id: string }>();
  const { loading } = useAuth("ADMIN");
  const [product, setProduct] = useState<Product | null>(null);

  useEffect(() => {
    apiFetch<Product>(`/api/admin/products/${params.id}`).then(setProduct).catch(() => setProduct(null));
  }, [params.id]);

  if (loading || !product) return <p>Đang tải...</p>;

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-3xl font-bold">Sửa sản phẩm</h1>
      <ProductForm product={product} />
      <ProductImageUploader productId={product.id} onUploaded={setProduct} />
    </section>
  );
}

