# Agent Workflow Kit v1.0.1

Bộ kit local giúp làm việc với coding agent theo quy trình: **yêu cầu → contract → duyệt → checkpoint → patch → test/review → handoff**. Đã chốt phạm vi ADVISORY, một executor ghi tuần tự; tiếp tục đóng băng phát triển mở rộng.

## Bắt đầu bằng một prompt

Mở **dự án cần làm việc** trong coding agent, rồi gửi [toàn bộ prompt trong INIT_PROMPT.md](INIT_PROMPT.md). Agent sẽ clone tag `v1.0.1` ra ngoài project, kiểm kit, làm mới managed workflow trong **cả AGENTS.md và CLAUDE.md**, kiểm state/path/override và xác nhận SETUP_READY. Người dùng đã chọn ADVISORY và cho phép setup trong prompt; không phải gõ lệnh hoặc duyệt lại các bước cài thông thường.

**Bắt buộc làm mới/xác minh các file chỉ dẫn**, kể cả khi đã có sẵn. Chỉ clone kit hoặc thấy file tồn tại chưa được tính là setup xong. Nội dung riêng của dự án được giữ nguyên; custom block/override xung đột phải được báo trước khi có thể tiếp tục. [BOOTSTRAP.md](BOOTSTRAP.md) mô tả đầy đủ điều kiện nghiệm thu.

Sau setup chỉ cần nói: “Sửa lỗi …”, “Thêm …”, “Tiếp tục việc …”. Agent tự tìm task/khảo sát và trình contract; bạn duyệt contract trước khi code. Cài kit không phê duyệt task sản phẩm và không tự cho phép commit/push/deploy.

## Nội dung repo

- [INIT_PROMPT.md](INIT_PROMPT.md): một prompt copy/paste cho người dùng.
- [BOOTSTRAP.md](BOOTSTRAP.md): quy trình setup bắt buộc cho agent.
- [README_START_HERE.md](README_START_HERE.md), [hướng dẫn dùng](guides/00_BAT_DAU_V1_0.md): tài liệu vận hành; các ví dụ Concat là bối cảnh pilot trên máy tác giả, không là đường dẫn cài cho người khác.
- `agentflow_core`, `agentflow_runtime`, `agentflow_security`, `agentflow_si`, `tools`, `tests`: toàn bộ source/helper và tests của kit.
- `release`, `docs`, `native`, `source-preview`: nghiệm thu và tài liệu theo mốc; legacy/preview không phải installer chính, không tự kích hoạt backlog hoặc hooks cũ.

## Kiểm thử và đóng gói

Python 3.11+ và Git. Không cần package mới để cài guidance. Một số test/lab dùng cryptography hoặc Node nếu máy đã có; skip phải được báo riêng.

```sh
python3 -B tools/verify_release.py
python3 -B tools/release_acceptance.py
python3 -B tools/build_practical_release.py
```

Builder xuất ZIP và checksum ra **thư mục cha của checkout**. Không đặt checkout ngay cạnh một artifact cùng tên mà bạn muốn giữ nguyên. Metadata `.git` không được hash/đóng gói; các file payload khác vẫn được kiểm nghiêm ngặt. Hai báo cáo local có thể chạy lại không nằm trong manifest; checksum ZIP bao phủ toàn bộ bản giao. Manifest/checksum kiểm toàn vẹn, không chứng thực nhà phát hành.

## Phạm vi đã kiểm

v1.0.1 sửa F1–F5: lookup task cũ và intake transaction, kiểu JSON/placeholder, phản hồi state lỗi, nested Cargo/CI discovery. Xem [nghiệm thu v1.0.1](release/V1_0_1_ACCEPTANCE.json); [nghiệm thu phân phối Git/setup](release/GITHUB_DISTRIBUTION.json) ghi kiểm thử bổ sung. Các kết quả A4 là pilot có giới hạn trên Concat, không phải mọi task/provider.

ADVISORY phụ thuộc agent tuân thủ và permissions provider; chưa có mandatory OS write boundary/trusted approval adapter hoặc multiwriter safety. Không tự đổi sandbox/auth/model, không dùng workflow lịch sử để mở rộng phạm vi. Claude có file hướng dẫn tương thích nhưng chưa được chứng nhận native như Codex local.

Các bản ZIP có checksum được lưu ở trang Releases của repo; tag `v1.0.1` là phiên bản dùng cho prompt init. Không di chuyển/xóa kit đang được project tham chiếu và không reset/pull đè source local đã tùy biến.
