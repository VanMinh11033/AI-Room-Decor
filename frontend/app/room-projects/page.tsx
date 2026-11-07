"use client";

import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyImagePlaceholder, PageHeader } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Paginated, RoomProject } from "@/types/api";

export default function RoomProjectsPage() {
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [projects, setProjects] = useState<RoomProject[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(nextPage = 1) {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<Paginated<RoomProject>>(`/api/room-projects?page=${nextPage}&page_size=12`);
      setProjects(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dự án phòng");
    } finally {
      setLoading(false);
    }
  }

  async function archiveProject(projectId: number) {
    if (!window.confirm("Bạn muốn lưu trữ dự án này?")) return;
    await apiFetch(`/api/room-projects/${projectId}`, { method: "DELETE" });
    load(page);
  }

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading]);

  if (authLoading) return <p className="font-semibold text-charcoal/60">Đang kiểm tra tài khoản...</p>;

  return (
    <section className="space-y-7">
      <PageHeader
        eyebrow="Studio cá nhân"
        title="Dự án của tôi"
        description="Quản lý ảnh phòng, phân tích AI, sở thích decor và các phương án thiết kế đã tạo."
        action={<Link href="/room-projects/new" className="primary-cta"><Plus size={18} /> Tạo dự án</Link>}
      />

      {loading && <p className="font-semibold text-charcoal/60">Đang tải...</p>}
      {error && <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</p>}

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <article key={project.id} className="overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-card transition hover:-translate-y-1 hover:shadow-soft">
            <Link href={`/room-projects/${project.id}`}>
              <div className="aspect-[4/3] bg-ivory">
                {project.room_image_url ? (
                  <img src={apiAssetUrl(project.room_image_url)} alt={project.title} className="h-full w-full object-cover" />
                ) : (
                  <EmptyImagePlaceholder label="Chưa có ảnh phòng" />
                )}
              </div>
              <div className="p-5">
                <h2 className="text-lg font-black text-ink">{project.title}</h2>
                <p className="mt-1 text-sm text-charcoal/60">{project.room_type || "Chưa chọn loại phòng"}</p>
                <div className="mt-4 grid gap-2 text-xs font-bold text-charcoal/65">
                  <span>Phân tích: {project.status === "COMPLETED" ? "Hoàn tất" : "Chưa hoàn tất"}</span>
                  <span>Sở thích: {project.preference_configured ? "Đã thiết lập" : "Chưa thiết lập"}</span>
                  <span>Ngày tạo: {new Date(project.created_at).toLocaleDateString("vi-VN")}</span>
                </div>
                <span className="mt-4 inline-flex rounded-xl bg-ink px-4 py-2 text-sm font-bold text-white">Tiếp tục thiết kế</span>
              </div>
            </Link>
            <button onClick={() => archiveProject(project.id)} className="mx-5 mb-5 inline-flex items-center gap-2 text-sm font-bold text-red-600">
              <Trash2 size={16} /> Lưu trữ
            </button>
          </article>
        ))}
      </div>

      {!loading && projects.length === 0 && !error && <div className="surface-card p-6 text-charcoal/60">Bạn chưa có dự án phòng nào.</div>}

      <div className="flex items-center justify-between rounded-2xl bg-white/80 p-3 text-sm font-bold text-charcoal/65 shadow-sm">
        <span>Tổng {total} dự án</span>
        <div className="flex gap-2">
          <button disabled={page <= 1} onClick={() => load(page - 1)} className="secondary-cta px-4 py-2 disabled:opacity-40">Trước</button>
          <button disabled={page * 12 >= total} onClick={() => load(page + 1)} className="secondary-cta px-4 py-2 disabled:opacity-40">Sau</button>
        </div>
      </div>
    </section>
  );
}
