import { LookupManager } from "@/components/admin/LookupManager";

export default function AdminRoomTypesPage() {
  return <LookupManager title="loại phòng" publicPath="/api/room-types" adminPath="/api/admin/room-types" />;
}

