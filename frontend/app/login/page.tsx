"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { apiFetch, setTokens } from "@/lib/api";
import { SectionCard } from "@/components/customer/DesignPrimitives";

function LoginForm() {
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return; // Prevent double submit

    setLoading(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");

    try {
      const result = await apiFetch<{
        access_token: string;
        refresh_token: string;
        user: { role?: { name: string } };
      }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setTokens(result.access_token, result.refresh_token);

      const redirect = searchParams.get("redirect") || searchParams.get("returnUrl");
      if (redirect && redirect.startsWith("/") && !redirect.startsWith("//")) {
        window.location.href = redirect;
      } else {
        window.location.href = result.user?.role?.name === "ADMIN" ? "/admin" : "/room-projects";
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại. Vui lòng thử lại.");
      setLoading(false);
    }
  }

  return (
    <SectionCard>
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-ink text-white shadow-card">
        <Sparkles size={24} />
      </div>
      <h1 className="text-3xl font-black text-ink">Đăng nhập</h1>
      <p className="mt-2 text-sm leading-6 text-charcoal/60">Tiếp tục dự án decor phòng cá nhân của bạn.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <input
          name="email"
          type="email"
          placeholder="Email"
          required
          disabled={loading}
          className="premium-input w-full disabled:opacity-50"
        />
        <input
          name="password"
          type="password"
          placeholder="Mật khẩu"
          required
          disabled={loading}
          className="premium-input w-full disabled:opacity-50"
        />
        {error && (
          <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-bold text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="primary-cta w-full flex items-center justify-center gap-2 disabled:opacity-60"
        >
          {loading ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              <span>Đang đăng nhập...</span>
            </>
          ) : (
            <span>Đăng nhập</span>
          )}
        </button>
      </form>
      <p className="mt-5 text-sm text-charcoal/60">
        Chưa có tài khoản?{" "}
        <Link className="font-bold text-clay hover:underline" href="/register">
          Đăng ký
        </Link>
      </p>
    </SectionCard>
  );
}

export default function LoginPage() {
  return (
    <section className="mx-auto max-w-md">
      <Suspense fallback={<p className="font-semibold text-charcoal/60">Đang tải...</p>}>
        <LoginForm />
      </Suspense>
    </section>
  );
}
