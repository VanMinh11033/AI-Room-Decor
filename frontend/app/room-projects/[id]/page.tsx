"use client";

import Link from "next/link";
import { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  BrainCircuit,
  Camera,
  ChevronLeft,
  ImagePlus,
  Loader2,
  Palette,
  RefreshCw,
  Sparkles,
  Upload,
} from "lucide-react";
import { EmptyImagePlaceholder, SectionCard } from "@/components/customer/DesignPrimitives";
import { EditorialHeading } from "@/components/ui/EditorialHeading";
import { LuxuryButton } from "@/components/ui/LuxuryButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StudioNavHeader } from "@/components/studio/StudioNavHeader";
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

  if (authLoading || loading) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="font-serif text-lg text-[#242B23]">Đang tải không gian phòng...</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="text-red-600 font-semibold">{pageError || "Không tìm thấy dự án phòng"}</p>
        <Link href="/room-projects">
          <LuxuryButton variant="secondary" size="md">Về danh sách dự án</LuxuryButton>
        </Link>
      </div>
    );
  }

  return (
    <section className="space-y-8 w-full max-w-full">
      {/* Studio Navigation Header */}
      <StudioNavHeader
        projectId={project.id}
        projectTitle={project.title}
        roomImageUrl={project.room_image_url}
        currentStep={1}
        hasRoomImage={hasImage}
        hasPreferences={Boolean(project.preference_configured)}
        selectedProductsCount={0}
        saveState="saved"
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 w-full min-w-0">
        {/* LEFT COLUMN: Room Showcase & Upload Card (7 cols) */}
        <div className="space-y-6 lg:col-span-7 w-full min-w-0">
          <div className="overflow-hidden rounded-3xl border border-[#242B23]/10 bg-white p-3 shadow-soft">
            <div className="relative aspect-[16/10] w-full overflow-hidden rounded-2xl bg-[#FBF9F5] flex items-center justify-center">
              {project.room_image_url ? (
                <img
                  src={apiAssetUrl(project.room_image_url)}
                  alt={project.title}
                  className="h-full w-full object-contain"
                />
              ) : (
                <EmptyImagePlaceholder label="Chưa có ảnh không gian phòng" />
              )}
              {hasImage && (
                <div className="absolute left-3.5 top-3.5">
                  <StatusBadge variant={analysisCompleted ? "verified" : "pending"}>
                    {analysisCompleted ? "Đã phân tích bố cục" : "Ảnh hiện trạng gốc"}
                  </StatusBadge>
                </div>
              )}
            </div>
          </div>

          {/* Upload Card */}
          <section
            onDrop={onDrop}
            onDragOver={(e) => e.preventDefault()}
            className="rounded-3xl border border-dashed border-[#8A6B4E]/30 bg-white p-6 shadow-sm space-y-4"
          >
            <input
              ref={inputRef}
              onChange={onFileChange}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
            />
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#8A6B4E]/10 text-[#8A6B4E]">
                  <Camera size={22} />
                </div>
                <div>
                  <h2 className="font-serif text-lg text-[#242B23]">
                    {hasImage ? "Thay đổi ảnh không gian" : "Tải ảnh căn phòng của bạn"}
                  </h2>
                  <p className="text-xs text-[#5A6258] mt-0.5">
                    Kéo thả file ảnh chụp thực tế hoặc chọn từ máy (JPG, PNG, WebP tối đa 15MB).
                  </p>
                </div>
              </div>
              <LuxuryButton
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => inputRef.current?.click()}
                className="shrink-0"
              >
                <ImagePlus size={16} />
                <span>{hasImage ? "Đổi ảnh" : "Chọn ảnh"}</span>
              </LuxuryButton>
            </div>

            {/* Selected File Pending Upload */}
            {file && (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-[#8A6B4E]/20 bg-[#FBF9F5] p-3.5">
                <div className="flex min-w-0 items-center gap-3">
                  {previewUrl && (
                    <img
                      src={previewUrl}
                      alt={file.name}
                      className="h-14 w-18 rounded-xl object-cover border border-[#242B23]/10"
                    />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-[#242B23]">{file.name}</p>
                    <p className="text-[11px] text-[#5A6258] mt-0.5">{formatBytes(file.size)}</p>
                  </div>
                </div>
                <LuxuryButton
                  variant="primary"
                  size="sm"
                  loading={uploading}
                  disabled={uploading}
                  onClick={uploadImage}
                  className="shrink-0"
                >
                  <Upload size={14} />
                  <span>Xác nhận tải lên</span>
                </LuxuryButton>
              </div>
            )}
          </section>
        </div>

        {/* RIGHT COLUMN: AI Analysis & Step Progression (5 cols) */}
        <aside className="space-y-6 lg:col-span-5 w-full min-w-0">
          <div className="rounded-3xl border border-[#242B23]/10 bg-white p-6 sm:p-8 shadow-card space-y-6">
            <div className="space-y-2 border-b border-[#242B23]/10 pb-5">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A6B4E]">
                Thị Giác AI Không Gian
              </span>
              <h3 className="font-serif text-xl sm:text-2xl text-[#242B23]">
                Phân tích cấu trúc & ánh sáng
              </h3>
              <p className="text-xs text-[#5A6258] leading-relaxed">
                Hệ thống tự động phát hiện ánh sáng, màu chủ đạo và nhận diện các diện tích trống có thể trang trí.
              </p>
            </div>

            {!hasImage && (
              <div className="rounded-2xl border border-[#242B23]/10 bg-[#FBF9F5] p-5 text-center space-y-2">
                <p className="text-xs text-[#5A6258]">
                  Vui lòng tải ảnh phòng ở khung bên cạnh để AI tiến hành phân tích không gian.
                </p>
              </div>
            )}

            {hasImage && !analysis && (
              <div className="rounded-2xl border border-[#8A6B4E]/20 bg-[#FBF9F5] p-5 space-y-3">
                <p className="text-xs font-semibold text-[#242B23]">Ảnh đã sẵn sàng phân tích</p>
                <p className="text-xs text-[#5A6258]">
                  Bấm nút bên dưới để AI quét kết cấu phòng và mở khóa bước gợi ý nội thất catalog.
                </p>
                <LuxuryButton
                  variant="primary"
                  size="md"
                  loading={analyzing}
                  disabled={analyzing}
                  onClick={() => analyze(false)}
                  className="w-full justify-center"
                >
                  <BrainCircuit size={16} />
                  <span>Phân tích căn phòng</span>
                </LuxuryButton>
              </div>
            )}

            {analysisFailed && (
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4 space-y-3">
                <div className="flex gap-2.5">
                  <AlertCircle size={18} className="text-red-700 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold text-red-800">Phân tích chưa hoàn tất</p>
                    <p className="text-xs text-red-700 mt-0.5">
                      {mapAnalysisError(analysis?.error_code || analysis?.error_message || "")}
                    </p>
                  </div>
                </div>
                <LuxuryButton
                  variant="secondary"
                  size="sm"
                  loading={analyzing}
                  onClick={() => analyze(true)}
                  className="w-full justify-center"
                >
                  <RefreshCw size={14} />
                  <span>Thử phân tích lại</span>
                </LuxuryButton>
              </div>
            )}

            {analysisCompleted && <AnalysisResult analysis={analysis} />}

            {actionError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 font-semibold">
                {actionError}
              </div>
            )}

            {/* Progression CTAs */}
            <div className="border-t border-[#242B23]/10 pt-5 space-y-3">
              {analysisCompleted ? (
                <Link href={`/room-projects/${project.id}/preferences`} className="block w-full">
                  <LuxuryButton variant="primary" size="lg" className="w-full justify-center">
                    <span>Tiếp tục chọn phong cách & màu sắc</span>
                    <ArrowRight size={18} />
                  </LuxuryButton>
                </Link>
              ) : hasImage ? (
                <LuxuryButton
                  variant="primary"
                  size="lg"
                  loading={analyzing}
                  disabled={analyzing}
                  onClick={() => analyze(false)}
                  className="w-full justify-center"
                >
                  <BrainCircuit size={18} />
                  <span>Phân tích căn phòng để tiếp tục</span>
                </LuxuryButton>
              ) : null}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function AnalysisResult({ analysis }: { analysis: RoomAnalysis }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <StatusTile
          label="Loại phòng"
          value={displayRoomType(analysis.room_type) || analysis.room_type || "Chưa xác định"}
        />
        <StatusTile
          label="Ánh sáng tự nhiên"
          value={analysis.lighting ? `${analysis.lighting.type} (${analysis.lighting.level})` : "Tự nhiên"}
        />
      </div>

      {/* Dominant Palette */}
      <div className="rounded-2xl border border-[#242B23]/10 bg-[#FBF9F5] p-4 space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[#5A6258]">
          Bảng màu sắc nhận diện
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          {analysis.dominant_colors.length > 0 ? (
            analysis.dominant_colors.map((color, index) => (
              <span
                key={`${index}-${color.name}`}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#242B23]/10 bg-white px-3 py-1 text-xs font-semibold text-[#242B23]"
              >
                <span
                  className="h-3.5 w-3.5 rounded-full border border-black/10 shrink-0"
                  style={{ backgroundColor: color.hex || "#e0dacf" }}
                />
                {displayColor(color.name) || color.name}
              </span>
            ))
          ) : (
            <span className="text-xs text-[#5A6258]">Tự nhiên trung tính</span>
          )}
        </div>
      </div>

      {/* Spatial Details */}
      {analysis.layout_summary && (
        <div className="rounded-2xl border border-[#242B23]/10 bg-[#FBF9F5] p-4 text-xs leading-relaxed text-[#5A6258]">
          <p className="font-semibold text-[#242B23] mb-1">Mô tả cấu trúc phòng</p>
          <p>{analysis.layout_summary}</p>
        </div>
      )}
    </div>
  );
}

function StatusTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[#242B23]/10 bg-[#FBF9F5] p-3.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5A6258]">{label}</p>
      <p className="mt-1 text-xs font-semibold text-[#242B23] truncate">{value}</p>
    </div>
  );
}

function mapAnalysisError(message: string) {
  if (message.includes("quota") || message.includes("QUOTA")) {
    return "Hạn mức gọi AI phân tích đã đạt giới hạn hôm nay. Hệ thống đang chuyển sang phân tích cục bộ.";
  }
  return "Không thể phân tích ảnh lúc này. Vui lòng thử lại sau giây lát.";
}

function mapUploadError(message: string) {
  if (message.includes("image") || message.includes("extension")) {
    return "Ảnh không hợp lệ. Vui lòng chọn định dạng JPG, PNG hoặc WebP.";
  }
  return "Tải ảnh lên chưa thành công. Vui lòng thử lại.";
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} bytes`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
