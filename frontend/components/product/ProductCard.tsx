import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { apiAssetUrl } from "@/lib/api";
import { displayCategory, displayStyle, joinDisplay } from "@/lib/display";
import { EmptyImagePlaceholder } from "@/components/customer/DesignPrimitives";
import type { Product } from "@/types/api";

export function ProductCard({
  product,
  priority = false,
}: {
  product: Product;
  priority?: boolean;
}) {
  const image =
    product.images.find((item) => item.is_primary)?.image_url ||
    product.images[0]?.image_url;
  const inStock = product.stock_quantity > 0;

  return (
    <Link
      href={`/products/${product.id}`}
      className="group block overflow-hidden rounded-2xl border border-[#242B23]/10 bg-white shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-[#8A6B4E]/40 hover:shadow-card"
    >
      <div className="relative aspect-[4/3] w-full overflow-hidden bg-[#FBF9F5]">
        {image ? (
          <img
            src={apiAssetUrl(image, { width: 600 })}
            alt={product.name}
            loading={priority ? undefined : "lazy"}
            decoding="async"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <EmptyImagePlaceholder />
        )}
        <div className="absolute left-3 top-3">
          <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-[#8A6B4E] shadow-sm backdrop-blur-sm">
            {displayCategory(product.category.name)}
          </span>
        </div>
        <div className="absolute right-3 top-3">
          {inStock ? (
            <span className="rounded-full bg-[#242B23]/75 px-2.5 py-0.5 text-[11px] font-semibold text-white backdrop-blur-sm">
              Còn {product.stock_quantity}
            </span>
          ) : (
            <span className="rounded-full bg-red-800/80 px-2.5 py-0.5 text-[11px] font-semibold text-white backdrop-blur-sm">
              Hết hàng
            </span>
          )}
        </div>
      </div>

      <div className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-serif text-lg font-normal text-[#242B23] line-clamp-2 leading-snug group-hover:text-[#8A6B4E] transition">
            {product.name}
          </h3>
          <ArrowUpRight
            size={18}
            className="mt-0.5 shrink-0 text-[#5A6258] transition-transform duration-300 group-hover:text-[#8A6B4E] group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
          />
        </div>

        <p className="text-xs text-[#5A6258] line-clamp-1 min-h-[1rem]">
          {joinDisplay(product.styles, (item) => displayStyle(item.name), "Phong cách Đương Đại")}
        </p>

        <div className="flex items-center justify-between pt-3 border-t border-[#242B23]/5">
          <p className="text-base sm:text-lg font-semibold text-[#242B23]">
            {Number(product.price).toLocaleString("vi-VN")} đ
          </p>
          <span className="text-xs font-medium text-[#8A6B4E] group-hover:underline">
            Chi tiết
          </span>
        </div>
      </div>
    </Link>
  );
}
