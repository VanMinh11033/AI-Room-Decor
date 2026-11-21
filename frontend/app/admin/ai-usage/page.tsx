"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  RotateCcw,
  Zap,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import type { AdminAIUsageListResponse } from "@/types/api";
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminSearchFilterBar,
  AdminStatMiniCard,
  AdminStatusBadge,
  AdminSurfaceCard,
  AdminTable,
  AdminTableCell,
  AdminTableContainer,
  AdminTableHead,
  AdminTableRow,
} from "@/components/admin/AdminPrimitives";

export default function AdminAIUsagePage() {
  const { loading: authLoading } = useAuth("ADMIN");
  const [provider, setProvider] = useState("");
  const [taskType, setTaskType] = useState("");
  const [status, setStatus] = useState("");
  const [data, setData] = useState<AdminAIUsageListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (provider) params.set("provider", provider);
    if (taskType) params.set("task_type", taskType);
    if (status) params.set("status", status);
    setLoading(true);
    try {
      const res = await apiFetch<AdminAIUsageListResponse>(
        `/api/admin/ai-usage?${params.toString()}`
      );
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được log AI.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!authLoading) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, provider, taskType, status]);

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  const summary = data?.summary;

  const cfUsed = summary?.today_cloudflare_calls ?? 0;
  const cfLimit = summary?.cloudflare_daily_system_limit ?? 10;
  const cfPercent = Math.min(100, Math.round((cfUsed / cfLimit) * 100));

  const geminiUsed = summary?.today_gemini_calls ?? 0;
  const geminiLimit = summary?.gemini_daily_system_limit ?? 50;
  const geminiPercent = Math.min(100, Math.round((geminiUsed / geminiLimit) * 100));

  const isKillSwitchActive = summary?.cloud_ai_enabled === false;

  const tableColumns = [
    { key: "id", label: "Mã Log" },
    { key: "context", label: "Khách / Dự án" },
    { key: "provider", label: "Engine & Model" },
    { key: "operation", label: "Tác vụ AI" },
    { key: "tokens", label: "Token", align: "center" as const },
    { key: "cost", label: "Ước tính chi phí", align: "right" as const },
    { key: "status", label: "Trạng thái", align: "center" as const },
    { key: "time", label: "Thời gian ghi nhận", align: "right" as const },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Hạ tầng & Giám sát AI"
        title="Theo dõi AI & Hạn mức Quota"
        subtitle="Giám sát hạn ngạch Cloudflare Workers AI & Gemini Cloud theo thời gian thực, quản lý cơ chế an toàn và bảo vệ chi phí vận hành."
      />

      {/* 2. Infrastructure & Quota Executive Cards */}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Realtime Quota Utilization Card */}
        <div className="rounded-[1.75rem] border border-[#2D332C] bg-[#2D332C] p-6 text-[#FAF8F5] shadow-luxury md:p-8">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#C9A77A]/40 bg-white/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[#C9A77A]">
              <Cpu size={13} />
              Daily Quota Protection
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                isKillSwitchActive
                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                  : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
              }`}
            >
              {isKillSwitchActive ? "Kill Switch: Đang Tắt" : "Cloud AI: Đang Bật"}
            </span>
          </div>

          <div className="mt-6 space-y-5">
            {/* Cloudflare Quota Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-[#FAF8F5]/90">Cloudflare Workers AI (FLUX.2 Dev & Vision)</span>
                <span className="text-[#C9A77A]">
                  {cfUsed} / {cfLimit} lượt hôm nay ({cfPercent}%)
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/15">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    cfPercent >= 90 ? "bg-rose-400" : cfPercent >= 70 ? "bg-amber-400" : "bg-[#C9A77A]"
                  }`}
                  style={{ width: `${cfPercent}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-[#FAF8F5]/65">
                <span>Hạn mức người dùng: <strong>3 lượt / user / ngày</strong></span>
                <span>Ngân sách miễn phí: <strong>10.000 Neurons / ngày</strong></span>
              </div>
            </div>

            {/* Gemini Cloud Quota Bar / Standby State */}
            <div className="space-y-1.5 border-t border-white/10 pt-3">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-[#FAF8F5]/80">Google Gemini Cloud AI</span>
                <span className="rounded-md bg-white/10 px-2 py-0.5 text-[10px] font-bold text-[#FAF8F5]/70">
                  {geminiUsed > 0 ? `${geminiUsed} / ${geminiLimit} lượt` : "Dự phòng (Standby)"}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    geminiUsed > 0 ? "bg-emerald-400" : "bg-white/20"
                  }`}
                  style={{ width: `${geminiUsed > 0 ? geminiPercent : 0}%` }}
                />
              </div>
              <p className="text-[10px] text-[#FAF8F5]/50">
                Hệ thống đang ưu tiên Cloudflare Workers AI làm provider chính; Gemini ở chế độ dự phòng.
              </p>
            </div>
          </div>

          <p className="mt-6 border-t border-white/10 pt-4 text-[11px] text-[#FAF8F5]/60">
            * Cơ chế Rate Limiting phân tầng ngăn chặn phát sinh chi phí ngoài ý muốn. Khi chạm ngưỡng ngày, hệ thống tự động chuyển sang Local CV Fallback.
          </p>
        </div>

        {/* Fallback & Reliability Ratios */}
        <AdminSurfaceCard
          title="Độ tin cậy & Cơ chế dự phòng"
          subtitle="Số lần kích hoạt bộ phân tích cục bộ khi Cloud AI đạt giới hạn"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-4">
              <div>
                <p className="text-xs font-bold text-[#242424]">Local CV Vision Fallback</p>
                <p className="text-[11px] text-[#777777]">Phân tích thị giác cục bộ khi Cloud Vision bận</p>
              </div>
              <span className="text-xl font-bold text-[#2D332C]">
                {summary?.local_fallback_calls ?? 0} lượt
              </span>
            </div>

            <div className="flex items-center justify-between rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-4">
              <div>
                <p className="text-xs font-bold text-[#242424]">Composite 2D Safe Fallback</p>
                <p className="text-[11px] text-[#777777]">Ghép phối cảnh catalog 2D an toàn</p>
              </div>
              <span className="text-xl font-bold text-[#2D332C]">
                {summary?.composite_fallback_calls ?? 0} lượt
              </span>
            </div>

            <div className="flex items-center justify-between border-t border-[#2D332C]/10 pt-3 text-xs text-[#777777]">
              <span>Tỷ lệ hoàn thành thành công:</span>
              <span className="font-bold text-emerald-700">
                {summary?.total_calls
                  ? `${Math.round(((summary.success_calls || 0) / summary.total_calls) * 100)}%`
                  : "100%"}
              </span>
            </div>
          </div>
        </AdminSurfaceCard>
      </div>

      {/* 3. 4 Mini Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AdminStatMiniCard
          label="Tổng lượt gọi AI"
          value={summary?.total_calls ?? "-"}
          sub="Toàn bộ lịch sử các tác vụ"
          icon={Activity}
        />
        <AdminStatMiniCard
          label="Thành công"
          value={summary?.success_calls ?? "-"}
          sub="Phản hồi HTTP 200 hợp lệ"
          icon={CheckCircle2}
        />
        <AdminStatMiniCard
          label="Thất bại / Lỗi"
          value={summary?.failed_calls ?? 0}
          sub="Gồm cả timeout & quota exceeded"
          icon={AlertCircle}
        />
        <AdminStatMiniCard
          label="Tổng token tiêu thụ"
          value={(summary?.total_tokens ?? 0).toLocaleString("vi-VN")}
          sub="Input + Output tokens"
          icon={Zap}
        />
      </div>

      {/* 4. Filter Bar */}
      <AdminSearchFilterBar>
        <select
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả Provider</option>
          <option value="cloudflare">Cloudflare Workers AI</option>
          <option value="gemini">Google Gemini</option>
          <option value="openai">OpenAI</option>
          <option value="local_fallback">Local Fallback</option>
        </select>

        <select
          value={taskType}
          onChange={(event) => setTaskType(event.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả tác vụ (Operations)</option>
          <option value="ROOM_IMAGE_ANALYSIS">Phân tích phòng (Vision)</option>
          <option value="ROOM_DESIGN_GENERATION">Tạo thiết kế (Diffusion)</option>
        </select>

        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả trạng thái</option>
          <option value="SUCCESS">Thành công (SUCCESS)</option>
          <option value="FAILED">Thất bại (FAILED)</option>
        </select>

        {(provider || taskType || status) && (
          <button
            type="button"
            onClick={() => {
              setProvider("");
              setTaskType("");
              setStatus("");
            }}
            title="Đặt lại"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] text-[#777777] transition hover:border-[#A68B6D] hover:bg-white hover:text-[#242424]"
          >
            <RotateCcw size={15} />
          </button>
        )}

        <button
          type="button"
          onClick={() => load()}
          className="ml-auto inline-flex items-center gap-1.5 rounded-xl border border-[#2D332C]/15 bg-white px-4 py-2 text-xs font-semibold text-[#242424] shadow-2xs hover:bg-[#FAF8F5]"
        >
          <RotateCcw size={13} className="text-[#A68B6D]" />
          Làm mới log
        </button>
      </AdminSearchFilterBar>

      {/* 5. Error Alert */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* 6. AI Usage Logs Table */}
      <AdminTableContainer>
        <AdminTable>
          <AdminTableHead columns={tableColumns} />
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="p-12 text-center text-sm font-medium text-[#777777]">
                  Đang tải nhật ký gọi AI...
                </td>
              </tr>
            ) : (data?.items || []).length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8">
                  <AdminEmptyState
                    icon={BrainCircuit}
                    title="Chưa có log AI phù hợp"
                    description="Không có bản ghi sử dụng AI nào phù hợp với bộ lọc hiện tại."
                  />
                </td>
              </tr>
            ) : (
              (data?.items || []).map((log) => (
                <AdminTableRow key={log.id}>
                  {/* Mã Log */}
                  <AdminTableCell>
                    <span className="font-bold text-[#242424]">#{log.id}</span>
                  </AdminTableCell>

                  {/* Context */}
                  <AdminTableCell>
                    <div className="text-xs">
                      <p className="font-semibold text-[#242424]">
                        {log.room_project_id ? `Project #${log.room_project_id}` : "Toàn cục"}
                      </p>
                      <p className="text-[#777777]">
                        {log.user_id ? `User #${log.user_id}` : "Hệ thống"}
                      </p>
                    </div>
                  </AdminTableCell>

                  {/* Provider & Model */}
                  <AdminTableCell>
                    <div>
                      <p className="font-bold text-[#2D332C]">{log.provider}</p>
                      <p className="text-xs text-[#777777] font-mono">{log.model}</p>
                    </div>
                  </AdminTableCell>

                  {/* Operation */}
                  <AdminTableCell>
                    <span className="inline-flex rounded-lg bg-[#FAF8F5] px-2.5 py-1 text-xs font-semibold text-[#242424]">
                      {displayTask(log.task_type)}
                    </span>
                  </AdminTableCell>

                  {/* Tokens */}
                  <AdminTableCell align="center">
                    <span className="font-medium text-[#242424]">
                      {log.total_tokens ? log.total_tokens.toLocaleString("vi-VN") : "—"}
                    </span>
                  </AdminTableCell>

                  {/* Chi phí */}
                  <AdminTableCell align="right">
                    <span className="text-xs text-[#777777]">
                      {money(log.estimated_cost)}
                    </span>
                  </AdminTableCell>

                  {/* Status */}
                  <AdminTableCell align="center">
                    <div className="inline-flex flex-col items-center gap-1">
                      <AdminStatusBadge status={log.status} size="sm" />
                      {log.error_code && (
                        <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                          {log.error_code}
                        </span>
                      )}
                    </div>
                  </AdminTableCell>

                  {/* Time */}
                  <AdminTableCell align="right">
                    <span className="text-xs text-[#777777]">
                      {new Date(log.created_at).toLocaleString("vi-VN")}
                    </span>
                  </AdminTableCell>
                </AdminTableRow>
              ))
            )}
          </tbody>
        </AdminTable>
      </AdminTableContainer>
    </div>
  );
}

function displayTask(taskType: string) {
  if (taskType === "ROOM_IMAGE_ANALYSIS") return "Phân tích thị giác (Vision)";
  if (taskType === "ROOM_DESIGN_GENERATION") return "Tạo thiết kế (FLUX)";
  return taskType;
}

function money(value: string | number) {
  const numberValue = Number(value || 0);
  if (!numberValue) return "—";
  return `${numberValue.toLocaleString("vi-VN", { maximumFractionDigits: 4 })} đ`;
}
