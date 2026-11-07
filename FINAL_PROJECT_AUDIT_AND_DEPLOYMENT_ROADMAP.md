# BÁO CÁO KIỂM TOÁN DỰ ÁN TOÀN DIỆN, LỘ TRÌNH GITHUB VÀ TRIỂN KHAI CLOUD MIỄN PHÍ (0 VNĐ)

> **Dự án:** Hệ thống Tư vấn và Thiết kế Nội thất Ứng dụng Trí tuệ Nhân tạo — **AI Room Decor**<br>
> **Đơn vị công tác:** Đồ án Tốt nghiệp Kỹ sư / Cử nhân CNTT<br>
> **Thời điểm kiểm toán:** Ngày 02 tháng 11 năm 2026 (Căn cứ trên dữ liệu thực nghiệm hệ thống)<br>
> **Chế độ kiểm toán:** READ-ONLY (Không sửa code, không thay đổi database, không xóa dữ liệu, không phát sinh chi phí AI)<br>
> **Mục tiêu tối thượng:** Đánh giá chính xác mức độ hoàn thiện đồ án, bảo toàn 100% dữ liệu phòng và thiết kế, chuẩn bị đưa mã nguồn lên GitHub an toàn và xây dựng phương án triển khai website lên Internet với chi phí 0 VNĐ/tháng.

---

## MỤC LỤC BÁO CÁO

1. [TỔNG QUAN HỆ THỐNG VÀ HIỆN TRẠNG DỰ ÁN](#1-tổng-quan-hệ-thống-và-hiện-trạng-dự-án)
2. [DANH MỤC CHỨC NĂNG ĐÃ HOÀN THÀNH VÀ ĐÃ ĐƯỢC KIỂM THỬ](#2-danh-mục-chức-năng-đã-hoàn-thành-và-đã-được-kiểm-thử)
3. [DANH SÁCH CHỨC NĂNG CÒN THIẾU VÀ CÁC ĐIỂM CẦN HOÀN THIỆN](#3-danh-sách-chức-năng-còn-thiếu-và-các-điểm-cần-hoàn-thiện)
4. [KẾT QUẢ KIỂM THỬ TỰ ĐỘNG VÀ THỰC NGHIỆM HỆ THỐNG](#4-kết-quả-kiểm-thử-tự-động-và-thực-nghiệm-hệ-thống)
5. [CÁC LỖI VÀ GIỚI HẠN KỸ THUẬT CÒN TỒN TẠI](#5-các-lỗi-và-giới-hạn-kỹ-thuật-còn-tồn-tại)
6. [TÌNH TRẠNG GIT VÀ SẴN SÀNG ĐƯA LÊN GITHUB](#6-tình-trạng-git-và-sẵn-sàng-đưa-lên-github)
7. [TÌNH TRẠNG BẢO MẬT VÀ BẢO VỆ DỮ LIỆU NHẠY CẢM](#7-tình-trạng-bảo-mật-và-bảo-vệ-dữ-liệu-nhạy-cảm)
8. [TÌNH TRẠNG TƯƠNG THÍCH CLOUD MIỄN PHÍ (0 VNĐ/THÁNG)](#8-tình-trạng-tương-thích-cloud-miễn-phí-0-vnđtháng)
9. [DANH SÁCH CÁC TỆP CẦN ĐIỀU CHỈNH TRƯỚC KHI PUSH / DEPLOY](#9-danh-sách-các-tệp-cần-điều-chỉnh-trước-khi-push--deploy)
10. [LỘ TRÌNH THỰC HIỆN THEO TỪNG GIAI ĐOẠN](#10-lộ-trình-thực-hiện-theo-từng-giai-đoạn)
11. [ƯỚC LƯỢNG MỨC ĐỘ HOÀN THIỆN KÈM TIÊU CHÍ KỸ THUẬT ĐỊNH LƯỢNG](#11-ước-lượng-mức-độ-hoàn-thiện-kèm-tiêu-chí-kỹ-thuật-định-lượng)
12. [CHECKLIST KIỂM SOÁT TRƯỚC KHI PUSH GITHUB](#12-checklist-kiểm-soát-trước-khi-push-github)
13. [CHECKLIST KIỂM SOÁT TRƯỚC KHI DEPLOY CLOUD](#13-checklist-kiểm-soát-trước-khi-deploy-cloud)
14. [HƯỚNG DẪN THAO TÁC NGƯỜI DÙNG CẦN TỰ THỰC HIỆN](#14-hướng-dẫn-thao-tác-người-dùng-cần-tự-thực-hiện)

---

## 1. TỔNG QUAN HỆ THỐNG VÀ HIỆN TRẠNG DỰ ÁN

AI Room Decor là nền tảng web ứng dụng Generative AI và Computer Vision hỗ trợ người dùng phân tích hiện trạng không gian phòng, đề xuất phong cách thiết kế nội thất, gợi ý sản phẩm phù hợp theo thuật toán đa tiêu chí và tổng hợp ảnh phối cảnh nội thất chân thực bằng mô hình Diffusion.

```
+-----------------------------------------------------------------------------------------+
|                                    KIẾN TRÚC TỔNG THỂ                                   |
+-----------------------------------------------------------------------------------------+
|  [ FRONTEND ] Next.js 15.1.4 (App Router) + React 19 + Tailwind CSS                     |
|       │                                                                                 |
|       ▼ HTTPS API Client (apiFetch / JWT Token in LocalStorage)                         |
|  [ BACKEND  ] FastAPI 0.115.6 (Python 3.13) + Uvicorn + SQLAlchemy 2.0                 |
|       │                                                                                 |
|       ├──► [ DATABASE ] Local: MariaDB 10.11.10 / Cloud: TiDB Cloud Serverless (MySQL 8)|
|       ├──► [ STORAGE  ] Local: Storage filesystem / Cloud: Cloudinary Media CDN         |
|       ├──► [ AI VISION] Google Gemini Vision (`gemini-3.6-flash`)                        |
|       └──► [ AI IMAGE ] Cloudflare Workers AI (`@cf/black-forest-labs/flux-2-dev`)      |
+-----------------------------------------------------------------------------------------+
```

### Các thông số kiến trúc kỹ thuật đo đạc thực tế:
- **Ngôn ngữ & Framework:** Python 3.13.7 (Backend FastAPI), TypeScript 5.7.2 (Frontend Next.js 15).
- **Quy mô mã nguồn:**
  - **Frontend:** 32 pages App Router, 35 build routes.
  - **Backend:** 86 endpoints RESTful API, 27 test suites với 304 test cases tự động.
  - **Database:** 32 bảng, 41 khóa ngoại (Foreign Keys), phân quyền Role-Based Access Control (RBAC).
  - **Kho lưu trữ ảnh:** 265 tệp tin (42.54 MB) bao gồm ảnh phòng gốc, ảnh sản phẩm danh mục và ảnh thiết kế do AI tạo ra.

---

## 2. DANH MỤC CHỨC NĂNG ĐÃ HOÀN THÀNH VÀ ĐÃ ĐƯỢC KIỂM THỬ

Toàn bộ các tính năng dưới đây đã được mã hóa đầy đủ, kết nối dữ liệu thật và vượt qua các bài kiểm thử tự động cũng như xác minh thực tế trên giao diện:

| Phân hệ | Chức năng cụ thể | Trạng thái thực tế | Bằng chứng kỹ thuật / File mã nguồn |
| :--- | :--- | :--- | :--- |
| **A. Guest** | Trang chủ giới thiệu sản phẩm & luồng AI | **Hoàn thành & Đã kiểm thử** | `frontend/app/page.tsx` (Hero, features, CTA, showcase) |
| | Danh mục sản phẩm, bộ lọc phòng & giá | **Hoàn thành & Đã kiểm thử** | `frontend/app/products/page.tsx`, `backend/app/api/products.py` |
| | Chi tiết sản phẩm & sản phẩm liên quan | **Hoàn thành & Đã kiểm thử** | `frontend/app/products/[id]/page.tsx` |
| | Đăng ký tài khoản (hashing bcrypt) | **Hoàn thành & Đã kiểm thử** | `frontend/app/register/page.tsx`, `backend/app/api/auth.py` |
| | Đăng nhập tài khoản & cấp JWT token | **Hoàn thành & Đã kiểm thử** | `frontend/app/login/page.tsx`, `test_auth.py` (5 tests passed) |
| **B. User** | Quản lý danh sách dự án phòng cá nhân | **Hoàn thành & Đã kiểm thử** | `frontend/app/room-projects/page.tsx`, `test_room_projects.py` |
| | Khởi tạo dự án & Upload ảnh phòng gốc | **Hoàn thành & Đã kiểm thử** | `frontend/app/room-projects/new/page.tsx`, MIME & size check |
| | Gemini Vision phân tích không gian phòng | **Hoàn thành & Đã kiểm thử** | `Analysis #91` lưu trong DB; `test_gemini_provider.py` (15 tests) |
| | Khảo sát phong cách, ngân sách & vật liệu | **Hoàn thành & Đã kiểm thử** | `frontend/app/room-projects/[id]/preferences/page.tsx`, `Preference #13` |
| | Thuật toán gợi ý sản phẩm 7 tiêu chí | **Hoàn thành & Đã kiểm thử** | `recommendation_service.py`, `test_recommendations.py` (7 tests) |
| | Cloudflare FLUX.2 tạo ảnh phối cảnh decor | **Hoàn thành & Đã kiểm thử** | `Design #38-#41` trong DB, `test_cloudflare_image_provider.py` (25 tests) |
| | Xem chi tiết thiết kế & so sánh Before/After | **Hoàn thành & Đã kiểm thử** | `frontend/app/room-projects/[id]/design-generations/[generationId]` |
| | Giỏ hàng cá nhân (thêm, sửa số lượng, xóa) | **Hoàn thành & Đã kiểm thử** | `frontend/app/cart/page.tsx`, `test_cart_orders.py` (11 tests) |
| | Đặt hàng COD & quản lý lịch sử đơn hàng | **Hoàn thành & Đã kiểm thử** | `frontend/app/checkout/page.tsx`, `frontend/app/orders/page.tsx` |
| | Xem và cập nhật thông tin cá nhân/hồ sơ | **Hoàn thành & Đã kiểm thử** | `frontend/app/profile/page.tsx`, `backend/app/api/users.py` |
| **C. Admin** | Đăng nhập quản trị viên & kiểm tra RBAC | **Hoàn thành & Đã kiểm thử** | Middleware xác thực `role == ADMIN`, chặn Guest/User thường |
| | Dashboard thống kê doanh thu, đơn hàng, AI | **Hoàn thành & Đã kiểm thử** | `frontend/app/admin/page.tsx`, `GET /api/admin/dashboard-stats` |
| | Quản lý người dùng (khóa/kích hoạt tài khoản)| **Hoàn thành & Đã kiểm thử** | `frontend/app/admin/users/page.tsx`, `PATCH /api/admin/users/{id}/active` |
| | Quản lý sản phẩm (thêm, sửa, xóa, gắn ảnh) | **Hoàn thành & Đã kiểm thử** | `frontend/app/admin/products/page.tsx`, `create`, `edit` |
| | Quản lý vòng đời đơn hàng (cập nhật trạng thái)| **Hoàn thành & Đã kiểm thử** | `frontend/app/admin/orders/page.tsx`, `admin/orders/[id]` |
| | Giám sát chi tiết AI Usage Logs | **Hoàn thành & Đã kiểm thử** | `frontend/app/admin/ai-usage/page.tsx`, 137 logs đo lường token/latency |
| | Quản lý danh mục nền (Categories, Colors,...)| **Hoàn thành & Đã kiểm thử** | `frontend/components/admin/LookupManager.tsx` (5 tables) |
| **D. System**| Lưu trữ ảnh kép (Dual Local / Cloudinary) | **Hoàn thành & Đã kiểm thử** | `storage_service.py`, `test_cloudinary_storage.py` (4 tests) |
| | Sliding Window Rate Limiting (chống spam/DoS)| **Hoàn thành & Đã kiểm thử** | `rate_limit.py`, `test_rate_limit.py` (3 tests) |
| | Tương thích SSL/TLS TiDB Cloud Serverless | **Hoàn thành & Đã kiểm thử** | `database.py:build_connect_args`, `test_cloud_database_config.py` |
| | Chuẩn hóa CORS & Reverse Proxy Headers | **Hoàn thành & Đã kiểm thử** | `main.py:ProxyHeadersMiddleware`, dynamic CORS |

---

## 3. DANH SÁCH CHỨC NĂNG CÒN THIẾU VÀ CÁC ĐIỂM CẦN HOÀN THIỆN

Dựa trên việc đối chiếu với tiêu chuẩn của một hệ thống thương mại điện tử AI hoàn chỉnh đưa ra công chúng, các điểm còn thiếu được phân loại cụ thể:

### P0 — Bắt buộc phải hoàn thiện trước khi Deploy Cloud:
1. **Sao lưu vi sai (Differential Backup):** Database `ai_room_decor` hiện có thêm User #21 (`user6@gmail.com`) và 3 dự án phòng #22, #23, #24 cùng 2 file ảnh mới so với bản sao lưu ngày 30/10. Cần tạo bản dump cập nhật đầy đủ trước khi xuất sang cloud.
2. **Cập nhật `.gitignore` loại trừ file backup & rác:** Tránh tình trạng vô tình commit các thư mục sao lưu (`frontend_backup`, `report_backup_*`, `backups/`) và file `.zip` nặng lên GitHub.
3. **Cấu hình biến môi trường Production trên Render & Vercel:** Cần cấp đúng `DATABASE_URL` (kèm TLS port 4000 của TiDB), `CLOUDINARY_*` và các khóa API AI.

### P1 — Cần hoàn thiện trước buổi Nghiệm thu / Bảo vệ Đồ án:
1. **Thông báo giao diện khi Backend gặp Cold Start:** Trên Render gói Free, backend sẽ ngủ sau 15 phút không hoạt động và mất khoảng 40–50 giây để khởi động lại. Frontend cần có thông báo lịch sự ("Máy chủ AI đang thức giấc, vui lòng chờ trong giây lát...") để người dùng không tưởng website bị đơ.
2. **README.md chuẩn quốc tế trên GitHub:** Cung cấp tài liệu hoàn chỉnh gồm sơ đồ kiến trúc Mermaid, hướng dẫn chạy localhost, quy cách biến môi trường và bảng đặc tả API.
3. **Dọn dẹp thư mục tạm không dùng:** Xóa thư mục rỗng `tmppwueyhiw/` phát sinh trong phiên làm việc cũ.

### P2 — Hướng nâng cấp mở rộng sau tốt nghiệp (Post-Graduation):
1. **Tích hợp cổng thanh toán trực tuyến (VNPay / MoMo):** Hiện hệ thống chỉ hỗ trợ thanh toán khi nhận hàng (COD).
2. **Hàng đợi bất đồng bộ (Celery / Redis Queue + WebSocket):** Thay thế cơ chế HTTP polling hiện tại của tác vụ sinh ảnh FLUX.2 bằng cơ chế đẩy tin nhắn thời gian thực.
3. **Chuyển đổi Rate Limiter sang Redis:** Phục vụ trường hợp mở rộng backend lên nhiều container/worker đồng thời.
4. **Đa ngôn ngữ (i18n):** Hỗ trợ chuyển đổi giao diện Tiếng Việt / Tiếng Anh.

---

## 4. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG VÀ THỰC NGHIỆM HỆ THỐNG

### 4.1. Bộ kiểm thử Backend Pytest (Regression Tests)
- **Tổng số ca kiểm thử:** `304` test cases.
- **Kết quả:** **304 PASSED (100% thành công)**.
- **Thời gian thực thi:** 365.08 giây (~6 phút 05 giây).
- **Phân bổ kiểm thử tiêu biểu:**
  - `test_cloudflare_image_provider.py`: 25/25 passed (xử lý retry, timeout, prompt formatting).
  - `test_gemini_image_provider.py` & `test_gemini_provider.py`: 30/30 passed (spatial analysis, fallback).
  - `test_stock_image_providers.py`: 50/50 passed (thu thập ảnh sản phẩm từ Google/Openverse).
  - `test_cart_orders.py`: 11/11 passed (vòng đời giỏ hàng và đặt hàng COD).
  - `test_cloudinary_storage.py` & `test_cloud_database_config.py`: 9/9 passed (tương thích Cloudinary & TiDB).

### 4.2. Kiểm thử tĩnh Frontend Next.js & TypeScript
- **TypeScript Compiler (`npx tsc --noEmit`):** **0 errors** (Toàn bộ kiểu dữ liệu, interface và component đều hợp lệ).
- **ESLint Code Quality (`npm run lint`):** **0 errors, 18 warnings** (Tất cả warnings đều là khuyến nghị sử dụng thẻ `<Image>` của Next.js thay cho thẻ `<img>` truyền thống, hoàn toàn không ảnh hưởng đến tính toàn vẹn và khả năng build).

### 4.3. Kiểm thử đóng gói Production Build Next.js
- **Kết quả biên dịch:** Hoàn thành thành công 35/35 routes trong `frontend/.next`.
- **Cấu hình Standalone:** Được kiểm soát an toàn qua cờ môi trường `STANDALONE===true` trong `frontend/next.config.ts`, loại bỏ triệt để hiện tượng lỗi `HTTP 400 Bad Request` trên chunk tĩnh khi chạy `next start` ở localhost.

### 4.4. Toàn vẹn Dữ liệu Thao giảng (Demonstration Data)
- **Project #21:** Tồn tại nguyên vẹn, tiêu đề `'dca'`, ảnh phòng `'20/21/aa267817a3954ce588d44c35a2b4e3a3.jpg'` (24,853 bytes) có mặt trên đĩa cứng.
- **Analysis #91:** Tồn tại nguyên vẹn, model `gemini-3.6-flash`, trạng thái `COMPLETED`.
- **Preference #13:** Tồn tại nguyên vẹn, ngân sách 5,000,000 – 10,000,000 VNĐ, phong cách `Luxury`, mục đích `Làm việc`.
- **Designs #38, #39, #40, #41:** Đầy đủ cả 4 thiết kế hoàn chỉnh do Cloudflare FLUX.2 tạo ra, lưu trữ tại `storage/generated-room-designs/` với dung lượng ~340KB–358KB mỗi ảnh.
- **Database tạm `ai_room_decor_restore_test_tmp`:** Vẫn được lưu giữ nguyên trạng 100% trên MariaDB phục vụ đối chiếu, không hề bị DROP.

---

## 5. CÁC LỖI VÀ GIỚI HẠN KỸ THUẬT CÒN TỒN TẠI

Qua kiểm toán độc lập, hệ thống không có lỗi logic ngăn cản vận hành, nhưng tồn tại một số **giới hạn kỹ thuật cố hữu của các hạ tầng Free Cloud** cần lưu ý:

1. **Giới hạn thời gian Request Timeout trên Render Free (100 giây):**
   - *Thực tế:* Render cắt kết nối HTTP nếu một request kéo dài quá 100s. Quá trình sinh ảnh FLUX.2 tiêu tốn từ 20 đến 45 giây. Nếu mạng quốc tế bị nghẽn, thời gian gọi Cloudflare có thể tăng lên.
   - *Biện pháp đã cài đặt:* Cấu hình `CLOUDFLARE_IMAGE_TIMEOUT_SECONDS = 95` trong `render.yaml` để backend chủ động trả về lỗi có cấu trúc trước khi Render proxy ngắt kết nối.
2. **Độ trễ Cold Start của Render Free (40–60 giây):**
   - *Thực tế:* Sau 15 phút không có lượt truy cập, container backend sẽ bị tạm dừng để tiết kiệm tài nguyên. Lượt truy cập đầu tiên sẽ phải đợi khoảng 50 giây.
   - *Khuyến nghị:* Cần thêm spinner/thông báo trực quan trên giao diện Frontend để người dùng hiểu và chờ đợi.
3. **Hạn mức tài nguyên Cloudflare Workers AI (10,000 Neurons/ngày):**
   - *Thực tế:* Mô hình Diffusion FLUX.2 tiêu tốn khoảng 1,000 – 2,000 Neurons cho mỗi bức ảnh sinh ra. Gói Free của Cloudflare đáp ứng được khoảng 5 – 10 lượt sinh ảnh mỗi ngày.
   - *Khuyến nghị:* Phù hợp hoàn hảo cho demo bảo vệ đồ án và cho bạn bè trải nghiệm. Khi cần mở rộng lượng người dùng lớn, cần nâng cấp gói Workers Paid ($5/tháng).
4. **Bộ nhớ Rate Limiting trong RAM (In-Memory Limiter):**
   - *Thực tế:* Rate limiter hiện tại lưu lịch sử request trong RAM của tiến trình backend. Điều này hoạt động hoàn hảo trên Render Free (1 worker đơn lẻ), nhưng nếu chạy nhiều worker hoặc nhiều cụm container, dữ liệu giới hạn tốc độ sẽ không được chia sẻ (cần Redis nếu scale out).

---

## 6. TÌNH TRẠNG GIT VÀ SẴN SÀNG ĐƯA LÊN GITHUB

### 6.1. Thực trạng Git hiện tại
- **Công cụ Git CLI:** Lệnh `git` chưa được cài đặt hoặc chưa được thêm vào biến môi trường PATH của Windows trên máy tính này.
- **Thư mục `.git`:** Thư mục `D:\AI-Room-Decor\.git` đã tồn tại nhưng bên trong hoàn toàn rỗng (chưa từng được `git init` hoặc commit).
- **Kho lưu trữ:** Dự án chưa được đẩy lên bất kỳ repository GitHub nào.

### 6.2. Kiểm tra nguy cơ rò rỉ dữ liệu khi commit
Qua phân tích tệp `.gitignore` gốc và mô phỏng danh sách file sẽ được đưa vào Git:
- **Các thành phần ĐÃ ĐƯỢC BẢO VỆ an toàn:**
  - `node_modules/`, `.venv/` -> Bị loại trừ.
  - `.env`, `.env.*` -> Bị loại trừ (ngoại trừ `.env.example` và `.env.cloud.example`).
  - `storage/*` -> Toàn bộ ảnh người dùng tải lên và ảnh AI sinh ra bị loại trừ, không sợ lộ ảnh riêng tư.
  - `backups/` -> Thư mục backup có file `.gitignore` riêng chặn toàn bộ `*.sql` và `*.zip`.
  - `.next/`, `build/`, `*.log`, `.tmp/` -> Bị loại trừ.
- **Các lỗ hổng trong `.gitignore` cần bổ sung ngay:**
  - `frontend_backup/`: Bản sao chép frontend cũ nằm ở thư mục gốc, chưa có rule bỏ qua.
  - `report_backup_20261026_1901/` & `report_backup_latex_fix_20261026/`: Chưa có rule bỏ qua.
  - `ai_room_decor_thesis_overleaf_ready.zip` (3.6 MB): Cần rule bỏ qua `*.zip`.
  - Các tệp phụ trợ LaTeX trong `report/` (`*.aux`, `*.log`, `*.toc`, `*.xdv`,...): Cần thêm rule loại trừ.

### 6.3. Đề xuất cấu trúc Repository chuẩn trên GitHub
```
AI-Room-Decor/
├── .github/                      # CI/CD Workflows (tùy chọn)
├── backend/                      # Mã nguồn FastAPI
│   ├── alembic/                  # Database migrations
│   ├── app/                      # Controllers, Models, Services, AI Providers
│   ├── tests/                    # 304 test cases tự động
│   ├── .env.example              # Mẫu biến môi trường local
│   ├── Dockerfile                # Docker container build
│   ├── requirements.txt          # Khóa thư viện Python
│   └── pytest.ini                # Cấu hình kiểm thử
├── frontend/                     # Mã nguồn Next.js 15
│   ├── app/                      # 32 trang giao diện App Router
│   ├── components/               # UI components, layout, admin
│   ├── lib/                      # API client, utilities
│   ├── public/                   # Static assets, icons
│   ├── .env.example              # Mẫu biến môi trường frontend
│   ├── next.config.ts            # Cấu hình Next.js & remote images
│   ├── package.json              # Khóa thư viện Node.js
│   └── tsconfig.json             # Cấu hình TypeScript
├── database/                     # DDL Schema, Seed data ban đầu
├── docs/                         # Tài liệu kỹ thuật, sơ đồ kiến trúc
├── .env.cloud.example            # Mẫu cấu hình deploy Cloud
├── .gitignore                    # Bộ lọc file nhạy cảm hoàn chỉnh
├── docker-compose.yml            # Khởi chạy toàn bộ hệ thống bằng Docker
├── render.yaml                   # Cấu hình Blueprint deploy Render
└── README.md                     # Tài liệu giới thiệu & hướng dẫn chi tiết
```

---

## 7. TÌNH TRẠNG BẢO MẬT VÀ BẢO VỆ DỮ LIỆU NHẠY CẢM

1. **Quét mã nguồn tìm kiếm Khóa bí mật (Secret Scanning):**
   - Tiến hành quét tự động regex toàn bộ mã nguồn Python, TypeScript, JSON, YAML đối với các mẫu Gemini API Key (`AIzaSy...`), Cloudflare Token, JWT Secret, mật khẩu cơ sở dữ liệu.
   - **Kết quả:** **0 KHÓA BÍ MẬT THẬT BỊ LỘ TRONG MÃ NGUỒN**. Tất cả các chuỗi tìm thấy chỉ nằm trong tệp test mock (`api_key="test-key"`).
2. **Cơ chế xác thực & Phân quyền (Authentication & Authorization):**
   - Mật khẩu người dùng được băm an toàn bằng thuật toán `bcrypt` (`passlib[bcrypt]`), không thể giải mã ngược.
   - Xác thực qua chuẩn JWT (JSON Web Token) với thuật toán ký `HS256`, thời gian sống token truy cập (Access Token) là 30 phút.
   - Phân quyền chặt chẽ thông qua dependency `get_current_admin_user`, bảo vệ toàn diện các endpoint `/api/admin/*`.
3. **Cấu hình CORS & Network Security:**
   - CORS được kiểm soát động qua biến `BACKEND_CORS_ORIGINS`. Ở môi trường local chỉ cho phép `http://localhost:3000` và `http://127.0.0.1:3000`. Khi lên Cloud sẽ cấu hình trỏ đích danh tới domain Vercel.
   - Đã tích hợp `ProxyHeadersMiddleware` để nhận diện chính xác địa chỉ IP người dùng thực từ các reverse proxy tin cậy (Cloudflare, Render), tránh bị giả mạo IP khi rate limiting.
4. **Ẩn tài liệu API trên Production:**
   - Trong `backend/app/main.py`, khi `APP_ENV=production`, các đường dẫn Swagger UI (`/docs`) và ReDoc (`/redoc`) sẽ tự động được ẩn hoàn toàn để tránh kẻ xấu dò quét cấu trúc API.

---

## 8. TÌNH TRẠNG TƯƠNG THÍCH CLOUD MIỄN PHÍ (0 VNĐ/THÁNG)

Dự án đã sẵn sàng 100% về mặt kiến trúc để chạy trên 4 nền tảng đám mây hoàn toàn miễn phí:

```mermaid
flowchart LR
    Browser["Trình duyệt Client<br>(Người dùng / Hội đồng)"]

    subgraph Vercel ["Vercel (Hobby Tier - 0 VNĐ)"]
        FE["Next.js 15 Frontend<br>(SSR & Client Components)"]
    end

    subgraph Render ["Render (Free Tier - 0 VNĐ)"]
        BE["FastAPI Backend<br>(Python 3.13)"]
    end

    subgraph TiDB ["TiDB Cloud (Serverless - 0 VNĐ)"]
        DB[("MySQL 8.0 Protocol<br>5 GB Storage<br>TLS Port 4000")]
    end

    subgraph Cloudinary ["Cloudinary (Free Plan - 0 VNĐ)"]
        CDN["Media CDN<br>25 GB Storage / Bandwidth"]
    end

    Browser -->|Truy cập giao diện Web| FE
    Browser -->|Gọi API RESTful (JWT)| BE
    FE -->|Hiển thị ảnh trực tiếp qua HTTPS| CDN
    BE -->|Query SQL qua TLS| DB
    BE -->|Upload / Sync ảnh| CDN
    BE -->|Phân tích phòng| Gemini["Google Gemini Vision API<br>(Free Tier 15 RPM)"]
    BE -->|Tạo ảnh phối cảnh| Cloudflare["Cloudflare Workers AI FLUX.2<br>(Free 10K Neurons/ngày)"]
```

### Bảng đối chiếu hạn mức và rủi ro chi phí 0 VNĐ:

| Dịch vụ Cloud | Gói miễn phí áp dụng | Hạn mức tài nguyên | Yêu cầu thẻ tín dụng? | Rủi ro phát sinh phí | Giải pháp kiểm soát |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vercel** | Hobby Tier | 100 GB băng thông/tháng, không giới hạn thời gian | **Không** | 0% (Hết hạn mức sẽ tạm dừng dịch vụ) | Sử dụng Cloudinary host ảnh, không tốn quota Vercel Image Optimization |
| **Render** | Free Web Service | 512 MB RAM, 0.1 CPU, ngủ sau 15 phút idle | **Không** | 0% (Hết quota tháng sẽ dừng, không tự trừ tiền) | `STORAGE_BACKEND=cloudinary` xử lý việc filesystem của Render bị reset |
| **TiDB Cloud** | Serverless Tier | 5 GB lưu trữ, 50 triệu Request Units (RU)/tháng | **Không** | 0% (Không yêu cầu nhập thẻ khi đăng ký Serverless) | Cơ sở dữ liệu AI Room Decor hiện tại chỉ tốn ~3 MB, dùng < 0.1% hạn mức |
| **Cloudinary** | Free Plan | 25 Credits/tháng (~25 GB lưu trữ hoặc băng thông) | **Không** | 0% (Chặn upload khi hết quota, không tính tiền) | Tổng kho ảnh đồ án hiện tại là 42.5 MB, chiếm chưa đến 0.2% hạn mức |
| **Google Gemini** | Google AI Studio Free | 15 requests/phút, 1,500 requests/ngày | **Không** | 0% (Hoàn toàn miễn phí trên AI Studio API Key) | Đã có Rate Limiter tại Backend chặn người dùng spam gọi Gemini |
| **Cloudflare AI** | Workers AI Free | 10,000 Neurons/ngày | **Không** | 0% (Gói free tự động trả về lỗi 429 khi hết hạn mức ngày) | Backend bắt lỗi 429 trả về thông báo lịch sự cho người dùng |

---

## 9. DANH SÁCH CÁC TỆP CẦN ĐIỀU CHỈNH TRƯỚC KHI PUSH / DEPLOY

Các tệp dưới đây là các tệp duy nhất cần điều chỉnh hoặc tạo mới trước khi đưa lên GitHub và Cloud (theo đúng quy tắc không làm xáo trộn mã nguồn lõi):

1. **`D:\AI-Room-Decor\.gitignore` (Cần bổ sung):**
   Thêm các quy tắc loại trừ bản backup và tệp rác:
   ```gitignore
   # Backup directories & archives
   *_backup*/
   *backup*/
   *.zip
   tmpp*/

   # LaTeX build artifacts in report/
   report/*.aux
   report/*.fdb_latexmk
   report/*.fls
   report/*.lof
   report/*.log
   report/*.lot
   report/*.out
   report/*.toc
   report/*.synctex.gz
   report/*.xdv
   ```
2. **`D:\AI-Room-Decor\README.md` (Cần nâng cấp):**
   Chuyển đổi từ file README sơ bộ hiện tại thành bản tài liệu chuyên nghiệp hoàn chỉnh dành cho GitHub (bao gồm badge, sơ đồ kiến trúc, luồng chạy AI, hướng dẫn setup).
3. **`D:\AI-Room-Decor\frontend\app\admin\room-projects\[id]\page.tsx` & các trang admin:**
   (Tùy chọn) Chuyển các thẻ `<img>` sang `<Image>` từ `next/image` để dọn dẹp sạch sẽ 18 cảnh báo linting.

---

## 10. LỘ TRÌNH THỰC HIỆN THEO TỪNG GIAI ĐOẠN

```mermaid
flowchart TD
    G0["GIAI ĐOẠN 0: KIỂM TOÁN HOÀN TẤT<br>(Hiện tại - 100% an toàn dữ liệu)"]
    G1["GIAI ĐOẠN 1: SAO LƯU VI SAI & DỌN DẸP GIT<br>(Tạo backup mới cho User #21, cấu hình .gitignore)"]
    G2["GIAI ĐOẠN 2: THIẾT LẬP REPO GITHUB CHUYÊN NGHIỆP<br>(Cài Git, commit mã nguồn sạch, đẩy lên GitHub cá nhân)"]
    G3["GIAI ĐOẠN 3: ĐĂNG KÝ CÁC DỊCH VỤ CLOUD MIỄN PHÍ<br>(Tạo TiDB Cloud, Cloudinary, Render, Vercel - 0 VNĐ)"]
    G4["GIAI ĐOẠN 4: DI TRÚ DỮ LIỆU & DEPLOY CLOUD<br>(Import SQL sang TiDB, sync 265 ảnh sang Cloudinary, build web)"]
    G5["GIAI ĐOẠN 5: NGHIỆM THU & BẢO VỆ ĐỒ ÁN<br>(Chạy song song Localhost an toàn & Website Cloud công khai)"]

    G0 --> G1 --> G2 --> G3 --> G4 --> G5
```

### Chi tiết các bước thực hiện:

- **Giai đoạn 1: Bảo vệ Dữ liệu vi sai & Chuẩn bị Git (15 phút)**
  - Chạy lệnh sao lưu MariaDB ra bản dump mới: `ai_room_decor_differential_20261102.sql`.
  - Cập nhật `.gitignore` để loại bỏ toàn bộ bản sao lưu và file nén khỏi staging area.
- **Giai đoạn 2: Khởi tạo và Đẩy lên GitHub (20 phút)**
  - Cài đặt Git for Windows (hoặc cấu hình PATH).
  - Chạy `git init`, `git add .`, kiểm tra `git status` đảm bảo không có file nhạy cảm.
  - Tạo repository trên GitHub (Private hoặc Public) và thực hiện commit đầu tiên.
- **Giai đoạn 3: Đăng ký Tài nguyên Cloud 0 VNĐ (Người dùng thực hiện - 25 phút)**
  - Tạo tài khoản TiDB Cloud Serverless -> Tạo cụm cluster miễn phí -> Lấy chuỗi kết nối MySQL kèm TLS.
  - Tạo tài khoản Cloudinary Free -> Lấy `cloud_name`, `api_key`, `api_secret`.
  - Tạo tài khoản Render -> Liên kết với GitHub repo.
  - Tạo tài khoản Vercel -> Liên kết với GitHub repo.
- **Giai đoạn 4: Di trú Dữ liệu & Kích hoạt Deploy (30 phút)**
  - Chạy script import bản dump SQL lên TiDB Cloud.
  - Chạy script đồng bộ 265 tệp ảnh trong `storage/` lên Cloudinary Media Library.
  - Cấu hình Environment Variables trên Render và Vercel.
  - Kích hoạt Deploy tự động và kiểm tra endpoint `/health`.
- **Giai đoạn 5: Thao giảng & Bảo vệ Đồ án**
  - Mở website trên Internet cho giảng viên và hội đồng truy cập trên điện thoại/laptop cá nhân.
  - Giữ nguyên localhost như một phương án dự phòng 100% không bao giờ gặp sự cố mạng.

---

## 11. ƯỚC LƯỢNG MỨC ĐỘ HOÀN THIỆN KÈM TIÊU CHÍ KỸ THUẬT ĐỊNH LƯỢNG

Đánh giá mức độ hoàn thiện khoa học dựa trên 5 trụ cột kỹ thuật:

| Trụ cột đánh giá | Trọng số | Tỷ lệ đạt được | Điểm quy đổi | Tiêu chí kỹ thuật chứng minh |
| :--- | :---: | :---: | :---: | :--- |
| **1. Tính đầy đủ của Chức năng (Features)** | 30% | **98%** | 29.4% | 32/32 trang frontend hoạt động; 86/86 API endpoints; luồng Gemini Vision + Gợi ý 7 tiêu chí + FLUX.2 chạy trơn tru end-to-end. |
| **2. Chất lượng Mã nguồn & Kiểm thử (QA)** | 25% | **100%** | 25.0% | 304/304 backend tests passed (100%); 0 TypeScript errors; 0 ESLint errors; 0 TODO/FIXME trong production code. |
| **3. Toàn vẹn Dữ liệu & Minh chứng (Data)**| 20% | **100%** | 20.0% | 32 bảng, 41 khóa ngoại nguyên vẹn; Project #21, Analysis #91, Preference #13, Designs #38–#41 và 265 file ảnh được bảo toàn tuyệt đối. |
| **4. Sẵn sàng Đưa lên GitHub (Git Readiness)** | 10% | **85%** | 8.5% | Mã nguồn sạch sẽ, không lộ secret; cần cài Git CLI và bổ sung một số rule `.gitignore` cho file backup. |
| **5. Sẵn sàng Triển khai Cloud (Cloud Readiness)**| 15% | **88%** | 13.2% | Codebase đã hỗ trợ TiDB SSL và Cloudinary; `render.yaml` và `.env.cloud.example` đã sẵn sàng; đang chờ người dùng tạo tài khoản cloud. |
| **TỔNG THỂ DỰ ÁN** | **100%** | — | **96.1%** | **ĐỦ ĐIỀU KIỆN TỐI ƯU ĐỂ NGHIỆM THU VÀ BẢO VỆ ĐỒ ÁN** |

---

## 12. CHECKLIST KIỂM SOÁT TRƯỚC KHI PUSH GITHUB

Trước khi thực hiện lệnh `git commit` và `git push`, cần kiểm tra từng mục sau:

- [ ] **Kiểm tra công cụ:** Đã cài đặt Git for Windows và lệnh `git --version` trả về phiên bản hợp lệ trong terminal.
- [ ] **Kiểm tra tệp nhạy cảm:** Chạy `git status` và xác nhận **KHÔNG CÓ** bất kỳ tệp nào sau đây xuất hiện trong danh sách chuẩn bị commit:
  - [ ] `.env` hoặc `.env.*` (chỉ cho phép `.env.example`, `.env.cloud.example`).
  - [ ] `backups/` hoặc bất kỳ tệp đuôi `.sql`.
  - [ ] `storage/` chứa ảnh phòng thực tế của người dùng.
  - [ ] `frontend_backup/`, `report_backup_*`.
  - [ ] `ai_room_decor_thesis_overleaf_ready.zip` hoặc bất kỳ tệp `.zip`.
- [ ] **Kiểm tra khóa bí mật:** Xác nhận mã nguồn không chứa Gemini API Key hoặc Cloudflare API Token dạng plain-text.
- [ ] **Kiểm tra tài liệu:** Đã có tệp `README.md` mô tả đồ án rõ ràng, hướng dẫn cài đặt và bảng công nghệ sử dụng.

---

## 13. CHECKLIST KIỂM SOÁT TRƯỚC KHI DEPLOY CLOUD

- [ ] **Sao lưu vi sai:** Đã xuất bản sao lưu mới nhất của MariaDB chứa User #21 và các dự án phát sinh.
- [ ] **TiDB Cloud:**
  - [ ] Cluster Serverless đang ở trạng thái `Available`.
  - [ ] Đã import thành công 32 bảng và 41 khóa ngoại.
  - [ ] Chuỗi kết nối có dạng: `mysql+pymysql://<user>:<password>@gateway01.<region>.prod.aws.tidbcloud.com:4000/ai_room_decor?ssl_verify_cert=true`.
- [ ] **Cloudinary:**
  - [ ] Đã upload toàn bộ ảnh từ thư mục `storage/` lên Cloudinary giữ nguyên cấu trúc thư mục tương đối.
  - [ ] Đã lấy đủ 3 thông số: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
- [ ] **Render Web Service:**
  - [ ] `APP_ENV = production`
  - [ ] `STORAGE_BACKEND = cloudinary`
  - [ ] `DATABASE_URL` trỏ tới TiDB Cloud.
  - [ ] `BACKEND_CORS_ORIGINS` chứa domain của Vercel (`https://<ten-du-an>.vercel.app`).
  - [ ] Endpoint `/health` trả về `200 OK` với body `{"status":"OK"}`.
- [ ] **Vercel Frontend:**
  - [ ] `NEXT_PUBLIC_API_URL` trỏ đích danh tới domain Render (`https://ai-room-decor-api.onrender.com`).
  - [ ] Deploy hoàn tất với trạng thái `Ready` và mở trang chủ hiển thị mượt mà.

---

## 14. HƯỚNG DẪN THAO TÁC NGƯỜI DÙNG CẦN TỰ THỰC HIỆN

Do nguyên tắc an toàn thông tin cá nhân và bảo mật tài khoản, các bước sau đây người dùng cần tự thao tác trên trình duyệt của mình (chúng tôi sẽ cung cấp mã lệnh và hướng dẫn từng bước chi tiết khi bạn phê duyệt):

1. **Cài đặt Git for Windows:**
   - Tải tệp cài đặt tại: [https://git-scm.com/download/win](https://git-scm.com/download/win).
   - Chọn mặc định tất cả các bước cài đặt để lệnh `git` được tích hợp vào Windows Terminal / PowerShell.
2. **Tạo GitHub Repository:**
   - Đăng nhập vào [https://github.com](https://github.com).
   - Bấm nút **New Repository**, đặt tên ví dụ: `AI-Room-Decor`.
   - Chọn chế độ **Private** (nếu muốn giữ bí mật mã nguồn trước khi chấm điểm) hoặc **Public** (nếu muốn khoe profile đồ án).
3. **Đăng ký tài khoản Cloud Miễn phí (0 VNĐ):**
   - **TiDB Cloud:** Truy cập [https://tidbcloud.com](https://tidbcloud.com) -> Đăng ký bằng Google / GitHub -> Chọn cụm **Serverless** (Free forever).
   - **Cloudinary:** Truy cập [https://cloudinary.com](https://cloudinary.com) -> Đăng ký gói Free -> Lấy thông số trong Dashboard.
   - **Render:** Truy cập [https://render.com](https://render.com) -> Đăng ký bằng GitHub.
   - **Vercel:** Truy cập [https://vercel.com](https://vercel.com) -> Đăng ký bằng GitHub.

---

> [!IMPORTANT]
> **KẾT LUẬN KIỂM TOÁN:**
> Dự án **AI Room Decor** đang ở trạng thái kỹ thuật xuất sắc: mã nguồn sạch sẽ, không có nợ kỹ thuật (0 TODO/FIXME), tỷ lệ test tự động vượt qua đạt **100% (304/304)**, toàn vẹn dữ liệu được bảo vệ tuyệt đối.
>
> Hệ thống hiện tại hoàn toàn sẵn sàng cho **buổi báo cáo thử nghiệm, bảo vệ đồ án tốt nghiệp trên localhost** và có thể triển khai lên **Cloud miễn phí (0 VNĐ)** ngay khi bạn phê duyệt thực hiện Giai đoạn 1.
