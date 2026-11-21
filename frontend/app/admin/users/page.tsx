"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Mail,
  RotateCcw,
  Search,
  Shield,
  ShieldCheck,
  UserCheck,
  Users,
  UserX,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import { displayRole } from "@/lib/display";
import type { User } from "@/types/api";
import {
  AdminBadge,
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

export default function AdminUsersPage() {
  const { user: currentUser, loading: authLoading } = useAuth("ADMIN");
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<User | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await apiFetch<User[]>("/api/admin/users");
      setUsers(data);
      if (selected) {
        setSelected(data.find((item) => item.id === selected.id) || null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách người dùng.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!authLoading) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading]);

  async function toggleActive(user: User) {
    if (user.id === currentUser?.id) {
      alert("Bạn không thể tự vô hiệu hóa tài khoản quản trị của chính mình!");
      return;
    }
    setError("");
    setMessage("");
    try {
      const updated = await apiFetch<User>(`/api/admin/users/${user.id}/active`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      setUsers((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setSelected(updated);
      setMessage(`Đã ${updated.is_active ? "kích hoạt" : "tạm khóa"} tài khoản "${updated.full_name}".`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được trạng thái tài khoản.");
    }
  }

  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        String(u.id).includes(q) ||
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q);
      const matchRole = !roleFilter || u.role.name === roleFilter;
      const matchStatus =
        !statusFilter ||
        (statusFilter === "active" ? u.is_active : !u.is_active);
      return matchSearch && matchRole && matchStatus;
    });
  }, [users, searchQuery, roleFilter, statusFilter]);

  if (authLoading) {
    return (
      <div className="rounded-[1.5rem] border border-[#2D332C]/10 bg-white p-8 text-sm font-medium text-[#777777] shadow-card">
        Đang kiểm tra quyền quản trị...
      </div>
    );
  }

  const adminCount = users.filter((u) => u.role.name === "ADMIN").length;
  const activeCount = users.filter((u) => u.is_active).length;

  const tableColumns = [
    { key: "user", label: "Tài khoản & Người dùng" },
    { key: "role", label: "Vai trò", align: "center" as const },
    { key: "status", label: "Trạng thái", align: "center" as const },
    { key: "created", label: "Ngày tham gia" },
    { key: "action", label: "Thao tác", align: "right" as const },
  ];

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <AdminPageHeader
        eyebrow="Hệ thống & Phân quyền"
        title="Quản lý người dùng"
        subtitle="Quản trị danh sách khách hàng và quản trị viên, kiểm soát quyền hạn và trạng thái kích hoạt tài khoản."
      />

      {/* 2. Top Summary KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AdminStatMiniCard
          label="Tổng người dùng"
          value={users.length}
          sub="Tất cả tài khoản hệ thống"
          icon={Users}
        />
        <AdminStatMiniCard
          label="Quản trị viên"
          value={adminCount}
          sub="Có quyền truy cập Admin Shell"
          icon={ShieldCheck}
        />
        <AdminStatMiniCard
          label="Khách hàng"
          value={users.length - adminCount}
          sub="Người dùng decor cá nhân"
          icon={UserCheck}
        />
        <AdminStatMiniCard
          label="Đang kích hoạt"
          value={activeCount}
          sub="Tài khoản đang hoạt động"
          icon={CheckCircle2}
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
            placeholder="Tìm theo tên, email, ID..."
          />
        </div>

        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả vai trò</option>
          <option value="ADMIN">Quản trị viên (ADMIN)</option>
          <option value="CUSTOMER">Khách hàng (CUSTOMER)</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] px-4 py-2.5 text-sm text-[#242424] focus:border-[#A68B6D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A77A]/25"
        >
          <option value="">Tất cả trạng thái</option>
          <option value="active">Đang hoạt động</option>
          <option value="inactive">Đã tạm khóa</option>
        </select>

        {(searchQuery || roleFilter || statusFilter) && (
          <button
            type="button"
            onClick={() => {
              setSearchQuery("");
              setRoleFilter("");
              setStatusFilter("");
            }}
            title="Đặt lại"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#2D332C]/15 bg-[#FAF8F5] text-[#777777] transition hover:border-[#A68B6D] hover:bg-white hover:text-[#242424]"
          >
            <RotateCcw size={15} />
          </button>
        )}
      </AdminSearchFilterBar>

      {/* Notifications */}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 shadow-sm">
          {error}
        </div>
      )}
      {message && (
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-800 shadow-sm">
          <CheckCircle2 size={16} className="text-emerald-600" />
          <span>{message}</span>
        </div>
      )}

      {/* 4. Main Grid: Table & Selected User Drawer */}
      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <AdminTableContainer>
          <AdminTable>
            <AdminTableHead columns={tableColumns} />
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="p-12 text-center text-sm font-medium text-[#777777]">
                    Đang tải danh sách người dùng...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8">
                    <AdminEmptyState
                      icon={Users}
                      title="Không tìm thấy người dùng nào"
                      description="Thử thay đổi từ khóa tìm kiếm hoặc bỏ các bộ lọc đã chọn."
                    />
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const isSelected = selected?.id === u.id;
                  const initials = u.full_name?.charAt(0)?.toUpperCase() || "U";

                  return (
                    <AdminTableRow
                      key={u.id}
                      onClick={() => setSelected(u)}
                      className={isSelected ? "bg-[#FAF8F5] ring-1 ring-inset ring-[#C9A77A]/40" : ""}
                    >
                      <AdminTableCell>
                        <div className="flex items-center gap-3">
                          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#2D332C]/10 bg-[#FAF8F5] text-xs font-bold text-[#2D332C]">
                            {initials}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate font-bold text-[#242424]">{u.full_name}</p>
                            <p className="truncate text-xs text-[#777777]">
                              #{u.id} · {u.email}
                            </p>
                          </div>
                        </div>
                      </AdminTableCell>

                      <AdminTableCell align="center">
                        <AdminBadge
                          variant={u.role.name === "ADMIN" ? "forest" : "stone"}
                          size="sm"
                        >
                          {displayRole(u.role.name)}
                        </AdminBadge>
                      </AdminTableCell>

                      <AdminTableCell align="center">
                        <AdminStatusBadge
                          status={u.is_active ? "ACTIVE" : "INACTIVE"}
                          customLabel={u.is_active ? "Hoạt động" : "Khóa"}
                          size="sm"
                        />
                      </AdminTableCell>

                      <AdminTableCell>
                        <span className="text-xs text-[#777777]">
                          {new Date(u.created_at).toLocaleDateString("vi-VN")}
                        </span>
                      </AdminTableCell>

                      <AdminTableCell align="right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelected(u);
                          }}
                          className="rounded-lg border border-[#2D332C]/15 bg-white px-2.5 py-1 text-xs font-semibold text-[#242424] shadow-2xs hover:bg-[#FAF8F5]"
                        >
                          Chi tiết
                        </button>
                      </AdminTableCell>
                    </AdminTableRow>
                  );
                })
              )}
            </tbody>
          </AdminTable>
        </AdminTableContainer>

        {/* Right Drawer: Selected User Details */}
        <div>
          <AdminSurfaceCard
            title={selected ? selected.full_name : "Chi tiết người dùng"}
            subtitle={selected ? `Tài khoản #${selected.id}` : "Chọn một tài khoản để xem thông tin"}
          >
            {selected ? (
              <div className="space-y-5">
                <div className="flex items-center gap-3 rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/80 p-4">
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#2D332C] text-sm font-bold text-[#C9A77A]">
                    {selected.full_name?.charAt(0)?.toUpperCase() || "U"}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-bold text-[#242424]">{selected.full_name}</p>
                    <p className="truncate text-xs text-[#777777]">{selected.email}</p>
                    <div className="mt-1 flex items-center gap-1.5">
                      <AdminBadge variant={selected.role.name === "ADMIN" ? "forest" : "stone"} size="sm">
                        {displayRole(selected.role.name)}
                      </AdminBadge>
                      <AdminStatusBadge
                        status={selected.is_active ? "ACTIVE" : "INACTIVE"}
                        customLabel={selected.is_active ? "Hoạt động" : "Đã khóa"}
                        size="sm"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="flex items-center justify-between border-b border-[#2D332C]/5 pb-2.5">
                    <span className="flex items-center gap-1.5 text-[#777777]">
                      <Mail size={13} className="text-[#A68B6D]" /> Email:
                    </span>
                    <span className="font-semibold text-[#242424]">{selected.email}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[#2D332C]/5 pb-2.5">
                    <span className="flex items-center gap-1.5 text-[#777777]">
                      <Shield size={13} className="text-[#A68B6D]" /> Quyền hạn:
                    </span>
                    <span className="font-semibold text-[#242424]">{selected.role.name}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[#2D332C]/5 pb-2.5">
                    <span className="flex items-center gap-1.5 text-[#777777]">
                      <Calendar size={13} className="text-[#A68B6D]" /> Ngày tạo tài khoản:
                    </span>
                    <span className="font-semibold text-[#242424]">
                      {new Date(selected.created_at).toLocaleString("vi-VN")}
                    </span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[#2D332C]/5 pb-2.5">
                    <span className="flex items-center gap-1.5 text-[#777777]">
                      <Clock size={13} className="text-[#A68B6D]" /> Cập nhật lần cuối:
                    </span>
                    <span className="font-semibold text-[#242424]">
                      {new Date(selected.updated_at || selected.created_at).toLocaleString("vi-VN")}
                    </span>
                  </div>
                </div>

                {/* Account Action */}
                <div className="border-t border-[#2D332C]/10 pt-4">
                  <button
                    type="button"
                    onClick={() => toggleActive(selected)}
                    disabled={selected.id === currentUser?.id}
                    className={`inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold shadow-sm transition ${
                      selected.is_active
                        ? "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-40"
                        : "border border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 disabled:opacity-40"
                    }`}
                  >
                    {selected.is_active ? (
                      <>
                        <UserX size={14} />
                        Khóa tài khoản này
                      </>
                    ) : (
                      <>
                        <UserCheck size={14} />
                        Mở khóa & Kích hoạt lại
                      </>
                    )}
                  </button>
                  {selected.id === currentUser?.id && (
                    <p className="mt-2 text-center text-[10px] italic text-[#777777]">
                      * Không thể tự vô hiệu hóa tài khoản quản trị đang đăng nhập
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <AdminEmptyState
                icon={Users}
                title="Chưa chọn tài khoản"
                description="Bấm vào một hàng người dùng trong bảng để xem chi tiết và kích hoạt."
              />
            )}
          </AdminSurfaceCard>
        </div>
      </div>
    </div>
  );
}


