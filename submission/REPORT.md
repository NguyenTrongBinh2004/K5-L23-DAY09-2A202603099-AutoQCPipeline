@'
# Báo cáo Day 09 — Nguyễn Trọng Bình, 2A202603099

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát `10`, xuất bản nháp tại `submission/export/clean_v1`). Lô đầu vào có **224** ảnh thô, bước lọc ban đầu loại **31** ảnh lỗi/trùng/rò rỉ tập test, còn lại **193** ảnh. Lý do chưa thể **Release**: lỗi bắt buộc đã sạch (`0` ERROR), nhưng sau khi người duyệt (mô phỏng) xem hết ngân sách **80/80** ảnh trong hàng đợi **121** ảnh, vẫn còn **34/193** ảnh (**17.62%**, `warn_ratio = 0.1762`) dính cảnh báo, cao hơn mức trần **10%** (`warn_ratio_hold = 0.10`).

## 2. Lỗi và phân việc

| Mã lỗi | Số ảnh / dòng (`02_error_list_v1`) | Ai sửa (máy / người) | Vì sao |
|---|---:|---|---|
| `LEAK_TEST` | 11 ảnh (11 dòng) | Máy (Intake / Autofix) | Trùng ảnh với `test/` hoặc `gold_val/`, phải xóa để tránh leak dữ liệu đánh giá |
| `DUP_IMAGE_EXACT` | 8 ảnh (8 dòng) | Máy (Intake / Autofix) | Trùng y hệt từng byte với ảnh đã nhận trước đó |
| `DUP_IMAGE_NEAR` | 7 ảnh (7 dòng) | Máy (Intake / Autofix) | Ảnh gần trùng (`phash_dist <= 16`), xóa bản sao dư |
| `BAD_SIZE` | 3 ảnh (3 dòng) | Máy (Intake / Autofix) | Cạnh ngắn nhỏ hơn `250px` (`240x180`, `240x226`), ảnh quá mờ/nhỏ |
| `CORRUPT_IMAGE` | 2 ảnh (2 dòng) | Máy (Intake / Autofix) | File ảnh lỗi (`UnidentifiedImageError`, `OSError`), không mở được |
| `BOX_OUT_OF_IMAGE` | 8 ảnh (8 dòng) | Máy (Autofix: `clip_box`) | Mép box tràn nhẹ ra ngoài `[0, 1]`, cắt gọn về biên `[0, 1]` |
| `DUP_BOX` | 7 ảnh (7 dòng) | Máy (Autofix: `drop_line`) | Hai box cùng class chồng nhau (`IoU > 0.9`), xóa dòng lặp phía sau |
| `BAD_CLASS_ID` | 6 ảnh (6 dòng) | Máy (Autofix: `drop_line`) | Class ID ngoài khoảng `0..3`, không tự đoán lớp đúng được nên xóa dòng |
| `BOX_ZERO` | 4 ảnh (4 dòng) | Máy (Autofix: `drop_line`) | Box có `w <= 0` hoặc `h <= 0`, xóa bỏ |
| `BAD_FORMAT` | 3 ảnh (3 dòng) | Máy (Autofix: `drop_line`) | Dòng nhãn không đủ/sai định dạng 5 cột YOLO |
| `BAD_CLASS_NAME` | 1 dataset / `data.yaml` (2 dòng) | Máy (Autofix: `rename_classes`) | Tên class trong `data.yaml` sai chuẩn, ghi lại đúng `[car, person, truck, bus]` |
| `MISSING_LABEL_FILE` | 6 ảnh (6 dòng) | Người (Review queue: `needs_label`) | Ảnh chưa có file `.txt`, máy không tự bịa nhãn được nên đẩy lên đầu cho người gán |
| `POSSIBLE_MISSING` | 52 ảnh (53 dòng) | Người (Review queue) | Model lớn (`yolo26l`) bắt được vật thể nhưng file nhãn chưa có box |
| `POSSIBLE_FALSE_POS` | 26 ảnh (28 dòng) | Người (Review queue) | Box trong nhãn không khớp dự đoán nào của model lớn, nghi nhãn thừa |
| `POSSIBLE_LOOSE_BOX` | 23 ảnh (27 dòng) | Người (Review queue) | Đúng class nhưng box lệch/lỏng (`IoU < 0.5`), cần người chỉnh lại khung |
| `POSSIBLE_WRONG_CLASS` | 17 ảnh (17 dòng) | Người (Review queue) | Khớp vị trí (`IoU >= 0.5`) nhưng khác class với model lớn, cần người check lại |
| `EMPTY_LABEL` | 11 ảnh (11 dòng) | Người (Review queue) | File nhãn trống, cần xem lại là ảnh nền thật hay người gán sót |
| `BOX_TINY` | 4 ảnh (6 dòng) | Người (Review queue) | Cạnh ngắn box `< 12px`, cần đối chiếu guideline xem giữ hay bỏ |
| `BOX_HUGE` | 3 ảnh (3 dòng) | Người (Review queue) | Box chiếm `> 95%` diện tích ảnh, nghi khoanh nhầm cả khung hình |
| `CLASS_RARE` | 1 dataset (4 dòng) | Người (Review queue) | Cảnh báo class xuất hiện ít (`< 5` box trong lô) |

**Thứ tự hàng đợi (`05_review_queue.csv`) và kết quả duyệt 80 ảnh:**
- Hàng đợi **121** ảnh sắp xếp theo tổng trọng số lỗi của từng ảnh. Đứng đầu là `img_0020` (`priority = 11.524`) do vừa bị máy xóa dòng lỗi (`FIXED_DROP_LINE`, trọng số `2`) vừa dính cả `POSSIBLE_WRONG_CLASS` (`3`) lẫn `POSSIBLE_MISSING` (`2`). Ngay sau đó là **6** ảnh thiếu file nhãn (`NEEDS_LABEL`, `priority = 10.0` như `img_0031`, `img_0053`) vì đây là lỗi bắt buộc phải xử lý trước.
- Với ngân sách **80/121** ảnh, người duyệt xử lý xong toàn bộ **6/6** ảnh thiếu nhãn (`NEEDS_LABEL`) và giải quyết được **72/125** cảnh báo ngữ nghĩa (`POSSIBLE_*`), kéo số lỗi nhóm này từ **125** xuống còn **53** dòng (gồm `41/53` `POSSIBLE_MISSING`, `14/17` `POSSIBLE_WRONG_CLASS`, `9/27` `POSSIBLE_LOOSE_BOX`, và `8/28` `POSSIBLE_FALSE_POS`).

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **16** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.83` (F1 `0.67` → `0.91`); `DUP_IMAGE_EXACT`: giữ nguyên `1.00 / 1.00` | Bắt được phần lớn ảnh gần trùng (`83.3%` trên tập calib) mà Precision vẫn là `1.00` (không xóa nhầm ảnh sạch). Nếu đẩy lên `20`, Recall của `DUP_IMAGE_EXACT` tụt mạnh xuống `0.33` (F1 `0.50`) do gom cụm chéo làm lệch ảnh gốc đại diện. |
| `second_opinion.conf` | 0.25 | **0.6** | `MISSING`: `0.50 / 1.00` → `0.57 / 1.00` (F1 `0.67` → `0.73`); `WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83` (F1 `0.67` → `0.71`); `LOOSE_BOX`: `0.29 / 0.40` → `0.20 / 0.20` | Giữ **Recall = `1.00`** cho `POSSIBLE_MISSING` (không bỏ sót vật thể thiếu nhãn), đồng thời tăng Precision và F1 cho cả `MISSING` lẫn `WRONG_CLASS` để đỡ rác hàng đợi. Bù lại `LOOSE_BOX` giảm Recall từ `0.40` xuống `0.20` vì các box dự đoán có conf tầm trung bị lọc mất. |

**Điểm dễ bị đánh lừa khi calibrate & kiểm tra trên dữ liệu thật:**
- Trong bảng sweep `second_opinion.conf`, dòng `FALSE_POS` đứng yên ở `0.31 / 1.00 / 0.48` từ `0.1` đến `0.8` vì check này dùng ngưỡng `fp_conf = 0.1` cố định chứ không ăn theo `conf`. Ngoài ra nếu tham F1 của `WRONG_CLASS` mà chọn `conf = 0.8` (`F1 = 0.91`) thì Recall của `MISSING` rớt từ `1.00` xuống `0.75` (lọt 25% lỗi thiếu nhãn).
- Kiểm tra trên tập `raw` (`01_intake.csv`): ngưỡng `phash_dist = 16` loại **31/224** ảnh gồm **11** ảnh leak `test/`, **8** ảnh trùng từng byte, **7** ảnh gần trùng có `dist` từ `0` tới đúng biên `16` (như cặp với `img_0008`, `img_0074`, `img_0113`), **3** ảnh kích thước nhỏ và **2** ảnh hỏng — các cặp bị loại đều hợp lý.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Chứng minh gate chặn đúng:**
- Chạy `python -X utf8 -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt): pipeline nhận **193/224** ảnh, phát hiện **36** lỗi bắt buộc ở vòng 1 và tự sửa **35** lỗi (`20` `drop_line`, `8` `clip_box`, `1` `rename_classes`, `6` `needs_label`).
- Do ngân sách duyệt bằng `0`, **6** ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) vẫn chưa có nhãn nên sang vòng 3 vẫn còn **6 ERROR (`n_errors = 6`)**. Gate trả về **`REWORK`**, mã thoát **`20`**, lý do `"Còn 6 lỗi bắt buộc (ERROR) chưa được xử lý."` và không tạo thư mục xuất (`Test-Path work/exp_nb` = `False`).

**(b) Các điểm mù của pipeline:**
1. **Box lỏng nhẹ hoặc vật bị khuất một phần (`POSSIBLE_LOOSE_BOX`):** Tại `conf = 0.6`, Recall trên tập `calib` chỉ đạt `0.20` (sót `4/5` ca) vì các vật bị che khuất thường có confidence dưới `0.6` hoặc độ lệch IoU nằm sát ngưỡng `0.5`.
2. **Phụ thuộc vào model `yolo26l`:** Trên tập `calib`, `POSSIBLE_WRONG_CLASS` vẫn sót `1/6` ca (`Recall = 0.83`) khi cả nhãn gốc và `yolo26l` cùng nhầm giữa các xe cỡ lớn (`truck` và `bus` ở góc xa). Ngược lại `POSSIBLE_FALSE_POS` có Precision thấp (`0.31`, `11` cảnh báo giả trên `5` lỗi thật) do model lớn bỏ sót các xe nhỏ ở xa mà người gán đã gán đúng.
3. **Ảnh trùng bị biến đổi hình học mạnh (xoay 90°/180°, lật, crop sâu):** `pHash` (`phash_dist <= 16`) chỉ bắt tốt ảnh nén lại hoặc đổi sáng nhẹ, không bắt được ảnh bị xoay hoặc cắt cúp nhiều.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy (do làm phần pipeline lõi trên máy cá nhân trước, chưa chạy train GPU trên Colab).

