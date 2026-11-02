# Integration & Setup Guide — KHUNG ĐANG XÂY DỰNG

**KHÔNG SỬ DỤNG để cài trên repo thật.** Các lệnh và UI cần được kiểm tra bằng bản release Đ7, không sao chép lệnh Preview như một hướng dẫn chính thức.

## Chương dự kiến

1. Yêu cầu hệ thống và compatibility matrix theo macOS/Codex/Claude phiên bản.
2. Tải kit, xác minh checksum/signature nếu có.
3. Preflight/doctor và bản xem trước thay đổi khi cài.
4. Cài theo từng repo; state directory; cấu hình quyền và trusted approval.
5. Bật/kiểm tra adapter Codex Desktop và Codex CLI.
6. Bật/kiểm tra adapter Claude Desktop Code và Claude Code CLI, xác minh một shared working tree.
7. Khởi tạo và phê duyệt Engineering/Domain Profile lần đầu.
8. Chạy smoke test và chế độ strict; giải quyết NOT_CERTIFIED.
9. Multi-session & Git shared state, cấu hình resource isolation.
10. Upgrade, backup, migration, rollback, uninstall và recovery.
11. Troubleshooting, known limitations và security model.

**Tiêu chí hoàn thành:** Phải có thể làm lại toàn bộ quá trình trên một repo thử macOS bằng đúng từng câu lệnh/hình thức giao diện đã được chứng nhận, không yêu cầu người dùng nhớ Task ID hoặc thay đổi conventions thủ công.
