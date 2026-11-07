"""テスト用の作り物のプリント（文字の層がある 1 ページの PDF）を作る。"""
import sys

LINES = ["School Event Notice", "Grade 2  /  2026-11-05",
         "Field trip on 2026-11-11 (Wed).", "Please bring lunch, a water bottle and a picnic sheet."]


def make(path, extra=None):
    lines = LINES + ([extra] if extra else [])
    text = "BT /F1 14 Tf 72 720 Td 20 TL " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            f"<< /Length {len(text)} >>\nstream\n{text}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    open(path, "wb").write(out)


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
