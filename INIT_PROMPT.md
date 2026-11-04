# Prompt init mặc định — v1.1.0

Copy toàn bộ khối dưới và gửi agent trong thư mục dự án muốn làm việc. Thư mục hiện tại được chốt trước khi clone.

```text
Thiết lập và áp dụng Agent Workflow Kit v1.1.0 cho thư mục đang làm việc hiện tại.

1. Chốt TARGET_CWD bằng pwd -P trước mọi cd/clone/setup. Dùng đúng Git root hiện tại; không tự chọn repo cha/con, git init hay setup hàng loạt.

2. Dùng Git và Python 3.11+ có sẵn; nếu thiếu thì báo đúng phần thiếu, không tự cài. Clone bằng git clone --branch v1.1.0 --single-branch https://github.com/hieumai1905/agent-kit.git vào ~/.local/share/agent-workflow-kit/v1.1.0 ở ngoài TARGET_CWD. Nếu đường dẫn đó nằm trong repo, chọn vị trí bền vững khác bên ngoài. Nếu clone đã tồn tại, kiểm tra origin, HEAD và working tree; không reset/clean/pull hoặc ghi đè thay đổi. Runtime commit bắt buộc là 0dfecbb8971f495fa70dc8073a0214b5f2fbc907. Resolve annotated tag bằng refs/tags/v1.1.0^{commit}; HEAD, peeled tag local và peeled tag trên remote phải cùng đúng SHA này. Không fallback sang main/latest khi không khớp.

3. Chạy python3 -B KIT/tools/verify_release.py; đọc README.md và BOOTSTRAP.md. Tôi chọn ADVISORY và cho phép setup trong chat này: dùng state-home ngoài repo, giữ lại state/history hiện có, preview rồi apply guidance cùng backup/local-only protection. Làm mới đúng managed block kit cũ trong AGENTS.md và CLAUDE.md; giữ mọi luật riêng và thay đổi người dùng. Không bỏ qua tracked/mixed/customized guidance, override xung đột, writer bận hoặc source đổi bất ngờ; báo BLOCKED và đối chiếu, không xóa luật, unstage/untrack, force-add, đổi .gitignore/hooks hoặc takeover.

4. Sau apply, đọc lại guidance để áp dụng trong chat này. Chỉ báo SETUP_READY sau khi version, doctor, artifacts/INDEX và đối chiếu source/index/HEAD đạt. Runtime clone, state, backup, payload, note, log và receipt của kit phải ở ngoài repo dự án và không vào commit dự án. Product regression tests vẫn đi cùng code sản phẩm.

5. Sau setup tôi sẽ giao việc bình thường. Dùng contract ngắn cho việc nhỏ; nhận diện đúng CODE/CLI/UI trước approval và reuse quyền đã có trong phạm vi. Runtime tự nhận identity, không truyền session ID. Luồng begin → verify → handoff; test lỗi thì retry trước đợt sửa; dùng next_command đã trả về. Nghiên cứu chỉ lưu một note riêng trong artifact_directory khi cần, không gọi API task/brief. Structured brief chỉ dùng cho triển khai nhiều mốc đã duyệt. Không suy UI đã hoạt động từ unit tests.

Setup không cho phép sửa code sản phẩm, cài dependencies, đổi model/settings, thêm agent hay stage/commit/push/deploy. Chỉ áp dụng cho chat này; không cập nhật hoặc gửi tin các chat đang chạy khác.
```
