import React from "react";
import { Loader2 } from "lucide-react";

export interface LuxuryButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "bronze" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: React.ReactNode;
}

export const LuxuryButton = React.forwardRef<HTMLButtonElement, LuxuryButtonProps>(
  (
    {
      className = "",
      variant = "primary",
      size = "md",
      loading = false,
      disabled = false,
      icon,
      children,
      type = "button",
      ...rest
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-semibold tracking-wide transition-all duration-200 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8A6B4E] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:scale-100 disabled:opacity-50 select-none";

    const sizeStyles = {
      sm: "min-h-[36px] px-3.5 py-1.5 text-xs rounded-lg gap-1.5",
      md: "min-h-[44px] px-5 py-2.5 text-sm rounded-xl gap-2",
      lg: "min-h-[52px] px-7 py-3.5 text-base rounded-2xl gap-2.5",
    };

    const variantStyles = {
      primary:
        "bg-[#242B23] text-white shadow-card hover:-translate-y-0.5 hover:bg-[#343D32] hover:shadow-soft active:translate-y-0",
      secondary:
        "border border-[#DDD7CD] bg-white text-[#242424] shadow-sm hover:-translate-y-0.5 hover:border-[#8A6B4E] hover:bg-[#FBF9F5] hover:text-[#242B23] active:translate-y-0",
      bronze:
        "bg-[#8A6B4E] text-white shadow-card hover:-translate-y-0.5 hover:bg-[#72573E] hover:shadow-soft active:translate-y-0",
      ghost:
        "bg-transparent text-[#5A6258] hover:bg-black/5 hover:text-[#242424] active:bg-black/10",
      danger:
        "bg-[#B3261E] text-white shadow-sm hover:-translate-y-0.5 hover:bg-[#921E17] active:translate-y-0",
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
        {...rest}
      >
        {loading ? <Loader2 size={size === "sm" ? 14 : size === "lg" ? 20 : 16} className="animate-spin shrink-0" /> : icon}
        <span>{children}</span>
      </button>
    );
  }
);

LuxuryButton.displayName = "LuxuryButton";
