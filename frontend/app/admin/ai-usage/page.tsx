"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import { displayStatus } from "@/lib/display";
import type { AdminAIUsageListResponse } from "@/types/api";

export default function AdminAIUsagePage() {
  const { loading } = useAuth("ADMIN");
  const [provider, setProvider] = useState("");
  const [taskType, setTaskType] = useState("");
  const [status, setStatus] = useState("");
  const [data, setData] = useState<AdminAIUsageListResponse | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (provider) params.set("provider", provider);
    if (taskType) params.set("task_type", taskType);
    if (status) params.set("status", status);
    try {
      setData(await apiFetch<AdminAIUsageListResponse>(`/api/admin/ai-usage?${params.toString()}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được log AI.");
    }
  }

  useEffect(() => {
    if (!loading) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, provider, taskType, status]);

  if (loading) return <p>Đang kiểm tra quyền...</p>;

  const summary = data?.summary;
  const cards = [
    ["Tổng lượt gọi AI", summary?.total_calls],
    ["Thành công", summary?.success_calls],
    ["Thất bại", summary?.failed_calls],
    ["Gemini Cloud (Hôm nay)", summary ? `${summary.today_gemini_calls ?? 0}/${summary.gemini_daily_system_limit ?? 50}` : "-"],
    ["Cloudflare AI (Hôm nay)", summary ? `${summary.today_cloudflare_calls ?? 0}/${summary.cloudflare_daily_system_limit ?? 10}` : "-"],
    ["Local Vision Fallback", summary?.local_fallback_calls],
    ["Composite 2D Fallback", summary?.composite_fallback_calls ?? 0],
    ["Cloud AI Status", summary?.cloud_ai_enabled ? "BẬT (Active)" : "NGẮT (Kill Switch)"],
  ];

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">Theo dõi AI & Quota</h1>
        <p className="mt-2 text-sm text-black/60">Giám sát lượt gọi AI, hạn mức ngày, fallback và bảo vệ ngân sách.</p>
        {summary?.cost_disclaimer && (
          <p className="mt-1 text-xs italic text-black/50">* {summary.cost_disclaimer}</p>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
            <p className="text-sm text-black/50">{label}</p>
            <p className="mt-1 text-2xl font-bold text-ink">{value ?? "-"}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3 rounded-lg border border-black/10 bg-white p-4 shadow-sm">
        <select value={provider} onChange={(event) => setProvider(event.target.value)} className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
          <option value="">Tất cả provider</option>
          <option value="gemini">Gemini</option>
          <option value="cloudflare">Cloudflare</option>
          <option value="openai">OpenAI</option>
          <option value="local_fallback">Local fallback</option>
          <option value="not_configured">Chưa cấu hình</option>
        </select>
        <select value={taskType} onChange={(event) => setTaskType(event.target.value)} className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
          <option value="">Tất cả operation</option>
          <option value="ROOM_IMAGE_ANALYSIS">Phân tích phòng</option>
          <option value="ROOM_DESIGN_GENERATION">Tạo thiết kế</option>
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-md border border-black/15 bg-white px-3 py-2 text-sm">
          <option value="">Tất cả trạng thái</option>
          <option value="SUCCESS">Thành công</option>
          <option value="FAILED">Thất bại</option>
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-black/10 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-black/5">
            <tr>
              <th className="p-3">ID</th>
              <th className="p-3">User/Project</th>
              <th className="p-3">Provider</th>
              <th className="p-3">Model</th>
              <th className="p-3">Operation</th>
              <th className="p-3">Token</th>
              <th className="p-3">Chi phí</th>
              <th className="p-3">Trạng thái</th>
              <th className="p-3">Thời gian</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((log) => (
              <tr key={log.id} className="border-t border-black/10">
                <td className="p-3">#{log.id}</td>
                <td className="p-3">User #{log.user_id || "-"} / Project #{log.room_project_id || "-"}</td>
                <td className="p-3 font-semibold text-ink">{log.provider}</td>
                <td className="p-3">{log.model}</td>
                <td className="p-3">{displayTask(log.task_type)}</td>
                <td className="p-3">{log.total_tokens}</td>
                <td className="p-3">{money(log.estimated_cost)}</td>
                <td className="p-3">
                  <p>{displayStatus(log.status)}</p>
                  {log.error_code && <p className="text-xs font-semibold text-red-700">{log.error_code}</p>}
                </td>
                <td className="p-3">{new Date(log.created_at).toLocaleString("vi-VN")}</td>
              </tr>
            ))}
            {data?.items.length === 0 && <tr><td colSpan={9} className="p-6 text-center text-black/50">Chưa có log phù hợp.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function displayTask(taskType: string) {
  if (taskType === "ROOM_IMAGE_ANALYSIS") return "Phân tích phòng";
  if (taskType === "ROOM_DESIGN_GENERATION") return "Tạo thiết kế";
  return taskType;
}

function money(value: string | number) {
  const numberValue = Number(value || 0);
  if (!numberValue) return "—";
  return `${numberValue.toLocaleString("vi-VN", { maximumFractionDigits: 6 })} đ`;
}
