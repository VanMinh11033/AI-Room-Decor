/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Camera,
  CheckCircle2,
  Clock,
  Compass,
  Eye,
  History,
  Layers3,
  Palette,
  ScanSearch,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Wand2,
} from "lucide-react";

export default function HomePage() {
  return (
    <div className="homepage-fullwidth space-y-16 md:space-y-24">
      {/* =========================================================
          1. FULL-WIDTH SPLIT HERO — BRIGHT EDITORIAL LUXURY STUDIO
      ========================================================= */}
      <section className="relative overflow-hidden rounded-[2rem] border border-[#2D332C]/10 bg-gradient-to-br from-white via-[#FAF8F5] to-[#F2ECE3] p-5 shadow-soft sm:p-8 md:p-10 lg:p-12 xl:p-16">
        {/* Subtle decorative background accents */}
        <div className="pointer-events-none absolute -right-28 -top-28 h-96 w-96 rounded-full bg-[#C9A77A]/18 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 left-1/3 h-80 w-80 rounded-full bg-[#A68B6D]/12 blur-3xl" />

        {/* Split Hero Grid: Left ~46%, Right Image ~54% on Desktop */}
        <div className="relative grid items-center gap-10 lg:grid-cols-[0.88fr_1.12fr] lg:gap-10 xl:grid-cols-[0.85fr_1.15fr] xl:gap-14">
          {/* Left Column: Editorial Content */}
          <div className="space-y-7">
            <div className="motion-fade-up">
              <span className="studio-pill">
                <Sparkles size={14} className="text-[#C9A77A]" />
                AI Interior Design Studio
              </span>
            </div>

            <h1 className="motion-fade-up motion-delay-100 max-w-2xl text-3xl font-bold leading-[1.12] tracking-tight text-[#242424] sm:text-4xl md:text-5xl xl:text-[3.4rem] 2xl:text-[3.75rem]">
              Kiến tạo không gian sống chuẩn mực cùng{" "}
              <span className="relative inline-block text-[#2D332C]">
                <span className="relative z-10 text-[#A68B6D]">Trí tuệ Nhân tạo</span>
                <span className="pointer-events-none absolute bottom-1 left-0 -z-0 h-3 w-full rounded-sm bg-[#C9A77A]/25" />
              </span>
            </h1>

            <p className="motion-fade-up motion-delay-150 max-w-2xl text-base leading-8 text-[#777777] md:text-lg">
              Tải lên bức ảnh căn phòng hiện tại, chọn ngân sách và phong cách yêu thích.{" "}
              <strong className="font-semibold text-[#242424]">AI Room Decor</strong> phân tích bố cục không gian, gợi ý sản phẩm nội thất thật từ catalog và dựng phương án thiết kế trực quan ngay trước mắt bạn.
            </p>

            {/* Primary & Secondary CTAs */}
            <div className="flex flex-wrap items-center gap-4 pt-1">
              <Link
                href="/room-projects/new"
                className="motion-fade-up motion-delay-200 primary-cta group border border-[#C9A77A]/40 bg-[#2D332C] px-7 py-4 text-sm font-semibold text-[#FAF8F5] hover:bg-[#A68B6D] hover:text-white"
              >
                Bắt đầu thiết kế với AI
                <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
              <Link
                href="/products"
                className="motion-fade-up motion-delay-300 secondary-cta group px-7 py-4 text-sm font-semibold"
              >
                Khám phá nội thất
                <ArrowUpRight
                  size={17}
                  className="text-[#A68B6D] transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                />
              </Link>
            </div>

            {/* Real Architecture Capabilities Strip */}
            <div className="motion-fade-up motion-delay-350 grid gap-4 border-t border-[#2D332C]/10 pt-7 sm:grid-cols-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#A68B6D]">AI Vision</p>
                <p className="mt-1 text-sm font-semibold text-[#242424]">Nhận diện bố cục & ánh sáng</p>
              </div>
              <div className="sm:border-l sm:border-[#2D332C]/10 sm:pl-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#A68B6D]">Smart Matching</p>
                <p className="mt-1 text-sm font-semibold text-[#242424]">Gợi ý nội thất từ Catalog thật</p>
              </div>
              <div className="sm:border-l sm:border-[#2D332C]/10 sm:pl-4">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#A68B6D]">AI Visualization</p>
                <p className="mt-1 text-sm font-semibold text-[#242424]">Tạo ảnh phối cảnh trực quan</p>
              </div>
            </div>
          </div>

          {/* Right Column (~53-55% width): Large Interior Visual + Non-Overlapping Floating Cards */}
          <div className="relative w-full xl:px-4 xl:py-3">
            {/* Decorative Architectural Backplate */}
            <div className="pointer-events-none absolute inset-1 hidden rounded-[2.25rem] border border-[#C9A77A]/35 bg-[#FAF8F5]/70 sm:block xl:inset-x-6 xl:inset-y-1 xl:rotate-1" />

            {/* Main Large Showcase Frame */}
            <div className="motion-image-reveal group relative overflow-hidden rounded-[2rem] border border-[#2D332C]/10 bg-white p-2.5 shadow-luxury sm:p-3.5">
              <div className="relative aspect-[16/10] min-h-[260px] w-full overflow-hidden rounded-[1.5rem] bg-[#FAF8F5] sm:min-h-[360px] lg:min-h-[440px] xl:min-h-[520px]">
                <img
                  src="https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=2000&q=85"
                  alt="Không gian phòng khách phong cách Modern Luxury sáng và sang trọng"
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.03]"
                />
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#2D332C]/50 via-transparent to-transparent" />
                <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-white/25 bg-[#2D332C]/80 px-4 py-2.5 text-xs text-[#FAF8F5] backdrop-blur-md sm:bottom-4 sm:left-4 sm:right-4">
                  <span className="font-semibold tracking-wide">
                    Không gian tham khảo · Modern Luxury & Minimalist
                  </span>
                  <span className="rounded-full bg-[#C9A77A]/25 px-3 py-0.5 font-semibold text-[#C9A77A]">
                    Interior Studio
                  </span>
                </div>
              </div>
            </div>

            {/* Floating Cards Container:
                - Mobile/Tablet (<1280px): 2-column grid cleanly below the image (never covers image/text)
                - Desktop (xl 1280px+): Anchored at top-left and top-right/bottom-right corners without covering left text or bottom caption */}
            <div className="mt-4 grid gap-3.5 sm:grid-cols-2 xl:mt-0">
              {/* Floating Card 1: AI Vision */}
              <div className="motion-fade-up motion-delay-250 xl:motion-float-slow z-10 rounded-2xl border border-[#C9A77A]/50 bg-white/95 p-4 shadow-soft backdrop-blur-md xl:absolute xl:left-0 xl:top-6 xl:w-64">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#2D332C] text-[#C9A77A]">
                    <ScanSearch size={18} />
                  </span>
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#A68B6D]">AI Vision</p>
                    <p className="text-xs font-bold text-[#242424]">Phân tích không gian</p>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5 text-[#777777]">
                  Nhận diện loại phòng, ánh sáng, vật thể hiện có & vùng trống.
                </p>
                <div className="mt-3 flex items-center gap-1.5">
                  <span className="h-4 w-4 rounded-full border border-[#2D332C]/15 bg-[#FAF8F5]" title="Warm Ivory" />
                  <span className="h-4 w-4 rounded-full border border-[#2D332C]/15 bg-[#E8E0D5]" title="Soft Sand" />
                  <span className="h-4 w-4 rounded-full border border-[#2D332C]/15 bg-[#A68B6D]" title="Warm Wood" />
                  <span className="h-4 w-4 rounded-full border border-[#2D332C]/15 bg-[#2D332C]" title="Deep Olive" />
                  <span className="ml-auto text-[11px] font-semibold text-[#2D332C]">Bảng màu thực</span>
                </div>
              </div>

              {/* Floating Card 2: AI Image */}
              <div className="motion-fade-up motion-delay-350 xl:motion-float-reverse z-10 rounded-2xl border border-[#C9A77A]/50 bg-[#2D332C] p-4 text-[#FAF8F5] shadow-luxury xl:absolute xl:right-0 xl:top-6 xl:w-64">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[#C9A77A]/40 bg-white/10 text-[#C9A77A]">
                    <Wand2 size={18} />
                  </span>
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#C9A77A]">AI Image</p>
                    <p className="text-xs font-bold text-white">Tạo phương án Decor</p>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5 text-[#FAF8F5]/80">
                  Phối cảnh trực quan từ ảnh phòng gốc và ảnh sản phẩm tham chiếu.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================
          2. FULL-WIDTH ASYMMETRIC BENTO GRID — 5 TÍNH NĂNG AI
      ========================================================= */}
      <section className="space-y-10">
        <div className="flex flex-col justify-between gap-4 border-b border-[#2D332C]/10 pb-6 lg:flex-row lg:items-end">
          <div>
            <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-[#A68B6D]">
              <Compass size={15} /> Hệ sinh thái tính năng AI
            </span>
            <h2 className="mt-2.5 text-3xl font-bold tracking-tight text-[#242424] md:text-4xl">
              Nền tảng thiết kế & mua sắm nội thất khép kín
            </h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-[#777777] md:text-base">
            Mỗi tính năng được thiết kế để giải quyết trọn vẹn bài toán từ lúc chụp ảnh căn phòng trống đến khi chọn mua từng món đồ nội thất.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-12">
          {/* Bento Card 1 (Span 7): AI Room Analysis */}
          <article className="studio-bento-card motion-fade-up motion-delay-100 group lg:col-span-7">
            <div className="grid h-full gap-6 md:grid-cols-[1.02fr_0.98fr] md:items-center">
              <div className="flex flex-col justify-between space-y-5">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-[#FAF8F5] px-3.5 py-1 text-xs font-bold uppercase tracking-[0.16em] text-[#A68B6D] ring-1 ring-[#C9A77A]/35">
                    <ScanSearch size={14} /> 01 · AI Room Analysis
                  </div>
                  <h3 className="mt-4 text-2xl font-bold text-[#242424] xl:text-3xl">
                    Phân tích không gian phòng bằng thị giác AI
                  </h3>
                  <p className="mt-3 text-sm leading-7 text-[#777777] md:text-base">
                    Hệ thống đọc trực tiếp bức ảnh căn phòng bạn tải lên để nhận diện loại phòng, nguồn sáng, màu sắc chủ đạo, các vật thể hiện hữu và những vùng trống có thể bố trí thêm nội thất.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2 pt-1">
                  {["Loại phòng", "Ánh sáng tự nhiên", "Màu chủ đạo", "Vật thể hiện có", "Khoảng trống decor"].map(
                    (tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-[#2D332C]/10 bg-[#FAF8F5] px-3.5 py-1.5 text-xs font-semibold text-[#2D332C]"
                      >
                        {tag}
                      </span>
                    )
                  )}
                </div>
              </div>

              <div className="relative aspect-[16/11] min-h-[240px] overflow-hidden rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5] xl:min-h-[290px]">
                <img
                  src="https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=1200&q=85"
                  alt="Minh họa phân tích bố cục và ánh sáng căn phòng"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
                <div className="absolute inset-x-3 bottom-3 rounded-xl bg-white/95 p-3 shadow-sm backdrop-blur-md">
                  <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#A68B6D]">
                    Gemini Vision Engine
                  </p>
                  <p className="mt-0.5 text-xs font-semibold text-[#242424]">
                    Trích xuất cấu trúc & bảng màu tự động
                  </p>
                </div>
              </div>
            </div>
          </article>

          {/* Bento Card 2 (Span 5): Personalized Interior Recommendations */}
          <article className="studio-bento-card motion-fade-up motion-delay-200 group flex flex-col justify-between bg-gradient-to-br from-white via-white to-[#FAF8F5] lg:col-span-5">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-[#FAF8F5] px-3.5 py-1 text-xs font-bold uppercase tracking-[0.16em] text-[#A68B6D] ring-1 ring-[#C9A77A]/35">
                <SlidersHorizontal size={14} /> 02 · Personalized Recommendations
              </div>
              <h3 className="mt-4 text-2xl font-bold text-[#242424] xl:text-3xl">
                Gợi ý nội thất cá nhân hóa theo luật
              </h3>
              <p className="mt-3 text-sm leading-7 text-[#777777] md:text-base">
                Kết hợp kết quả phân tích phòng với sở thích phong cách, màu sắc, chất liệu và ngân sách của bạn để chấm điểm mức độ phù hợp kèm giải thích rõ ràng cho từng sản phẩm.
              </p>
            </div>

            <div className="mt-6 space-y-3 rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5] p-5">
              <div className="flex items-center justify-between text-xs font-bold text-[#242424]">
                <span>Tiêu chí đối sánh đa chiều</span>
                <span className="rounded-full bg-[#2D332C] px-3 py-1 text-[11px] text-[#C9A77A]">
                  Chấm điểm 0–100%
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {["Modern Luxury", "Minimalist", "Japandi", "Scandinavian", "Gỗ tự nhiên", "Đúng ngân sách"].map(
                  (chip) => (
                    <span
                      key={chip}
                      className="rounded-lg border border-[#C9A77A]/35 bg-white px-3 py-1.5 text-xs font-medium text-[#242424]"
                    >
                      {chip}
                    </span>
                  )
                )}
              </div>
            </div>
          </article>

          {/* Bento Card 3 (Span 4): AI Image Generation */}
          <article className="studio-bento-card motion-fade-up motion-delay-200 group flex flex-col justify-between lg:col-span-4">
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[#C9A77A]/40 bg-[#2D332C] text-[#C9A77A] transition-transform duration-300 group-hover:scale-105">
                <Layers3 size={22} />
              </div>
              <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
                03 · AI Image Generation
              </p>
              <h3 className="mt-2 text-xl font-bold text-[#242424] xl:text-2xl">Tạo ảnh thiết kế AI trực quan</h3>
              <p className="mt-2.5 text-sm leading-6 text-[#777777] md:text-base">
                Sử dụng ảnh căn phòng gốc cùng ảnh tham chiếu của các sản phẩm bạn đã chọn để dựng phương án không gian hoàn chỉnh qua Cloudflare FLUX.2 Dev.
              </p>
            </div>
            <div className="mt-6 border-t border-[#2D332C]/10 pt-4">
              <Link
                href="/room-projects/new"
                className="inline-flex items-center gap-1.5 text-sm font-bold text-[#2D332C] transition-colors hover:text-[#A68B6D]"
              >
                Tạo dự án thiết kế <ArrowRight size={15} />
              </Link>
            </div>
          </article>

          {/* Bento Card 4 (Span 4): Furniture Catalog */}
          <article className="studio-bento-card motion-fade-up motion-delay-300 group flex flex-col justify-between lg:col-span-4">
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[#C9A77A]/40 bg-[#FAF8F5] text-[#2D332C] transition-colors duration-300 group-hover:bg-[#2D332C] group-hover:text-[#C9A77A]">
                <ShoppingBag size={22} />
              </div>
              <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
                04 · Furniture Catalog
              </p>
              <h3 className="mt-2 text-xl font-bold text-[#242424] xl:text-2xl">Catalog nội thất thật</h3>
              <p className="mt-2.5 text-sm leading-6 text-[#777777] md:text-base">
                Toàn bộ sản phẩm được truy xuất trực tiếp từ cơ sở dữ liệu thật. Hỗ trợ lọc theo danh mục, phong cách, vật liệu, màu sắc, loại phòng và khoảng giá.
              </p>
            </div>
            <div className="mt-6 border-t border-[#2D332C]/10 pt-4">
              <Link
                href="/products"
                className="inline-flex items-center gap-1.5 text-sm font-bold text-[#2D332C] transition-colors hover:text-[#A68B6D]"
              >
                Mở danh mục sản phẩm <ArrowRight size={15} />
              </Link>
            </div>
          </article>

          {/* Bento Card 5 (Span 4): Room Design History */}
          <article className="studio-bento-card motion-fade-up motion-delay-400 group flex flex-col justify-between lg:col-span-4">
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[#C9A77A]/40 bg-[#FAF8F5] text-[#2D332C] transition-colors duration-300 group-hover:bg-[#2D332C] group-hover:text-[#C9A77A]">
                <History size={22} />
              </div>
              <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-[#A68B6D]">
                05 · Room Design History
              </p>
              <h3 className="mt-2 text-xl font-bold text-[#242424] xl:text-2xl">Lưu trữ & lịch sử phương án</h3>
              <p className="mt-2.5 text-sm leading-6 text-[#777777] md:text-base">
                Quản lý nhiều dự án phòng, xem lại lịch sử các phương án AI đã tạo, đối chiếu danh sách nội thất đi kèm và thêm toàn bộ vào giỏ hàng.
              </p>
            </div>
            <div className="mt-6 border-t border-[#2D332C]/10 pt-4">
              <Link
                href="/room-projects"
                className="inline-flex items-center gap-1.5 text-sm font-bold text-[#2D332C] transition-colors hover:text-[#A68B6D]"
              >
                Quản lý dự án của tôi <ArrowRight size={15} />
              </Link>
            </div>
          </article>
        </div>
      </section>

      {/* =========================================================
          3. FULL-WIDTH AI DESIGN PROCESS — TIMELINE 5 BƯỚC
      ========================================================= */}
      <section className="rounded-[2rem] border border-[#2D332C]/10 bg-white p-6 shadow-card sm:p-8 md:p-12 xl:p-14">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-[#A68B6D]">
              <Clock size={15} /> Quy trình thực tế trên hệ thống
            </span>
            <h2 className="mt-2.5 text-3xl font-bold tracking-tight text-[#242424] md:text-4xl">
              5 bước từ bức ảnh căn phòng đến không gian hoàn thiện
            </h2>
          </div>
          <Link
            href="/room-projects/new"
            className="inline-flex items-center gap-2 text-sm font-bold text-[#2D332C] transition-colors hover:text-[#A68B6D]"
          >
            Bắt đầu Bước 01 ngay <ArrowRight size={16} />
          </Link>
        </div>

        <div className="relative mt-10">
          {/* Subtle Horizontal Connector Line on Desktop */}
          <div className="pointer-events-none absolute left-10 right-10 top-11 hidden h-px bg-gradient-to-r from-[#C9A77A]/20 via-[#C9A77A]/60 to-[#C9A77A]/20 lg:block" />

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
            <ProcessStep
              number="01"
              icon={Camera}
              title="Tải ảnh phòng"
              description="Tạo dự án mới và tải lên ảnh chụp căn phòng hiện tại (JPG, PNG, WebP)."
              delayClass="motion-delay-100"
            />
            <ProcessStep
              number="02"
              icon={ScanSearch}
              title="AI phân tích"
              description="Gemini Vision nhận diện loại phòng, ánh sáng, màu sắc và vùng trống."
              delayClass="motion-delay-150"
            />
            <ProcessStep
              number="03"
              icon={Palette}
              title="Chọn phong cách"
              description="Thiết lập phong cách, màu sắc, vật liệu, mục đích và ngân sách decor."
              delayClass="motion-delay-200"
            />
            <ProcessStep
              number="04"
              icon={ShoppingBag}
              title="Chọn nội thất"
              description="Xem gợi ý sản phẩm thật có điểm phù hợp cao và chọn các món yêu thích."
              delayClass="motion-delay-250"
            />
            <ProcessStep
              number="05"
              icon={Sparkles}
              title="Tạo thiết kế AI"
              description="Sinh ảnh decor AI để xem trước, so sánh phương án và đặt mua sản phẩm."
              delayClass="motion-delay-300"
            />
          </div>
        </div>
      </section>

      {/* =========================================================
          4. FULL-WIDTH BEFORE / AFTER SHOWCASE — ẢNH LỚN & RÕ NÉT
      ========================================================= */}
      <section className="overflow-hidden rounded-[2rem] border border-[#2D332C]/10 bg-gradient-to-br from-[#FAF8F5] via-white to-[#F3EFEA] p-6 shadow-soft sm:p-8 md:p-12 xl:p-14">
        <div className="grid items-center gap-10 xl:grid-cols-[1.22fr_0.78fr] xl:gap-14">
          {/* Left (~61% on Desktop): Large Before / After Visual Comparison */}
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-[#C9A77A]/40 bg-white px-3.5 py-1.5 text-xs font-semibold text-[#2D332C]">
                <Eye size={14} className="text-[#A68B6D]" /> Minh họa trực quan chế độ đối chiếu Before / After
              </span>
              <span className="text-xs font-medium text-[#777777]">
                Nguồn ảnh minh họa: Unsplash Interior Architecture
              </span>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              {/* Before Panel */}
              <div className="group relative overflow-hidden rounded-3xl border border-[#2D332C]/10 bg-white p-3 shadow-card">
                <div className="relative aspect-[16/11] min-h-[240px] overflow-hidden rounded-2xl bg-[#FAF8F5] sm:min-h-[280px]">
                  <img
                    src="https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1400&q=85"
                    alt="Minh họa không gian phòng trước khi bổ sung nội thất"
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                  <span className="absolute left-3.5 top-3.5 rounded-full bg-[#242424]/80 px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-white backdrop-blur-md">
                    Trước (Không gian gốc)
                  </span>
                </div>
                <div className="px-2 pb-1 pt-3.5">
                  <p className="text-sm font-bold text-[#242424]">Bước đầu vào: Ảnh chụp hiện trạng</p>
                  <p className="mt-1 text-xs leading-5 text-[#777777]">
                    AI giữ nguyên cấu trúc tường, cửa sổ và hướng sáng tự nhiên.
                  </p>
                </div>
              </div>

              {/* After Panel */}
              <div className="group relative overflow-hidden rounded-3xl border border-[#C9A77A]/60 bg-white p-3 shadow-soft">
                <div className="relative aspect-[16/11] min-h-[240px] overflow-hidden rounded-2xl bg-[#FAF8F5] sm:min-h-[280px]">
                  <img
                    src="https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1400&q=85"
                    alt="Minh họa không gian phòng sau khi phối cảnh nội thất"
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                  <span className="absolute left-3.5 top-3.5 inline-flex items-center gap-1.5 rounded-full bg-[#2D332C]/90 px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-[#C9A77A] backdrop-blur-md">
                    <Sparkles size={12} /> Sau (Phối cảnh nội thất)
                  </span>
                </div>
                <div className="px-2 pb-1 pt-3.5">
                  <p className="text-sm font-bold text-[#242424]">Kết quả: Phương án bố trí trực quan</p>
                  <p className="mt-1 text-xs leading-5 text-[#777777]">
                    Kết hợp các sản phẩm tham chiếu đã chọn từ catalog thật.
                  </p>
                </div>
              </div>
            </div>

            {/* Reference Product Workflow Strip */}
            <div className="rounded-2xl border border-[#2D332C]/10 bg-white/90 px-4 py-3.5 text-xs leading-5 text-[#777777] shadow-sm sm:text-sm">
              <span className="font-bold text-[#2D332C]">Lưu ý minh bạch:</span> Hình ảnh trên minh họa bố cục giao diện so sánh Before/After. Khi sử dụng thực tế, hệ thống sẽ tạo phương án trực tiếp từ{" "}
              <strong className="font-semibold text-[#242424]">ảnh căn phòng bạn tải lên</strong> và{" "}
              <strong className="font-semibold text-[#242424]">các sản phẩm thật bạn chọn</strong> trong dự án.
            </div>
          </div>

          {/* Right (~39% on Desktop): Explanation & Direct Action */}
          <div className="space-y-6">
            <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-[#A68B6D]">
              <Wand2 size={15} /> Trực quan hóa trước khi mua
            </span>
            <h2 className="text-3xl font-bold tracking-tight text-[#242424] md:text-4xl">
              So sánh trực diện Trước & Sau ngay trên từng dự án phòng
            </h2>
            <p className="text-base leading-7 text-[#777777]">
              Không còn phải tưởng tượng món đồ nội thất có hợp với căn phòng của mình hay không. Tại trang kết quả thiết kế, bạn có thể đối chiếu song song ảnh phòng gốc và phương án decor AI, xem danh sách sản phẩm đã dùng và thêm tất cả vào giỏ hàng.
            </p>

            <ul className="space-y-3.5 pt-1 text-sm leading-6 text-[#242424] md:text-base">
              <li className="flex items-start gap-3">
                <CheckCircle2 size={19} className="mt-1 shrink-0 text-[#A68B6D]" />
                <span>
                  <strong>Ảnh tham chiếu sản phẩm thật:</strong> Giữ kiểu dáng, màu sắc và đặc điểm nội thất sát với catalog nhất có thể.
                </span>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 size={19} className="mt-1 shrink-0 text-[#A68B6D]" />
                <span>
                  <strong>Lưu lịch sử nhiều phương án:</strong> Dễ dàng tạo thêm phương án mới với tổ hợp sản phẩm khác để so sánh.
                </span>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 size={19} className="mt-1 shrink-0 text-[#A68B6D]" />
                <span>
                  <strong>Mua sắm liền mạch:</strong> Thêm lẻ từng món hoặc thêm toàn bộ sản phẩm trong bản thiết kế vào giỏ hàng.
                </span>
              </li>
            </ul>

            <div className="flex flex-wrap gap-3.5 pt-2">
              <Link href="/room-projects/new" className="primary-cta group px-6 py-3.5">
                Tạo dự án phòng của bạn
                <ArrowRight size={17} className="transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
              <Link href="/room-projects" className="secondary-cta px-6 py-3.5">
                Xem các dự án đã lưu
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================
          5. FULL-WIDTH FINAL STUDIO CALL TO ACTION BANNER
      ========================================================= */}
      <section className="relative overflow-hidden rounded-[2rem] border border-[#C9A77A]/35 bg-[#2D332C] px-6 py-12 text-[#FAF8F5] shadow-luxury sm:px-10 md:px-14 md:py-16">
        <div className="pointer-events-none absolute -right-20 -top-20 h-80 w-80 rounded-full bg-[#C9A77A]/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-20 h-80 w-80 rounded-full bg-[#A68B6D]/15 blur-3xl" />

        <div className="relative flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-center">
          <div className="max-w-3xl space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-[#C9A77A]/40 bg-white/10 px-3.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#C9A77A]">
              <Sparkles size={14} /> Bắt đầu hành trình Decor
            </span>
            <h2 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
              Sẵn sàng biến căn phòng của bạn thành không gian đáng sống?
            </h2>
            <p className="text-base leading-7 text-[#FAF8F5]/80 md:text-lg">
              Khởi tạo dự án phòng mới để trải nghiệm trọn vẹn quy trình phân tích AI Vision, gợi ý nội thất cá nhân hóa và dựng ảnh thiết kế AI.
            </p>
          </div>

          <div className="flex w-full shrink-0 flex-col gap-3 sm:w-auto sm:flex-row">
            <Link
              href="/room-projects/new"
              className="group inline-flex items-center justify-center gap-2.5 rounded-xl border border-[#C9A77A]/50 bg-[#A68B6D] px-7 py-4 text-sm font-semibold tracking-wide text-white shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:bg-[#C9A77A] hover:text-[#242424] active:scale-[0.98]"
            >
              Bắt đầu thiết kế với AI
              <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
            <Link
              href="/products"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/25 bg-white/10 px-7 py-4 text-sm font-semibold tracking-wide text-[#FAF8F5] backdrop-blur-md transition-all duration-300 hover:-translate-y-0.5 hover:border-[#C9A77A] hover:bg-white hover:text-[#242424] active:scale-[0.98]"
            >
              Khám phá Catalog
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function ProcessStep({
  number,
  icon: Icon,
  title,
  description,
  delayClass,
}: {
  number: string;
  icon: typeof Camera;
  title: string;
  description: string;
  delayClass: string;
}) {
  return (
    <div
      className={`motion-fade-up ${delayClass} group relative flex flex-col justify-between rounded-2xl border border-[#2D332C]/10 bg-[#FAF8F5]/85 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-[#C9A77A] hover:bg-white hover:shadow-soft`}
    >
      <div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#C9A77A]/40 bg-white text-[#2D332C] shadow-sm transition-colors duration-300 group-hover:bg-[#2D332C] group-hover:text-[#C9A77A]">
            <Icon size={21} />
          </span>
          <span className="text-2xl font-bold tracking-tight text-[#C9A77A]/80 transition-colors duration-300 group-hover:text-[#A68B6D]">
            {number}
          </span>
        </div>
        <h3 className="mt-5 text-lg font-bold text-[#242424]">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-[#777777]">{description}</p>
      </div>
    </div>
  );
}




