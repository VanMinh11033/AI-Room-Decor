import React from "react";
import { Sparkles } from "lucide-react";

export interface EditorialHeadingProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  align?: "left" | "center" | "right";
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

export function EditorialHeading({
  eyebrow,
  title,
  subtitle,
  align = "left",
  size = "md",
  className = "",
}: EditorialHeadingProps) {
  const alignStyles = {
    left: "text-left",
    center: "text-center mx-auto",
    right: "text-right ml-auto",
  };

  const titleSizes = {
    sm: "text-xl sm:text-2xl",
    md: "text-2xl sm:text-3xl md:text-4xl",
    lg: "text-3xl sm:text-4xl md:text-5xl",
    xl: "text-4xl sm:text-5xl md:text-6xl",
  };

  return (
    <div className={`space-y-3 ${alignStyles[align]} ${className}`}>
      {eyebrow && (
        <div className="inline-flex items-center gap-2 rounded-full border border-[#8A6B4E]/30 bg-white/90 px-3.5 py-1 text-xs font-bold uppercase tracking-[0.16em] text-[#8A6B4E] shadow-sm">
          <Sparkles size={14} className="shrink-0" />
          <span>{eyebrow}</span>
        </div>
      )}

      <h1 className={`font-serif font-bold tracking-tight text-[#242B23] break-words ${titleSizes[size]}`}>
        {title}
      </h1>

      {subtitle && (
        <p className="max-w-2xl text-sm sm:text-base leading-relaxed text-[#5A6258]">
          {subtitle}
        </p>
      )}
    </div>
  );
}
