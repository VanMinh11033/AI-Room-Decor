"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  CheckCircle2,
  ChevronRight,
  Package,
  Plus,
  Ruler,
  ShoppingCart,
  Sparkles,
  X,
} from "lucide-react";
import { EmptyImagePlaceholder } from "@/components/customer/DesignPrimitives";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiAssetUrl, apiFetch, getAccessToken } from "@/lib/api";
import { addToCart } from "@/lib/cart";
import { setPreselectedProduct } from "@/lib/studio";
import {
  displayCategory,
  displayColor,
  displayMaterial,
  displayRoomType,
  displayStyle,
  joinDisplay,
} from "@/lib/display";
import type { Paginated, Product, RoomProject } from "@/types/api";

function ProductDetailContent() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [product, setProduct] = useState<Product | null>(null);
  const [selectedImage, setSelectedImage] = useState("");
  const [cartMessage, setCartMessage] = useState("");
  const [adding, setAdding] = useState(false);

  // AI Studio Integration Modal state (AUD-P1-002)
  const [studioModalOpen, setStudioModalOpen] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [userProjects, setUserProjects] = useState<RoomProject[]>([]);
  const [studioError, setStudioError] = useState("");

  const justAdded = searchParams.get("added") === "1" || searchParams.get("added") === "true";
  const cartRetry = searchParams.get("cart_retry") === "1";
  const shouldOpenStudio = searchParams.get("open_studio") === "1" || searchParams.get("open_studio") === "true";

  useEffect(() => {
    apiFetch<Product>(`/api/products/${params.id}`)
      .then((data) => {
        setProduct(data);
        setSelectedImage(data.images.find((item) => item.is_primary)?.image_url || data.images[0]?.image_url || "");
      })
      .catch(() => setProduct(null));
  }, [params.id]);

  // If redirected back with open_studio=1 after authentication
  useEffect(() => {
    if (shouldOpenStudio && product) {
      handleDesignWithProduct();
    }
  }, [shouldOpenStudio, product]);

  async function handleAddToCart() {
    if (!product || adding) return;
    setAdding(true);
    setCartMessage("");
    try {
      await addToCart(product.id, 1, `/products/${product.id}`);
      setCartMessage("Đã thêm vào giỏ hàng thành công.");
    } catch (err) {
      setCartMessage(err instanceof Error ? err.message : "Không thêm được vào giỏ hàng.");
    } finally {
      setAdding(false);
    }
  }

  async function handleDesignWithProduct() {
    if (!product) return;

    // Check authentication
    if (!getAccessToken()) {
      setPreselectedProduct({
        id: product.id,
        name: product.name,
        image_url: selectedImage,
      });
      const returnUrl = `/products/${product.id}?open_studio=1`;
      window.location.href = `/login?redirect=${encodeURIComponent(returnUrl)}&pending_action=design_with_product&product_id=${product.id}`;
      return;
    }

    setProjectsLoading(true);
    setStudioError("");
    try {
      const data = await apiFetch<Paginated<RoomProject>>("/api/room-projects?page=1&page_size=20");
      setUserProjects(data.items || []);

      if (!data.items || data.items.length === 0) {
        // Customer has no room project yet - navigate directly to create one with preselected product
        setPreselectedProduct({
          id: product.id,
          name: product.name,
          image_url: selectedImage,
        });
        router.push(`/room-projects/new?preselect_product_id=${product.id}`);
      } else {
        // Customer has existing projects - display choice modal
        setStudioModalOpen(true);
      }
    } catch (err) {
      setStudioError(err instanceof Error ? err.message : "Không tải được danh sách dự án.");
    } finally {
      setProjectsLoading(false);
    }
  }

  function handleSelectProject(project: RoomProject) {
    if (!product) return;

    setPreselectedProduct({
      id: product.id,
      name: product.name,
      image_url: selectedImage,
    });

    setStudioModalOpen(false);

    // If project already has preferences, go straight to recommendations
    if (project.preference_configured) {
      router.push(`/room-projects/${project.id}/recommendations?preselect_product_id=${product.id}`);
    } else {
      router.push(`/room-projects/${project.id}?preselect_product_id=${product.id}`);
    }
  }

  function handleCreateNewProjectWithProduct() {
    if (!product) return;
    setPreselectedProduct({
      id: product.id,
      name: product.name,
      image_url: selectedImage,
    });
    setStudioModalOpen(false);
    router.push(`/room-projects/new?preselect_product_id=${product.id}`);
  }

  if (!product) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="font-serif text-lg text-[#242B23]">Đang tải chi tiết sản phẩm...</p>
        <p className="text-xs text-[#5A6258]">Vui lòng chờ trong giây lát.</p>
      </div>
    );
  }

  const inStock = product.stock_quantity > 0;

  return (
    <section className="grid gap-10 lg:grid-cols-12 w-full max-w-full">
      {/* LEFT: Image Gallery (7 cols) */}
      <div className="space-y-4 lg:col-span-7 w-full min-w-0">
        <div className="overflow-hidden rounded-3xl border border-[#242B23]/10 bg-white p-3 shadow-soft">
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-[#FBF9F5]">
            {selectedImage ? (
              <img
                src={apiAssetUrl(selectedImage)}
                alt={product.name}
                className="h-full w-full object-cover transition-transform duration-500 hover:scale-105"
              />
            ) : (
              <EmptyImagePlaceholder />
            )}
            <div className="absolute left-3.5 top-3.5">
              <span className="rounded-full bg-white/90 px-3.5 py-1 text-xs font-semibold text-[#8A6B4E] shadow-sm backdrop-blur-sm">
                {displayCategory(product.category.name)}
              </span>
            </div>
          </div>
        </div>

        {/* Thumbnail Selector */}
        {product.images.length > 1 && (
          <div className="grid grid-cols-4 sm:grid-cols-5 gap-3">
            {product.images.map((image) => (
              <button
                key={image.id}
                type="button"
                onClick={() => setSelectedImage(image.image_url)}
                className={`aspect-square overflow-hidden rounded-xl border bg-white p-1 transition ${
                  selectedImage === image.image_url
                    ? "border-[#8A6B4E] ring-2 ring-[#8A6B4E]/30 shadow-sm"
                    : "border-[#242B23]/10 hover:border-[#8A6B4E]/50"
                }`}
              >
                <img
                  src={apiAssetUrl(image.image_url)}
                  alt={image.alt_text || product.name}
                  className="h-full w-full rounded-lg object-cover"
                />
              </button>
            ))}
          </div>
        )}

        {/* Architectural Quality Notice */}
        <div className="rounded-2xl border border-[#242B23]/10 bg-[#FBF9F5] p-5 space-y-2 text-xs leading-relaxed text-[#5A6258]">
          <p className="font-semibold text-[#242B23]">Thông tin tham chiếu AI Studio</p>
          <p>
            Sản phẩm này có đầy đủ ảnh chuẩn catalog và tỷ lệ 3D, sẵn sàng để AI Room Decor đưa trực tiếp vào phương án phối cảnh phòng của bạn.
          </p>
        </div>
      </div>

      {/* RIGHT: Product Details & Actions (5 cols) */}
      <div className="space-y-6 lg:col-span-5 w-full min-w-0">
        <div className="rounded-3xl border border-[#242B23]/10 bg-white p-6 sm:p-8 shadow-card space-y-6">
          <div className="space-y-3 border-b border-[#242B23]/10 pb-6">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#8A6B4E]">
                {displayCategory(product.category.name)}
              </span>
              {inStock ? (
                <StatusBadge variant="verified">Còn {product.stock_quantity} sản phẩm</StatusBadge>
              ) : (
                <StatusBadge variant="rejected">Hết hàng</StatusBadge>
              )}
            </div>

            <h1 className="font-serif text-2xl sm:text-3xl font-normal text-[#242B23] leading-snug break-words">
              {product.name}
            </h1>

            <p className="font-serif text-2xl sm:text-3xl font-semibold text-[#242B23]">
              {Number(product.price).toLocaleString("vi-VN")} đ
            </p>
          </div>

          <p className="text-sm leading-relaxed text-[#5A6258]">
            {product.description}
          </p>

          {/* Action CTAs: Add to Cart + Design with Product */}
          <div className="space-y-3 pt-2">
            <div className="flex flex-col sm:flex-row gap-3">
              <LuxuryButton
                variant="primary"
                size="lg"
                onClick={handleAddToCart}
                loading={adding}
                disabled={!inStock || adding}
                className="w-full justify-center"
              >
                <ShoppingCart size={18} />
                <span>Thêm vào giỏ hàng</span>
              </LuxuryButton>

              <LuxuryButton
                variant="bronze"
                size="lg"
                onClick={handleDesignWithProduct}
                loading={projectsLoading}
                disabled={projectsLoading}
                className="w-full justify-center"
              >
                <Sparkles size={18} />
                <span>Thiết kế phòng với món này</span>
              </LuxuryButton>
            </div>
          </div>

          {/* Cart Feedback */}
          {cartMessage && (
            <p className="text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl p-3">
              {cartMessage}
            </p>
          )}

          {justAdded && (
            <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/90 p-3.5 text-xs text-emerald-900">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-700 shrink-0" />
                <span className="font-semibold">Đã lưu sản phẩm vào giỏ hàng của bạn.</span>
              </div>
              <Link href="/cart" className="font-bold underline text-emerald-800 hover:text-emerald-950 flex items-center gap-1">
                Xem giỏ <ChevronRight size={14} />
              </Link>
            </div>
          )}

          {cartRetry && (
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50/90 p-3.5 text-xs text-amber-900">
              <span>Chưa thể tự động lưu vào giỏ do gián đoạn kết nối. Vui lòng bấm thử lại để tiếp tục.</span>
              <button
                type="button"
                onClick={handleAddToCart}
                disabled={adding}
                className="font-bold underline text-amber-950 hover:text-amber-800 shrink-0"
              >
                {adding ? "Đang thêm..." : "Thử thêm lại ngay"}
              </button>
            </div>
          )}

          {studioError && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
              {studioError}
            </div>
          )}
        </div>

        {/* Specifications Card */}
        <div className="rounded-3xl border border-[#242B23]/10 bg-white p-6 sm:p-8 shadow-sm space-y-5">
          <h3 className="font-serif text-lg font-normal text-[#242B23]">Thông số kỹ thuật</h3>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <InfoItem label="Phong cách" value={joinDisplay(product.styles, (item) => displayStyle(item.name))} />
            <InfoItem label="Màu sắc" value={joinDisplay(product.colors, (item) => displayColor(item.name))} />
            <InfoItem label="Vật liệu" value={joinDisplay(product.materials, (item) => displayMaterial(item.name))} />
            <InfoItem label="Loại phòng" value={joinDisplay(product.room_types, (item) => displayRoomType(item.name))} />
            <InfoItem
              label="Kích thước (R x C x S)"
              value={[product.width, product.height, product.depth].filter(Boolean).join(" x ") || "Theo tiêu chuẩn catalog"}
              icon={<Ruler size={14} />}
            />
            <InfoItem
              label="Khối lượng"
              value={product.weight ? `${product.weight} kg` : "Tiêu chuẩn"}
              icon={<Package size={14} />}
            />
          </dl>
        </div>
      </div>

      {/* AI Studio Project Selector Modal (AUD-P1-002) */}
      {studioModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-lg rounded-3xl border border-[#242B23]/10 bg-white p-6 sm:p-8 shadow-2xl space-y-6">
            <button
              onClick={() => setStudioModalOpen(false)}
              className="absolute right-5 top-5 rounded-full p-2 text-[#5A6258] hover:bg-[#FBF9F5] hover:text-[#242B23] transition"
              aria-label="Đóng hộp thoại"
            >
              <X size={20} />
            </button>

            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#242B23] text-white">
                <Sparkles size={20} />
              </div>
              <div>
                <h3 className="font-serif text-xl text-[#242B23]">Phối cảnh cùng AI Studio</h3>
                <p className="text-xs text-[#5A6258]">Chọn không gian phòng của bạn để đưa món đồ này vào bản thiết kế.</p>
              </div>
            </div>

            {/* Selected Product Summary Pill */}
            <div className="flex items-center gap-3 rounded-2xl border border-[#8A6B4E]/30 bg-[#FBF9F5] p-3">
              <div className="h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-white border border-[#242B23]/10">
                {selectedImage ? (
                  <img src={apiAssetUrl(selectedImage)} alt={product.name} className="h-full w-full object-cover" />
                ) : (
                  <EmptyImagePlaceholder />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#8A6B4E]">
                  {displayCategory(product.category.name)}
                </p>
                <p className="text-sm font-semibold text-[#242B23] truncate">{product.name}</p>
                <p className="text-xs text-[#5A6258]">{Number(product.price).toLocaleString("vi-VN")} đ</p>
              </div>
            </div>

            {/* Existing Projects List */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#5A6258]">
                Dự án phòng hiện có ({userProjects.length})
              </p>
              <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
                {userProjects.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => handleSelectProject(p)}
                    className="w-full flex items-center justify-between rounded-xl border border-[#242B23]/10 bg-white p-3 text-left transition hover:border-[#8A6B4E] hover:bg-[#FBF9F5] group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {p.room_image_url ? (
                        <img
                          src={apiAssetUrl(p.room_image_url)}
                          alt={p.title}
                          className="h-11 w-11 rounded-lg object-cover shrink-0 border border-[#242B23]/10"
                        />
                      ) : (
                        <div className="h-11 w-11 rounded-lg bg-[#FBF9F5] flex items-center justify-center shrink-0 border border-[#242B23]/10 text-xs text-[#5A6258]">
                          Phòng
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[#242B23] truncate group-hover:text-[#8A6B4E] transition">
                          {p.title}
                        </p>
                        <p className="text-xs text-[#5A6258]">{p.room_type || "Chưa phân loại"}</p>
                      </div>
                    </div>
                    <span className="text-xs font-semibold text-[#8A6B4E] shrink-0 pl-2">Chọn phòng</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Create New Project Option */}
            <div className="border-t border-[#242B23]/10 pt-4">
              <LuxuryButton
                variant="secondary"
                size="md"
                onClick={handleCreateNewProjectWithProduct}
                className="w-full justify-center"
              >
                <Plus size={16} />
                <span>Tạo dự án phòng mới với món này</span>
              </LuxuryButton>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function InfoItem({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-[#5A6258] flex items-center gap-1.5">
        {icon}
        {label}
      </dt>
      <dd className="text-xs font-semibold text-[#242B23]">{value || "-"}</dd>
    </div>
  );
}

export default function ProductDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="py-16 text-center space-y-3">
          <p className="font-serif text-lg text-[#242B23]">Đang tải chi tiết sản phẩm...</p>
          <p className="text-xs text-[#5A6258]">Vui lòng chờ trong giây lát.</p>
        </div>
      }
    >
      <ProductDetailContent />
    </Suspense>
  );
}
