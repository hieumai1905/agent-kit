# Guard và checkpoint trước patch trong delegated ADVISORY

Dùng với protocol ủy quyền opt-in; không là protected writer hoặc quyền OS.

## Luồng bắt buộc

`tools/checked_patch_flow.js` có một hàm async không phụ thuộc package: `checkedPatchFlow(steps)`. Agent dùng đúng hàm đó trong **một** invocation JavaScript của provider. Ba callbacks tuần tự:

1. **prepare:** gọi `prepare-write` bằng decision checkpoint đã điền, với expected revision PROGRESS. Python kiểm report/freshness/baseline → lưu CONTRACT_DECISION/IMPLEMENTING → đọc lại chính record đó → kiểm lại. Không trả kết quả prepared nếu bất kỳ bước nào lỗi.
2. **recheck:** ghi đúng checkpoint_ref trả về vào JSON ngoài repo và gọi `check-write`. Helper đọc latest record thật, từ chối ref sai/đã bị thay thế, contract/source đổi, stop flags hoặc observation hết hạn. Không initialize/migrate state và không tự làm mới timestamp.
3. **patch:** chỉ sau cả hai kết quả thành công và cùng reference, gọi tool patch có sẵn của provider. Kit Python không ghi product code. Sau đó phải review kết quả/tool output/file hashes; callback được gọi không có nghĩa patch/test/DoD đã PASS.

Các kết quả nonzero, pending session, thiếu exit code, tool isError, JSON hỏng, status sai hoặc ref đổi đều trả STOPPED_NO_FURTHER_PATCH trước patch. Không gọi apply_patch riêng sau đó và không chạy guard/patch song song. Không dựa vào việc parent functions tool đã chạy xong để coi child command là thành công.

`STOPPED_NO_FURTHER_PATCH` có `patch_called` để phân biệt lỗi precondition (false) với lỗi tool patch sau khi đã được gọi (true). Lỗi sau patch có thể để lại thay đổi; không tự retry hoặc rollback. Kiểm tra thực tế rồi báo phần đã/chưa làm.

## Lệnh và dữ liệu

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" checkpoint-template TASK_ID --milestone CONTRACT_DECISION
python3 tools/agentflow.py --repo "/ABS/REPO" prepare-write TASK_ID "/OUTSIDE/decision.json" --expected-revision N
python3 tools/agentflow.py --repo "/ABS/REPO" check-write TASK_ID "/OUTSIDE/checkpoint-ref.json"
```

Agent kiểm current contract và điền template theo CONTINUITY.md: phase IMPLEMENTING, summary/completed/remaining/next_action, blockers rỗng, source_hashes cho mọi file dự kiến patch. `advisory_delegation` phải là report đầy đủ của DELEGATED_ADVISORY.md, có canonical_contract_binding đúng core, cùng contract document thật và digest envelope D, cùng task/files/actions, native source observations còn dưới 30 giây và được agent báo ELIGIBLE sau review độc lập. Đây vẫn là dữ liệu cùng UID chưa được chứng thực; helper không xác thực ai đã nói gì.

prepare-write trả:

```json
{
  "process_result": "DECISION_CHECKPOINT_SAVED_UNVERIFIED",
  "checkpoint_ref": {
    "task_id": "...", "record_id": "...", "revision": 1,
    "sha256": "...", "contract_sha256": "...", "contract_revision": 2
  },
  "trusted": false, "write_authorized": false, "native_certified": false
}
```

Chỉ lưu object `checkpoint_ref` cho check-write. Ref không là token hay grant; cùng UID có thể sửa dữ liệu, và helper luôn đọc record hiện hành. Kết quả check là DECISION_CHECKPOINT_RECHECKED_UNVERIFIED. Kết quả cuối JS là PATCH_TOOL_RETURNED_REVIEW_REQUIRED, không là VERIFIED/COMPLETED.

## Dùng trong provider

Đọc helper JS trong bản kit đang cài, giữ đúng định nghĩa hàm đã kiểm thử, rồi gọi với callbacks dùng tools hiện có. `prepare`/`recheck` trả raw object exec_command (`exit_code`, `output`, có thể session_id/isError). `recheck` chuyển đúng ref sang JSON ngoài repo, dùng shell quoting đúng hoặc file API để không biến JSON thành shell code. `patch` không được xuất hiện ở đường nào khác của invocation đó. Không cần Node để chạy hàm trong JS isolate của provider; Node chỉ là runtime tùy chọn cho tests local.

Chuẩn bị candidate/metadata/hash cần thiết **trước** lần native source review cuối. Sau khi đọc H/D và thông điệp mới, ghi gọn anchors, bindings, kết luận và observation time thật; không nhét cả transcript lồng nhau vào shell argv. Timestamp chỉ thay đổi sau khi đọc native source mới thực sự, không gán thời gian hiện tại cho dữ liệu cache. Nếu quá 30 giây thì dừng/đọc lại; không tăng TTL để che lỗi.

Khi ghi anchor mới nhất, kiểm thứ tự mà provider trả về: `turns` có thể newest-first nhưng `items` trong từng turn vẫn chronological. Không dùng `.find(...)` trên toàn bộ mảng flatten rồi đặt tên là `latest_message_id`; đối chiếu message cuối liên quan trong turn mới nhất và lưu ID của lần đọc native. Nếu phát hiện metadata sai, giữ evidence gốc và đính chính riêng. Anchor và trace tự báo không thay thế transcript thực tế hoặc xác thực danh tính.

## Giới hạn

Hàm chặn callback patch trong luồng đã kiểm; agent vẫn có thể gọi tool khác ngoài luồng. Native H/D phải được đọc riêng, không dùng report/helper output làm authority. Read-then-write không nguyên tử với thu hồi quyền hoặc writer khác.
