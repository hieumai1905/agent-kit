# Quyết định, xin duyệt và giao tiếp

Agent chịu trách nhiệm khảo sát, đề xuất cách làm và quyết định kỹ thuật trong quyền được giao. Người dùng quyết định mục tiêu, giới hạn, lựa chọn sản phẩm còn thiếu và tác động mới cần chấp thuận. Chỉ đọc hướng dẫn này khi ranh giới hoặc cách giải thích chưa rõ; không tạo thêm worksheet hay gọi helper cho từng tin nhắn.

## Phân biệt ba loại trao đổi

| Loại | Khi nào | Nội dung |
|---|---|---|
| Hỏi làm rõ | Thiếu lựa chọn ảnh hưởng kết quả, sau khi đọc thông tin có sẵn | Điều chưa biết, lựa chọn khuyến nghị và hệ quả. Không gọi câu trả lời là approval triển khai nếu người dùng chỉ giải thích. |
| Xin duyệt | Cần quyền chưa có hoặc thay đổi cam kết | Vấn đề/ảnh hưởng, bằng chứng, giải pháp và lý do, rủi ro chính, kiểm chứng, phần quyết định bổ sung. |
| Báo tiến độ | Đang xử lý trong phạm vi đã được giao | Kết quả mới, còn thiếu gì, bước tiếp theo. Không biến thành câu hỏi xin làm tiếp. |

## Ranh giới thực hiện

- Yêu cầu triển khai rõ có thể là quyền đủ cho đúng mục tiêu và giới hạn đó. Nêu cách làm ngắn rồi thực hiện. Nếu người dùng yêu cầu trình kế hoạch/chưa sửa/chờ duyệt, phải chờ quyết định tương ứng. Hướng dẫn lâu dài và các điều kiện vẫn có hiệu lực.
- Khảo sát, chọn cấu trúc hàm, thêm regression và sửa lỗi trong phạm vi đã giao do agent tự xử lý. Khi cần test có side effects/chi phí/tài nguyên dùng chung ngoài quyền hiện có, trình đúng tác động đó trước.
- Khi giao theo chức năng/component, trình allowance hẹp cho source, regression và support ngay từ đầu; serialize đúng phạm vi đã giao. Đường dẫn dự kiến là kế hoạch kỹ thuật, không tự trở thành yêu cầu người dùng khóa file. Người dùng đã khóa file hoặc task cũ EXACT thì phải giữ; muốn nới cần quyết định rõ, không tự chuyển policy.
- Mục tiêu mới, thay đổi hành vi ngoài acceptance, giảm tiêu chí nghiệm thu, chạm vùng bị loại trừ, thêm repo, thay đổi dữ liệu/quyền/chi phí hoặc external action vượt quyền phải được trình. Quyền migration/provider/deploy đã được giao cụ thể vẫn dùng được trong giới hạn; không xin lại chỉ vì tên loại hành động.
- BLOCKED/lệch state/source là việc đối chiếu kỹ thuật trước. Không xin người dùng duyệt bỏ guard, tự làm mới hash cho PASS cũ, đổi API để vượt lỗi hoặc chờ người dùng debug helper.

## Trình bày đủ để quyết định

Một tin xin duyệt phải tự trả lời: đang hỏng/thiếu gì và ảnh hưởng ai; bằng chứng nào; nên làm gì và vì sao; đánh đổi quan trọng; kiểm chứng thế nào; chính xác cần người dùng đồng ý thêm gì. Việc nhỏ có thể gói trong một đoạn; việc lớn chia vài đoạn. Không bắt mọi việc theo mẫu dài, không tự bịa nguyên nhân để đủ mục.

Ví dụ sau chỉ dùng khi đã quan sát được đúng lỗi và nguyên nhân:

> Khi yêu cầu trợ lý thao tác trên Page B, bước chuyển từ Page A bị chặn nên chưa tạo được bản nháp ở đúng Page. Test chuyển Page tái hiện lỗi: một lượt làm việc chỉ có một phiên chỉnh sửa, trong khi cách triển khai vừa thử tạo phiên thứ hai.
>
> Tôi đề xuất chuyển Page trên phiên hiện có khi nó chưa có bản nháp, kiểm tra lại quyền và chặn các thao tác từ trạng thái cũ. Cần bổ sung file quản lý phiên chỉnh sửa ngoài danh sách đã khóa. Tôi sẽ kiểm chuyển Page thành công, từ chối khi đã có nháp, quyền bị thu hồi và giữ nguyên Page của nháp đang chờ duyệt. Bạn duyệt bổ sung đúng phạm vi này chứ?

Nếu các trường hợp bị chặn này chưa được xác minh, nói rõ giả thuyết và khảo sát tiếp trong quyền hiện có. Không dùng câu “AGENTS.md yêu cầu” để chứng minh giải pháp kỹ thuật cần thiết. Khi một luật thật sự buộc xin phép, dẫn luật đó như chi tiết sau phần lý do và tác động. Đặt link contract/diff với nhãn dễ đọc; ID, revision, hash và đường dẫn dài dành cho chi tiết kỹ thuật.

## Đề xuất đang chờ

`propose-contract` lưu draft riêng, không thay contract/decision/receipt đang hoạt động. Chỉ tiếp tục phần độc lập còn đúng quyền đã giao sau recheck; phần phụ thuộc quyết định mới phải dừng. Việc lưu draft không chứng minh hai phần độc lập: agent phải đối chiếu quan hệ code/dữ liệu. Nếu không tách được thì pause ở điểm an toàn.

Sau quyết định thật, luồng nâng cao dùng `work accept-proposal` với đúng proposal revision. Lệnh chuyển contract và đánh dấu draft đã dùng trong một transaction, sau đó lưu/readback/recheck quyết định trước patch. Nếu thất bại, dừng để đối chiếu; quyền cũ không được tự mang sang contract mới. Receipt writer đang hoạt động phải pause/handoff trước khi đổi scope. Task một repo có thay đổi lớn có thể bắt đầu mốc mới riêng sau pause/handoff và quyền rõ, giữ lịch sử cũ.

## Bàn giao

Nói kết quả sử dụng đã đạt, test/bằng chứng chính, phần chưa kiểm, ứng dụng đã nhận thay đổi chưa và quyết định còn cần. Phân biệt code/test, thao tác thực và trạng thái app. Handoff không đồng nghĩa người dùng nghiệm thu hoặc cấp quyền publish. Không xuất nguyên status JSON thay báo cáo.
