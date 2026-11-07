"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import type { User } from "@/types/api";

export default function AdminUsersPage() {
  const { user: currentUser, loading } = useAuth("ADMIN");
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const data = await apiFetch<User[]>("/api/admin/users");
      setUsers(data);
      if (selected) {
        setSelected(data.find((item) => item.id === selected.id) || null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách người dùng.");
    }
  }

  useEffect(() => {
    if (!loading) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  async function toggleActive(user: User) {
    setError("");
    setMessage("");
    try {
      const updated = await apiFetch<User>(`/api/admin/users/${user.id}/active`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      setUsers((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setSelected(updated);
      setMessage("Đã cập nhật trạng thái tài khoản.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không cập nhật được trạng thái tài khoản.");
    }
  }

  if (loading) return <p>Đang kiểm tra quyền...</p>;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">Người dùng</h1>
        <p className="mt-2 text-sm text-black/60">Theo dõi tài khoản và kích hoạt/ngừng hoạt động khách hàng khi cần.</p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div>}
      {message && <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm font-semibold text-green-700">{message}</div>}

      <div className="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
        <div className="overflow-hidden rounded-lg border border-black/10 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/5">
              <tr>
                <th className="p-3">ID</th>
                <th className="p-3">Tên</th>
                <th className="p-3">Email</th>
                <th className="p-3">Vai trò</th>
                <th className="p-3">Trạng thái</th>
                <th className="p-3">Ngày tạo</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-t border-black/10 hover:bg-black/5">
                  <td className="p-3">#{user.id}</td>
                  <td className="p-3 font-semibold text-ink">{user.full_name}</td>
                  <td className="p-3">{user.email}</td>
                  <td className="p-3">{displayRole(user.role.name)}</td>
                  <td className="p-3">{user.is_active ? "Hoạt động" : "Ngừng hoạt động"}</td>
                  <td className="p-3">{new Date(user.created_at).toLocaleDateString("vi-VN")}</td>
                  <td className="p-3">
                    <button onClick={() => setSelected(user)} className="font-semibold text-clay hover:underline">Chi tiết</button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-black/50">Chưa có người dùng.</td></tr>}
            </tbody>
          </table>
        </div>

        <aside className="rounded-lg border border-black/10 bg-white p-5 shadow-sm">
          <h2 className="font-bold text-ink">Chi tiết người dùng</h2>
          {selected ? (
            <div className="mt-4 space-y-3 text-sm">
              <Info label="ID" value={`#${selected.id}`} />
              <Info label="Tên" value={selected.full_name} />
              <Info label="Email" value={selected.email} />
              <Info label="Vai trò" value={displayRole(selected.role.name)} />
              <Info label="Trạng thái" value={selected.is_active ? "Hoạt động" : "Ngừng hoạt động"} />
              <Info label="Ngày tạo" value={new Date(selected.created_at).toLocaleString("vi-VN")} />
              <button
                onClick={() => toggleActive(selected)}
                disabled={selected.id === currentUser?.id}
                className="mt-3 w-full rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-40"
              >
                {selected.is_active ? "Ngừng hoạt động" : "Kích hoạt lại"}
              </button>
              {selected.id === currentUser?.id && <p className="text-xs text-black/50">Không thể tự vô hiệu hóa tài khoản đang đăng nhập.</p>}
            </div>
          ) : (
            <p className="mt-4 text-sm text-black/50">Chọn một người dùng để xem chi tiết.</p>
          )}
        </aside>
      </div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-black/45">{label}</p>
      <p className="font-semibold text-ink">{value}</p>
    </div>
  );
}

function displayRole(role: string) {
  if (role === "ADMIN") return "Quản trị viên";
  if (role === "CUSTOMER") return "Khách hàng";
  return role;
}
