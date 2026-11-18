"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove_image_code(code: str) -> bool:
    return code in REMOVE_IMAGE_CODES or code.startswith("DUP_IMAGE")


def _clip_yolo_line(raw_line: str) -> str | None:
    """Cắt box về [0, 1]. Trả về chuỗi dòng mới, hoặc None nếu sau khi cắt box không còn diện tích."""
    cls_id, cx, cy, w, h = parse_yolo_line(raw_line)
    x1 = max(0.0, min(1.0, cx - w / 2.0))
    y1 = max(0.0, min(1.0, cy - h / 2.0))
    x2 = max(0.0, min(1.0, cx + w / 2.0))
    y2 = max(0.0, min(1.0, cy + h / 2.0))

    nw = x2 - x1
    nh = y2 - y1
    if nw <= 0.0 or nh <= 0.0:
        return None

    ncx = (x1 + x2) / 2.0
    ncy = (y1 + y2) / 2.0
    return f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"


def fix(ds, issues, cfg) -> list[dict]:
    fixes: list[dict] = []
    error_issues = [i for i in issues if i.severity == ERROR]

    # 1. Xử lý cấp dataset: BAD_CLASS_NAME
    has_bad_class_name = any(i.code == "BAD_CLASS_NAME" for i in error_issues)
    if has_bad_class_name and ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        old_names = data.get("names")
        target_classes = list(cfg["classes"])
        if old_names != target_classes:
            data["names"] = target_classes
            if "nc" in data:
                data["nc"] = len(target_classes)
            ds.yaml_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            fixes.append({
                "image": "data.yaml",
                "line": None,
                "action": "rename_classes",
                "before": str(old_names),
                "after": str(target_classes),
            })

    # 2. Xử lý xoá ảnh + nhãn: DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE
    removed_stems: set[str] = set()
    for i in error_issues:
        if _is_remove_image_code(i.code):
            stem = i.image
            if stem in removed_stems:
                continue
            img_p = ds.image_path(stem)
            lbl_p = ds.label_path(stem)
            existed = False
            if img_p is not None and img_p.exists():
                img_p.unlink()
                existed = True
            if lbl_p.exists():
                lbl_p.unlink()
                existed = True
            removed_stems.add(stem)
            if existed:
                fixes.append({
                    "image": stem,
                    "line": None,
                    "action": "remove_image",
                    "before": i.code,
                    "after": "đã xoá ảnh và nhãn",
                })

    # 3. Xử lý MISSING_LABEL_FILE (không tạo file nhãn rỗng, luôn ghi nhận nếu file chưa có)
    recorded_missing: set[str] = set()
    for i in error_issues:
        if i.code == "MISSING_LABEL_FILE":
            stem = i.image
            if stem in removed_stems or stem in recorded_missing:
                continue
            if not ds.label_path(stem).exists():
                recorded_missing.add(stem)
                fixes.append({
                    "image": stem,
                    "line": None,
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                })

    # 4. Gom các lỗi theo từng file nhãn và số dòng GỐC (đếm từ 1)
    # Ưu tiên: drop_line thắng clip_box trên cùng một dòng
    file_line_ops: dict[str, dict[int, str]] = defaultdict(dict)
    for i in error_issues:
        stem = i.image
        if stem in removed_stems or i.line is None:
            continue
        if i.code in DROP_CODES:
            file_line_ops[stem][i.line] = "drop"
        elif i.code == "BOX_OUT_OF_IMAGE":
            if file_line_ops[stem].get(i.line) != "drop":
                file_line_ops[stem][i.line] = "clip"

    # Áp dụng sửa đổi cho từng file nhãn và ghi lại MỘT lần
    for stem, line_ops in file_line_ops.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue

        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines: list[str] = []
        modified = False

        for line_no, raw_text in enumerate(raw_lines, start=1):
            op = line_ops.get(line_no)
            if op is None:
                new_lines.append(raw_text)
                continue

            before_str = raw_text.strip()
            if op == "drop":
                modified = True
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": before_str,
                    "after": "",
                })
            elif op == "clip":
                try:
                    clipped = _clip_yolo_line(raw_text)
                except ValueError:
                    clipped = None

                if clipped is None:
                    modified = True
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": before_str,
                        "after": "",
                    })
                elif clipped != before_str:
                    modified = True
                    new_lines.append(clipped)
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": before_str,
                        "after": clipped,
                    })
                else:
                    new_lines.append(raw_text)

        if modified:
            content = "\n".join(new_lines) + ("\n" if new_lines else "")
            lbl_p.write_text(content, encoding="utf-8")

    return fixes
