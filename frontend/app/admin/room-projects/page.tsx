"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import { displayRoomType, displayStatus } from "@/lib/display";
import type { AdminRoomProjectListItem, AdminRoomProjectListResponse } from "@/types/api";

export default function AdminRoomProjectsPage() {
  const { loading } = useAuth("ADMIN");
  const [items, setItems] = useState<AdminRoomProjectListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<AdminRoomProjectListResponse>("/api/admin/room-projects")
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dự án phòng."));
  }, []);

  if (loading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">Dự án phòng</h1>
        <p className="mt-2 text-sm text-black/60">Theo dõi quá trình phân tích phòng, sở thích và lịch sử thiết kế AI của khách hàng.</p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div>}

      <div className="overflow-hidden rounded-lg border border-black/10 bg-white">
        <div className="border-b border-black/10 px-4 py-3 text-sm font-semibold text-black/60">Tổng cộng {total} dự án</div>
        <table className="w-full text-left text-sm">
          <thead className="bg-black/5">
            <tr>
              <th className="p-3">Dự án</th>
              <th className="p-3">Khách hàng</th>
              <th className="p-3">Loại phòng</th>
              <th className="p-3">Trạng thái dự án</th>
              <th className="p-3">Phân tích</th>
              <th className="p-3">Thiết kế AI</th>
              <th className="p-3">Ngày tạo</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.project.id} className="border-t border-black/10 hover:bg-black/5">
                <td className="p-3">
                  <Link href={`/admin/room-projects/${item.project.id}`} className="font-semibold text-clay hover:underline">
                    #{item.project.id} · {item.project.title}
                  </Link>
                </td>
                <td className="p-3">
                  <p className="font-semibold text-ink">{item.customer?.full_name || "Khách hàng"}</p>
                  <p className="text-xs text-black/50">{item.customer?.email || `#${item.project.user_id}`}</p>
                </td>
                <td className="p-3">{displayRoomType(item.project.room_type) || "-"}</td>
                <td className="p-3">{displayStatus(item.project.status)}</td>
                <td className="p-3">{item.analysis_status ? displayStatus(item.analysis_status) : "Chưa có"}</td>
                <td className="p-3">{item.design_generation_count}</td>
                <td className="p-3">{new Date(item.project.created_at).toLocaleString("vi-VN")}</td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-black/50">Chưa có dự án phòng.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
