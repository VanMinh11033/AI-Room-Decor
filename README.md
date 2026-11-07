# AI Room Decor — Nền Tảng Gợi Ý & Thiết Kế Trang Trí Nội Thất Cá Nhân Hóa

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2015-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![MySQL / MariaDB](https://img.shields.io/badge/Database-MySQL%208%20%7C%20MariaDB-4479A1.svg?logo=mysql&logoColor=white)](https://www.mysql.com)
[![Cloudflare Workers AI](https://img.shields.io/badge/AI%20Image-Cloudflare%20FLUX.2-F38020.svg?logo=cloudflare&logoColor=white)](https://developers.cloudflare.com/workers-ai/)
[![Google Gemini](https://img.shields.io/badge/AI%20Vision-Gemini%20Flash-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Docker](https://img.shields.io/badge/Container-Docker%20Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)

> **Đồ án Tốt nghiệp / Báo cáo Nghiên cứu Ứng dụng Công nghệ**<br>
> **Đơn vị:** Trường Đại học Kiến trúc Đà Nẵng (DAU) — Khoa Công nghệ Thông tin<br>
> **Đề tài:** Xây dựng hệ thống gợi ý decor phòng theo cá nhân hóa người dùng<br>
> **Sinh viên thực hiện:**<br>
> - **Trần Văn Minh** (MSSV: `2351220028`)
> - **Nguyễn Khang Hy** (MSSV: `2351220008`)<br>
> **Giảng viên hướng dẫn:** TS. Đỗ Phúc Hảo<br>
> **Thời gian thực hiện:** 11/2026

---

## 1. Giới thiệu tổng quan

**AI Room Decor** là hệ thống hỗ trợ người dùng chuyển đổi không gian sống thông qua quy trình kết hợp thông minh giữa Trí tuệ nhân tạo (AI Vision, Generative AI) và Thương mại điện tử (E-commerce).

Khác biệt với các giải pháp tạo ảnh trang trí ngẫu nhiên không gắn liền với sản phẩm thực tế, **AI Room Decor** xây dựng chuỗi nghiệp vụ hoàn chỉnh:
1. **Phân tích bối cảnh căn phòng** (loại phòng, phong cách hiện tại, tông màu chủ đạo, nguồn sáng, vị trí khoảng trống).
2. **Thu thập sở thích cá nhân hóa** (gu thẩm mỹ, vật liệu mong muốn, phân khúc ngân sách, mục đích sử dụng).
3. **Gợi ý sản phẩm nội thất có sẵn trong kho** bằng thuật toán chấm điểm đa tiêu chí minh bạch (Rule-Based Multi-Criteria Scoring).
4. **Tạo ảnh phối cảnh trang trí trực quan (AI Visual Staging)** đưa chính xác các sản phẩm được chọn vào không gian thực của phòng bằng mô hình khuếch tán FLUX.2 trên Cloudflare Workers AI.
5. **Đặt hàng trực tuyến nguyên tử (Transactional Checkout)** với cơ chế trừ kho an toàn, lưu snapshot giá và quản trị đơn hàng.

---

## 2. Kiến trúc hệ thống

```
+-------------------------------------------------------------------------+
|                        TẦNG TRÌNH DIỄN (FRONTEND)                       |
|   Next.js 15 App Router | React 19 | Tailwind CSS | TypeScript | Lucide |
|      (Trang khách hàng: Khám phá, Dự án phòng, Giỏ hàng & Checkout)     |
|      (Trang quản trị: Catalog, Phê duyệt ảnh, Giám sát AI usage)        |
+------------------------------------+------------------------------------+
                                     | HTTP REST API + Bearer JWT
+------------------------------------+------------------------------------+
|                         TẦNG DỊCH VỤ (BACKEND)                          |
|             FastAPI | Python 3.12/3.13 | Pydantic v2 | SQLAlchemy 2     |
|  - Auth & RBAC (Customer / Admin)     - Rule-Based Recommendation (7 tiêu chí)
|  - Room Project & Context Lifecycle   - Reference Image Pipeline (Alpha Trim)
|  - Order Transaction Engine (ACID)    - Reverse Proxy & Rate Limiting   |
+------------------+----------------------------------+-------------------+
                   |                                  |
+------------------+---------------+  +---------------+-------------------+
|      TẦNG DỮ LIỆU & LƯU TRỮ      |  |           TẦNG DỊCH VỤ AI         |
| - MariaDB 10 / MySQL 8 (Alembic) |  | - Gemini Flash (Room Vision)      |
| - Filesystem / Cloudinary        |  | - Cloudflare FLUX.2 (GenAI Image) |
| - Snapshot Audit & Migrations    |  | - Deterministic Fallback Engine   |
+----------------------------------+  +-----------------------------------+
```

---

## 3. Các tính năng cốt lõi

### 3.1. Phân tích hiện trạng phòng (AI Room Vision)
- Nhận diện loại phòng (`living_room`, `bedroom`, `kitchen`, `office`, ...), tông màu hiện có, các vật thể nhận diện được và các vùng khoảng trống tiềm năng.
- Tích hợp **Google Gemini Flash** với cấu trúc dữ liệu JSON chặt chẽ.
- Trang bị cơ chế **Deterministic Fallback (Pillow Engine)** tự động trích xuất màu sắc và bố cục cơ bản khi mạng gián đoạn hoặc API vượt ngưỡng hạn ngạch (429/503), đảm bảo hệ thống không bao giờ bị dừng gián đoạn.

### 3.2. Thuật toán gợi ý cá nhân hóa 7 tiêu chí
Động cơ gợi ý tính toán điểm tương thích $S \in [0, 100]$ minh bạch dựa trên công thức trọng số:
$$S = S_{\text{style}} + S_{\text{room}} + S_{\text{color}} + S_{\text{material}} + S_{\text{category}} + S_{\text{budget}} + S_{\text{purpose}}$$
- Giải trình rõ lý do vì sao sản phẩm được gợi ý (breakdown từng tiêu chí).
- Hoàn toàn chạy nội bộ trên server backend, không phát sinh chi phí gọi mô hình ngôn ngữ lớn (LLM).

### 3.3. Sinh ảnh thiết kế nội thất phối cảnh (Generative Visual Staging)
- Kết hợp ảnh phòng gốc của người dùng với ảnh tham chiếu tách nền của các món nội thất trong kho.
- Sử dụng mô hình **`@cf/black-forest-labs/flux-2-dev`** trên **Cloudflare Workers AI** cho chất lượng dựng ảnh vượt trội.
- Hỗ trợ chế độ **Deterministic Composite** (ghép ảnh lớp layer) phục vụ môi trường kiểm thử không cần kết nối mạng ngoài.

### 3.4. Quản lý Catalog & Chuẩn hóa ảnh sản phẩm
- Thuật toán tự động phát hiện viền, cắt bỏ vùng trong suốt thừa (bounding box trimming), chuẩn hóa tỷ lệ khung hình.
- Công cụ tìm kiếm và bổ sung ảnh mẫu từ Openverse / Pixabay / Pexels cho quản trị viên.

### 3.5. Thương mại điện tử & Giao dịch an toàn
- Giỏ hàng phía máy chủ đồng bộ với tài khoản người dùng.
- Cơ chế đặt hàng giao dịch ACID nguyên tử: kiểm tra tồn kho, trừ kho, lưu snapshot giá và địa chỉ tại thời điểm đặt, hỗ trợ rollback khi có xung đột.

### 3.6. Báo cáo học thuật chuẩn Đại học Kiến trúc Đà Nẵng
- Đề tài được nghiên cứu và bảo vệ với tài liệu báo cáo học thuật chuyên sâu gồm **80 trang** theo đúng quy cách của Trường Đại học Kiến trúc Đà Nẵng (DAU). Toàn bộ mã nguồn trên kho lưu trữ này tập trung vào mã nguồn ứng dụng và quy trình triển khai website thực tế.

---

## 4. Công nghệ sử dụng

| Phân hệ | Công nghệ chính | Vai trò / Chi tiết |
|---|---|---|
| **Frontend** | Next.js 15, React 19, TypeScript | Server Components, Client Routing, giao diện responsive Tailwind CSS |
| **Backend** | FastAPI, Python 3.12+, Uvicorn | RESTful API hiệu năng cao, Dependency Injection, Pydantic v2 |
| **ORM & Migration** | SQLAlchemy 2.0, Alembic | Quản lý schema database theo phiên bản, Session pool |
| **Cơ sở dữ liệu** | MySQL 8.4 / MariaDB 10.4 | Cơ sở dữ liệu quan hệ ACID, hỗ trợ TiDB Cloud cho môi trường Cloud |
| **AI Vision** | Google Gemini (`google-genai`) | Phân tích thị giác máy tính, nhận diện không gian |
| **AI Generation** | Cloudflare Workers AI FLUX.2 | Tạo ảnh nội thất phối cảnh generative inpainting |
| **Lưu trữ** | Local Storage / Cloudinary | Quản lý ảnh tải lên, ảnh sản phẩm và ảnh render AI |
| **Xác thực** | JWT (HS256 via python-jose) + bcrypt | Đăng nhập an toàn, refresh token, phân quyền RBAC |
| **Kiểm thử** | Pytest, Next.js ESLint, TypeScript tsc | Kiểm thử tự động backend và static analysis frontend |

---

## 5. Cấu trúc thư mục

```text
AI-Room-Decor/
├── backend/                       # Source code ứng dụng FastAPI
│   ├── alembic/                   # Các phiên bản migration cơ sở dữ liệu
│   │   └── versions/              # 0001 -> 0006 schema migrations
│   ├── app/
│   │   ├── ai/                    # Providers AI (Gemini Vision, Cloudflare FLUX.2, Fallback)
│   │   ├── api/                   # Router endpoints (auth, products, projects, orders, admin)
│   │   ├── core/                  # Cấu hình Pydantic Settings, DB session, Security
│   │   ├── models/                # SQLAlchemy Entity Models
│   │   ├── recommendation/        # Thuật toán tính điểm gợi ý 7 tiêu chí
│   │   ├── schemas/               # Pydantic Schemas (Request/Response DTO)
│   │   └── services/              # Nghiệp vụ: phân tích phòng, giỏ hàng, đặt hàng, sinh ảnh
│   ├── scripts/                   # Script bảo trì (reset admin password, test pilot)
│   ├── tests/                     # Bộ kiểm thử tự động pytest
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                      # Source code ứng dụng Next.js 15
│   ├── app/                       # Next.js App Router (khách hàng + admin dashboard)
│   ├── components/                # React UI Components (Navigation, ProductCard, Admin)
│   ├── hooks/                     # Custom React Hooks
│   ├── lib/                       # API client, Cart state, formatters
│   ├── types/                     # TypeScript Interfaces
│   ├── Dockerfile
│   └── package.json
├── database/                      # Ghi chú khởi tạo cơ sở dữ liệu
├── docs/                          # Tài liệu kỹ thuật: Kiến trúc API, Triển khai Cloud, Audit
├── .env.example                   # Mẫu cấu hình môi trường phát triển cục bộ
├── .env.cloud.example             # Mẫu cấu hình môi trường đám mây (Render / Vercel / TiDB)
├── docker-compose.yml             # Cấu hình khởi chạy trọn gói bằng Docker
├── render.yaml                    # Blueprint triển khai Backend lên Cloud Render
└── README.md                      # Tài liệu tổng quan dự án
```

---

## 6. Hướng dẫn cài đặt & Khởi chạy

### Lựa chọn 1: Chạy nhanh bằng Docker Compose

Yêu cầu máy đã cài **Docker** và **Docker Compose**.

```bash
# 1. Sao chép file cấu hình mẫu
copy .env.example .env

# 2. Khởi tạo toàn bộ dịch vụ (MySQL 8, FastAPI backend, Next.js frontend)
docker compose up --build -d

# 3. Theo dõi trạng thái log
docker compose logs -f
```
- Frontend: `http://localhost:3000`
- Backend API Docs (Swagger): `http://localhost:8000/docs`

---

### Lựa chọn 2: Cài đặt từng phần trên môi trường cục bộ

#### Bước 1: Khởi tạo Cơ sở dữ liệu (MariaDB / MySQL)
Chạy dịch vụ MariaDB (qua XAMPP hoặc MySQL Workbench), tạo cơ sở dữ liệu:
```sql
CREATE DATABASE ai_room_decor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE ai_room_decor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### Bước 2: Thiết lập Backend FastAPI
```bash
cd backend

# Khởi tạo môi trường ảo Python
python -m venv .venv
.venv\Scripts\activate          # Trên Windows
# source .venv/bin/activate     # Trên Linux/macOS

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt

# Tạo file cấu hình môi trường
copy .env.example .env
# Chỉnh sửa .env: cấu hình DATABASE_URL, JWT_SECRET_KEY, API keys...

# Chạy migration để khởi tạo cấu trúc bảng
alembic upgrade head

# Nạp dữ liệu mẫu ban đầu (Catalog & Ảnh sản phẩm)
python -m app.seed_catalog
python -m app.seed_product_images

# Khởi chạy server FastAPI
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### Bước 3: Thiết lập Frontend Next.js
Mở một cửa sổ dòng lệnh mới:
```bash
cd frontend

# Cài đặt gói npm
npm install

# Tạo cấu hình môi trường frontend
copy .env.example .env.local

# Khởi chạy ứng dụng Next.js ở chế độ phát triển
npm run dev
```

Truy cập hệ thống tại: **`http://localhost:3000`**

---

## 7. Cấu hình biến môi trường

Hệ thống cung cấp hai file mẫu rõ ràng:
- **`.env.example`**: Dùng cho phát triển tại máy cá nhân (kết nối MySQL/MariaDB cục bộ, filesystem storage).
- **`.env.cloud.example`**: Dùng cho triển khai trên đám mây (TiDB Cloud Serverless, Cloudinary CDN, Render, Vercel).

Các biến quan trọng cần chú ý:
- `DATABASE_URL`: Chuỗi kết nối SQLAlchemy (`mysql+pymysql://...`).
- `JWT_SECRET_KEY`: Khóa bí mật mã hóa JWT (tạo chuỗi ngẫu nhiên bằng `openssl rand -hex 32`).
- `GEMINI_API_KEY`: API Key từ Google AI Studio cho tính năng phân tích phòng.
- `CLOUDFLARE_ACCOUNT_ID` & `CLOUDFLARE_API_TOKEN`: Khóa xác thực Cloudflare Workers AI cho mô hình FLUX.2.
- `STORAGE_BACKEND`: Chọn `local` (lưu tại thư mục máy chủ) hoặc `cloudinary` (lưu trữ ảnh đám mây).
- `NEXT_PUBLIC_API_URL`: Địa chỉ URL của Backend API mà Frontend Next.js kết nối đến.

> [!IMPORTANT]
> **Tuyệt đối không đưa các tệp `.env` chứa khóa bí mật thực tế lên Git repository.** Mọi thông tin nhạy cảm đã được loại trừ tự động qua `.gitignore`.

---

## 8. Kiểm thử & Đảm bảo chất lượng

Dự án được trang bị bộ kiểm thử tự động toàn diện:

```bash
# Kiểm thử Backend (Unit test & Integration test)
cd backend
pytest

# Kiểm tra tĩnh Frontend (TypeScript Types & ESLint)
cd frontend
npm run typecheck
npm run lint

# Biên dịch thử nghiệm Frontend
npm run build
```

---

## 9. Triển khai lên môi trường Đám mây (Cloud Deployment)

Chi tiết quy trình triển khai đầy đủ với chi phí 0 VNĐ (Free Tier) có thể tham khảo tại [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md):
- **Cơ sở dữ liệu:** TiDB Cloud Serverless (MySQL Compatible, 5GB miễn phí trọn đời).
- **Lưu trữ hình ảnh:** Cloudinary (25GB băng thông miễn phí mỗi tháng).
- **Backend API:** Render Web Service (FastAPI Docker runtime).
- **Frontend Web:** Vercel (Next.js Edge Network toàn cầu).

---

## 10. Giấy phép & Bản quyền học thuật

Đồ án được phát triển nhằm mục đích nghiên cứu học thuật và báo cáo tốt nghiệp tại **Trường Đại học Kiến trúc Đà Nẵng (DAU)**. Toàn bộ mã nguồn và tài liệu thuộc quyền tác giả của nhóm sinh viên thực hiện dưới sự hướng dẫn của giảng viên phụ trách.
