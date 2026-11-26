"use client";

import Link from "next/link";
import {
  Camera,
  Check,
  ChevronLeft,
  Compass,
  Eye,
  Layers,
  Sparkles,
} from "lucide-react";
import { apiAssetUrl } from "@/lib/api";

export type StudioSaveState = "saved" | "saving" | "unsaved" | "error";

export interface StudioNavHeaderProps {
  projectId?: number | string;
  projectTitle?: string;
  roomImageUrl?: string | null;
  currentStep: 1 | 2 | 3 | 4 | 5;
  hasRoomImage?: boolean;
  hasPreferences?: boolean;
  selectedProductsCount?: number;
  latestGenerationId?: string | number | null;
  isSaving?: boolean;
  saveState?: StudioSaveState;
}

export function StudioNavHeader({
  projectId,
  projectTitle = "Dự án thiết kế phòng",
  roomImageUrl,
  currentStep,
  hasRoomImage = false,
  hasPreferences = false,
  selectedProductsCount = 0,
  latestGenerationId,
  isSaving = false,
  saveState,
}: StudioNavHeaderProps) {
  const steps = [
    {
      step: 1 as const,
      label: "Ảnh không gian",
      sublabel: "Hiện trạng phòng",
      icon: Camera,
      href: projectId ? `/room-projects/${projectId}` : "/room-projects/new",
      isAccessible: true,
      isCompleted: hasRoomImage,
    },
    {
      step: 2 as const,
      label: "Phong cách",
      sublabel: "Sở thích & Gu thẩm mỹ",
      icon: Compass,
      href: projectId ? `/room-projects/${projectId}/preferences` : "#",
      isAccessible: Boolean(projectId && hasRoomImage),
      isCompleted: hasPreferences,
    },
    {
      step: 3 as const,
      label: "Chọn nội thất",
      sublabel: "1–3 sản phẩm catalog",
      icon: Layers,
      href: projectId ? `/room-projects/${projectId}/recommendations` : "#",
      isAccessible: Boolean(projectId && hasRoomImage),
      isCompleted: selectedProductsCount > 0,
    },
    {
      step: 4 as const,
      label: "Tạo phối cảnh",
      sublabel: "Xử lý AI Studio",
      icon: Sparkles,
      href: projectId ? `/room-projects/${projectId}/recommendations` : "#",
      isAccessible: Boolean(projectId && hasRoomImage && selectedProductsCount > 0),
      isCompleted: Boolean(latestGenerationId),
    },
    {
      step: 5 as const,
      label: "Phương án",
      sublabel: "Xem kết quả decor",
      icon: Eye,
      href: projectId && latestGenerationId ? `/room-projects/${projectId}/design-generations/${latestGenerationId}` : "#",
      isAccessible: Boolean(projectId && latestGenerationId),
      isCompleted: Boolean(latestGenerationId),
    },
  ];

  return (
    <div className="w-full space-y-4">
      {/* 1. Top Meta Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#242B23]/10 pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/room-projects"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[#242B23]/10 bg-white text-[#5A6258] transition hover:border-[#8A6B4E] hover:text-[#242B23]"
            title="Danh sách dự án"
          >
            <ChevronLeft size={18} />
          </Link>

          {roomImageUrl && (
            <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-lg border border-[#242B23]/10 bg-[#FBF9F5]">
              <img
                src={apiAssetUrl(roomImageUrl)}
                alt={projectTitle}
                className="h-full w-full object-cover"
              />
            </div>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A6B4E]">
                AI Room Studio
              </span>
              <span className="text-[#DDD7CD]">·</span>
              <div className="flex items-center gap-1.5 text-[11px]">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    (saveState || (isSaving ? "saving" : "saved")) === "saving"
                      ? "bg-amber-400 animate-pulse"
                      : (saveState || (isSaving ? "saving" : "saved")) === "saved"
                      ? "bg-emerald-500"
                      : (saveState || (isSaving ? "saving" : "saved")) === "error"
                      ? "bg-red-500"
                      : "bg-[#8A6B4E]"
                  }`}
                />
                <span className="text-[#5A6258]">
                  {(saveState || (isSaving ? "saving" : "saved")) === "saving"
                    ? "Đang lưu..."
                    : (saveState || (isSaving ? "saving" : "saved")) === "saved"
                    ? "Đã lưu"
                    : (saveState || (isSaving ? "saving" : "saved")) === "error"
                    ? "Lưu thất bại"
                    : "Chưa lưu"}
                </span>
              </div>
            </div>
            <h1 className="font-serif text-lg sm:text-xl font-normal text-[#242B23] truncate">
              {projectTitle}
            </h1>
          </div>
        </div>

        {/* Selected Items Context Pill */}
        <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
          {selectedProductsCount > 0 ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#8A6B4E]/30 bg-[#8A6B4E]/10 px-3 py-1 text-xs font-semibold text-[#8A6B4E]">
              <Sparkles size={13} />
              Đã chọn {selectedProductsCount}/3 nội thất
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#242B23]/10 bg-white px-3 py-1 text-xs text-[#5A6258]">
              Chưa chọn sản phẩm
            </span>
          )}
        </div>
      </div>

      {/* 2. Five-Step Interactive Progress Stepper */}
      <nav aria-label="Tiến trình thiết kế phòng" className="w-full">
        <ol className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-3 w-full min-w-0">
          {steps.map((s) => {
            const isCurrent = s.step === currentStep;
            const Icon = s.icon;

            const baseClasses =
              "flex flex-col justify-between rounded-xl sm:rounded-2xl border p-2.5 sm:p-3 text-left transition duration-200 min-w-0";

            let stateClasses = "border-[#242B23]/10 bg-white/70 text-[#5A6258] opacity-60";
            let iconBoxClasses = "bg-[#DDD7CD]/30 text-[#5A6258]";

            if (isCurrent) {
              stateClasses =
                "border-[#8A6B4E] bg-white ring-2 ring-[#8A6B4E]/20 shadow-sm text-[#242B23] opacity-100";
              iconBoxClasses = "bg-[#242B23] text-white";
            } else if (s.isCompleted) {
              stateClasses =
                "border-[#1E6B37]/30 bg-[#EBF6EE]/60 text-[#1E6B37] hover:bg-[#EBF6EE] opacity-100";
              iconBoxClasses = "bg-[#1E6B37] text-white";
            } else if (s.isAccessible) {
              stateClasses =
                "border-[#242B23]/10 bg-white text-[#242B23] hover:border-[#8A6B4E]/50 opacity-100";
              iconBoxClasses = "bg-[#DDD7CD]/50 text-[#242B23]";
            }

            const content = (
              <>
                <div className="flex items-center justify-between gap-1 mb-1.5">
                  <span
                    className={`flex h-6 w-6 sm:h-7 sm:w-7 items-center justify-center rounded-lg text-xs font-semibold ${iconBoxClasses}`}
                  >
                    {s.isCompleted && !isCurrent ? (
                      <Check size={14} />
                    ) : (
                      <Icon size={14} />
                    )}
                  </span>
                  <span className="text-[10px] font-semibold text-[#8A6B4E]">
                    0{s.step}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="text-xs sm:text-sm font-semibold truncate">
                    {s.label}
                  </p>
                  <p className="hidden md:block text-[11px] text-[#5A6258] truncate">
                    {s.sublabel}
                  </p>
                </div>
              </>
            );

            if (s.isAccessible && s.href !== "#") {
              return (
                <li key={s.step} className="min-w-0">
                  <Link href={s.href} className={`${baseClasses} ${stateClasses} block w-full h-full`}>
                    {content}
                  </Link>
                </li>
              );
            }

            return (
              <li key={s.step} className="min-w-0">
                <div className={`${baseClasses} ${stateClasses} cursor-not-allowed`}>
                  {content}
                </div>
              </li>
            );
          })}
        </ol>
      </nav>
    </div>
  );
}
