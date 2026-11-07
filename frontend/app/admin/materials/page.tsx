import { LookupManager } from "@/components/admin/LookupManager";

export default function AdminMaterialsPage() {
  return <LookupManager title="vật liệu" publicPath="/api/materials" adminPath="/api/admin/materials" />;
}

