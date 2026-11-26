import React from "react";

export interface SkeletonProps {
  className?: string;
  variant?: "text" | "rectangular" | "circular" | "card" | "title";
  width?: string | number;
  height?: string | number;
}

export function SkeletonLoader({
  className = "",
  variant = "text",
  width,
  height,
}: SkeletonProps) {
  const variantStyles = {
    text: "h-4 rounded-md",
    title: "h-6 w-3/4 rounded-lg",
    rectangular: "rounded-2xl",
    card: "rounded-2xl aspect-[4/3]",
    circular: "rounded-full",
  };

  const style: React.CSSProperties = {
    width: width,
    height: height,
  };

  return (
    <div
      style={style}
      className={`animate-pulse bg-[#DDD7CD]/50 ${variantStyles[variant]} ${className}`}
      aria-hidden="true"
    />
  );
}
