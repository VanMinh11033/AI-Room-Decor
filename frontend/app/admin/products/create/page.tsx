import { ProductForm } from "@/components/admin/ProductForm";

export default function CreateProductPage() {
  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-3xl font-bold">Thêm sản phẩm</h1>
      <ProductForm />
    </section>
  );
}

