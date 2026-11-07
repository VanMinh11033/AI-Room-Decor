"use client";

import { FormEvent, useEffect, useState } from "react";
import { UserRound } from "lucide-react";
import { PageHeader, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { UserProfile } from "@/types/api";

export default function ProfilePage() {
  const { user, loading } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    apiFetch<UserProfile>("/api/users/me/profile").then(setProfile).catch(() => null);
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const updated = await apiFetch<UserProfile>("/api/users/me/profile", {
      method: "PUT",
      body: JSON.stringify({
        phone: form.get("phone") || null,
        address: form.get("address") || null,
        preferred_style: form.get("preferred_style") || null,
        preferred_colors: form.get("preferred_colors") || null,
        preferred_materials: form.get("preferred_materials") || null,
      }),
    });
    setProfile(updated);
    setMessage("Đã lưu hồ sơ");
  }

  if (loading || !user) return <p className="font-semibold text-charcoal/60">Đang tải...</p>;

  return (
    <section className="space-y-7">
      <PageHeader eyebrow="Hồ sơ khách hàng" title="Gu decor của bạn" description="Lưu thông tin liên hệ và sở thích tổng quát để trải nghiệm cá nhân hóa nhất quán hơn." />
      <div className="grid gap-6 md:grid-cols-[0.8fr_1.2fr]">
        <SectionCard>
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-ink text-white shadow-card">
            <UserRound size={28} />
          </div>
          <h1 className="mt-5 text-2xl font-black text-ink">{user.full_name}</h1>
          <p className="mt-2 text-charcoal/60">{user.email}</p>
          <p className="mt-3 inline-flex rounded-full bg-ivory px-3 py-1 text-xs font-black text-clay">{user.role.name}</p>
        </SectionCard>

        <SectionCard title="Hồ sơ decor">
          <form onSubmit={onSubmit} className="grid gap-4">
            <input name="phone" placeholder="Số điện thoại" defaultValue={profile?.phone || ""} className="premium-input" />
            <input name="address" placeholder="Địa chỉ" defaultValue={profile?.address || ""} className="premium-input" />
            <input name="preferred_style" placeholder="Phong cách yêu thích" defaultValue={profile?.preferred_style || ""} className="premium-input" />
            <input name="preferred_colors" placeholder="Màu sắc yêu thích" defaultValue={profile?.preferred_colors || ""} className="premium-input" />
            <input name="preferred_materials" placeholder="Vật liệu yêu thích" defaultValue={profile?.preferred_materials || ""} className="premium-input" />
            {message && <p className="text-sm font-bold text-green-700">{message}</p>}
            <button className="primary-cta justify-self-start" type="submit">Lưu hồ sơ</button>
          </form>
        </SectionCard>
      </div>
    </section>
  );
}
