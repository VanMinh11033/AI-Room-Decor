"use client";

import React, { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";
import { LuxuryButton } from "@/components/ui/LuxuryButton";

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  loading?: boolean;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Xác nhận",
  cancelLabel = "Hủy bỏ",
  variant = "danger",
  loading = false,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmBtnRef = useRef<HTMLButtonElement>(null);

  // Close on Escape & trap focus
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    // Auto-focus confirm button on open
    const timeout = setTimeout(() => {
      confirmBtnRef.current?.focus();
    }, 50);

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      clearTimeout(timeout);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-desc"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[#242B23]/50 backdrop-blur-sm transition-opacity"
        onClick={loading ? undefined : onClose}
        aria-hidden="true"
      />

      {/* Modal Card */}
      <div
        ref={dialogRef}
        className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-[#242B23]/10 bg-white p-6 shadow-2xl transition-all"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                variant === "danger"
                  ? "bg-red-50 text-red-600 border border-red-200"
                  : "bg-[#8A6B4E]/10 text-[#8A6B4E] border border-[#8A6B4E]/20"
              }`}
            >
              <AlertTriangle size={20} />
            </span>
            <h2 id="confirm-dialog-title" className="font-serif text-lg font-bold text-[#242B23]">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            aria-label="Đóng hộp thoại"
            className="rounded-lg p-1 text-[#5A6258] transition hover:bg-black/5 hover:text-[#242B23] disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        <p id="confirm-dialog-desc" className="mt-3 text-sm text-[#5A6258] leading-relaxed">
          {description}
        </p>

        <div className="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end gap-2.5">
          <LuxuryButton
            variant="secondary"
            size="sm"
            disabled={loading}
            onClick={onClose}
            className="w-full sm:w-auto"
          >
            {cancelLabel}
          </LuxuryButton>
          <LuxuryButton
            ref={confirmBtnRef}
            variant={variant === "danger" ? "danger" : "primary"}
            size="sm"
            loading={loading}
            disabled={loading}
            onClick={onConfirm}
            className="w-full sm:w-auto"
          >
            {confirmLabel}
          </LuxuryButton>
        </div>
      </div>
    </div>
  );
}
