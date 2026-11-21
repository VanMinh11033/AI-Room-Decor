import { Check, ImageIcon, Sparkles } from "lucide-react";

type StepState = "done" | "current" | "pending" | "error";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && (
          <div className="inline-flex items-center gap-2 rounded-full border border-clay/20 bg-white px-3 py-1 text-sm font-bold text-clay shadow-sm">
            <Sparkles size={15} />
            {eyebrow}
          </div>
        )}
        <h1 className="mt-4 max-w-4xl text-2xl sm:text-3xl md:text-5xl font-black tracking-tight text-ink break-words">{title}</h1>
        {description && <p className="mt-4 max-w-2xl text-base leading-7 text-charcoal/70 md:text-lg">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function SectionCard({
  title,
  subtitle,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`surface-card p-5 md:p-6 ${className}`}>
      {(title || subtitle) && (
        <div>
          {title && <h2 className="text-xl font-black text-ink">{title}</h2>}
          {subtitle && <p className="mt-1 text-sm leading-6 text-charcoal/60">{subtitle}</p>}
        </div>
      )}
      <div className={title || subtitle ? "mt-5" : ""}>{children}</div>
    </section>
  );
}

export function EmptyImagePlaceholder({ label = "Chưa có ảnh" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-40 w-full flex-col items-center justify-center gap-3 bg-gradient-to-br from-ivory to-sand/60 px-6 text-center text-charcoal/55">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-clay shadow-sm">
        <ImageIcon size={24} />
      </span>
      <span className="text-sm font-bold">{label}</span>
    </div>
  );
}

export function ScoreBadge({ score }: { score: number }) {
  const rounded = Math.round(score);
  const strong = rounded >= 80;
  const medium = rounded >= 55;
  return (
    <span
      className={`rounded-full px-3 py-1 text-sm font-black shadow-sm ${
        strong ? "bg-ink text-white" : medium ? "bg-clay text-white" : "bg-white text-charcoal"
      }`}
    >
      {rounded}% phù hợp
    </span>
  );
}

export function RoomFlowStepper({ steps }: { steps: { label: string; state: StepState }[] }) {
  return (
    <div className="flex sm:grid gap-2 sm:gap-3 rounded-2xl sm:rounded-3xl border border-ink/10 bg-white/85 p-2 sm:p-3 shadow-card backdrop-blur overflow-x-auto sm:grid-cols-5">
      {steps.map((step, index) => (
        <div
          key={step.label}
          className={`shrink-0 min-w-[130px] sm:min-w-0 rounded-xl sm:rounded-2xl px-2.5 py-2 sm:px-3 sm:py-3 transition ${
            step.state === "current"
              ? "border border-clay/30 bg-clay/10 shadow-sm"
              : step.state === "done"
                ? "bg-moss/10"
                : step.state === "error"
                  ? "bg-red-50"
                  : "bg-ivory"
          }`}
        >
          <div className="flex items-center gap-2">
            <span
              className={`flex h-7 w-7 sm:h-8 sm:w-8 shrink-0 items-center justify-center rounded-full text-xs font-black ${
                step.state === "done"
                  ? "bg-moss text-white"
                  : step.state === "current"
                    ? "bg-clay text-white"
                    : step.state === "error"
                      ? "bg-red-600 text-white"
                      : "bg-white text-charcoal/45"
              }`}
            >
              {step.state === "done" ? <Check size={14} className="sm:hidden" /> : null}
              {step.state === "done" ? <Check size={16} className="hidden sm:block" /> : null}
              {step.state !== "done" ? index + 1 : null}
            </span>
            <span className="text-xs sm:text-sm font-black text-ink truncate">{step.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SelectionChip({
  selected,
  label,
  onClick,
  children,
}: {
  selected: boolean;
  label: string;
  onClick: () => void;
  children?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-bold transition ${
        selected
          ? "border-clay bg-clay text-white shadow-sm"
          : "border-ink/10 bg-white text-ink hover:border-clay/40 hover:bg-ivory"
      }`}
    >
      {children}
      {label}
      {selected && <Check size={15} />}
    </button>
  );
}
