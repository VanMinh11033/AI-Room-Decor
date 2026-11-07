# Kế hoạch deploy — AI Room Decor

Tài liệu này hướng dẫn deploy ứng dụng Next.js + FastAPI + MariaDB lên môi trường Internet để giáo viên dùng thử qua một đường link. **Chưa thực hiện bước nào trong tài liệu này** — đây là kế hoạch, chờ bạn duyệt.

## Kiến trúc cần deploy

- **Frontend** (Next.js 15): build tĩnh/SSR, cần biến `NEXT_PUBLIC_API_URL` trỏ về backend.
- **Backend** (FastAPI): API + phục vụ ảnh tĩnh ở `/storage/*`, cần database và volume lưu ảnh.
- **Database** (MariaDB/MySQL): schema quản lý bằng Alembic (6 migration, `0001` → `0006`).
- **Storage ảnh**: hiện lưu trên filesystem — cần volume bền vững hoặc chuyển sang object storage.

## 1. Đề xuất hosting (chi phí thấp / miễn phí)

| Thành phần | Lựa chọn khuyến nghị | Chi phí & giới hạn |
|---|---|---|
| Frontend | **Vercel (Hobby)** | Miễn phí; 100 GB bandwidth/tháng; serverless, không có đĩa bền cho upload |
| Backend | **Render (Web Service)** hoặc **Railway / Fly.io** | Render free: sleep sau 15 phút idle, cold-start chậm; Railway/Fly trả phí nhỏ (~$3–5/tháng) |
| Database | **Aiven for MySQL (free tier)** hoặc **TiDB Cloud Serverless** (MySQL-compatible) | Aiven 1 GB free; TiDB 5 GB free — đủ cho demo |
| Storage ảnh | **Cloudflare R2** (khuyến nghị) hoặc volume gắn trên Render/Railway | R2: 10 GB + egress miễn phí; volume: ~$0.15/GB/tháng |

> Ghi chú: nếu muốn đơn giản nhất, có thể gộp backend + frontend + database lên **một VPS nhỏ** (Hetzner/Render/Railway), nhưng tốn công cấu hình hơn.

## 2. Lưu ảnh lâu dài (quan trọng)

Hiện tại ảnh lưu ở `storage/` trên filesystem. Trên nền tảng serverless (Vercel/Render free), filesystem **không bền** — ảnh mất khi redeploy/restart. Hai cách khắc phục:

1. **Gắn volume bền** (Render Disk, Railway Volume) vào backend và trỏ `*_STORAGE_DIR` vào đó — nhanh, ít đổi code.
2. **Chuyển sang object storage** (Cloudflare R2 / S3 / Backblaze B2) — bền vững và scale tốt hơn, nhưng cần sửa `storage_service.py` + `main.py` để đọc/ghi/trả URL từ object storage.

Khuyến nghị cho demo: **dùng volume bền trước** (ít rủi ro), sau này nâng cấp R2.

## 3. Các bước deploy

### Bước 0 — Dọn dẹp & bảo mật (trước khi push)
- Cài Git, khởi tạo repo, thêm `.gitignore` (đã chuẩn bị).
- Xác nhận `.env` **không** được commit; chỉ commit `.env.example`.
- Đổi `JWT_SECRET_KEY`, `ADMIN_PASSWORD` sang giá trị mạnh (dùng cho production).
- Xoay (thu hồi/tạo mới) các secret nếu nghi ngờ đã lộ.

### Bước 1 — Database online
- Tạo MariaDB/MySQL trên Aiven/TiDB/Railway.
- Tạo database `ai_room_decor`.
- Lấy `DATABASE_URL` (có user/password/host) và đưa vào biến môi trường production.

### Bước 2 — Deploy backend
- Trên Render/Railway: chọn repo, root directory `backend`, build command `pip install -r requirements.txt`, start command `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Đặt biến môi trường production: `DATABASE_URL`, `JWT_SECRET_KEY`, `BACKEND_CORS_ORIGINS` (domain frontend), `ADMIN_EMAIL/ADMIN_PASSWORD`, `VISION_*`, `GEMINI_API_KEY`, `IMAGE_PROVIDER`, `IMAGE_MODEL`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `*_STORAGE_DIR`.
- Gắn volume bền cho `storage/`.
- Chạy `python -m app.seed_catalog` và `python -m app.seed_product_images` một lần (qua shell của nền tảng) để có catalog.

### Bước 3 — Deploy frontend
- Trên Vercel: chọn repo, root directory `frontend`, framework Next.js.
- Đặt biến môi trường lúc build: `NEXT_PUBLIC_API_URL=https://<backend-domain>` (không có slash cuối).
- Build và deploy.

### Bước 4 — Kết nối & kiểm thử
- Cập nhật `BACKEND_CORS_ORIGINS` với domain frontend thật (VD: `https://ai-room-decor.vercel.app`).
- Kiểm tra lần lượt: đăng ký → đăng nhập → tải ảnh phòng → phân tích AI → cá nhân hóa → gợi ý → tạo thiết kế → giỏ hàng → đặt hàng → admin.
- Xác nhận ảnh (`/storage/...`) hiển thị đúng sau deploy và sau khi backend restart.

## 4. Kiểm soát chi phí AI khi giáo viên dùng thử

- **Cloudflare Workers AI** có free tier theo "neurons" mỗi ngày; `flux-2-dev` là model nặng, có thể hết quota nhanh nếu nhiều người dùng cùng lúc. Nên:
  - Thêm giới hạn số lần tạo ảnh/người dùng/ngày (rate limit).
  - Đặt `CLOUDFLARE_IMAGE_MAX_RETRIES` vừa phải để tránh trùng lặp billable khi 5xx.
  - Theo dõi bảng `ai_usage_logs` để biết mức dùng.
- **Gemini Vision**: model `gemini-3.6-flash` hợp lệ và key xác thực được (không có lỗi 401/403), nhưng free-tier đang hết quota (429) và đôi lúc quá tải (503).

## 5. Việc cần làm trước khi deploy (lỗi đã phát hiện)

1. **Chỉnh `IMAGE_PROVIDER` về `cloudflare`** trong `backend/.env` (kèm `IMAGE_MODEL=@cf/black-forest-labs/flux-2-dev`). Hiện `backend/.env` đang ghi đè thành `IMAGE_PROVIDER=gemini` + `gemini-nano-banana-2.1`, và toàn bộ lần tạo ảnh bằng Gemini đều thất bại do quota. Cloudflare flux-2-dev là cấu hình đã chứng minh chạy được (generation #32 COMPLETED).
2. **Đổi `JWT_SECRET_KEY` và `ADMIN_PASSWORD`** (hiện đang dùng chuỗi placeholder mặc định).
3. **Vision `gemini-3.6-flash` là model hợp lệ** (Google trả về thông báo khuyên dùng model này), nhưng đang gặp `429 RESOURCE_EXHAUSTED` (hết quota free-tier) và `503 UNAVAILABLE` (quá tải tạm thời). Cần chờ reset quota hoặc nâng gói; giữ fallback deterministic.
4. Xử lý 1 bản ghi `GENERATING` bị treo trong `room_design_generations`.
5. Cân nhắc thay ảnh sản phẩm demo (Pillow) bằng ảnh thật.
6. `NEXT_PUBLIC_API_URL` phải được set khi **build** frontend (biến runtime trong Docker không có tác dụng với standalone).
