"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2, Mail, ShoppingCart, Sparkles } from "lucide-react";
import { apiFetch, setTokens } from "@/lib/api";
import { addToCart, clearPendingCartIntent, getPendingCartIntent } from "@/lib/cart";
import { isValidInternalRedirect } from "@/lib/security";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";

function LoginForm() {
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");
  const [pendingCartNotice, setPendingCartNotice] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const pendingAction = searchParams.get("pending_action");
  const productIdParam = searchParams.get("product_id");

  useEffect(() => {
    const intent = getPendingCartIntent();
    if (pendingAction === "add_cart" || intent !== null) {
      setPendingCartNotice(true);
    }
  }, [pendingAction]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return; // Prevent double submit

    setLoading(true);
    setError("");
    setStatusText("Đang xác thực thông tin...");
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

      // Handle pending unauthenticated actions (AUD-P1-001)
      const intent = getPendingCartIntent();
      const isCartAction = pendingAction === "add_cart" || Boolean(intent);
      const targetProductId = Number(productIdParam || intent?.product_id);
      const targetQuantity = Number(searchParams.get("quantity") || intent?.quantity || 1);

      let addSucceeded = false;
      if (isCartAction && targetProductId > 0) {
        setStatusText("Đang đồng bộ sản phẩm vào giỏ hàng...");
        try {
          await addToCart(targetProductId, targetQuantity);
          addSucceeded = true;
          // Atomically clear intent ONLY after successful addition (Phase 0 Hardening)
          clearPendingCartIntent();
        } catch (addErr) {
          // Preserve intent in storage for retry if network or stock failed
          console.warn("Auto add-to-cart failed post-login; preserving intent for retry:", addErr);
        }
      } else {
        clearPendingCartIntent();
      }

      // Compute safe return destination (reject open redirects)
      const rawRedirect = searchParams.get("redirect") || searchParams.get("returnUrl");
      let destination: string;

      if (rawRedirect && isValidInternalRedirect(rawRedirect)) {
        destination = rawRedirect;
        // Append context query param if returning to product page
        if (isCartAction && destination.startsWith("/products/")) {
          destination += destination.includes("?")
            ? addSucceeded
              ? "&added=1"
              : "&cart_retry=1"
            : addSucceeded
            ? "?added=1"
            : "?cart_retry=1";
        }
      } else if (pendingAction === "design_with_product" && targetProductId > 0) {
        destination = `/products/${targetProductId}?open_studio=1`;
      } else if (result.user?.role?.name === "ADMIN") {
        destination = "/admin";
      } else if (isCartAction) {
        destination = "/cart?added=1";
      } else {
        destination = "/room-projects";
      }

      window.location.href = destination;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại. Vui lòng thử lại.");
      setLoading(false);
      setStatusText("");
    }
  }

  // Preserve query string when navigating to register
  const registerQuery = searchParams.toString() ? `?${searchParams.toString()}` : "";

  return (
    <div className="rounded-3xl border border-[#DDD7CD] bg-white p-7 sm:p-9 shadow-card">
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#242B23] text-white shadow-card">
        <Sparkles size={24} className="text-[#DDD7CD]" />
      </div>

      <EditorialHeading
        eyebrow="Tài khoản cá nhân"
        title="Đăng nhập"
        subtitle="Tiếp tục hành trình thiết kế không gian và quản lý đơn hàng của bạn."
        size="sm"
      />

      {pendingCartNotice && (
        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-[#8A6B4E]/30 bg-[#FBF9F5] p-4 text-xs text-[#242B23]">
          <ShoppingCart size={18} className="shrink-0 text-[#8A6B4E] mt-0.5" />
          <span className="leading-relaxed">
            Sản phẩm decor bạn vừa chọn sẽ được <strong className="font-bold text-[#8A6B4E]">tự động thêm vào giỏ hàng</strong> ngay sau khi đăng nhập thành công.
          </span>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="mt-5 rounded-2xl border border-red-200 bg-red-50/90 p-4 text-xs font-semibold text-red-800"
        >
          {error}
        </div>
      )}

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="login-email" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
            Địa chỉ Email
          </label>
          <div className="relative">
            <input
              id="login-email"
              name="email"
              type="email"
              placeholder="ten@vidu.com"
              required
              disabled={loading}
              className="premium-input w-full pr-10 disabled:opacity-50"
            />
            <Mail size={16} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[#5A6258]" />
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="login-password" className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
            Mật khẩu
          </label>
          <div className="relative">
            <input
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              required
              disabled={loading}
              className="premium-input w-full pr-10 disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5A6258] hover:text-[#242B23]"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        <div className="pt-2">
          <LuxuryButton
            type="submit"
            variant="primary"
            size="md"
            loading={loading}
            className="w-full text-sm font-bold"
          >
            {loading ? statusText || "Đang đăng nhập..." : "Đăng nhập"}
          </LuxuryButton>
        </div>
      </form>

      <div className="mt-6 border-t border-[#DDD7CD]/60 pt-5 text-center text-xs text-[#5A6258]">
        Chưa có tài khoản?{" "}
        <Link className="font-bold text-[#8A6B4E] hover:underline" href={`/register${registerQuery}`}>
          Đăng ký tài khoản mới
        </Link>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <section className="mx-auto max-w-md py-8">
      <Suspense
        fallback={
          <div className="flex justify-center p-8">
            <Loader2 size={24} className="animate-spin text-[#8A6B4E]" />
          </div>
        }
      >
        <LoginForm />
      </Suspense>
    </section>
  );
}
