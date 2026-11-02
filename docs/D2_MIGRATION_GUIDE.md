# Đ2 — SQLite v2 → v3 migration và rollback

- **Đ1** dùng schema v2. **Đ2 prototype** dùng schema v3, chỉ thêm `approval_challenges` và `verified_approval_receipts`; mọi state thực thi vẫn không được tự cấp quyền.
- Trước khi khởi tạo Đ2 với state directory Đ1, **backup state Đ1** bằng CLI Đ1 trên repo thử. `LocalCoordinator()` tự migrate tiến lên v3 trong transaction; giữ lại tất cả records cũ và checksums migrations.
- Sau khi migrate, **không thể dùng binary Đ1 để mở DB v3**; cơ chế downgrade tại chỗ không được hỗ trợ. Nếu cần quay về Đ1, khôi phục bản backup Đ1 vào **state directory mới**, không overwrite database v3 đang chạy.
- Không có migration tự động từ Preview đời cũ chưa version hóa; đã được từ chối từ Đ1.
- File `docs/D1_STATE_API.md`, `.release/WAVE1_ACCEPTANCE.json` và `WAVE1_MANIFEST.json` được giữ như **tài liệu và chứng cứ lịch sử** cho source Đ1; source hiện hành sau Đ2 là schema v3 và audit `.release/WAVE2_ACCEPTANCE.json`.
- Cả v2/v3 đều cùng user sở hữu SQLite, KHÔNG phải trust boundary.
