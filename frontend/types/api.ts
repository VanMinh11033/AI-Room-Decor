export type Role = {
  id: number;
  name: "CUSTOMER" | "ADMIN";
};

export type User = {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  role: Role;
  created_at: string;
  updated_at: string;
};

export type UserProfile = {
  id: number;
  phone?: string | null;
  address?: string | null;
  preferred_style?: string | null;
  preferred_colors?: string | null;
  preferred_materials?: string | null;
};

export type Category = {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
};

export type CatalogItem = {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
};

export type Color = {
  id: number;
  name: string;
  slug: string;
  hex_code?: string | null;
  is_active: boolean;
};

export type ProductStatus = "DRAFT" | "ACTIVE" | "INACTIVE";

export type Product = {
  id: number;
  category_id: number;
  category: Category;
  name: string;
  slug: string;
  description?: string | null;
  price: string;
  stock_quantity: number;
  style?: string | null;
  color?: string | null;
  material?: string | null;
  room_type?: string | null;
  width?: string | null;
  height?: string | null;
  depth?: string | null;
  weight?: string | null;
  tags?: string | null;
  status: ProductStatus;
  is_active: boolean;
  images: { id: number; image_url: string; alt_text?: string | null; sort_order: number; is_primary: boolean }[];
  materials: CatalogItem[];
  styles: CatalogItem[];
  room_types: CatalogItem[];
  colors: Color[];
};

export type Paginated<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};

export type DashboardStats = {
  total_users: number;
  total_products: number;
  active_products: number;
  total_room_projects: number;
  total_design_generations: number;
  total_orders: number;
  pending_orders: number;
  completed_orders: number;
  total_ai_calls: number;
  completed_order_revenue: string;
  system_status: string;
};

export type AdminRecentOrder = {
  id: number;
  customer?: User | null;
  total_amount: string;
  status: string;
  created_at: string;
};

export type AdminRecentRoomProject = {
  id: number;
  title: string;
  customer?: User | null;
  status: string;
  room_type?: string | null;
  analysis_status?: string | null;
  design_generation_count: number;
  created_at: string;
};

export type AdminAIUsage = {
  id: number;
  user_id?: number | null;
  room_project_id?: number | null;
  provider: string;
  model: string;
  task_type: string;
  status: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: string;
  error_code?: string | null;
  created_at: string;
};

export type AdminDashboard = {
  stats: DashboardStats;
  recent_orders: AdminRecentOrder[];
  recent_room_projects: AdminRecentRoomProject[];
  recent_ai_usage: AdminAIUsage[];
};

export type RoomProject = {
  id: number;
  user_id: number;
  title: string;
  room_type?: string | null;
  room_image_url?: string | null;
  image_original_filename?: string | null;
  image_content_type?: string | null;
  image_size_bytes?: number | null;
  status: string;
  preference_configured: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminRoomProjectListItem = {
  project: RoomProject;
  customer?: User | null;
  analysis_status?: string | null;
  design_generation_count: number;
};

export type AdminRoomProjectListResponse = {
  total: number;
  items: AdminRoomProjectListItem[];
};

export type RoomAnalysis = {
  id: number;
  room_project_id: number;
  user_id: number;
  image_checksum: string;
  status: string;
  provider: string;
  model: string;
  room_type?: string | null;
  dominant_colors: { name: string; hex?: string | null; percentage?: number | null }[];
  existing_objects: { name: string; confidence: number }[];
  empty_areas: { location: string; description?: string | null; suitable_for_decor: boolean }[];
  lighting?: { type: string; level: string } | null;
  design_characteristics: string[];
  layout_summary?: string | null;
  confidence?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type RoomPreference = {
  id: number;
  room_project_id: number;
  user_id: number;
  budget_min?: string | null;
  budget_max?: string | null;
  currency: string;
  purpose?: string | null;
  notes?: string | null;
  styles: CatalogItem[];
  colors: Color[];
  materials: CatalogItem[];
  categories: Category[];
  created_at: string;
  updated_at: string;
};

export type ProductRecommendation = {
  product: Product;
  score: number;
  reasons: string[];
  breakdown: Record<string, number>;
};

export type RecommendationResponse = {
  room_project_id: number;
  analysis_id: number;
  preference: RoomPreference;
  total: number;
  items: ProductRecommendation[];
};

export type DesignGeneration = {
  id: number;
  room_project_id: number;
  user_id: number;
  status: "GENERATING" | "COMPLETED" | "FAILED" | string;
  provider: string;
  model: string;
  prompt_version: string;
  source_image_path: string;
  generated_image_url?: string | null;
  generated_image_path?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  latency_ms?: number | null;
  completed_at?: string | null;
  products: Product[];
  created_at: string;
  updated_at: string;
};

export type DesignGenerationListResponse = {
  total: number;
  items: DesignGeneration[];
};

export type AdminRoomProjectDetail = {
  project: RoomProject;
  customer?: User | null;
  latest_analysis?: RoomAnalysis | null;
  preference?: RoomPreference | null;
  design_generations: DesignGeneration[];
};

export type AdminAIUsageSummary = {
  total_calls: number;
  success_calls: number;
  failed_calls: number;
  gemini_calls: number;
  cloudflare_calls: number;
  local_fallback_calls: number;
  total_tokens: number;
  total_cost: string;
};

export type AdminAIUsageListResponse = {
  total: number;
  summary: AdminAIUsageSummary;
  items: AdminAIUsage[];
};

export type CartItem = {
  id: number;
  product_id: number;
  quantity: number;
  unit_price: string;
  subtotal: string;
  product: Product | null;
};

export type Cart = {
  id: number;
  items: CartItem[];
  subtotal: string;
  total_items: number;
};

export type OrderItem = {
  id: number;
  product_id: number;
  quantity: number;
  unit_price: string;
  subtotal: string;
  product: Product | null;
};

export type Order = {
  id: number;
  user_id: number;
  status: string;
  total_amount: string;
  shipping_address?: string | null;
  customer?: User | null;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
};

export type OrderListResponse = {
  total: number;
  items: Order[];
};

export type ProductImageCandidate = {
  id: number;
  product_id: number;
  product_name?: string | null;
  source: string;
  source_page_url?: string | null;
  image_url: string;
  public_url?: string | null;
  license?: string | null;
  license_url?: string | null;
  attribution?: string | null;
  creator?: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | string;
  width?: number | null;
  height?: number | null;
  file_format?: string | null;
  semantic_decision?: string | null;
  created_at: string;
};

export type ProductImageCandidateList = {
  total: number;
  page: number;
  page_size: number;
  items: ProductImageCandidate[];
};

export type ProductImageCandidateSearchResult = {
  product_id: number;
  staged: number;
  skipped: number;
};
