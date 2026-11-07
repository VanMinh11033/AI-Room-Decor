"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderPlus } from "lucide-react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { RoomProject } from "@/types/api";

export default function NewRoomProjectPage() {
  const router = useRouter();
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [title, setTitle] = useState("");
  const [roomType, setRoomType] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const project = await apiFetch<RoomProject>("/api/room-projects", {
        method: "POST",
        body: JSON.stringify({ title, room_type: roomType || null }),
      });
      router.push(`/room-projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được dự án phòng");
    } finally {
      setSaving(false);
    }
  }

  if (authLoading) return <p className="font-semibold text-charcoal/60">Đang kiểm tra tài khoản...</p>;

  return (
    <section className="mx-auto max-w-3xl space-y-7">
      <PageHeader
        eyebrow="Dự án mới"
        title="Tạo dự án phòng"
        description="Đặt tên dự án để bắt đầu upload ảnh phòng, phân tích AI và cá nhân hóa decor."
      />
      <SectionCard>
        <form onSubmit={onSubmit} className="space-y-5">
          <label className="block text-sm font-bold text-ink">
            Tên dự án
            <input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} maxLength={255} className="premium-input mt-2 w-full" placeholder="Ví dụ: Phòng khách căn hộ mới" />
          </label>
          <label className="block text-sm font-bold text-ink">
            Loại phòng
            <input value={roomType} onChange={(event) => setRoomType(event.target.value)} maxLength={100} className="premium-input mt-2 w-full" placeholder="Phòng ngủ, phòng khách, góc làm việc..." />
          </label>
          {error && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-bold text-red-700">{error}</p>}
          <button disabled={saving} className="primary-cta">
            <FolderPlus size={18} /> {saving ? "Đang tạo..." : "Tạo dự án"}
          </button>
        </form>
      </SectionCard>
    </section>
  );
}
