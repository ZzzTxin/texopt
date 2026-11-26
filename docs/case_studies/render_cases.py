"""Render actual before/after PDFs; no paper figures are redrawn."""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import fitz

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "workbench/case_studies"
spec = importlib.util.spec_from_file_location("case_runner", Path(__file__).with_name("run_cases.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
RENDERS = HERE / "renders"


def font(size):
    path = chinese_font_path()
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default()


def chinese_font_path():
    for directory in (Path("C:/Windows/Fonts"), Path("/mnt/c/Windows/Fonts")):
        for name in ("simhei.ttf", "msyh.ttc", "simsun.ttc"):
            path = directory / name
            if path.is_file():
                return path
    return None


def render(name, phase, dpi=40, page=None):
    main = runner.source_path(name).name
    pdf = (HERE / "runs" / name / "rule_only.pdf" if phase == "rule_only"
           else HERE / "runs" / name / phase / Path(main).with_suffix(".pdf"))
    target = RENDERS / name / f"{phase}_{dpi}" / (f"p{page}" if page else "all")
    target.mkdir(parents=True, exist_ok=True)
    existing = sorted(target.glob("page-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    if existing and min(p.stat().st_mtime for p in existing) >= pdf.stat().st_mtime:
        return existing
    for p in existing:
        p.unlink()
    with fitz.open(pdf) as doc:
        pages = [page - 1] if page else range(len(doc))
        for i in pages:
            doc[i].get_pixmap(dpi=dpi, alpha=False).save(target / f"page-{i+1}.png")
    return sorted(target.glob("page-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))


def contact(name):
    before = render(name, "before")
    after = render(name, "after")
    count = max(len(before), len(after))
    cell_w, cell_h = 190, 270
    pairs_per_row = 3
    result = Image.new("RGB", (pairs_per_row * 2 * cell_w, math.ceil(count / pairs_per_row) * cell_h + 45), "#e8ecf1")
    draw = ImageDraw.Draw(result)
    draw.text((12, 10), f"{name}：左为优化前，右为优化后；数字为 PDF 页码", font=font(20), fill="black")
    differences = []
    for index in range(count):
        x = (index % pairs_per_row) * cell_w * 2
        y = (index // pairs_per_row) * cell_h + 45
        pair = []
        for offset, images in [(0, before), (1, after)]:
            if index >= len(images):
                continue
            im = Image.open(images[index]).convert("RGB")
            pair.append(im)
            im.thumbnail((cell_w - 8, cell_h - 30))
            result.paste(im, (x + offset * cell_w + 4, y + 24))
            draw.text((x + offset * cell_w + 5, y + 3), f"{'前' if offset == 0 else '后'} {index + 1}", font=font(16), fill="black")
        if len(pair) == 2 and pair[0].size == pair[1].size:
            differences.append({"page": index+1, "mean_pixel_difference": round(sum(ImageStat.Stat(ImageChops.difference(*pair)).mean)/3, 3)})
    path = RENDERS / f"{name}_contact.png"
    result.save(path)
    print(json.dumps({"case": name, "contact": str(path), "largest_changes": sorted(differences, key=lambda r: -r['mean_pixel_difference'])[:10]}, ensure_ascii=False))


def vector_panels(name, panels, out, dpi=130):
    main = runner.source_path(name).name
    documents = []
    for phase, page_no, label in panels:
        if phase == "full_review":
            pdf = HERE / "pifold_full_review/work" / Path(main).with_suffix(".pdf")
        else:
            pdf = (HERE / "runs" / name / "rule_only.pdf" if phase == "rule_only"
                   else HERE / "runs" / name / phase / Path(main).with_suffix(".pdf"))
        documents.append(fitz.open(pdf))
    margin, gap, header = 16, 14, 42
    widths = [d[p-1].rect.width for d, (_,p,_) in zip(documents, panels)]
    heights = [d[p-1].rect.height for d, (_,p,_) in zip(documents, panels)]
    width = sum(widths) + (len(panels)-1)*gap + 2*margin
    height = max(heights) + header + margin
    output = fitz.open()
    page = output.new_page(width=width, height=height)
    page.draw_rect(page.rect, color=None, fill=(0.93,0.95,0.97), overlay=False)
    font_path = chinese_font_path()
    label_font = "panelzh" if font_path else "china-s"
    if font_path:
        page.insert_font(fontname=label_font, fontfile=str(font_path))
    x = margin
    for doc, panel, w, h in zip(documents, panels, widths, heights):
        phase, number, label = panel
        page.insert_text((x, 27), label, fontname=label_font, fontsize=19, color=(0.08,0.10,0.13))
        page.show_pdf_page(fitz.Rect(x,header,x+w,header+h), doc, number-1)
        x += w + gap
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    output.subset_fonts()
    output.save(out.with_suffix(".pdf"), garbage=4, deflate=True)
    page.get_pixmap(dpi=dpi, alpha=False).save(out)
    output.close()
    for doc in documents:
        doc.close()
    print(json.dumps({"case": name, "image": str(out), "vector_pdf": str(out.with_suffix('.pdf')), "pages": [p[1] for p in panels]}, ensure_ascii=False))


def pair(name, before_page, after_page, out):
    before_label = "原稿（保留）" if name == "openstl" else "优化前"
    after_label = "原处理（不采用）" if name == "openstl" else "优化后"
    vector_panels(name, [("before", before_page, f"{before_label}｜PDF 第 {before_page} 页"),
                        ("after", after_page, f"{after_label}｜PDF 第 {after_page} 页")], out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest="mode", required=True)
    ct = sp.add_parser("contact")
    ct.add_argument("names", nargs="+")
    pp = sp.add_parser("pair")
    pp.add_argument("name")
    pp.add_argument("before", type=int)
    pp.add_argument("after", type=int)
    pp.add_argument("out")
    triple = sp.add_parser("triple")
    triple.add_argument("name")
    triple.add_argument("page", type=int)
    triple.add_argument("out")
    args = ap.parse_args()
    if args.mode == "contact":
        for name in args.names:
            contact(name)
    elif args.mode == "pair":
        pair(args.name, args.before, args.after, args.out)
    else:
        vector_panels(args.name, [("before",args.page,"原稿"),
                      ("rule_only",args.page,"规则闭环后"),
                      ("after",args.page,"视觉提案后")], args.out)


if __name__ == "__main__":
    main()
