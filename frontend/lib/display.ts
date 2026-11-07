type NullableText = string | null | undefined;

function normalize(value: NullableText) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}

function lookup(value: NullableText, dictionary: Record<string, string>) {
  if (!value) return "";
  const normalized = normalize(value);
  return dictionary[normalized] || String(value);
}

const categoryLabels: Record<string, string> = {
  accessories: "Phụ kiện decor",
  bed: "Giường",
  bedding: "Bộ chăn ga",
  chair: "Ghế",
  lighting: "Đèn trang trí",
  "plant decor": "Cây trang trí",
  rug: "Thảm",
  sofa: "Sofa",
  storage: "Tủ/kệ lưu trữ",
  table: "Bàn",
  "wall decor": "Trang trí tường",
};

const materialLabels: Record<string, string> = {
  bamboo: "Tre",
  fabric: "Vải",
  glass: "Kính",
  leather: "Da",
  metal: "Kim loại",
  plastic: "Nhựa",
  rattan: "Mây",
  stone: "Đá",
  wood: "Gỗ",
};

const styleLabels: Record<string, string> = {
  bohemian: "Bohemian",
  classic: "Cổ điển",
  industrial: "Công nghiệp",
  japandi: "Japandi",
  luxury: "Sang trọng",
  minimalist: "Tối giản",
  modern: "Hiện đại",
  rustic: "Mộc mạc",
  scandinavian: "Bắc Âu",
  vintage: "Vintage",
};

const roomTypeLabels: Record<string, string> = {
  bathroom: "Phòng tắm",
  bedroom: "Phòng ngủ",
  "dining room": "Phòng ăn",
  kitchen: "Nhà bếp",
  "living room": "Phòng khách",
  office: "Phòng làm việc",
  studio: "Studio",
  "study room": "Phòng học",
  workspace: "Góc làm việc",
};

const colorLabels: Record<string, string> = {
  beige: "Be",
  black: "Đen",
  blue: "Xanh dương",
  brass: "Đồng thau",
  brown: "Nâu",
  cream: "Kem",
  gray: "Xám",
  green: "Xanh lá",
  navy: "Xanh navy",
  oak: "Gỗ sồi",
  orange: "Cam",
  pink: "Hồng",
  purple: "Tím",
  red: "Đỏ",
  sage: "Xanh sage",
  terracotta: "Đất nung",
  walnut: "Gỗ óc chó",
  white: "Trắng",
  yellow: "Vàng",
};

const statusLabels: Record<string, string> = {
  active: "Đang bán",
  analyzing: "Đang phân tích",
  available: "Có sẵn",
  cancelled: "Đã hủy",
  completed: "Hoàn tất",
  confirmed: "Đã xác nhận",
  draft: "Bản nháp",
  failed: "Thất bại",
  generating: "Đang tạo",
  inactive: "Tạm ẩn",
  out_of_stock: "Hết hàng",
  "out of stock": "Hết hàng",
  pending: "Đang chờ",
  processing: "Đang xử lý",
  shipped: "Đang giao",
  success: "Thành công",
};

export function displayCategory(value: NullableText) {
  return lookup(value, categoryLabels);
}

export function displayMaterial(value: NullableText) {
  return lookup(value, materialLabels);
}

export function displayStyle(value: NullableText) {
  return lookup(value, styleLabels);
}

export function displayRoomType(value: NullableText) {
  return lookup(value, roomTypeLabels);
}

export function displayColor(value: NullableText) {
  return lookup(value, colorLabels);
}

export function displayStatus(value: NullableText) {
  return lookup(value, statusLabels);
}

export function joinDisplay<T>(items: T[] | undefined, selector: (item: T) => string, fallback = "-") {
  const text = (items || []).map(selector).filter(Boolean).join(", ");
  return text || fallback;
}
