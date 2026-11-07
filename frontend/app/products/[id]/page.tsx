"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Package, Ruler, ShoppingCart } from "lucide-react";
import { EmptyImagePlaceholder, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStatus, displayStyle, joinDisplay } from "@/lib/display";
import type { Product } from "@/types/api";

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [selectedImage, setSelectedImage] = useState("");
  const [cartMessage, setCartMessage] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    apiFetch<Product>(`/api/products/${params.id}`)
      .then((data) => {
        setProduct(data);
        setSelectedImage(data.images.find((item) => item.is_primary)?.image_url || data.images[0]?.image_url || "");
      })
      .catch(() => setProduct(null));
  }, [params.id]);

  async function handleAddToCart() {
    if (!product) return;
    setAdding(true);
    setCartMessage("");
    try {
      await addToCart(product.id);
      setCartMessage("Đã thêm vào giỏ hàng.");
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Không thêm được vào giỏ hàng.");
    } finally {
      setAdding(false);
    }
  }

  if (!product) return <p className="font-semibold text-charcoal/60">Đang tải sản phẩm...</p>;

  return (
    <section className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
      <div className="space-y-4">
        <div className="overflow-hidden rounded-3xl border border-ink/10 bg-white shadow-soft">
          <div className="aspect-[4/3] bg-ivory">
            {selectedImage ? (
              <img src={apiAssetUrl(selectedImage)} alt={product.name} className="h-full w-full object-cover" />
            ) : (
              <EmptyImagePlaceholder />
            )}
          </div>
        </div>
        {product.images.length > 0 && (
          <div className="grid grid-cols-5 gap-3">
            {product.images.map((image) => (
              <button
                key={image.id}
                onClick={() => setSelectedImage(image.image_url)}
                className={`aspect-square overflow-hidden rounded-2xl border bg-white transition ${
                  selectedImage === image.image_url ? "border-clay shadow-card" : "border-ink/10 hover:border-clay/40"
                }`}
              >
                <img src={apiAssetUrl(image.image_url)} alt={image.alt_text || product.name} className="h-full w-full object-cover" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-5">
        <SectionCard>
          <p className="text-sm font-black uppercase tracking-[0.16em] text-clay">{displayCategory(product.category.name)}</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-ink md:text-5xl">{product.name}</h1>
          <p className="mt-4 leading-7 text-charcoal/70">{product.description}</p>
          <p className="mt-6 text-3xl font-black text-clay">{Number(product.price).toLocaleString("vi-VN")} đ</p>
          <button onClick={handleAddToCart} disabled={adding} className="primary-cta mt-7">
            <ShoppingCart size={18} /> {adding ? "Đang thêm..." : "Thêm vào giỏ hàng"}
          </button>
          {cartMessage && <p className="mt-3 text-sm font-bold text-green-700">{cartMessage}</p>}
        </SectionCard>

        <SectionCard title="Thông tin sản phẩm">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Info label="Phong cách" value={joinDisplay(product.styles, (item) => displayStyle(item.name))} />
            <Info label="Màu sắc" value={joinDisplay(product.colors, (item) => displayColor(item.name))} />
            <Info label="Vật liệu" value={joinDisplay(product.materials, (item) => displayMaterial(item.name))} />
            <Info label="Loại phòng" value={joinDisplay(product.room_types, (item) => displayRoomType(item.name))} />
            <Info label="Tồn kho" value={String(product.stock_quantity)} icon={<Package size={16} />} />
            <Info label="Trạng thái" value={displayStatus(product.status)} />
            <Info label="Kích thước" value={[product.width, product.height, product.depth].filter(Boolean).join(" x ") || "-"} icon={<Ruler size={16} />} />
            <Info label="Khối lượng" value={product.weight ? `${product.weight} kg` : "-"} />
            <div className="sm:col-span-2">
              <Info label="Tags" value={product.tags || "-"} />
            </div>
          </dl>
        </SectionCard>
      </div>
    </section>
  );
}

function Info({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-ivory px-4 py-3">
      <dt className="flex items-center gap-2 text-xs font-black uppercase tracking-wide text-charcoal/45">{icon}{label}</dt>
      <dd className="mt-1 font-bold text-ink">{value}</dd>
    </div>
  );
}
