"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Boxes,
  BrainCircuit,
  DoorOpen,
  Eye,
  Lightbulb,
  Maximize2,
  Palette,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import {
  displayColor,
  displayMaterial,
  displayRoomType,
  displayStyle,
  joinDisplay,
} from "@/lib/display";
import type { AdminRoomProjectDetail } from "@/types/api";
import {
  AdminBadge,
  AdminPageHeader,
  AdminStatusBadge,
  AdminSurfaceCard,
} from "@/components/admin/AdminPrimitives";

export default function AdminRoomProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { loading: authLoading } = useAuth("ADMIN");
  const [detail, setDetail] = useState<AdminRoomProjectDetail | null>(null);
  const [error, setError] = useState("");
  const [selectedPreviewImage, setSelectedPreviewImage] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading) {
      apiFetch<AdminRoomProjectDetail>(`/api/admin/room-projects/${params.id}`)
        .then(setDetail)
        .catch((err) => setError(err instanceof Error ? err.message : "Không tải được chi tiết dự án."));
    }
  }, [authLoading, params.id]);

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm font-semibold text-red-700 shadow-sm">
        {error}
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang tải thông tin dự án không gian #{params.id}...
      </div>
    );
  }

  const { project, customer, latest_analysis: analysis, preference, design_generations } = detail;

  const isLocalVisionFallback =
    analysis?.provider?.toLowerCase().includes("local") ||
    analysis?.model?.toLowerCase().includes("fallback");

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Chi tiết không gian AI Studio"
        title={`Dự án #${project.id} · ${project.title}`}
        subtitle={`Khách hàng: ${customer?.full_name || "Khách hàng"} · Loại phòng: ${
          displayRoomType(project.room_type) || "Chưa xác định"
        }`}
        backHref="/admin/room-projects"
        backLabel="Quay lại danh sách dự án"
        badge={<AdminStatusBadge status={project.status} />}
        actions={
          <div className="flex items-center gap-2">
            <span className="rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] px-3.5 py-2 text-xs font-semibold text-[#242424]">
              {design_generations.length} phương án decor
            </span>
          </div>
        }
      />

      {/* 2. Top Split: Original Room Photo & AI Vision Analysis */}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Zone 1: Original Room Photo (Full Aspect Ratio Preservation) */}
        <AdminSurfaceCard
          title="Ảnh phòng gốc của khách hàng"
          subtitle={project.image_original_filename || "Tệp hình ảnh phòng tải lên"}
          action={
            project.room_image_url && (
              <button
                type="button"
                onClick={() => setSelectedPreviewImage(apiAssetUrl(project.room_image_url!))}
                className="inline-flex items-center gap-1 text-xs font-semibold text-[#A68B6D] hover:text-[#2D332C]"
              >
                <Maximize2 size={13} /> Phóng to
              </button>
            )
          }
        >
          <div className="relative overflow-hidden rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]">
            {project.room_image_url ? (
              <div className="flex max-h-[480px] w-full items-center justify-center p-2">
                <img
                  src={apiAssetUrl(project.room_image_url)}
                  alt={project.title}
                  className="max-h-[460px] w-auto max-w-full rounded-xl object-contain shadow-sm"
                />
              </div>
            ) : (
              <div className="flex h-80 items-center justify-center text-sm text-[#777777]">
                Chưa có ảnh phòng.
              </div>
            )}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
            <div className="rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-3">
              <span className="text-[#777777]">Loại phòng khai báo:</span>
              <p className="mt-1 font-bold text-[#242424]">
                {displayRoomType(project.room_type) || "Không chọn"}
              </p>
            </div>
            <div className="rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-3">
              <span className="text-[#777777]">Tài khoản sở hữu:</span>
              <p className="mt-1 font-bold text-[#242424] truncate">
                {customer?.full_name || `User #${project.user_id}`}
              </p>
            </div>
            <div className="col-span-2 rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-3 sm:col-span-1">
              <span className="text-[#777777]">Thời gian tải lên:</span>
              <p className="mt-1 font-bold text-[#242424]">
                {new Date(project.created_at).toLocaleDateString("vi-VN")}
              </p>
            </div>
          </div>
        </AdminSurfaceCard>

        {/* Zone 2: AI Vision Analysis Breakdown */}
        <AdminSurfaceCard
          title="Kết quả phân tích thị giác AI"
          subtitle="Nhận diện cấu trúc không gian, ánh sáng và màu sắc"
          action={
            analysis ? (
              <AdminStatusBadge status={analysis.status} size="sm" />
            ) : (
              <AdminBadge variant="stone" size="sm">Chưa có</AdminBadge>
            )
          }
        >
          {analysis ? (
            <div className="space-y-4">
              {/* Provider & Model Badge */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5] p-3.5">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                    Engine / Vision Provider
                  </p>
                  <p className="font-bold text-[#242424]">{analysis.provider} · {analysis.model}</p>
                </div>
                {isLocalVisionFallback ? (
                  <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-800">
                    Local CV Fallback
                  </span>
                ) : (
                  <span className="rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-800">
                    Cloudflare Vision Active
                  </span>
                )}
              </div>

              {/* Dominant Colors Strip */}
              {analysis.dominant_colors && analysis.dominant_colors.length > 0 && (
                <div className="rounded-2xl border border-[#2D332C]/10 bg-white p-3.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#777777]">
                    <Palette size={13} className="text-[#C9A77A]" />
                    <span>Màu sắc chủ đạo nhận diện</span>
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {analysis.dominant_colors.map((c, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[#2D332C]/10 bg-[#FAF8F5] px-3 py-1 text-xs font-semibold text-[#242424]"
                      >
                        {c.hex && (
                          <span
                            className="h-3 w-3 rounded-full border border-black/10"
                            style={{ backgroundColor: c.hex }}
                          />
                        )}
                        {displayColor(c.name)}
                        {c.percentage ? (
                          <span className="text-[10px] text-[#777777]">({c.percentage}%)</span>
                        ) : null}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Lighting & Architecture */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-3">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-[#777777]">
                    <Lightbulb size={13} className="text-[#A68B6D]" />
                    <span>Ánh sáng không gian</span>
                  </div>
                  <p className="mt-1 text-xs font-semibold text-[#242424]">
                    {analysis.lighting
                      ? `${analysis.lighting.type} (${analysis.lighting.level})`
                      : "Tự nhiên vừa phải"}
                  </p>
                </div>

                <div className="rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-3">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-[#777777]">
                    <DoorOpen size={13} className="text-[#A68B6D]" />
                    <span>Loại phòng nhận diện</span>
                  </div>
                  <p className="mt-1 text-xs font-semibold text-[#242424]">
                    {displayRoomType(analysis.room_type) || "Không xác định"}
                  </p>
                </div>
              </div>

              {/* Characteristics & Layout Summary */}
              {analysis.design_characteristics && analysis.design_characteristics.length > 0 && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-[#777777]">
                    Đặc điểm kiến trúc
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {analysis.design_characteristics.map((char, idx) => (
                      <span
                        key={idx}
                        className="rounded-lg bg-[#FAF8F5] px-2.5 py-1 text-xs text-[#242424]"
                      >
                        {char}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {analysis.layout_summary && (
                <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/40 p-3.5">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-[#777777]">
                    Tóm tắt bố cục & Khoảng trống
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[#242424]">
                    {analysis.layout_summary}
                  </p>
                </div>
              )}

              {analysis.error_code && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-bold text-red-700">
                  Mã lỗi AI Vision: {analysis.error_code}
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-64 flex-col items-center justify-center text-center text-xs text-[#777777]">
              <Eye size={24} className="mb-2 text-[#A68B6D]" />
              <p>Chưa có dữ liệu phân tích Vision cho phòng này.</p>
            </div>
          )}
        </AdminSurfaceCard>
      </div>

      {/* 3. Decor Preferences Zone */}
      <AdminSurfaceCard
        title="Sở thích & Yêu cầu decor của khách hàng"
        subtitle="Thông số cá nhân hóa khách hàng đã chọn để AI tư vấn và phối sản phẩm"
      >
        {preference ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#777777]">
                Ngân sách dự kiến
              </span>
              <p className="mt-1 text-base font-bold text-[#A68B6D]">
                {Number(preference.budget_min || 0).toLocaleString("vi-VN")} đ -{" "}
                {Number(preference.budget_max || 0).toLocaleString("vi-VN")} đ
              </p>
            </div>

            <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#777777]">
                Phong cách thiết kế
              </span>
              <p className="mt-1 text-sm font-semibold text-[#242424]">
                {joinDisplay(preference.styles, (item) => displayStyle(item.name)) || "Không chọn"}
              </p>
            </div>

            <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#777777]">
                Bảng màu ưa chuộng
              </span>
              <p className="mt-1 text-sm font-semibold text-[#242424]">
                {joinDisplay(preference.colors, (item) => displayColor(item.name)) || "Không chọn"}
              </p>
            </div>

            <div className="rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#777777]">
                Chất liệu mong muốn
              </span>
              <p className="mt-1 text-sm font-semibold text-[#242424]">
                {joinDisplay(preference.materials, (item) => displayMaterial(item.name)) || "Tùy chọn"}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-xs italic text-[#777777]">Khách hàng chưa hoàn thành bước chọn sở thích.</p>
        )}
      </AdminSurfaceCard>

      {/* 4. AI Design Generations History (Natural Ratio & Product Details) */}
      <AdminSurfaceCard
        title="Lịch sử các phương án thiết kế AI (Design Generations)"
        subtitle={`${design_generations.length} phiên bản phối cảnh do AI sinh ra`}
      >
        {design_generations.length === 0 ? (
          <div className="flex h-40 flex-col items-center justify-center text-center text-xs text-[#777777]">
            <BrainCircuit size={28} className="mb-2 text-[#A68B6D]" />
            <p>Khách hàng chưa tạo phương án thiết kế AI nào cho phòng này.</p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            {design_generations.map((gen) => {
              const hasImage = Boolean(gen.generated_image_url);
              const isVerified = gen.verification_status === "VERIFIED";

              return (
                <div
                  key={gen.id}
                  className="flex flex-col justify-between overflow-hidden rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/60 p-5 shadow-sm transition hover:shadow-card"
                >
                  <div className="space-y-4">
                    {/* Header info */}
                    <div className="flex items-start justify-between gap-3 border-b border-[#2D332C]/10 pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-bold text-[#242424]">Phương án decor #{gen.id}</h4>
                          {gen.generation_mode && (
                            <AdminBadge variant="gold" size="sm">
                              {gen.generation_mode}
                            </AdminBadge>
                          )}
                        </div>
                        <p className="mt-0.5 text-xs text-[#777777]">
                          Engine: {gen.provider} · {gen.model}
                        </p>
                      </div>

                      <div className="flex flex-col items-end gap-1">
                        <AdminStatusBadge status={gen.status} size="sm" />
                        {gen.verification_status && (
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                              isVerified
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {gen.verification_status}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Preserved Natural Image Ratio Frame */}
                    {hasImage ? (
                      <div className="relative overflow-hidden rounded-xl border border-[#2D332C]/10 bg-white">
                        <div className="flex max-h-[360px] w-full items-center justify-center p-2">
                          <img
                            src={apiAssetUrl(gen.generated_image_url!)}
                            alt={`Thiết kế #${gen.id}`}
                            className="max-h-[340px] w-auto max-w-full rounded-lg object-contain shadow-xs transition duration-300 hover:scale-[1.01]"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setSelectedPreviewImage(apiAssetUrl(gen.generated_image_url!))
                          }
                          className="absolute bottom-3 right-3 inline-flex items-center gap-1 rounded-lg bg-black/70 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm hover:bg-black"
                        >
                          <Maximize2 size={12} /> Xem lớn
                        </button>
                      </div>
                    ) : (
                      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-[#2D332C]/20 bg-white text-xs text-[#777777]">
                        Ảnh đang tạo hoặc không thành công
                      </div>
                    )}

                    {/* Products Used in this Design */}
                    {gen.products && gen.products.length > 0 && (
                      <div className="space-y-2 rounded-xl border border-[#2D332C]/10 bg-white p-3.5">
                        <div className="flex items-center justify-between text-xs font-bold text-[#242424]">
                          <span className="flex items-center gap-1 text-[#A68B6D]">
                            <Boxes size={14} />
                            Sản phẩm áp dụng ({gen.products.length}):
                          </span>
                          {gen.total_price && (
                            <span className="text-[#2D332C]">
                              {Number(gen.total_price).toLocaleString("vi-VN")} đ
                            </span>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          {gen.products.map((p) => (
                            <div
                              key={p.id}
                              className="flex items-center justify-between text-xs text-[#777777]"
                            >
                              <span className="truncate text-[#242424]">{p.name}</span>
                              <span className="shrink-0 font-medium">
                                {Number(p.price).toLocaleString("vi-VN")} đ
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Error / Warning Alert */}
                    {gen.error_code && (
                      <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                        <p className="font-bold">Mã lỗi: {gen.error_code}</p>
                        {gen.error_message && <p className="mt-0.5">{gen.error_message}</p>}
                      </div>
                    )}
                  </div>

                  {/* Footer Stats */}
                  <div className="mt-4 flex items-center justify-between border-t border-[#2D332C]/10 pt-3 text-[11px] text-[#777777]">
                    <span>
                      {gen.latency_ms ? `Độ trễ: ${(gen.latency_ms / 1000).toFixed(1)}s` : "Hoàn thành"}
                    </span>
                    <span>{new Date(gen.created_at).toLocaleString("vi-VN")}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </AdminSurfaceCard>

      {/* Lightbox Modal for Large Image Inspection */}
      {selectedPreviewImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
          onClick={() => setSelectedPreviewImage(null)}
        >
          <div
            className="relative max-h-[92vh] max-w-[92vw] overflow-hidden rounded-2xl bg-white p-2 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={selectedPreviewImage}
              alt="Phóng to ảnh"
              className="max-h-[88vh] w-auto max-w-full rounded-xl object-contain"
            />
            <button
              type="button"
              onClick={() => setSelectedPreviewImage(null)}
              className="absolute right-4 top-4 rounded-full bg-black/70 px-3 py-1 text-xs font-bold text-white hover:bg-black"
            >
              Đóng (ESC)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
