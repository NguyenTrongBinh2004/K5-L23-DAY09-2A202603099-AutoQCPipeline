# Báo cáo Day 09 — Nguyễn Trọng Bình, 2A202603099

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát `10`, xuất bản nháp thử nghiệm tại `submission/export/clean_v1`). Từ **224** ảnh thô ban đầu, bước nhận dữ liệu loại **31** ảnh lỗi/trùng/rò rỉ và giữ lại **193** ảnh đưa vào dataset. Lý do giữ ở trạng thái **Hold**: toàn bộ lỗi bắt buộc đã được xử lý sạch (`0` ERROR), nhưng sau khi người duyệt (mô phỏng) xử lý hết ngân sách **80/80** ảnh trong hàng đợi **121** ảnh, vẫn còn **34/193** ảnh (**17.62%**, `warn_ratio = 0.1762`) mang cảnh báo, vượt ngưỡng cho phép **10%** (`warn_ratio_hold = 0.10`).

## 2. Lỗi và phân việc

| Mã lỗi | Số ảnh / dòng (`02_error_list_v1`) | Ai sửa (máy / người) | Vì sao |
|---|---:|---|---|
| `LEAK_TEST` | 11 ảnh (11 dòng) | Máy (Intake / Autofix) | Trùng ảnh với tập `test/` hoặc `gold_val/`, phải loại bỏ để chống rò rỉ dữ liệu đánh giá |
| `DUP_IMAGE_EXACT` | 8 ảnh (8 dòng) | Máy (Intake / Autofix) | Trùng từng byte với ảnh đã nhận trước đó, loại bỏ để tránh lệch phân phối và học vẹt |
| `DUP_IMAGE_NEAR` | 7 ảnh (7 dòng) | Máy (Intake / Autofix) | Trùng gần đúng (`phash_dist <= 16`), loại bỏ bản sao dư thừa |
| `BAD_SIZE` | 3 ảnh (3 dòng) | Máy (Intake / Autofix) | Cạnh ngắn nhỏ hơn ngưỡng `250px` (`240x180`, `240x226`), không đủ chi tiết nhận diện |
| `CORRUPT_IMAGE` | 2 ảnh (2 dòng) | Máy (Intake / Autofix) | File ảnh hỏng (`UnidentifiedImageError`, `OSError`), không thể đọc pixel |
| `BOX_OUT_OF_IMAGE` | 8 ảnh (8 dòng) | Máy (Autofix: `clip_box`) | Mép box tràn nhẹ ra ngoài `[0, 1]`, máy cắt an toàn về biên `[0, 1]` mà vẫn giữ nguyên đối tượng |
| `DUP_BOX` | 7 ảnh (7 dòng) | Máy (Autofix: `drop_line`) | Hai box cùng lớp trùng nhau (`IoU > 0.9`), xóa dòng dư thừa phía sau |
| `BAD_CLASS_ID` | 6 ảnh (6 dòng) | Máy (Autofix: `drop_line`) | ID lớp nằm ngoài phạm vi hợp lệ `0..3`, không thể tự đoán lớp đúng nên xóa dòng |
| `BOX_ZERO` | 4 ảnh (4 dòng) | Máy (Autofix: `drop_line`) | Chiều rộng hoặc chiều cao `<= 0` (box không có diện tích), xóa an toàn |
| `BAD_FORMAT` | 3 ảnh (3 dòng) | Máy (Autofix: `drop_line`) | Dòng nhãn sai cấu trúc 5 cột số YOLO, xóa để không làm hỏng quá trình huấn luyện |
| `BAD_CLASS_NAME` | 1 dataset / `data.yaml` (2 dòng) | Máy (Autofix: `rename_classes`) | Tên lớp trong `data.yaml` lệch chuẩn, ghi lại đúng danh sách `[car, person, truck, bus]` |
| `MISSING_LABEL_FILE` | 6 ảnh (6 dòng) | Người (Review queue: `needs_label`) | Ảnh chưa có file `.txt`; máy không thể tự bịa nhãn nên đẩy lên đầu hàng đợi cho người gán |
| `POSSIBLE_MISSING` | 52 ảnh (53 dòng) | Người (Review queue) | Model lớn (`yolo26l`) phát hiện vật thể nhưng nhãn chưa có box; cần người xác nhận ngữ nghĩa |
| `POSSIBLE_FALSE_POS` | 26 ảnh (28 dòng) | Người (Review queue) | Box nhãn không khớp dự đoán nào của model lớn; có thể là nhãn thừa hoặc vật bị che khuất |
| `POSSIBLE_LOOSE_BOX` | 23 ảnh (27 dòng) | Người (Review queue) | Box đúng lớp nhưng độ khớp `IoU < 0.5` so với dự đoán; cần người nắn lại khung bao |
| `POSSIBLE_WRONG_CLASS` | 17 ảnh (17 dòng) | Người (Review queue) | Box khớp vị trí (`IoU >= 0.5`) nhưng khác lớp với dự đoán model lớn; cần người đối chiếu |
| `EMPTY_LABEL` | 11 ảnh (11 dòng) | Người (Review queue) | File nhãn rỗng (ảnh nền), cần người kiểm tra lại xem thực sự không có vật thể hay bị sót |
| `BOX_TINY` | 4 ảnh (6 dòng) | Người (Review queue) | Cạnh ngắn box `< 12px`, cần người xem xét giữ lại hay bỏ theo guideline |
| `BOX_HUGE` | 3 ảnh (3 dòng) | Người (Review queue) | Diện tích box chiếm `> 95%` khung ảnh, cần người kiểm tra box bao trùm nhầm toàn cảnh |
| `CLASS_RARE` | 1 dataset (4 dòng) | Người (Review queue) | Cảnh báo thống kê lớp hiếm (`< 5` box trong lô) để bổ sung dữ liệu nếu cần |

**Giải thích thứ tự hàng đợi (`05_review_queue.csv`) và hiệu quả ngân sách 80 ảnh:**
- Hàng đợi `05_review_queue.csv` (tổng **121** ảnh) xếp ưu tiên theo tổng trọng số rủi ro của các lỗi trên từng ảnh: đứng đầu là `img_0020` (`priority = 11.524`) vì ảnh này vừa bị máy xóa dòng lỗi (`FIXED_DROP_LINE`, trọng số `2`) vừa đồng thời dính hai cảnh báo ngữ nghĩa nghiêm trọng (`POSSIBLE_WRONG_CLASS` trọng số `3` và `POSSIBLE_MISSING` trọng số `2`), ngay sau đó là **6** ảnh thiếu file nhãn (`NEEDS_LABEL`, `priority = 10.0` như `img_0031`, `img_0053`) vì lỗi bắt buộc phải được người gán trước khi xuất.
- Với ngân sách **80/121** ảnh, người duyệt đã xử lý toàn bộ **6/6** ảnh thiếu nhãn (`NEEDS_LABEL`) và giải quyết được **72/125** lỗi ngữ nghĩa (`POSSIBLE_*`), giảm số cảnh báo ngữ nghĩa từ **125** dòng xuống còn **53** dòng (cụ thể: xử lý được `41/53` `POSSIBLE_MISSING`, `14/17` `POSSIBLE_WRONG_CLASS`, `9/27` `POSSIBLE_LOOSE_BOX` và `8/28` `POSSIBLE_FALSE_POS`).

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **16** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.83` (F1 `0.67` → `0.91`); `DUP_IMAGE_EXACT`: giữ nguyên `1.00 / 1.00` (F1 `1.00`) | Tăng tối đa khả năng bắt ảnh gần trùng (`83.3%` trên tập `calib`) mà vẫn giữ Precision tuyệt đối `1.00` (không xóa nhầm ảnh sạch). Nếu tăng lên `20`, Recall của `DUP_IMAGE_EXACT` tụt mạnh từ `1.00` xuống `0.33` (F1 `0.50`) do gom cụm chéo làm lệch ảnh gốc đại diện. |
| `second_opinion.conf` | 0.25 | **0.6** | `MISSING`: `0.50 / 1.00` → `0.57 / 1.00` (F1 `0.67` → `0.73`); `WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83` (F1 `0.67` → `0.71`); `LOOSE_BOX`: `0.29 / 0.40` → `0.20 / 0.20` | Giữ **Recall = `1.00`** cho lỗi thiếu nhãn (`POSSIBLE_MISSING`, không bỏ sót vật thể bị quên gán) đồng thời nâng Precision/F1 cho cả `MISSING` và `WRONG_CLASS` để giảm cảnh báo giả cho hàng đợi duyệt. Đánh đổi là `LOOSE_BOX` giảm Recall từ `0.40` xuống `0.20` do các box dự đoán có độ tự tin trung bình bị lọc bỏ. |

**Chỗ calibration có thể đánh lừa và bằng chứng thực tế:**
- Trong bảng sweep `second_opinion.conf`, chỉ số của `FALSE_POS` đứng yên ở `0.31 / 1.00 / 0.48` trên toàn bộ dải `0.1` đến `0.8` vì `POSSIBLE_FALSE_POS` dùng ngưỡng cố định `fp_conf = 0.1` chứ không phụ thuộc vào `conf`. Ngoài ra, nếu chỉ chọn ngưỡng theo F1 cao nhất của `WRONG_CLASS` tại `conf = 0.8` (`F1 = 0.91`), Recall của `MISSING` sẽ rơi từ `1.00` xuống `0.75` (để lọt 25% lỗi thiếu nhãn).
- Trên tập `raw` thực tế (`01_intake.csv`), ngưỡng `phash_dist = 16` loại đúng **31/224** ảnh (gồm **11** ảnh rò rỉ `test/`, **8** ảnh trùng từng byte, **7** ảnh gần trùng có `dist` từ `0` đến đúng biên `16` như cặp với `img_0008`, `img_0074`, `img_0113`, cùng **3** ảnh kích thước nhỏ và **2** ảnh hỏng), làm sạch dữ liệu đầu vào hợp lý mà không loại nhầm ảnh khác cảnh.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Chứng minh cửa chặn hoạt động đúng:**
- Khi chạy lệnh `python -X utf8 -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (ngân sách người duyệt bằng `0`), pipeline nhận **193/224** ảnh, phát hiện **36** lỗi bắt buộc ở vòng 1 và tự động sửa **35** lỗi (`20` `drop_line`, `8` `clip_box`, `1` `rename_classes`, `6` `needs_label`).
- Sang vòng 2 và vòng 3, vì không có người duyệt nào xử lý **6** ảnh thiếu file nhãn (`MISSING_LABEL_FILE`), vẫn còn nguyên **6 lỗi bắt buộc (`n_errors = 6`)**. Cửa chặn (`gate.py`) lập tức kết luận **`REWORK`** với mã thoát **`20`**, lý do `"Còn 6 lỗi bắt buộc (ERROR) chưa được xử lý."`, và Bước 5 chặn hoàn toàn việc xuất dữ liệu (`Test-Path work/exp_nb` trả về `False`).

**(b) Các điểm mù của pipeline và bằng chứng:**
1. **Box lỏng nhẹ hoặc box của vật thể bị che khuất một phần (`POSSIBLE_LOOSE_BOX`):** Trên tập `calib`, tại ngưỡng `conf = 0.6`, Recall của `POSSIBLE_LOOSE_BOX` chỉ đạt `0.20` (bỏ sót `4/5` lỗi box lỏng) do các dự đoán của model kiểm tra (`yolo26l`) trên vật thể khuất/lệch góc thường có độ tự tin dưới `0.6` hoặc mức lệch biên nhỏ quanh ngưỡng `IoU = 0.5`.
2. **Sự phụ thuộc vào năng lực của model kiểm tra thứ hai (`yolo26l`):** Trên tập `calib`, `POSSIBLE_WRONG_CLASS` vẫn bỏ sót `1/6` ca (`Recall = 0.83`) khi cả nhãn thô và model lớn cùng nhận nhầm loại phương tiện (ví dụ `truck` và `bus` ở góc chụp xa), đồng thời `POSSIBLE_FALSE_POS` có Precision thấp (`0.31`, tạo `11` cảnh báo giả trên `5` lỗi thật) do model lớn bỏ sót các vật thể nhỏ ở xa mà người gán đã gán đúng.
3. **Ảnh trùng lặp qua biến đổi hình học mạnh (xoay 90°/180°, lật gương, cắt cúp sâu):** Thuật toán `pHash` (`phash_dist <= 16`) bắt tốt ảnh nén lại hoặc đổi sáng nhẹ, nhưng không bất biến với phép xoay hoặc crop sâu làm khoảng cách Hamming vượt quá `16`.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy (do ưu tiên hoàn thiện và kiểm thử toàn bộ lõi AutoQC pipeline trên máy cá nhân trước khi chạy huấn luyện GPU trên Google Colab).

## 6. Quyết định và ghi chú AI

**(a) Quyết định cuối và điều kiện để chuyển sang Release:**
- **Quyết định hiện tại:** **Hold** (dữ liệu đã sạch lỗi bắt buộc tại `submission/export/clean_v1` để thử nghiệm nội bộ, nhưng chưa đủ chuẩn phát hành chính thức).
- **Hành động để đạt Release:** Cần giảm số ảnh còn cảnh báo từ **34/193** (`17.62%`) xuống dưới ngưỡng **10%** (tức tối đa **19/193** ảnh, `warn_ratio <= 0.0984`). Chỉ cần cấp thêm ngân sách duyệt khoảng **15–20 ảnh** (nâng `budget_images` từ `80` lên khoảng `100` ảnh theo thứ tự ưu tiên sẵn có trong `05_review_queue.csv`) để người duyệt xử lý nốt nhóm cảnh báo `POSSIBLE_FALSE_POS` (20 cảnh báo) và `POSSIBLE_LOOSE_BOX` (18 cảnh báo) đứng đầu phần còn lại của hàng đợi.

**(b) Ghi chú sử dụng AI:**
- **Prompt chính:** Yêu cầu hỗ trợ hoàn thiện mã nguồn 4 module (`label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py`) bám sát docstring của từng file và tổng hợp phân tích calibration/báo cáo từ số liệu thực tế trong `submission/reports/`.
- **Cách kiểm code AI:** Chạy kiểm thử đơn vị độc lập cho từng module (`pytest tests/test_<tên>.py -q`) cho tới khi đạt `79 passed`, kiểm tra kỹ các ca biên (dòng trống giữa file, một dòng dính 2 lỗi, tính idempotent khi chạy lại) và đối chiếu kết quả chạy toàn pipeline với `--budget 0` lẫn ngân sách `80`.
- **1 lần AI sai:** Khi hướng dẫn chạy lệnh tổng hợp số liệu trên Windows PowerShell, AI đưa câu lệnh một dòng với dấu ngoặc kép lồng nhau khiến PowerShell báo lỗi cú pháp/mã hóa ký tự; đã khắc phục bằng cách chuyển sang khối here-string `@' ... '@ | python -X utf8`.
