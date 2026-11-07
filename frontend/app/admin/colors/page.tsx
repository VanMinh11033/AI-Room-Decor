import { LookupManager } from "@/components/admin/LookupManager";

export default function AdminColorsPage() {
  return <LookupManager title="màu sắc" publicPath="/api/colors" adminPath="/api/admin/colors" colorMode />;
}

