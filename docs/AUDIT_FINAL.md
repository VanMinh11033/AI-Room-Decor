# Báo cáo tổng kiểm tra đồ án — AI Room Decor

> Ngày: 2026-10-11
> Phạm vi: `D:\AI-Room-Decor`
> Phương pháp: khảo sát code thực tế (read-only), chạy test/typecheck/lint/build, truy vấn DB read-only. **Không** sửa code, **không** gọi API AI trả phí, **không** xóa/sửa dữ liệu.
> Điểm số là đánh giá kỹ thuật nội bộ, **không phải** điểm chính thức của giáo viên.

---

## 1. Tóm tắt hiện trạng

Đồ án thực tế đã vượt xa mô tả trong `README.md` (README đã lỗi thời — vẫn ghi "image generation / recommendation / cart-order để dành cho phase sau", trong khi tất cả đều đã được cài đặt). Hệ thống là một nền tảng decor phòng đầy đủ: tài khoản & phân quyền, catalog sản phẩm, dự án phòng, upload ảnh, phân tích AI, cá nhân hóa, gợi ý sản phẩm theo luật, tạo thiết kế bằng API sinh ảnh, giỏ hàng, đơn hàng và admin dashboard.

**Điểm mạnh**: kiến trúc rõ ràng, tách lớp tốt, backend là nguồn chân lý cho tiền/kho, phân quyền chặt, xử lý lỗi AI phân loại rõ (auth/quota/model/5xx), có fallback trung thực, test suite 238 test phủ khắp, frontend build sạch, UI tiếng Việt nhất quán.

**Điểm yếu chính**: tỉ lệ gọi AI thật **thất bại rất cao** (62/71 phân tích phòng thất bại; 13/22 lần tạo thiết kế thất bại). Nguyên nhân khả nghi nhất là cấu hình Vision (tên model `gemini-3.6-flash` và định dạng API key bất thường) — cần xác minh key/model thật trước khi demo.

---

## 2. Kiến trúc thực tế

- **Frontend**: Next.js 15 (App Router) + React 19 + Tailwind + lucide-react. Giao tiếp qua client API `lib/api.ts` (token lưu `localStorage`).
- **Backend**: FastAPI + SQLAlchemy 2 + Alembic + PyMySQL, JWT (jose) + bcrypt (passlib).
- **Database**: MySQL 8 (qua Docker Compose hoặc local), schema qua 6 migration Alembic (`0001_initial_schema` → `0006_product_image_candidates`).
- **Lưu trữ ảnh**: filesystem (`storage/`), phục vụ tĩnh qua `/storage` mount trên FastAPI; DB chỉ lưu đường dẫn + metadata.
- **AI**:
  - Vision (phân tích phòng): `app/ai/vision/` — `gemini`, `openai`, `local_fallback`.
  - Sinh ảnh (tạo thiết kế): `app/ai/image/` — `cloudflare`, `gemini`, `openai`, `composite` (deterministic, opt-in).
  - Gợi ý sản phẩm: `app/recommendation/` — **thuật toán theo luật (rule-based)**, không gọi LLM.

Luồng cốt lõi: Ảnh phòng → (Vision) Phân tích → (Preference) Cá nhân hóa → (Rule engine) Gợi ý sản phẩm → chọn sản phẩm → (Image API) sinh ảnh → lưu kết quả → lịch sử → thêm vào giỏ hàng → checkout.

---

## 3. Danh sách chức năng và trạng thái

| Nhóm | Chức năng | Trạng thái |
|---|---|---|
| A. Tài khoản | Đăng ký / đăng nhập / refresh token | ✅ Hoàn thành |
| A. Tài khoản | Đăng xuất | ✅ Hoàn thành (xóa token client) |
| A. Tài khoản | Phân quyền CUSTOMER / ADMIN (`require_admin`) | ✅ Hoàn thành |
| A. Tài khoản | Bảo vệ trang/API admin | ✅ Hoàn thành |
| A. Tài khoản | Validate đầu vào + lỗi xác thực | ✅ Hoàn thành |
| A. Tài khoản | Quên / đặt lại mật khẩu | ❌ Chưa có |
| B. Dự án & ảnh | Tạo/liệt kê/archive dự án phòng | ✅ Hoàn thành |
| B. Dự án & ảnh | Upload ảnh (định dạng + dung lượng + signature) | ✅ Hoàn thành |
| B. Dự án & ảnh | Lưu ảnh đúng vị trí, phân biệt ảnh gốc/kết quả | ✅ Hoàn thành |
| C. Phân tích AI | Gọi Vision, lưu kết quả, xử lý lỗi | ✅ Hoàn thành (code) / ⚠️ thực tế tỉ lệ lỗi cao |
| C. Phân tích AI | Fallback deterministic khi Gemini quá tải/quota | ✅ Hoàn thành |
| D. Cá nhân hóa | Chọn phong cách/màu/vật liệu/loại/ngân sách/mục đích | ✅ Hoàn thành |
| D. Cá nhân hóa | Sở thích ảnh hưởng đến gợi ý | ✅ Hoàn thành (qua rule engine) |
| E. Catalog | Danh mục/sản phẩm/giá/ảnh/trạng thái | ✅ Hoàn thành |
| E. Catalog | Lọc + sắp xếp | ✅ Hoàn thành |
| E. Catalog | Gợi ý theo điểm phù hợp + lý do | ✅ Hoàn thành (rule-based) |
| F. Tạo thiết kế | Provider/model thật (Cloudflare flux-2-dev) | ✅ Đã cấu hình |
| F. Tạo thiết kế | Gửi ảnh phòng + ảnh reference sản phẩm + prompt | ✅ Hoàn thành |
| F. Tạo thiết kế | Lưu ảnh kết quả + lịch sử + product_ids | ✅ Hoàn thành |
| F. Tạo thiết kế | Phân biệt trạng thái GENERATING/COMPLETED/FAILED | ✅ Hoàn thành (UI + DB) |
| G. Giỏ hàng | Thêm/nhiều SP, trùng, số lượng, tăng/giảm/xóa | ✅ Hoàn thành |
| G. Đơn hàng | Checkout transactional, snapshot giá, trừ kho | ✅ Hoàn thành |
| G. Đơn hàng | Hủy đơn, admin đổi trạng thái | ✅ Hoàn thành |
| H. Admin | CRUD sản phẩm/danh mục/thuộc tính | ✅ Hoàn thành |
| H. Admin | Duyệt ảnh ứng viên (approve/reject) | ✅ Hoàn thành |
| H. Admin | Thống kê từ DB thật | ✅ Hoàn thành |
| I. Lưu trữ & DB | Models/quan hệ/FK/migration nhất quán | ✅ Hoàn thành |
| I. Lưu trữ & DB | Chống path traversal, giới hạn dung lượng | ✅ Hoàn thành |

Chú giải: ✅ đã triển khai trong code (được test hoặc đọc code); ⚠️ đã triển khai nhưng chưa xác minh được kết quả thật ổn định; ❌ chưa có.

---

## 4. Kết quả kiểm thử (số liệu thật)

| Kiểm tra | Kết quả |
|---|---|
| Backend `pytest` (lần 1) | **157 passed, 81 errors** — toàn bộ 81 error là `PermissionError: Access is denied` trên `C:\...\Temp\pytest-of-LENOVO` (ACL thư mục Temp hệ thống hỏng), **không phải lỗi logic** |
| Backend `pytest` (chạy lại `--basetemp` local) | **Exit code 0 — toàn bộ pass** |
| Backend `--collect-only` | **238 tests** |
| Frontend `npm run typecheck` | **Pass (exit 0)** |
| Frontend `npm run lint` | **0 error, 18 warnings** (16 cảnh báo dùng `<img>` thay `next/image`, 1 `exhaustive-deps`, 1 `no-anonymous-default-export`) |
| Frontend `npm run build` | **Thành công** — 26 route, compiled sạch |

Phân loại test: **238 pass / 0 fail / 0 skip** (sau workaround môi trường). Toàn bộ test là mock/đơn vị + tích hợp qua `TestClient`, **không gọi API ngoài thật** (đúng yêu cầu an toàn). Test phủ: auth, catalog, cart/orders, room projects/preferences/analysis, recommendations, design generations, cloudflare/gemini/composite/openai providers, vision fallback, product image candidates/collector/reference, semantic filter, stock providers, admin monitoring.

---

## 5. Bảng tích hợp API AI

| Chức năng | Provider/model | Đầu vào | Đầu ra | Nơi lưu | Bằng chứng | Trạng thái | Lỗi/giới hạn |
|---|---|---|---|---|---|---|---|
| Phân tích ảnh phòng (Vision) | `gemini` (config model `gemini-3.6-flash`); tùy chọn `openai` | Ảnh phòng + prompt JSON schema | room_type, màu, vật thể, khu trống, ánh sáng, bố cục, confidence | `room_analyses` + `ai_usage_logs` | `test_gemini_provider.py`, `test_vision_fallback.py` | ⚠️ Code đúng nhưng **62/71 bản ghi FAILED** | Model/key khả nghi; cần xác minh thật |
| Fallback phân tích | `local_fallback` / `deterministic-v1` | Ảnh phòng (đo Pillow) | Chỉ màu + kích thước (không bịa room_type/style) | `room_analyses` | `test_vision_fallback.py` | ✅ Đúng thiết kế, trung thực | Chỉ khi Gemini quá tải/quota |
| Gợi ý sản phẩm | **Rule-based** (không AI) | analysis + preference + catalog | score 0-100 + reasons + breakdown | trả về on-demand | `test_recommendations.py` | ✅ Hoàn thành | Đây là thuật toán luật, **không phải AI** |
| Sinh ảnh thiết kế | `cloudflare` (`@cf/black-forest-labs/flux-2-dev`); tùy chọn `gemini`/`openai` | Ảnh phòng + ≤3 ảnh reference SP + prompt v2 | Ảnh decor (bytes) | `storage/generated-room-designs` + `room_design_generations` | `test_cloudflare_image_provider.py`, `test_design_generations.py` | ⚠️ 8 COMPLETED / 13 FAILED | `CLOUDFLARE_IMAGE_SERVER_ERROR` (2), quota Gemini (5) |
| Compositor | `composite` / `deterministic-compositor-v2` (opt-in) | Ảnh phòng + ảnh SP cắt nền | Ảnh ghép PNG | `storage` | `test_design_compositor.py` | ✅ Deterministic, không generative | Từ chối ảnh cảnh (scene) |

**Phân định rõ**: AI phân tích ảnh = Vision; API sinh ảnh = Image generation; gợi ý sản phẩm = thuật toán luật; xử lý ảnh thường = compositor/Pillow. Hệ thống **không tự huấn luyện** mô hình nào (đúng quyết định của giáo viên).

### Ghi nhận về `CLOUDFLARE_IMAGE_SERVER_ERROR`
- Đây là lỗi **thật, đã ghi 2 lần** trong `room_design_generations.error_code` và là HTTP 5xx từ Cloudflare Workers AI (`POST /accounts/{id}/ai/run/{model}`), được code map đúng ở `_map_http_error` (status ≥ 500 → `CLOUDFLARE_IMAGE_SERVER_ERROR`).
- **Chưa tái hiện** trong phiên audit vì sẽ gọi API trả phí (cần sự đồng ý). Không tự chuyển sang compositor/provider khác (đúng yêu cầu).
- Điểm cần lưu ý: Cloudflare image provider **không có cơ chế retry** cho 5xx (khác với Gemini vision provider có retry + backoff). Đây là cơ hội cải thiện độ bền nếu muốn.

---

## 6. Đánh giá UI/UX

Đánh giá dựa trên đọc code + build thành công (chưa chạy browser thật — xem mục 8).

- **Nhất quán**: có design system rõ (màu `clay`/`ink`/`ivory`/`moss`, bo góc, shadow, typography), component dùng chung `DesignPrimitives.tsx`, `ProductCard.tsx`, `ui/Button.tsx`, `ui/Input.tsx`.
- **Luồng AI**: `RoomFlowStepper` 5 bước (Ảnh phòng → Phân tích AI → Cá nhân hóa → Gợi ý → Thiết kế), có trạng thái done/current/pending/error.
- **Trạng thái**: loading, empty, success, error, disabled đều có; lỗi AI hiển thị tiếng Việt rõ ràng; fallback có thông báo "Gemini đang tạm quá tải...".
- **Tiếng Việt**: toàn bộ label/error/thông báo bằng tiếng Việt (một vài error-code kỹ thuật còn để nguyên nhưng đã map sang tiếng Việt ở tầng UI).
- **Responsive**: dùng Tailwind breakpoint (`sm/md/lg/xl`), phù hợp desktop/tablet/mobile.
- **Hạn chế**: dùng `<img>` thay `next/image` (16 warning — ảnh hưởng LCP/tối ưu, không ảnh hưởng chức năng); chưa xác minh bằng trình duyệt.

---

## 7. Danh sách lỗi theo mức độ nghiêm trọng

**Nghiêm trọng (High)**
1. **AI phân tích phòng lỗi hàng loạt** — 62/71 bản ghi `room_analyses` FAILED. Khả nghi: `VISION_MODEL=gemini-3.6-flash` (tên model không chuẩn) và định dạng `GEMINI_API_KEY` (bắt đầu `AQ.` thay vì `AIza`) — cần xác minh key/model thật.
2. **JWT_SECRET_KEY = `change-this-secret-in-local-env`** (giá trị mặc định, chưa đổi) — rủi ro bảo mật nếu chạy ngoài local.

**Trung bình (Medium)**
3. **1 bản ghi `room_design_generations` treo ở `GENERATING`** (không COMPLETED/FAILED) — lỗi nhất quán dữ liệu do request bị ngắt giữa chừng.
4. **Ảnh sản phẩm là ảnh demo** do `seed_product_images.py` vẽ bằng Pillow (thư mục `generated-demo`), không phải ảnh thật — giảm độ tin cậy của ảnh reference khi sinh thiết kế và catalog.
5. **Cloudflare image provider không retry 5xx** — dễ thất bại khi Cloudflare quá tải tạm thời.
6. **Token lưu `localStorage`** (rủi ro XSS) thay vì httpOnly cookie.
7. **Mật khẩu admin mặc định yếu** (`Admin@123456`) + email admin hardcode trong `.env`.

**Thấp (Low)**
8. Không có rate-limiting trên endpoint đăng ký/đăng nhập.
9. `seed_catalog` + `seed_product_images` **không tự chạy lúc startup** — DB mới sẽ trống catalog nếu không seed thủ công.
10. `README.md` / `docs/api.md` / `ai-service/README.md` / `database/README.md` lỗi thời so với code.
11. 18 lint warnings (`<img>`, `exhaustive-deps`, deprecated `on_event`, `jose` utcnow).

---

## 8. Bằng chứng và giới hạn xác minh

**Đã xác minh (có bằng chứng)**
- Code backend/frontend được đọc trực tiếp (routes, services, providers, models, schemas, seed).
- Backend: 238 test pass; frontend: typecheck/lint/build pass.
- DB (read-only): 16 users, 30 products (đủ ảnh), 17 room projects, 71 analyses, 22 design generations, 95 AI usage logs, 1 order (CANCELLED), 15 image candidates.

**Chưa xác minh (UNKNOWN) — cần môi trường/tư vấn thêm**
- Kết quả AI Vision/Sinh ảnh **thật** ở hiện tại: chưa gọi API mới (không muốn tốn credit khi chưa được đồng ý). Key/model Gemini có thể không hợp lệ — cần một lần gọi thử có giới hạn để xác nhận.
- Giao diện chưa được chạy/kiểm tra trên trình duyệt thật (chỉ mới build thành công).
- `CLOUDFLARE_IMAGE_SERVER_ERROR` chưa tái hiện (sẽ tốn credit Cloudflare).

---

## 9. Yêu cầu còn thiếu để sẵn sàng demo & bảo vệ

1. Xác minh và sửa cấu hình **Gemini Vision** (key/model hợp lệ) — đây là chặn lớn nhất cho demo phân tích phòng.
2. Xử lý bản ghi `GENERATING` bị treo (cơ chế timeout/mark-failed cho generation chưa hoàn tất).
3. Đổi `JWT_SECRET_KEY` và mật khẩu admin trước khi chạy trình diễn.
4. Cân nhắc thay ảnh sản phẩm demo bằng ảnh thật (nếu có nguồn hợp lệ) để reference sinh ảnh và catalog thuyết phục hơn.
5. Cập nhật `README.md`/docs cho khớp thực tế (phục vụ báo cáo).

---

## 10. Kế hoạch khắc phục (ưu tiên)

1. **Xác minh Gemini key/model** (1 lần gọi thử có giới hạn) → sửa tên model về model thật đang hỗ trợ.
2. **Thêm retry có giới hạn + backoff cho Cloudflare 5xx** và **đánh dấu failed** cho generation treo (job/timeout).
3. **Bảo mật**: đổi JWT secret + admin password, cân nhắc httpOnly cookie.
4. **Dữ liệu**: thay/làm giàu ảnh sản phẩm thật (nếu có nguồn được phê duyệt), tự động seed catalog khi startup.
5. **Tài liệu + UI**: cập nhật README, thay `<img>` → `next/image`, thêm rate-limiting, (tùy chọn) thêm quên mật khẩu.

---

## 11. Kết luận & chấm điểm

**Có thể demo chưa?** Ở mức cấu trúc và chức năng: **có thể demo được luồng đầy đủ** (đăng ký → dự án → upload → phân tích → cá nhân hóa → gợi ý → sinh ảnh → giỏ hàng → đơn hàng → admin). Tuy nhiên demo **phân tích AI và sinh ảnh** đang có rủi ro thất bại cao vì cấu hình Gemini/Cloudflare chưa được xác minh ổn định — cần xử lý mục 1–2 ở trên trước.

**Có thể hoàn thiện báo cáo chưa?** Có — kiến trúc và phạm vi đã đủ để viết báo cáo. Nên ghi rõ trong báo cáo: recommendation là thuật toán luật (không phải AI), Vision/Image là API AI có sẵn (không tự train).

**Điều kiện cần đạt trước khi nộp**: (1) Vision và Image generation chạy thật ít nhất 1 lần thành công end-to-end; (2) không còn bản ghi trạng thái sai; (3) bảo mật cơ bản (JWT secret, admin password) đã đổi.

**Điểm tham khảo (thang 100, nội bộ)**

| Hạng mục | Điểm | Ghi chú |
|---|---|---|
| Chức năng | 78 | Đầy đủ, thiếu quên mật khẩu |
| AI/API | 70 | Tích hợp chuẩn nhưng tỉ lệ lỗi thật cao |
| Giao diện | 82 | Đồng bộ, tiếng Việt, đủ trạng thái (chưa browser-verify) |
| Độ ổn định | 72 | Build/test pass; AI thật + bản ghi treo |
| Bảo mật | 72 | Phân quyền tốt; secret mặc định, token localStorage |
| Khả năng trình bày | 78 | Kiến trúc rõ, dữ liệu demo có sẵn |
| **Tổng (tham khảo)** | **≈ 75** | Đánh giá nội bộ |

---

## 5 việc quan trọng nhất cần làm tiếp theo

1. **Xác minh & sửa cấu hình Gemini Vision** (key + tên model) — chặn lớn nhất cho demo phân tích phòng (62/71 lần thất bại hiện tại).
2. **Sửa bản ghi `GENERATING` treo + thêm retry 5xx cho Cloudflare** — để sinh ảnh ổn định và dữ liệu nhất quán.
3. **Đổi `JWT_SECRET_KEY` và mật khẩu admin** trước khi chạy trình diễn.
4. **Chạy thử end-to-end 1 lần trên trình duyệt thật** (phân tích → gợi ý → sinh ảnh) để có bằng chứng demo, sau khi đã xử lý mục 1.
5. **Cập nhật README/docs + thay ảnh sản phẩm demo bằng ảnh thật** (nếu có nguồn hợp lệ) để báo cáo và catalog thuyết phục hơn.
