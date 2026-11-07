"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { apiFetch, setTokens } from "@/lib/api";
import { SectionCard } from "@/components/customer/DesignPrimitives";

export default function RegisterPage() {
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      const result = await apiFetch<{ access_token: string; refresh_token: string }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
          full_name: form.get("full_name"),
        }),
      });
      setTokens(result.access_token, result.refresh_token);
      window.location.href = "/room-projects";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại");
    }
  }

  return (
    <section className="mx-auto max-w-md">
      <SectionCard>
        <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-clay text-white shadow-card">
          <Sparkles size={24} />
        </div>
        <h1 className="text-3xl font-black text-ink">Tạo tài khoản</h1>
        <p className="mt-2 text-sm leading-6 text-charcoal/60">Lưu dự án phòng, sở thích decor và các phương án thiết kế AI.</p>
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <input name="full_name" placeholder="Họ tên" required className="premium-input w-full" />
          <input name="email" type="email" placeholder="Email" required className="premium-input w-full" />
          <input name="password" type="password" placeholder="Mật khẩu tối thiểu 8 ký tự" minLength={8} required className="premium-input w-full" />
          {error && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-bold text-red-700">{error}</p>}
          <button type="submit" className="primary-cta w-full">Tạo tài khoản</button>
        </form>
        <p className="mt-5 text-sm text-charcoal/60">
          Đã có tài khoản? <Link className="font-bold text-clay" href="/login">Đăng nhập</Link>
        </p>
      </SectionCard>
    </section>
  );
}
