"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayCategory, displayColor, displayMaterial, displayRoomType, displayStatus, displayStyle, joinDisplay } from "@/lib/display";
import type { AdminRoomProjectDetail } from "@/types/api";

export default function AdminRoomProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { loading } = useAuth("ADMIN");
  const [detail, setDetail] = useState<AdminRoomProjectDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading) {
      apiFetch<AdminRoomProjectDetail>(`/api/admin/room-projects/${params.id}`)
        .then(setDetail)
        .catch((err) => setError(err instanceof Error ? err.message : "Không tải được chi tiết dự án."));
    }
  }, [loading, params.id]);

  if (loading) return <p>Đang kiểm tra quyền...</p>;
  if (error && !detail) return <p className="text-red-600">{error}</p>;
  if (!detail) return <p className="text-black/50">Đang tải...</p>;

  const { project, customer, latest_analysis: analysis, preference } = detail;

  return (
    <section className="space-y-6">
      <Link href="/admin/room-projects" className="inline-flex items-center gap-2 text-sm font-semibold text-black/60 hover:text-ink">
        <ChevronLeft size={16} /> Dự án phòng
      </Link>

      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold text-ink">#{project.id} · {project.title}</h1>
          <p className="mt-2 text-sm text-black/60">{customer?.full_name || "Khách hàng"} · {customer?.email || `#${project.user_id}`}</p>
        </div>
        <span className="rounded-full bg-stone px-4 py-2 text-sm font-bold text-ink">{displayStatus(project.status)}</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
          <h2 className="font-bold text-ink">Ảnh phòng gốc</h2>
          <div className="mt-4 overflow-hidden rounded-lg border border-black/10 bg-stone">
            {project.room_image_url ? (
              <img src={apiAssetUrl(project.room_image_url)} alt={project.title} className="h-80 w-full object-cover" />
            ) : (
              <div className="flex h-80 items-center justify-center text-sm text-black/50">Chưa có ảnh phòng.</div>
            )}
          </div>
          <div className="mt-4 grid gap-2 text-sm">
            <Info label="Loại phòng" value={displayRoomType(project.room_type) || "-"} />
            <Info label="File" value={project.image_original_filename || "-"} />
            <Info label="Ngày tạo" value={new Date(project.created_at).toLocaleString("vi-VN")} />
          </div>
        </section>

        <section className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
          <h2 className="font-bold text-ink">Phân tích AI mới nhất</h2>
          {analysis ? (
            <div className="mt-4 space-y-3 text-sm">
              <Info label="Trạng thái" value={displayStatus(analysis.status)} />
              <Info label="Provider" value={`${analysis.provider} · ${analysis.model}`} />
              <Info label="Loại phòng nhận diện" value={displayRoomType(analysis.room_type) || "-"} />
              <Info label="Màu chủ đạo" value={analysis.dominant_colors.map((color) => displayColor(color.name)).join(", ") || "-"} />
              <Info label="Đặc điểm thiết kế" value={analysis.design_characteristics.join(", ") || "-"} />
              <Info label="Tóm tắt layout" value={analysis.layout_summary || "-"} />
              {analysis.error_code && <Info label="Lỗi" value={analysis.error_code} />}
            </div>
          ) : (
            <p className="mt-4 text-sm text-black/50">Chưa có phân tích phòng.</p>
          )}
        </section>
      </div>

      <section className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
        <h2 className="font-bold text-ink">Sở thích decor</h2>
        {preference ? (
          <div className="mt-4 grid gap-3 text-sm md:grid-cols-2 lg:grid-cols-4">
            <Info label="Ngân sách" value={`${money(preference.budget_min || "0")} - ${money(preference.budget_max || "0")}`} />
            <Info label="Phong cách" value={joinDisplay(preference.styles, (item) => displayStyle(item.name))} />
            <Info label="Màu sắc" value={joinDisplay(preference.colors, (item) => displayColor(item.name))} />
            <Info label="Vật liệu" value={joinDisplay(preference.materials, (item) => displayMaterial(item.name))} />
            <Info label="Danh mục mong muốn" value={joinDisplay(preference.categories, (item) => displayCategory(item.name))} />
            <Info label="Mục đích" value={preference.purpose || "-"} />
          </div>
        ) : (
          <p className="mt-4 text-sm text-black/50">Chưa cấu hình sở thích.</p>
        )}
      </section>

      <section className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
        <h2 className="font-bold text-ink">Lịch sử thiết kế AI</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {detail.design_generations.map((generation) => (
            <article key={generation.id} className="rounded-lg border border-black/10 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-ink">Thiết kế #{generation.id}</p>
                  <p className="mt-1 text-sm text-black/60">{generation.provider} · {generation.model}</p>
                </div>
                <span className="rounded-full bg-stone px-3 py-1 text-xs font-bold text-ink">{displayStatus(generation.status)}</span>
              </div>
              {generation.generated_image_url && (
                <img src={apiAssetUrl(generation.generated_image_url)} alt={`Thiết kế ${generation.id}`} className="mt-3 h-48 w-full rounded-md object-cover" />
              )}
              <p className="mt-3 text-sm text-black/60">Sản phẩm: {generation.products.map((product) => product.name).join(", ") || "-"}</p>
              {generation.error_code && <p className="mt-2 text-sm font-semibold text-red-700">{generation.error_code}</p>}
            </article>
          ))}
          {detail.design_generations.length === 0 && <p className="text-sm text-black/50">Chưa có thiết kế AI.</p>}
        </div>
      </section>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-black/45">{label}</p>
      <p className="font-semibold text-ink">{value}</p>
    </div>
  );
}

function money(value: string | number) {
  return `${Number(value || 0).toLocaleString("vi-VN")} đ`;
}
