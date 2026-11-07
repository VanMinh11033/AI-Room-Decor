import { LookupManager } from "@/components/admin/LookupManager";

export default function AdminCategoriesPage() {
  return <LookupManager title="danh mục" publicPath="/api/categories" adminPath="/api/admin/categories" />;
}

