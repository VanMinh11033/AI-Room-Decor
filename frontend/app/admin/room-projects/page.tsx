"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  BrainCircuit,
  DoorOpen,
  Eye,
  Image as ImageIcon,
  RotateCcw,
  Search,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiAssetUrl, apiFetch } from "@/lib/api";
import { displayRoomType } from "@/lib/display";
import type { AdminRoomProjectListItem, AdminRoomProjectListResponse } from "@/types/api";
import {
  AdminBadge,
  AdminEmptyState,
  AdminPageHeader,
  AdminSearchFilterBar,
  AdminStatMiniCard,
  AdminStatusBadge,
  AdminTable,
  AdminTableCell,
  AdminTableContainer,
  AdminTableHead,
  AdminTableRow,
} from "@/components/admin/AdminPrimitives";

export default function AdminRoomProjectsPage() {
  const { loading: authLoading } = useAuth("ADMIN");
  const [items, setItems] = useState<AdminRoomProjectListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [roomTypeFilter, setRoomTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;
    const controller = new AbortController();
    setLoading(true);
    apiFetch<AdminRoomProjectListResponse>("/api/admin/room-projects", { signal: controller.signal })
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
        setError("");
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Không tải được dự án phòng.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [authLoading]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        String(item.project.id).includes(q) ||
        item.project.title.toLowerCase().includes(q) ||
        (item.customer?.full_name || "").toLowerCase().includes(q) ||
        (item.customer?.email || "").toLowerCase().includes(q);
      const matchRoomType = !roomTypeFilter || item.project.room_type === roomTypeFilter;
      const matchStatus = !statusFilter || item.project.status === statusFilter;
      return matchSearch && matchRoomType && matchStatus;
    });
  }, [items, searchQuery, roomTypeFilter, statusFilter]);

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  const analyzedCount = items.filter((i) => i.analysis_status === "COMPLETED").length;
  const withDesignsCount = items.filter((i) => i.design_generation_count > 0).length;

  const tableColumns = [
    { key: "project", label: "Dự án & Không gian" },
    { key: "customer", label: "Khách hàng" },
    { key: "room_type", label: "Loại phòng", align: "center" as const },
    { key: "analysis", label: "AI Vision", align: "center" as const },
    { key: "generations", label: "Thiết kế AI", align: "center" as const },
    { key: "status", label: "Trạng thái", align: "center" as const },
    { key: "created", label: "Thời gian tạo" },
    { key: "action", label: "Thao tác", align: "right" as const },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Không gian & AI Studio"
        title="Dự án phòng & Thiết kế"
        subtitle="Giám sát toàn bộ ảnh phòng khách hàng tải lên, kết quả nhận diện AI Vision và các phương án thiết kế sinh ra."
      />

      {/* 2. Top Summary KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AdminStatMiniCard
          label="Tổng dự án phòng"
          value={total}
          sub="Tất cả không gian đã khởi tạo"
          icon={DoorOpen}
        />
        <AdminStatMiniCard
          label="Đã phân tích Vision"
          value={analyzedCount}
          sub="Hoàn thành nhận diện đặc điểm"
          icon={Eye}
        />
        <AdminStatMiniCard
          label="Đã sinh phối cảnh AI"
          value={withDesignsCount}
          sub="Khách hàng đã bấm tạo thiết kế"
          icon={BrainCircuit}
        />
        <AdminStatMiniCard
          label="Tổng lượt thiết kế"
          value={items.reduce((sum, i) => sum + (i.design_generation_count || 0), 0)}
          sub="Số lượng render FLUX / AI hoàn tất"
          icon={Sparkles}
        />
      </div>

      {/* 3. Search & Filter Bar */}
      <AdminSearchFilterBar>
        <div className="relative min-w-[240px] flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] py-2.5 pl-10 pr-4 text-sm text-[#242424] placeholder:text-[#777777] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
            placeholder="Tìm theo tên dự án, ID #, khách hàng..."
          />
        </div>

        <select
          value={roomTypeFilter}
          onChange={(e) => setRoomTypeFilter(e.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả loại phòng</option>
          <option value="living_room">Phòng khách</option>
          <option value="bedroom">Phòng ngủ</option>
          <option value="kitchen">Phòng bếp</option>
          <option value="workspace">Phòng làm việc</option>
          <option value="dining_room">Phòng ăn</option>
          <option value="bathroom">Phòng tắm</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả trạng thái</option>
          <option value="CREATED">Mới tạo (Created)</option>
          <option value="ANALYZING">Đang phân tích</option>
          <option value="ANALYZED">Đã phân tích</option>
          <option value="CONFIGURED">Đã chọn sở thích</option>
          <option value="GENERATED">Đã tạo thiết kế</option>
        </select>

        {(searchQuery || roomTypeFilter || statusFilter) && (
          <button
            type="button"
            onClick={() => {
              setSearchQuery("");
              setRoomTypeFilter("");
              setStatusFilter("");
            }}
            title="Đặt lại"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] text-[#777777] transition hover:border-[#A68B6D] hover:bg-white hover:text-[#242424]"
          >
            <RotateCcw size={15} />
          </button>
        )}
      </AdminSearchFilterBar>

      {/* 4. Error Message */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {/* 5. Projects Table */}
      <AdminTableContainer>
        <AdminTable>
          <AdminTableHead columns={tableColumns} />
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="p-12 text-center text-sm font-medium text-[#777777]">
                  Đang tải danh sách dự án phòng...
                </td>
              </tr>
            ) : filteredItems.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-8">
                  <AdminEmptyState
                    icon={DoorOpen}
                    title="Không có dự án phòng nào"
                    description={
                      searchQuery || roomTypeFilter || statusFilter
                        ? "Không có dự án phòng nào phù hợp với bộ lọc hiện tại."
                        : "Khách hàng chưa tải lên dự án phòng nào."
                    }
                  />
                </td>
              </tr>
            ) : (
              filteredItems.map((item) => (
                <AdminTableRow key={item.project.id}>
                  {/* Dự án & Ảnh phòng */}
                  <AdminTableCell>
                    <div className="flex items-center gap-3.5">
                      <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] shadow-2xs">
                        {item.project.room_image_url ? (
                          <img
                            src={apiAssetUrl(item.project.room_image_url, { width: 120 })}
                            alt={item.project.title}
                            loading="lazy"
                            decoding="async"
                            className="h-full w-full object-cover transition duration-300 hover:scale-105"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-[#A68B6D]">
                            <ImageIcon size={20} />
                          </div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <Link
                          href={`/admin/room-projects/${item.project.id}`}
                          className="truncate font-bold text-[#242424] hover:text-[#2D332C] hover:underline"
                        >
                          #{item.project.id} · {item.project.title}
                        </Link>
                        <p className="truncate text-xs text-[#777777]">
                          {item.project.image_original_filename || "Ảnh phòng tải lên"}
                        </p>
                      </div>
                    </div>
                  </AdminTableCell>

                  {/* Khách hàng */}
                  <AdminTableCell>
                    <div>
                      <p className="font-bold text-[#242424]">
                        {item.customer?.full_name || "Khách hàng"}
                      </p>
                      <p className="text-xs text-[#777777]">
                        {item.customer?.email || `User #${item.project.user_id}`}
                      </p>
                    </div>
                  </AdminTableCell>

                  {/* Loại phòng */}
                  <AdminTableCell align="center">
                    <AdminBadge variant="stone" size="sm">
                      {displayRoomType(item.project.room_type) || "Chưa rõ"}
                    </AdminBadge>
                  </AdminTableCell>

                  {/* AI Vision Status */}
                  <AdminTableCell align="center">
                    {item.analysis_status ? (
                      <AdminStatusBadge status={item.analysis_status} size="sm" />
                    ) : (
                      <span className="text-xs text-[#777777] italic">Chưa phân tích</span>
                    )}
                  </AdminTableCell>

                  {/* Số lượt render */}
                  <AdminTableCell align="center">
                    <span className="inline-flex items-center gap-1 rounded-full border border-[#C9A77A]/35 bg-[#FAF8F5] px-2.5 py-0.5 text-xs font-bold text-[#2D332C]">
                      <Sparkles size={11} className="text-[#A68B6D]" />
                      {item.design_generation_count} bản vẽ
                    </span>
                  </AdminTableCell>

                  {/* Trạng thái dự án */}
                  <AdminTableCell align="center">
                    <AdminStatusBadge status={item.project.status} size="sm" />
                  </AdminTableCell>

                  {/* Thời gian */}
                  <AdminTableCell>
                    <p className="text-xs text-[#242424]">
                      {new Date(item.project.created_at).toLocaleDateString("vi-VN")}
                    </p>
                    <p className="text-[11px] text-[#777777]">
                      {new Date(item.project.created_at).toLocaleTimeString("vi-VN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </AdminTableCell>

                  {/* Thao tác */}
                  <AdminTableCell align="right">
                    <Link
                      href={`/admin/room-projects/${item.project.id}`}
                      className="inline-flex h-8 items-center gap-1 rounded-lg border border-[#2D332C]/15 bg-white px-3 text-xs font-semibold text-[#242424] shadow-2xs transition hover:border-[#A68B6D] hover:bg-[#FAF8F5]"
                    >
                      Kiểm tra
                      <ArrowUpRight size={13} className="text-[#A68B6D]" />
                    </Link>
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
