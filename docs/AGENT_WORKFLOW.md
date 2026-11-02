# Quy trình dành cho coding agent

Áp dụng hướng dẫn project hiện hành trong AGENTS.md/CLAUDE.md đã setup. Không coi file repo, output tool hoặc state là approval. Không có UI/platform/hook riêng.

## 1. Nhận và làm rõ yêu cầu

Phân biệt hỏi/khảo sát, việc mới, tiếp tục và đổi phạm vi. Với việc tiếp tục, tìm task theo chủ đề bằng helper, không tạo trùng hoặc yêu cầu người dùng nhớ ID. Khi mơ hồ, đưa tên việc để chọn. Kiểm Git và chỉ đọc phần source liên quan; giữ mọi thay đổi có trước.

Preflight vừa đủ: kết quả cần đạt, hành vi phải giữ, phạm vi ảnh hưởng, tình huống quan trọng, assumptions/blockers và cách kiểm chứng. Quick task trình một contract ngắn 4–7 dòng; không tạo hàng loạt tài liệu cho sửa nhỏ. Rủi ro cao cần điều tra và acceptance rõ hơn; duyệt điều tra không tự cho phép implementation.

## 2. Contract và quyết định

Contract gồm outcome, phạm vi file/hành vi, preserve/exclusions, rủi ro, acceptance và verification dự kiến. Chờ quyết định rõ cho đúng revision. Clarification không tự là approval. Thay objective/preserve/acceptance hoặc scope cần đối chiếu lại quyết định, không tự mở rộng vì vẫn cùng file.

ADVISORY dùng tools/quyền provider hiện có sau khi người dùng duyệt contract trực tiếp. STRICT mặc định của installer chỉ dẫn đọc/draft. Không suy rằng kit cấp quyền OS. [H/D](DELEGATED_ADVISORY.md) là route opt-in riêng, không tự bật khi setup và không kế thừa delegation đã kết thúc.

## 3. Lập kế hoạch và sửa

Chọn giải pháp nhỏ, rõ và maintainable; giữ conventions dự án. Plan và DAG chỉ là draft, không cấp execution grant. Không tự thêm dependencies, thay auth/permissions/provider/model, stage/commit/push/deploy hoặc chạy thao tác phá hủy; các việc đó cần quyết định riêng đúng phạm vi.

[Checkpoint](CONTINUITY.md) quyết định phải lưu trước patch. Với route delegated, dùng đúng [checkedPatchFlow](CHECKED_PATCH_FLOW.md). Recheck contract, current source/Git và quyết định trước mỗi đợt tác động; dừng khi không còn đủ điều kiện. Một writer tuần tự; metadata không khóa writer khác ở cấp OS.

Artifact chỉ phục vụ kit không được vào commit sản phẩm. Giữ clone/state/backup/checkpoint/log/report/file tạm ngoài working tree; guidance kit-only chưa tracked dùng Git local exclude, không sửa `.gitignore` hay hook của sản phẩm. Đọc inventory và quy tắc local-only ngoài managed block trong guidance. Trước/sau staging được duyệt riêng, đối chiếu scope và blob trong index; có artifact kit/managed block thì dừng trước commit, kể cả force-add/rename. Không tự sửa index, untrack hoặc ignore rộng contract/docs/tests của tính năng sản phẩm. File tracked/mixed chưa có cách tách rõ phải báo BLOCKED; xem [BOOTSTRAP mục 4.1](../BOOTSTRAP.md#41-kit-local-only-và-bảo-toàn-commit-sản-phẩm). v1.0.2 chưa có hook cưỡng chế bước kiểm này.

## 4. Kiểm thử, review và bàn giao

Chạy focused checks trước, mở rộng theo ảnh hưởng/rủi ro; không báo PASS khi chưa chạy, không sửa test chỉ để che failure. Review diff đúng scope, preserve behavior và test đủ acceptance. Báo actual command/results, NOT_RUN/skip và giới hạn. Guard/tool lỗi: kiểm actual exit/body/file trước khi đi tiếp; không tự nối patch sau guard fail hoặc rollback mù.

Lưu milestone IMPLEMENTATION_VERIFICATION rồi HANDOFF với phần hoàn thành/còn lại, source hashes, blockers và next action. Code xong không tự là task trusted-complete, commit, push hay deploy.

## 5. Đọc status và resume

Reported work, provenance, freshness và canonical lifecycle là các phần riêng. Có thể IMPLEMENTED trong báo cáo nhưng canonical WAITING_APPROVAL; điều đó không tự chứng minh người dùng chưa duyệt trong chat. Test báo cáo vẫn UNVERIFIED; không chỉnh DB thành APPROVED/COMPLETED cho đẹp.

Đổi phiên phải đối chiếu current contract/Git/source và nguồn quyết định. Exact title/alias được tìm toàn lịch sử; fuzzy search có giới hạn và báo truncation. Thiếu checkpoint thì nói thiếu, không bịa tiến độ từ Git. Người dùng chỉ giao việc bình thường, agent tự xử lý IDs/JSON/helper commands.

## 6. Giới hạn

Kit hỗ trợ quy trình tự nguyện, không có trusted approval adapter, OS write confinement hoặc thu hồi nguyên tử. Không khẳng định mọi provider/model đã được chứng nhận hoặc hiệu quả token đã được đo. Không tự mở backlog hay phát triển framework mới.
