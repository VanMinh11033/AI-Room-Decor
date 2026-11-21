"use client";

import React from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { displayStatus } from "@/lib/display";

/**
 * 1. AdminPageHeader - Unified header for all admin views
 */
export function AdminPageHeader({
  eyebrow,
  title,
  subtitle,
  backHref,
  backLabel = "Quay lại",
  actions,
  badge,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  backHref?: string;
  backLabel?: string;
  actions?: React.ReactNode;
  badge?: React.ReactNode;
}) {
  return (
    <div className="motion-fade-up rounded-[1.75rem] border border-[#2D332C]/10 bg-white p-6 shadow-card md:p-8">
      {backHref && (
        <div className="mb-4">
          <Link
            href={backHref}
            className="group inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-[#777777] transition-colors hover:text-[#2D332C]"
          >
            <ChevronLeft
              size={14}
              className="transition-transform duration-200 group-hover:-translate-x-1 text-[#A68B6D]"
            />
            {backLabel}
          </Link>
        </div>
      )}
      <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div className="space-y-2">
          {eyebrow && (
            <div className="inline-flex items-center gap-2 rounded-full border border-[#C9A77A]/45 bg-[#FAF8F5] px-3.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[#2D332C]">
              <Sparkles size={12} className="text-[#C9A77A]" />
              {eyebrow}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-[#242424] md:text-3xl">
              {title}
            </h1>
            {badge}
          </div>
          {subtitle && (
            <p className="max-w-2xl text-sm leading-relaxed text-[#777777]">
              {subtitle}
            </p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
      </div>
    </div>
  );
}

/**
 * 2. AdminSurfaceCard - Premium luxury card container
 */
export function AdminSurfaceCard({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-6 shadow-card transition-all duration-300 ${className}`}
    >
      {(title || action) && (
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4 border-b border-[#2D332C]/5 pb-4">
          <div>
            {title && (
              <h2 className="text-lg font-bold tracking-tight text-[#242424] md:text-xl">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-[#777777]">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

/**
 * 3. AdminStatMiniCard - Metric KPI card
 */
export function AdminStatMiniCard({
  label,
  value,
  sub,
  icon: Icon,
  trend,
  badge,
  href,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon?: LucideIcon;
  trend?: string;
  badge?: React.ReactNode;
  href?: string;
}) {
  const CardContent = (
    <div className="admin-kpi-card group relative flex h-full flex-col justify-between">
      <div>
        <div className="flex items-start justify-between gap-3">
          {Icon ? (
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#C9A77A]/35 bg-[#FAF8F5] text-[#2D332C] transition-colors duration-200 group-hover:border-[#C9A77A] group-hover:bg-[#2D332C] group-hover:text-[#C9A77A]">
              <Icon size={18} />
            </span>
          ) : (
            <span />
          )}
          {badge}
          {trend && (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200">
              {trend}
            </span>
          )}
        </div>
        <p className="mt-3.5 text-xs font-semibold uppercase tracking-[0.12em] text-[#777777]">
          {label}
        </p>
        <p className="mt-1 text-2xl font-bold tracking-tight text-[#242424] lg:text-3xl">
          {value ?? "-"}
        </p>
      </div>
      {sub && <p className="mt-2 text-xs text-[#777777] border-t border-[#2D332C]/5 pt-2">{sub}</p>}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block transition hover:scale-[1.01]">
        {CardContent}
      </Link>
    );
  }

  return CardContent;
}

/**
 * 4. AdminStatusBadge - Consistent semantic color status indicator
 */
export function AdminStatusBadge({
  status,
  size = "md",
  customLabel,
}: {
  status: string;
  size?: "sm" | "md";
  customLabel?: string;
}) {
  const norm = String(status || "").toUpperCase();
  const label = customLabel || displayStatus(norm) || norm;

  let colorClasses = "bg-stone-100 text-stone-700 border-stone-200";

  if (["ACTIVE", "COMPLETED", "SUCCESS", "VERIFIED", "PAID", "CONFIRMED"].includes(norm)) {
    colorClasses = "bg-emerald-50 text-emerald-800 border-emerald-200/90 font-bold";
  } else if (["PENDING", "PROCESSING", "GENERATING", "NEEDS_REVIEW"].includes(norm)) {
    colorClasses = "bg-amber-50 text-amber-800 border-amber-200/90 font-bold";
  } else if (["SHIPPED"].includes(norm)) {
    colorClasses = "bg-blue-50 text-blue-800 border-blue-200/90 font-bold";
  } else if (["CANCELLED", "FAILED", "INACTIVE", "REJECTED"].includes(norm)) {
    colorClasses = "bg-rose-50 text-rose-800 border-rose-200/90 font-bold";
  } else if (["DRAFT", "COMPOSITE_FALLBACK"].includes(norm)) {
    colorClasses = "bg-stone-100 text-stone-700 border-stone-300 font-semibold";
  }

  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[10px] tracking-wider uppercase"
      : "px-3 py-1 text-xs font-semibold tracking-wide";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border shadow-xs ${colorClasses} ${sizeClasses}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          norm === "ACTIVE" || norm === "COMPLETED" || norm === "SUCCESS" || norm === "VERIFIED"
            ? "bg-emerald-500"
            : norm === "PENDING" || norm === "PROCESSING" || norm === "NEEDS_REVIEW"
            ? "bg-amber-500 animate-pulse"
            : norm === "SHIPPED"
            ? "bg-blue-500"
            : norm === "CANCELLED" || norm === "FAILED" || norm === "REJECTED"
            ? "bg-rose-500"
            : "bg-stone-400"
        }`}
      />
      {label}
    </span>
  );
}

/**
 * 5. AdminBadge - Multi-purpose tag
 */
export function AdminBadge({
  children,
  variant = "stone",
  size = "md",
}: {
  children: React.ReactNode;
  variant?: "forest" | "gold" | "stone" | "blue" | "emerald" | "rose";
  size?: "sm" | "md";
}) {
  const styles = {
    forest: "bg-[#2D332C]/10 text-[#2D332C] border-[#2D332C]/20 font-semibold",
    gold: "bg-[#C9A77A]/15 text-[#2D332C] border-[#C9A77A]/40 font-semibold",
    stone: "bg-[#FAF8F5] text-[#777777] border-[#2D332C]/10",
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
    rose: "bg-rose-50 text-rose-700 border-rose-200",
  }[variant];

  const sizeClass = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border shadow-2xs ${styles} ${sizeClass}`}
    >
      {children}
    </span>
  );
}

/**
 * 6. AdminTable & Components - Styled luxury data table
 */
export function AdminTableContainer({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[1.25rem] border border-[#2D332C]/10 bg-white shadow-card">
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

export function AdminTable({ children }: { children: React.ReactNode }) {
  return <table className="w-full text-left text-sm text-[#242424]">{children}</table>;
}

export function AdminTableHead({
  columns,
}: {
  columns: { key: string; label: string; align?: "left" | "right" | "center"; className?: string }[];
}) {
  return (
    <thead className="border-b border-[#2D332C]/10 bg-[#FAF8F5]">
      <tr>
        {columns.map((col) => (
          <th
            key={col.key}
            className={`px-4 py-3.5 text-[11px] font-bold uppercase tracking-[0.14em] text-[#777777] ${
              col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
            } ${col.className || ""}`}
          >
            {col.label}
          </th>
        ))}
      </tr>
    </thead>
  );
}

export function AdminTableRow({
  children,
  onClick,
  className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <tr
      onClick={onClick}
      className={`border-b border-[#2D332C]/5 transition-colors duration-150 hover:bg-[#FAF8F5]/80 ${
        onClick ? "cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </tr>
  );
}

export function AdminTableCell({
  children,
  align = "left",
  className = "",
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <td
      className={`px-4 py-3.5 align-middle ${
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left"
      } ${className}`}
    >
      {children}
    </td>
  );
}

/**
 * 7. AdminSearchFilterBar - Form wrapper for search inputs & selectors
 */
export function AdminSearchFilterBar({
  children,
  onSubmit,
  className = "",
  formRef,
}: {
  children: React.ReactNode;
  onSubmit?: (e: React.FormEvent<HTMLFormElement>) => void;
  className?: string;
  formRef?: React.Ref<HTMLFormElement>;
}) {
  const containerClasses = `flex flex-wrap items-center gap-3 rounded-2xl border border-[#2D332C]/10 bg-white p-4 shadow-card ${className}`;

  if (onSubmit) {
    return (
      <form ref={formRef} onSubmit={onSubmit} className={containerClasses}>
        {children}
      </form>
    );
  }

  return <div className={containerClasses}>{children}</div>;
}

/**
 * 8. AdminPagination - Luxury page controls
 */
export function AdminPagination({
  page,
  pageSize,
  total,
  onPageChange,
  loading = false,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (nextPage: number) => void;
  loading?: boolean;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(total, page * pageSize);

  return (
    <div className="flex flex-col items-center justify-between gap-4 border-t border-[#2D332C]/10 px-5 py-4 sm:flex-row">
      <p className="text-xs text-[#777777]">
        Hiển thị <span className="font-semibold text-[#242424]">{startItem}</span> -{" "}
        <span className="font-semibold text-[#242424]">{endItem}</span> trên{" "}
        <span className="font-semibold text-[#242424]">{total}</span> kết quả
      </p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || loading}
          className="inline-flex h-9 items-center gap-1 rounded-xl border border-[#2D332C]/15 bg-white px-3 text-xs font-semibold text-[#242424] shadow-2xs transition hover:bg-[#FAF8F5] hover:border-[#A68B6D] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft size={14} /> Trước
        </button>

        <span className="rounded-xl border border-[#C9A77A]/30 bg-[#FAF8F5] px-3 py-1.5 text-xs font-bold text-[#2D332C]">
          Trang {page} / {totalPages}
        </span>

        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages || loading}
          className="inline-flex h-9 items-center gap-1 rounded-xl border border-[#2D332C]/15 bg-white px-3 text-xs font-semibold text-[#242424] shadow-2xs transition hover:bg-[#FAF8F5] hover:border-[#A68B6D] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Sau <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

/**
 * 9. AdminEmptyState - Standard empty placeholder
 */
export function AdminEmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      {Icon && (
        <span className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-[#C9A77A]/35 bg-[#FAF8F5] text-[#A68B6D] shadow-sm">
          <Icon size={26} />
        </span>
      )}
      <h3 className="text-base font-bold text-[#242424]">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-[#777777]">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
