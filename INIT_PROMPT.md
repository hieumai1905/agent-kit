# Prompt init mặc định — v1.1.1

Copy toàn bộ khối dưới và gửi agent tại Git root dự án muốn dùng. Mặc định là thư mục đang làm việc trước khi clone. Prompt chỉ cấp quyền setup, không giao sẵn một task sửa sản phẩm.

```text
Thiết lập và áp dụng Agent Workflow Kit v1.1.1 cho thư mục đang làm việc hiện tại, rồi chờ tôi giao việc.

1. Chốt TARGET_CWD bằng pwd -P trước mọi cd/clone/setup. Xác minh đây là đúng Git root dự án tôi đang làm. Nếu không đúng root hoặc có nhiều repo mơ hồ thì báo rõ trước setup; không tự chọn repo cha/con, git init hay cài hàng loạt.

2. Dùng Git và Python 3.11+ có sẵn; thiếu thì báo đúng phần thiếu, không tự cài. Clone bằng git clone --branch v1.1.1 --single-branch https://github.com/hieumai1905/agent-kit.git vào ~/.local/share/agent-workflow-kit/v1.1.1 ở ngoài repo dự án. Nếu clone đã tồn tại, kiểm origin, HEAD và working tree; không reset/clean/pull hoặc ghi đè thay đổi. Runtime commit bắt buộc: bd95478cd909777104df52ba49fb13dca832c780. Resolve annotated tag bằng refs/tags/v1.1.1^{commit}; HEAD, peeled tag local và peeled tag trên remote phải cùng đúng SHA này. Không fallback sang main/latest hoặc bản cũ khi sai lệch.

3. Chạy python3 -B KIT/tools/verify_release.py; đọc README.md và BOOTSTRAP.md. Tôi chọn ADVISORY và cho phép setup trong chat này. Dùng lại state-home ngoài repo nếu đã có, giữ state/history. Preview rồi apply cùng backup/local-only protection. Nâng cấp đúng managed block kit cũ trong AGENTS.md và CLAUDE.md; giữ luật riêng và thay đổi người dùng. Tracked/mixed/customized guidance, override xung đột, writer bận hoặc source đổi bất ngờ phải được đối chiếu; không xóa luật, unstage/untrack, force-add, đổi .gitignore/hooks hoặc takeover để vượt kiểm tra.

4. Sau apply, đọc lại guidance trong chat này. Chỉ báo SETUP_READY khi version, doctor, artifacts/INDEX và đối chiếu source/index/HEAD đạt. Clone, state, backup, payload, note, log và receipt kit ở ngoài repo dự án; guidance kit-only được bảo vệ local-only, không vào commit dự án. Product regression tests vẫn đi cùng code sản phẩm.

5. Khi tôi giao việc, dùng đúng quyền đã giao: yêu cầu triển khai rõ có thể đủ quyền; nếu tôi yêu cầu đề xuất trước/chưa sửa thì chờ duyệt. Tự xử lý quyết định kỹ thuật, regression và sửa lỗi trong phạm vi. Giữ khóa file/giới hạn cụ thể; không tự thêm allowance vào task cũ. Phát sinh tác động vượt quyền thì giải thích vấn đề, ảnh hưởng, bằng chứng, cách sửa và lý do, kiểm chứng cùng chính xác phần cần tôi quyết định. Trình bày dễ hiểu; không dùng ID, JSON hay đường dẫn dài thay giải thích.

Theo begin → verify → handoff; test lỗi thì retry trước sửa tiếp. File đã biết ghi nhận ngay từ begin; file mới trong allowance dùng refine trước patch. Khi tôi nhắc phương án đã trình, đọc work proposal của đúng việc để giữ nguyên đường dẫn/kiểm chứng, không tự dựng lại dưới tên mới. Đề xuất đang chờ không thay active scope; chỉ tiếp tục phần độc lập đã được phép. Dùng next_command do helper trả về; tiếp tục receipt của chính chat, không begin lại hoặc nhầm writer của mình thành chat khác. Runtime tự nhận identity. CODE/CLI/UI phải khớp yêu cầu thực; không suy UI chạy được từ unit tests. Lifecycle canonical chưa đổi không tự có nghĩa là thiếu approval.

Setup không cho phép sửa code sản phẩm, cài dependencies, đổi model/settings, thêm agent hay stage/commit/push/deploy. Chỉ áp dụng cho chat này; không gửi tin hoặc cập nhật các chat khác. Hoàn tất thì báo ngắn gọn phiên bản, repo đích, kết quả setup và trạng thái chờ nhận việc.
```
