"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None) -> list[Issue]:
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    sub_cfg = cfg["second_opinion"]
    conf_thresh = float(sub_cfg["conf"])
    min_area_px = float(sub_cfg["min_area_px"])
    fp_conf = float(sub_cfg["fp_conf"])
    iou_missing = float(sub_cfg["iou_missing"])
    iou_match = float(sub_cfg["iou_match"])
    iou_loose = float(sub_cfg["iou_loose"])

    n_classes = len(ds.classes)
    issues: list[Issue] = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue

        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        img_size = ds.image_size(stem)
        if img_size is None:
            continue
        img_w, img_h = img_size

        valid_labels = ds.valid_boxes(stem)
        stem_preds = preds[stem]

        # 1. Duyệt các dự đoán đạt ngưỡng conf & min_area_px theo đúng thứ tự trong preds[stem]
        for pred in stem_preds:
            p_cls, p_conf, px, py, pw, ph = pred
            p_cls = int(p_cls)
            p_conf = float(p_conf)
            area_px = (pw * img_w) * (ph * img_h)

            if p_conf < conf_thresh or area_px < min_area_px:
                continue

            p_box = (px, py, pw, ph)
            cands: list[tuple[int, float]] = []
            for l_cls, lx, ly, lw, lh in valid_labels:
                iou = iou_xywh(p_box, (lx, ly, lw, lh))
                if iou >= iou_missing:
                    cands.append((l_cls, iou))

            if not cands:
                issues.append(Issue(
                    check="second_opinion",
                    severity=WARN,
                    code="POSSIBLE_MISSING",
                    image=stem,
                    message=f"Model phát hiện đối tượng lớp {p_cls} (conf={p_conf:.2f}) nhưng thiếu nhãn",
                    extra={"conf": round(p_conf, 4)},
                ))
                continue

            same_cls_ious = [iou for l_cls, iou in cands if l_cls == p_cls]
            if same_cls_ious:
                best_same = max(same_cls_ious)
                if best_same < iou_loose:
                    issues.append(Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_LOOSE_BOX",
                        image=stem,
                        message=f"Box nhãn lớp {p_cls} khớp thấp với dự đoán (IoU={best_same:.2f} < {iou_loose})",
                        extra={"conf": round(p_conf, 4), "iou": round(best_same, 4)},
                    ))
            else:
                best_diff = max(iou for _, iou in cands)
                if best_diff >= iou_match:
                    issues.append(Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_WRONG_CLASS",
                        image=stem,
                        message=f"Nghi ngờ gán nhầm lớp (model dự đoán lớp {p_cls}, IoU={best_diff:.2f})",
                        extra={"conf": round(p_conf, 4), "iou": round(best_diff, 4)},
                    ))

        # 2. Kiểm tra POSSIBLE_FALSE_POS theo số dòng gốc
        fp_preds = [
            (float(p[1]), (float(p[2]), float(p[3]), float(p[4]), float(p[5])))
            for p in stem_preds
            if float(p[1]) >= fp_conf
        ]

        for line_no, text in raw_lines:
            try:
                l_cls, lx, ly, lw, lh = parse_yolo_line(text)
            except ValueError:
                continue
            if not (0 <= l_cls < n_classes):
                continue

            l_box = (lx, ly, lw, lh)
            max_iou = max((iou_xywh(l_box, p_box) for _, p_box in fp_preds), default=0.0)
            if max_iou < iou_missing:
                issues.append(Issue(
                    check="second_opinion",
                    severity=WARN,
                    code="POSSIBLE_FALSE_POS",
                    image=stem,
                    line=line_no,
                    message=f"Box nhãn lớp {l_cls} không khớp dự đoán nào của model (max IoU={max_iou:.2f})",
                    extra={"iou": round(max_iou, 4)},
                ))

    return issues
