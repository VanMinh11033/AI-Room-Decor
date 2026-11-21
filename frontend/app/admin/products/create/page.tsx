import { ProductForm } from "@/components/admin/ProductForm";
import { AdminPageHeader } from "@/components/admin/AdminPrimitives";

export default function CreateProductPage() {
  return (
    <div className="space-y-6">
      <AdminPageHeader
        eyebrow="Khởi tạo mới"
        title="Thêm sản phẩm mới"
        subtitle="Khởi tạo sản phẩm nội thất mới trong catalog hệ thống với đầy đủ thông số kích thước và thuộc tính AI."
        backHref="/admin/products"
        backLabel="Quay lại danh mục sản phẩm"
      />
      <div className="mx-auto max-w-4xl">
        <ProductForm />
      </div>
    </div>
  );
}
