import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { apiAssetUrl } from "@/lib/api";
import { displayCategory, displayStyle, joinDisplay } from "@/lib/display";
import { EmptyImagePlaceholder } from "@/components/customer/DesignPrimitives";
import type { Product } from "@/types/api";

export function ProductCard({ product }: { product: Product }) {
  const image = product.images.find((item) => item.is_primary)?.image_url || product.images[0]?.image_url;

  return (
    <Link
      href={`/products/${product.id}`}
      className="group block overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-card transition hover:-translate-y-1 hover:border-clay/30 hover:shadow-soft"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-ivory">
        {image ? (
          <img src={apiAssetUrl(image)} alt={product.name} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.04]" />
        ) : (
          <EmptyImagePlaceholder />
        )}
        <span className="absolute left-3 top-3 rounded-full bg-white/90 px-3 py-1 text-xs font-black text-clay shadow-sm">
          {displayCategory(product.category.name)}
        </span>
      </div>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <h3 className="line-clamp-2 text-lg font-black text-ink">{product.name}</h3>
          <ArrowUpRight size={18} className="mt-1 shrink-0 text-charcoal/35 transition group-hover:text-clay" />
        </div>
        <p className="mt-2 min-h-5 text-sm text-charcoal/60">{joinDisplay(product.styles, (item) => displayStyle(item.name), "Phong cách đang cập nhật")}</p>
        <div className="mt-4 flex items-end justify-between gap-3">
          <p className="text-xl font-black text-clay">{Number(product.price).toLocaleString("vi-VN")} đ</p>
          <span className="rounded-full bg-ivory px-3 py-1 text-xs font-bold text-charcoal/60">Còn {product.stock_quantity}</span>
        </div>
      </div>
    </Link>
  );
}
