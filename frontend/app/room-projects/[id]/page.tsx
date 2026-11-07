"use client";

import Link from "next/link";
import { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { AlertCircle, BrainCircuit, ChevronLeft, ImagePlus, Loader2, Palette, RefreshCw, Upload } from "lucide-react";
import { EmptyImagePlaceholder, PageHeader, RoomFlowStepper, SectionCard } from "@/components/customer/DesignPrimitives";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayColor, displayRoomType } from "@/lib/display";
import { useAuth } from "@/hooks/useAuth";
import type { RoomAnalysis, RoomProject } from "@/types/api";

export default function RoomProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { loading: authLoading } = useAuth("CUSTOMER");
  const [project, setProject] = useState<RoomProject | null>(null);
  const [analysis, setAnalysis] = useState<RoomAnalysis | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [pageError, setPageError] = useState("");
  const [actionError, setActionError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setPageError("");
    try {
      const data = await apiFetch<RoomProject>(`/api/room-projects/${params.id}`);
      setProject(data);
      try {
        setAnalysis(await apiFetch<RoomAnalysis>(`/api/room-projects/${params.id}/analysis`));
      } catch {
        setAnalysis(null);
      }
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Không tải được dự án phòng");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  async function uploadImage() {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    setActionError("");
    try {
      const updated = await apiFetch<RoomProject>(`/api/room-projects/${params.id}/image`, { method: "POST", body: formData });
      setProject(updated);
      setAnalysis(null);
      setFile(null);
    } catch (err) {
      setActionError(mapUploadError(err instanceof Error ? err.message : ""));
    } finally {
      setUploading(false);
    }
  }

  async function analyze(force = false) {
    setAnalyzing(true);
    setActionError("");
    try {
      const result = await apiFetch<RoomAnalysis>(`/api/room-projects/${params.id}/analyze${force ? "?force=true" : ""}`, { method: "POST" });
      setAnalysis(result);
      await load();
    } catch (err) {
      setActionError(mapAnalysisError(err instanceof Error ? err.message : ""));
      await load();
    } finally {
      setAnalyzing(false);
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setActionError("");
    setFile(event.target.files?.[0] || null);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setActionError("");
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }

  const hasImage = Boolean(project?.room_image_url);
  const analysisCompleted = analysis?.status === "COMPLETED";
  const analysisFailed = analysis?.status === "FAILED";
  const canSeeRecommendations = Boolean(project?.preference_configured && analysisCompleted);
  const status = useMemo(() => projectStatusLabel(project, analysis), [project, analysis]);

  if (authLoading || loading) return <p className="font-semibold text-charcoal/60">Đang tải dự án...</p>;
  if (!project) return <p className="text-red-600">{pageError || "Không tìm thấy dự án phòng"}</p>;

  return (
    <section className="space-y-8">
      <Link href="/room-projects" className="inline-flex items-center gap-2 text-sm font-bold text-charcoal/60 hover:text-ink">
        <ChevronLeft size={16} /> Dự án của tôi
      </Link>
      <PageHeader
        eyebrow={status.label}
        title={project.title}
        description={displayRoomType(project.room_type) || "Chưa chọn loại phòng"}
      />

      <RoomFlowStepper steps={[
        { label: "Ảnh phòng", state: hasImage ? "done" : "current" },
        { label: "Phân tích AI", state: analysisCompleted ? "done" : analysisFailed ? "error" : hasImage ? "current" : "pending" },
        { label: "Cá nhân hóa", state: project.preference_configured ? "done" : analysisCompleted ? "current" : "pending" },
        { label: "Gợi ý nội thất", state: canSeeRecommendations ? "current" : "pending" },
        { label: "Thiết kế AI", state: "pending" },
      ]} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.9fr)]">
        <div className="space-y-5">
          <div className="overflow-hidden rounded-3xl border border-ink/10 bg-white shadow-soft">
            <div className="aspect-[16/10] bg-ivory">
              {project.room_image_url ? (
                <img src={apiAssetUrl(project.room_image_url)} alt={project.title} className="h-full w-full object-cover" />
              ) : (
                <EmptyImagePlaceholder label="Chưa có ảnh phòng" />
              )}
            </div>
          </div>
          <UploadCard
            file={file}
            previewUrl={previewUrl}
            uploading={uploading}
            onFileChange={onFileChange}
            onDrop={onDrop}
            onPick={() => inputRef.current?.click()}
            onUpload={uploadImage}
            inputRef={inputRef}
          />
        </div>

        <aside className="space-y-5">
          <SectionCard
            title="Phân tích không gian"
            subtitle="AI đọc ảnh phòng để xác định bố cục, ánh sáng, màu chủ đạo và các khu vực có thể decor."
          >
            {!hasImage && <EmptyState text="Tải ảnh căn phòng trước khi phân tích." />}
            {hasImage && !analysis && (
              <ActionState title="Chưa có kết quả phân tích" text="Phân tích ảnh phòng hiện tại để mở bước gợi ý nội thất." buttonLabel="Phân tích căn phòng" loading={analyzing} onClick={() => analyze(false)} />
            )}
            {analysisFailed && <FailedState error={analysis} loading={analyzing} onRetry={() => analyze(true)} />}
            {analysisCompleted && <AnalysisResult analysis={analysis} />}
          </SectionCard>

          {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">{actionError}</div>}

          <SectionCard title="Bước tiếp theo">
            <div className="space-y-3">
              {!analysisCompleted && hasImage && (
                <button disabled={analyzing} onClick={() => analyze(analysisFailed)} className="primary-cta w-full">
                  {analyzing ? <Loader2 size={18} className="animate-spin" /> : <BrainCircuit size={18} />}
                  {analysisFailed ? "Thử phân tích lại" : "Phân tích căn phòng"}
                </button>
              )}
              {analysisCompleted && !project.preference_configured && (
                <Link href={`/room-projects/${project.id}/preferences`} className="primary-cta w-full">
                  <Palette size={18} /> Tiếp tục cá nhân hóa
                </Link>
              )}
              {canSeeRecommendations && (
                <Link href={`/room-projects/${project.id}/recommendations`} className="primary-cta w-full">
                  <Palette size={18} /> Xem gợi ý nội thất
                </Link>
              )}
              <button type="button" onClick={() => inputRef.current?.click()} className="secondary-cta w-full">
                <ImagePlus size={18} /> {hasImage ? "Thay ảnh" : "Chọn ảnh"}
              </button>
            </div>
          </SectionCard>
        </aside>
      </div>
    </section>
  );
}

function UploadCard({ file, previewUrl, uploading, onFileChange, onDrop, onPick, onUpload, inputRef }: {
  file: File | null;
  previewUrl: string;
  uploading: boolean;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onPick: () => void;
  onUpload: () => void;
  inputRef: React.MutableRefObject<HTMLInputElement | null>;
}) {
  return (
    <section onDrop={onDrop} onDragOver={(event) => event.preventDefault()} className="rounded-3xl border border-dashed border-clay/30 bg-white/85 p-5 shadow-card">
      <input ref={inputRef} onChange={onFileChange} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" />
      <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-center">
        <div className="flex gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-clay/10 text-clay">
            <Upload size={24} />
          </div>
          <div>
            <h2 className="font-black text-ink">Tải ảnh căn phòng</h2>
            <p className="mt-1 text-sm leading-6 text-charcoal/60">Kéo thả ảnh vào đây hoặc chọn từ máy tính. JPG, PNG, WebP.</p>
          </div>
        </div>
        <button type="button" onClick={onPick} className="secondary-cta px-4 py-2">Chọn ảnh</button>
      </div>
      {file && (
        <div className="mt-4 flex flex-col gap-4 rounded-2xl bg-ivory p-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            {previewUrl && <img src={previewUrl} alt={file.name} className="h-16 w-20 rounded-xl object-cover" />}
            <div className="min-w-0">
              <p className="truncate text-sm font-black text-ink">{file.name}</p>
              <p className="mt-1 text-xs text-charcoal/55">{formatBytes(file.size)}</p>
            </div>
          </div>
          <button disabled={uploading} onClick={onUpload} className="primary-cta px-4 py-2">
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            Tải ảnh lên
          </button>
        </div>
      )}
    </section>
  );
}

function ActionState({ title, text, buttonLabel, loading, onClick }: { title: string; text: string; buttonLabel: string; loading: boolean; onClick: () => void }) {
  return (
    <div className="rounded-2xl bg-ivory p-4">
      <p className="font-black text-ink">{title}</p>
      <p className="mt-1 text-sm leading-6 text-charcoal/60">{text}</p>
      <button disabled={loading} onClick={onClick} className="primary-cta mt-4 px-4 py-2">
        {loading ? <Loader2 size={16} className="animate-spin" /> : <BrainCircuit size={16} />}
        {buttonLabel}
      </button>
    </div>
  );
}

function FailedState({ error, loading, onRetry }: { error: RoomAnalysis; loading: boolean; onRetry: () => void }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 text-red-600" size={20} />
        <div>
          <p className="font-black text-red-800">Phân tích thất bại</p>
          <p className="mt-1 text-sm leading-6 text-red-700">{mapAnalysisError(error.error_code || error.error_message || "")}</p>
          <button disabled={loading} onClick={onRetry} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-red-700 px-4 py-2 text-sm font-bold text-white disabled:bg-red-300">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Thử phân tích lại
          </button>
        </div>
      </div>
    </div>
  );
}

function AnalysisResult({ analysis }: { analysis: RoomAnalysis }) {
  return (
    <div className="space-y-4">
      {analysis.provider === "local_fallback" && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm font-bold text-amber-800">
          Gemini đang tạm thời quá tải. Hệ thống đang sử dụng phân tích cơ bản tạm thời để bạn có thể tiếp tục.
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <StatusTile label="Loại phòng" value={displayRoomType(analysis.room_type) || "-"} />
        <StatusTile label="Ánh sáng" value={analysis.lighting ? `${analysis.lighting.type} · ${analysis.lighting.level}` : "-"} />
      </div>
      <div className="rounded-2xl bg-ivory p-4">
        <h3 className="font-black text-ink">Màu chủ đạo</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {analysis.dominant_colors.length > 0 ? analysis.dominant_colors.map((color, index) => (
            <span key={`${index}-${color.name}-${color.hex || ""}`} className="inline-flex items-center gap-2 rounded-full border border-ink/10 bg-white px-3 py-1 text-sm font-bold">
              <span className="h-5 w-5 rounded-full border border-ink/10" style={{ backgroundColor: color.hex || "#ffffff" }} />
              {displayColor(color.name)} {color.percentage ? `${color.percentage}%` : ""}
            </span>
          )) : <span className="text-sm text-charcoal/50">-</span>}
        </div>
      </div>
      <Panel title="Vật thể hiện có" items={analysis.existing_objects.map((item) => `${item.name} (${Math.round(item.confidence * 100)}%)`)} />
      <Panel title="Khu vực trống" items={analysis.empty_areas.map((area) => `${area.location}: ${area.description || "-"}`)} />
      <Panel title="Mô tả bố cục" items={[analysis.layout_summary || "-"]} />
    </div>
  );
}

function StatusTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-ivory px-4 py-3">
      <p className="text-xs font-black uppercase text-charcoal/45">{label}</p>
      <p className="mt-1 font-black text-ink">{value}</p>
    </div>
  );
}

function Panel({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl bg-ivory p-4">
      <h3 className="font-black text-ink">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm text-charcoal/70">
        {items.length > 0 ? items.map((item) => <li key={item}>{item}</li>) : <li>-</li>}
      </ul>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-2xl bg-ivory p-4 text-sm leading-6 text-charcoal/60">{text}</div>;
}

function projectStatusLabel(project: RoomProject | null, analysis: RoomAnalysis | null) {
  if (analysis?.status === "COMPLETED") return { label: "Đã phân tích" };
  if (analysis?.status === "FAILED" || project?.status === "FAILED") return { label: "Phân tích thất bại" };
  if (project?.status === "ANALYZING") return { label: "Đang phân tích" };
  if (project?.room_image_url) return { label: "Sẵn sàng phân tích" };
  return { label: "Cần ảnh phòng" };
}

function mapAnalysisError(message: string) {
  if (message === "AI_PROVIDER_NOT_CONFIGURED") return "AI phân tích phòng chưa được cấu hình.";
  if (message === "GEMINI_PROVIDER_AUTH_ERROR") return "Dịch vụ phân tích AI đang gặp lỗi xác thực. Vui lòng liên hệ quản trị viên.";
  if (message === "GEMINI_PROVIDER_MODEL_ERROR") return "Model phân tích AI hiện không khả dụng. Vui lòng liên hệ quản trị viên.";
  if (message === "GEMINI_PROVIDER_UNAVAILABLE") return "Gemini đang tạm thời quá tải. Hệ thống đã thử lại nhưng chưa thành công. Vui lòng thử lại sau ít phút.";
  if (message === "GEMINI_PROVIDER_QUOTA_ERROR") return "Đã vượt hạn mức phân tích AI. Vui lòng thử lại sau.";
  if (message === "VISION_PROVIDER_REQUEST_FAILED" || message === "VISION_PROVIDER_HTTP_ERROR") return "Không thể phân tích ảnh lúc này. Vui lòng thử lại.";
  if (message === "VISION_PROVIDER_MALFORMED_RESPONSE") return "Kết quả AI chưa đúng định dạng. Vui lòng thử lại.";
  if (message === "AI_ANALYSIS_FAILED") return "Phân tích ảnh thất bại. Vui lòng thử lại.";
  return "Không thể phân tích ảnh lúc này. Vui lòng thử lại.";
}

function mapUploadError(message: string) {
  if (message.includes("image") || message.includes("extension") || message.includes("corrupt")) return "Ảnh không hợp lệ. Vui lòng chọn JPG, PNG hoặc WebP.";
  return "Tải ảnh lên thất bại. Vui lòng thử lại.";
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} bytes`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
