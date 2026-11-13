"""Write fictional lab report PDFs for the demo people, into web/samples/.

    python tools/make_sample_reports.py

They look like a simple carrier-screening report, so the "Import my report (PDF)"
feature can be tried without any real data. No PDF library is needed: a one-page
text PDF is a short, well-defined file format, written by hand below.

Each report deliberately contains a line naming genes the person does NOT carry
("No pathogenic variants detected in: ..."), to test that the reader ignores it.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "samples"

STATUS = {"Pathogenic": "Carrier", "Likely pathogenic": "Carrier", "Uncertain significance": "Uncertain"}
DOB = {"amina": "14/03/1998", "khalid": "02/09/1995", "sara": "21/06/1999", "omar": "11/12/1996"}


def esc(text: str) -> str:
    """PDF strings are written in brackets ( ); escape \\ ( ) inside them."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(lines: list[tuple[float, float, str, str, float]]) -> bytes:
    """lines: (x, y, font F1|F2, text, size). Returns a valid one-page A4 PDF."""
    stream = "\n".join(f"BT /{f} {s} Tf 1 0 0 1 {x} {y} Tm ({esc(t)}) Tj ET" for x, y, f, t, s in lines).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def report_lines(pid: str, person: dict, panel: list[str]) -> list:
    y = 790
    L = [(50, y, "F2", "DEMO PREMARITAL SCREENING LAB", 16)]
    L.append((50, y - 20, "F1", "Expanded carrier screening report - FICTIONAL DEMO, NOT A REAL PERSON", 10))
    sex = "Female" if person["sex"] == "F" else "Male"
    L += [(50, y - 55, "F1", f"Name: {person['name']} (demo)", 11), (250, y - 55, "F1", f"Sex: {sex}", 11),
          (370, y - 55, "F1", f"Date of birth: {DOB.get(pid, '01/01/1997')}", 11),
          (50, y - 72, "F1", "Report date: 05/11/2026", 11), (250, y - 72, "F1", "Sample: blood", 11),
          (370, y - 72, "F1", "Panel: 10-gene demo panel", 11)]
    y -= 115
    L.append((50, y, "F2", "RESULTS", 12))
    y -= 22
    for x, h in ((50, "Gene"), (110, "Variant"), (330, "Classification"), (470, "Status")):
        L.append((x, y, "F2", h, 10))
    for v in person["variants"]:
        y -= 18
        status = STATUS.get(v["classification"], "")
        if v["gene"] in ("G6PD", "DMD") and status == "Carrier":
            status = "Carrier (X-linked)" if person["sex"] == "F" else "Hemizygous"
        for x, t in ((50, v["gene"]), (110, v["variant"]), (330, v["classification"]), (470, status)):
            L.append((x, y, "F1", t, 10))
    negatives = [g for g in panel if g not in {v["gene"] for v in person["variants"]}]
    y -= 30
    L.append((50, y, "F1", "No pathogenic variants detected in: " + ", ".join(negatives) + ".", 10))
    y -= 35
    L.append((50, y, "F2", "INTERPRETATION", 12))
    for text in ("Being a carrier usually has no effect on your own health.",
                 "A child can be affected only if both parents carry a change in the same gene.",
                 "Genetic counselling is recommended to discuss these results with your partner."):
        y -= 16
        L.append((50, y, "F1", text, 10))
    L.append((50, 60, "F1", "This is a fictional report generated for the BioSentinel Family demo. It contains no real person's data.", 8))
    return L


def main():
    personas = json.loads((ROOT / "data" / "personas.json").read_text(encoding="utf-8"))["personas"]
    panel = list(json.loads((ROOT / "data" / "panel_kb.json").read_text(encoding="utf-8"))["genes"])
    OUT.mkdir(parents=True, exist_ok=True)
    for pid, person in personas.items():
        path = OUT / f"{pid}_report.pdf"
        path.write_bytes(pdf_bytes(report_lines(pid, person, panel)))
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
