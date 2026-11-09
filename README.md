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

Người phát triển mới hoặc thành viên nghiệm thu khi clone mã nguồn từ GitHub về có thể thiết lập và chạy hệ thống theo hai phương thức dưới đây.

---

### Phương thức 1: Cài đặt từng bước trên môi trường cục bộ (Khuyến nghị cho phát triển)

#### 1. Yêu cầu hệ thống & Phần mềm tiên quyết
Trước khi bắt đầu, hãy đảm bảo máy tính đã cài đặt các công cụ sau:
- **Git**: [Tải Git](https://git-scm.com/) để quản lý mã nguồn.
- **Python**: Phiên bản **3.12** hoặc **3.13** (kèm `pip` và `venv`). Kiểm tra: `python --version`.
- **Node.js**: Phiên bản **18.x** hoặc **20.x+** LTS (kèm `npm`). Kiểm tra: `node -v` và `npm -v`.
- **Hệ quản trị CSDL MariaDB / MySQL**: **MariaDB 10.4+** hoặc **MySQL 8.0/8.4** (có thể dùng qua XAMPP, Laragon, MySQL Server độc lập hoặc Docker).

---

#### 2. Bước 1 — Clone mã nguồn Repository
Mở terminal (PowerShell, Command Prompt hoặc Bash) và clone repository về máy:
```bash
git clone https://github.com/<your-username>/AI-Room-Decor.git
cd AI-Room-Decor
```

---

#### 3. Bước 2 — Thiết lập Biến môi trường (`.env`) từ file mẫu
Hệ thống sử dụng file `.env` ở thư mục gốc (backend kế thừa) và `frontend/.env.local` cho frontend:

**Trên Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env.local
```

**Trên Windows (CMD):**
```cmd
copy .env.example .env
copy frontend\.env.example frontend\.env.local
```

**Trên Linux / macOS:**
```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

---

#### 4. Bước 3 — Tự thiết lập `JWT_SECRET_KEY` và mật khẩu Admin an toàn
Mở file `.env` vừa tạo và cập nhật các khóa bảo mật quan trọng:

1. **Sinh khóa bảo mật JWT ngẫu nhiên:**
   Chạy lệnh Python sau để tạo chuỗi ngẫu nhiên bảo mật cao (64 ký tự hex):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Sao chép kết quả và gán vào `JWT_SECRET_KEY` trong `.env`:
   ```env
   JWT_SECRET_KEY=chuoi_khoa_ngau_nhien_vua_sinh_o_tren
   ```

2. **Thiết lập tài khoản Quản trị viên (Admin Seed):**
   Trong `.env`, điền email và mật khẩu an toàn tự chọn của bạn:
   ```env
   ADMIN_EMAIL=admin@yourdomain.com
   ADMIN_PASSWORD=MatKhauBaoMat@2026!
   ADMIN_FULL_NAME=AI Room Decor Admin
   ```
   > [!WARNING]
   > - Tuyệt đối không để trống hoặc dùng mật khẩu mặc định yếu.
   > - Tuyệt đối không commit file `.env` chứa mật khẩu thật lên GitHub (đã được cấu hình loại trừ tự động trong `.gitignore`).

3. **Cấu hình chuỗi kết nối Database (`DATABASE_URL`):**
   Chỉnh sửa user/password phù hợp với MariaDB/MySQL trên máy bạn. Ví dụ:
   - Dùng XAMPP (mặc định user `root`, không mật khẩu):
     ```env
     DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/ai_room_decor?charset=utf8mb4
     TEST_DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/ai_room_decor_test?charset=utf8mb4
     ```
   - Dùng MySQL Server có mật khẩu `MySecretPass123`:
     ```env
     DATABASE_URL=mysql+pymysql://root:MySecretPass123@127.0.0.1:3306/ai_room_decor?charset=utf8mb4
     TEST_DATABASE_URL=mysql+pymysql://root:MySecretPass123@127.0.0.1:3306/ai_room_decor_test?charset=utf8mb4
     ```

---

#### 5. Bước 4 — Khởi tạo Database mới bằng Alembic
1. **Tạo Database trên MariaDB/MySQL:**
   Mở công cụ quản lý cơ sở dữ liệu (HeidiSQL, phpMyAdmin, MySQL Workbench, DBeaver) hoặc MySQL CLI và thực thi câu lệnh SQL:
   ```sql
   CREATE DATABASE ai_room_decor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE DATABASE ai_room_decor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. **Cài đặt môi trường ảo và thư viện Backend:**
   ```bash
   cd backend
   python -m venv .venv

   # Kích hoạt môi trường ảo:
   # Trên Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Hoặc Windows CMD:
   .venv\Scripts\activate.bat
   # Hoặc Linux / macOS:
   source .venv/bin/activate

   # Cài đặt toàn bộ thư viện:
   pip install -r requirements.txt
   ```

3. **Chạy Migration để tạo cấu trúc 15 bảng cơ sở dữ liệu:**
   ```bash
   alembic upgrade head
   ```
   *Lệnh này sẽ tự động đọc schema từ thư mục `alembic/versions/` và tạo đầy đủ các bảng, quan hệ khóa ngoại và chỉ mục (indexes).*

---

#### 6. Bước 5 — Nạp dữ liệu Catalog mẫu và tạo ảnh demo
Trong thư mục `backend` (môi trường ảo `.venv` đang kích hoạt):

1. **Nạp dữ liệu Catalog mẫu (30 sản phẩm nội thất chuẩn):**
   ```bash
   python -m app.seed_catalog
   ```
   *Lệnh này tạo các danh mục (`Sofa`, `Table`, `Chair`, ...), vật liệu, phong cách, màu sắc, 30 sản phẩm nội thất và đồng thời tự động khởi tạo các vai trò `CUSTOMER`, `ADMIN` cùng tài khoản Admin theo cấu hình trong `.env`.*

2. **Tạo ảnh minh họa demo cho sản phẩm:**
   ```bash
   python -m app.seed_product_images
   ```
   *Script sử dụng Pillow để sinh tự động ảnh vẽ minh họa chuẩn kích thước 800x800 cho từng món nội thất vào thư mục `storage/products/generated-demo/` và liên kết vào cơ sở dữ liệu.*

   > [!NOTE]
   > **Cơ chế an toàn của `seed_product_images.py`:**
   > Script được tích hợp hàng rào bảo vệ đa lớp (Layered Safety Guard):
   > - Chỉ cho phép thực thi trên cơ sở dữ liệu phát triển cục bộ (`ai_room_decor` hoặc `ai_room_decor_dev`) tại máy trạm (`127.0.0.1` / `localhost`).
   > - Tuyệt đối từ chối chạy khi phát hiện môi trường `production`, storage `cloudinary`, host đám mây từ xa (TiDB Cloud, AWS RDS), hoặc cơ sở dữ liệu kiểm thử `test`.

---

#### 7. Bước 6 — Khởi chạy Backend FastAPI
Vẫn tại thư mục `backend` (đang kích hoạt `.venv`):
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Server sẽ lắng nghe tại: `http://127.0.0.1:8000`
- Kiểm tra tài liệu Swagger UI: **`http://127.0.0.1:8000/docs`**
- Kiểm tra endpoint tình trạng: **`http://127.0.0.1:8000/health`** (trả về `{"status":"OK"}`)

---

#### 8. Bước 7 — Cài đặt và khởi chạy Frontend Next.js
Mở một cửa sổ dòng lệnh (terminal) **mới**:
```bash
cd frontend

# Cài đặt các gói phụ thuộc npm
npm install

# Đảm bảo frontend/.env.local có URL trỏ về backend:
# NEXT_PUBLIC_API_URL=http://localhost:8000

# Khởi chạy server phát triển Next.js
npm run dev
```
- Ứng dụng web sẽ khởi chạy tại: **`http://localhost:3000`**

---

#### 9. Bước 8 — Kiểm tra Website & Nghiệm thu chức năng
Mở trình duyệt web truy cập `http://localhost:3000` và kiểm tra các chức năng:
1. **Trang chủ & Khám phá Catalog (`/products`):**
   - Kiểm tra danh sách 30 sản phẩm hiển thị đầy đủ tên, giá, kích thước và ảnh demo vẽ isometric.
   - Thử nghiệm lọc sản phẩm theo danh mục (`Sofa`, `Table`, `Lighting`), khoảng giá và phong cách.
2. **Đăng ký & Đăng nhập khách hàng (`/register`, `/login`):**
   - Tạo tài khoản khách hàng mới để kiểm tra luồng xác thực JWT.
   - Thử thêm sản phẩm vào giỏ hàng (`/cart`), cập nhật số lượng và kiểm tra tính toán tổng tiền.
3. **Trang Quản trị Admin (`/admin`):**
   - Đăng nhập bằng tài khoản `ADMIN_EMAIL` và `ADMIN_PASSWORD` đã thiết lập tại Bước 3.
   - Kiểm tra bảng điều khiển: Quản lý danh mục, Quản lý sản phẩm, Quản lý đơn hàng và Giám sát AI usage.
4. **Quy trình Decor phòng bằng AI (`/room-projects`):**
   - Tạo dự án phòng mới (`/room-projects/new`), tải ảnh không gian phòng mẫu.
   - Thiết lập phong cách, màu sắc, ngân sách mong muốn.
   - Kiểm tra bảng gợi ý sản phẩm phù hợp dựa trên thuật toán chấm điểm 7 tiêu chí.

---

### Phương thức 2: Chạy trọn gói nhanh bằng Docker Compose

Dành cho người dùng muốn khởi chạy nhanh bằng container mà không cần cài đặt cục bộ MariaDB, Python hay Node.js:

1. **Yêu cầu:** Máy tính đã cài đặt và đang chạy **Docker Desktop** (hoặc Docker Engine + Docker Compose).
2. **Cấu hình môi trường:**
   ```bash
   copy .env.example .env
   ```
   *(Điền `JWT_SECRET_KEY` ngẫu nhiên và `ADMIN_PASSWORD` trong `.env` như hướng dẫn ở Bước 3).*
3. **Khởi chạy hệ thống:**
   ```bash
   docker compose up --build -d
   ```
   *Docker Compose sẽ tự động khởi tạo 3 container: MySQL 8.4 (`ai-room-decor-mysql`), FastAPI Backend (`ai-room-decor-backend` tự chạy migration khi khởi động), và Next.js Frontend (`ai-room-decor-frontend`). Kết nối CSDL giữa backend và MySQL container được cấu hình tự động thông qua Docker Network.*
4. **Theo dõi logs:**
   ```bash
   docker compose logs -f
   ```
5. **Truy cập:**
   - Frontend: `http://localhost:3000`
   - Backend API Docs: `http://localhost:8000/docs`

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
