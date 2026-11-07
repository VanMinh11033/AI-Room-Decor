"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { apiFetch, setTokens } from "@/lib/api";
import { SectionCard } from "@/components/customer/DesignPrimitives";

export default function LoginPage() {
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      const result = await apiFetch<{ access_token: string; refresh_token: string; user: { role: { name: string } } }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      setTokens(result.access_token, result.refresh_token);
      window.location.href = result.user.role.name === "ADMIN" ? "/admin" : "/room-projects";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    }
  }

  return (
    <section className="mx-auto max-w-md">
      <SectionCard>
        <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-ink text-white shadow-card">
          <Sparkles size={24} />
        </div>
        <h1 className="text-3xl font-black text-ink">Đăng nhập</h1>
        <p className="mt-2 text-sm leading-6 text-charcoal/60">Tiếp tục dự án decor phòng cá nhân của bạn.</p>
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <input name="email" type="email" placeholder="Email" required className="premium-input w-full" />
          <input name="password" type="password" placeholder="Mật khẩu" required className="premium-input w-full" />
          {error && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-bold text-red-700">{error}</p>}
          <button type="submit" className="primary-cta w-full">Đăng nhập</button>
        </form>
        <p className="mt-5 text-sm text-charcoal/60">
          Chưa có tài khoản? <Link className="font-bold text-clay" href="/register">Đăng ký</Link>
        </p>
      </SectionCard>
    </section>
  );
}
