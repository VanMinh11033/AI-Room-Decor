import React from "react";
import { CheckCircle2, AlertTriangle, Clock, XCircle, Sparkles } from "lucide-react";

export type BadgeVariant =
  | "verified"
  | "pending"
  | "review"
  | "rejected"
  | "customer_pick"
  | "fallback"
  | "neutral";

export interface StatusBadgeProps {
  variant: BadgeVariant;
  label?: string;
  children?: React.ReactNode;
  className?: string;
}

export function StatusBadge({ variant, label, children, className = "" }: StatusBadgeProps) {
  const configs: Record<BadgeVariant, { defaultLabel: string; icon: React.ReactNode; styles: string }> = {
    verified: {
      defaultLabel: "Chuẩn Catalog Độc Bản",
      icon: <CheckCircle2 size={13} className="shrink-0" />,
      styles: "bg-[#EBF6EE] text-[#1E6B37] border-[#1E6B37]/30",
    },
    pending: {
      defaultLabel: "Đang xử lý",
      icon: <Clock size={13} className="shrink-0" />,
      styles: "bg-[#EFF5FD] text-[#1A5FB4] border-[#1A5FB4]/30",
    },
    review: {
      defaultLabel: "Phối cảnh AI Không Gian",
      icon: <Sparkles size={13} className="shrink-0" />,
      styles: "bg-[#FEF7E6] text-[#9E5600] border-[#9E5600]/30",
    },
    rejected: {
      defaultLabel: "Chưa đạt tiêu chuẩn",
      icon: <XCircle size={13} className="shrink-0" />,
      styles: "bg-[#FDF2F1] text-[#B3261E] border-[#B3261E]/30",
    },
    customer_pick: {
      defaultLabel: "Lựa chọn từ Catalog",
      icon: <Sparkles size={13} className="shrink-0 text-[#8A6B4E]" />,
      styles: "bg-[#8A6B4E]/12 text-[#8A6B4E] border-[#8A6B4E]/35 font-black",
    },
    fallback: {
      defaultLabel: "Chuẩn Catalog Thay Thế",
      icon: <AlertTriangle size={13} className="shrink-0" />,
      styles: "bg-[#FEF7E6] text-[#9E5600] border-[#9E5600]/30",
    },
    neutral: {
      defaultLabel: "Thông tin",
      icon: null,
      styles: "bg-[#FBF9F5] text-[#5A6258] border-[#DDD7CD]",
    },
  };

  const config = configs[variant] || configs.neutral;
  const content = children || label || config.defaultLabel;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide ${config.styles} ${className}`}
    >
      {config.icon}
      <span>{content}</span>
    </span>
  );
}
