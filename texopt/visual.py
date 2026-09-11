# -*- coding: utf-8 -*-
"""视觉感知层（Phase 4）：PDF -> 页面图像，供具备视觉能力的模型消费。

定位（诚实标注，对应「视觉感知是未来重点」）：
  * 本模块把 PDF 逐页渲染为 PNG，附在 llm_request.json 的 page_images 里，
    交给有视觉理解能力的模型判断留白/视觉重心/图文关系/整体节奏等
    Level-3 问题。这是 Phase 4 的交付：**给 LLM 一双眼睛**。
  * 同时提供一组**像素代理指标**（whitespace/ink/vertical balance 等），
    用纯 stdlib 解析低分辨率 PGM 计算，用于可审计的粗略量化。
  * 明确边界：这些代理指标**不是人类审美评分**，且默认**不并入 A 分**
    （不改变 score.py 的语义）。它们只写进视觉报告，供参考与后续研究
    （Phase 5：逐步把 whitespace/content density/visual balance 等
    形式化并谨慎并入 A）。

依赖：pdftoppm（TeX Live 自带）；Windows 原生 exe 只能认真实盘符路径，
因此统一 cwd 到 PDF 所在目录、只传 basename。
"""
from __future__ import annotations

import glob
import os
import re
import shutil

from . import engine


def _pdftoppm() -> str | None:
    return engine.pdftoppm_path()


def _render(pdf_path: str, outdir: str, prefix: str, dpi: int,
            gray: bool, first: int | None, last: int | None,
            fmt: str) -> tuple[list[str], str | None]:
    """通用渲染：返回 (产出文件列表, 错误)。fmt: png|pgm。"""
    tool = _pdftoppm()
    if not tool:
        return [], "找不到 pdftoppm（TeX Live 应自带）"
    if not os.path.isfile(pdf_path):
        return [], f"找不到 PDF：{pdf_path}"
    os.makedirs(outdir, exist_ok=True)
    pdf_abs = os.path.abspath(pdf_path)
    cwd = os.path.dirname(pdf_abs)
    pdf_name = os.path.basename(pdf_abs)
    target_dir = os.path.abspath(outdir)
    # 输出到 outdir：先渲染到 cwd（Windows exe 可写），再搬到目标目录
    cmd = [tool]
    if gray:
        cmd.append("-gray")          # -gray 直接产出 PGM；pdftoppm 无 -pgm 选项
    elif fmt in ("png", "jpeg", "tiff"):
        cmd.append(f"-{fmt}")
    cmd += ["-r", str(dpi)]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    cmd += [pdf_name, prefix]
    rc, out_b, err_b = engine._run_with_timeout(cmd, cwd, 300)
    produced = sorted(glob.glob(os.path.join(cwd, prefix + "-*")))
    if not produced:
        msg = "pdftoppm 未产出图片" + (f"（rc={rc}）" if rc is not None else "（超时）")
        return [], msg
    moved = []
    for i, p in enumerate(produced, start=1):
        ext = os.path.splitext(p)[1]
        dst = os.path.join(target_dir, f"{prefix}-{i}{ext}")
        shutil.move(p, dst)
        moved.append(dst)
    return moved, None


def render_pages(pdf_path: str, outdir: str, dpi: int = 110,
                 first: int | None = None, last: int | None = None,
                 prefix: str = "page") -> tuple[list[str], str | None]:
    """逐页渲染 PDF 为 PNG（供视觉模型看）。返回 (图片路径列表, 错误)。"""
    return _render(pdf_path, outdir, prefix, dpi, gray=False,
                   first=first, last=last, fmt="png")


def render_gray(pdf_path: str, outdir: str, dpi: int = 40,
                prefix: str = "gray") -> tuple[list[str], str | None]:
    """低分辨率灰度 PGM（供像素代理指标用）。"""
    return _render(pdf_path, outdir, prefix, dpi, gray=True,
                   first=None, last=None, fmt="pgm")


# ---------------------------------------------------------------- PGM 解析

def _parse_pgm(path: str):
    """解析二进制 PGM(P5，maxval<=255) -> (w, h, data: bytes)。"""
    with open(path, "rb") as f:
        raw = f.read()
    # 头部：P5 后跟四个 token（含注释），再 1 个空白，随后是二进制数据
    i, tokens = 0, []
    while len(tokens) < 4:
        while i < len(raw) and raw[i:i + 1].isspace():
            i += 1
        if raw[i:i + 1] == b"#":                       # 注释行
            j = raw.find(b"\n", i)
            i = j + 1 if j >= 0 else len(raw)
            continue
        j = i
        while j < len(raw) and not raw[j:j + 1].isspace():
            j += 1
        tokens.append(raw[i:j])
        i = j
    if tokens[0] != b"P5":
        raise ValueError("仅支持 P5 二进制 PGM")
    w, h, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    i += 1                                              # 单个空白分隔符
    data = raw[i:i + w * h]
    return w, h, data


def page_proxy(pgm_path: str, ink_threshold: int = 200,
               empty_ratio: float = 0.004) -> dict:
    """单页像素代理（**实验性，非人类审美评分**）。

    返回：
      ink_ratio        墨迹占比（暗像素/总像素）
      top_bottom_ratio 上下半页墨迹比（视觉重心粗代理；越偏离 1 越失衡）
      max_empty_band   最大连续近空白行的长度占比（留白粗代理）
      max_empty_pos    该空白带的垂直中心位置（0=页顶,1=页底）
    """
    w, h, data = _parse_pgm(pgm_path)
    dark = bytearray(w * h)
    for p in range(w * h):
        dark[p] = 1 if data[p] < ink_threshold else 0
    total = w * h
    ink = sum(dark)
    rows = [sum(dark[r * w:(r + 1) * w]) for r in range(h)]
    # 上半 / 下半墨迹
    half = h // 2
    top = sum(rows[:half]) or 1
    bot = sum(rows[half:]) or 1
    # 最大连续近空白行带
    best_len = best_start = 0
    cur = 0
    for r in range(h):
        if rows[r] <= max(1, int(empty_ratio * w)):
            cur += 1
            if cur > best_len:
                best_len, best_start = cur, r - cur + 1
        else:
            cur = 0
    return {
        "ink_ratio": round(ink / total, 4),
        "top_bottom_ratio": round(top / bot, 3),
        "max_empty_band": round(best_len / h, 4) if h else 0.0,
        "max_empty_pos": round((best_start + best_len / 2) / h, 3) if h else 0.0,
    }


def visual_report(pdf_path: str, outdir: str, dpi: int = 110,
                  proxy_dpi: int = 40) -> dict:
    """渲染页面图 + 计算像素代理，返回结构化结果（供 report / llm_request）。

    返回 {images, proxies: [{page, ...}], error}。proxies 为实验性代理指标。
    """
    pages_dir = os.path.join(outdir, "pages")
    imgs, err = render_pages(pdf_path, pages_dir, dpi=dpi)
    if err:
        return {"images": [], "proxies": [], "error": err}
    gdir = os.path.join(outdir, ".grayscale")
    grays, gerr = render_gray(pdf_path, gdir, dpi=proxy_dpi)
    proxies = []
    for i, g in enumerate(grays, start=1):
        try:
            m = page_proxy(g)
            m["page"] = i
            proxies.append(m)
        except Exception as exc:                        # 单页失败不影响整体
            proxies.append({"page": i, "error": str(exc)})
    for g in grays:
        try:
            os.remove(g)
        except OSError:
            pass
    try:
        os.rmdir(gdir)
    except OSError:
        pass
    out = {"images": imgs, "proxies": proxies}
    _write_visual_md(os.path.join(outdir, "visual.md"), out)
    return out


def _write_visual_md(path: str, res: dict) -> None:
    L = ["# 视觉感知报告（Phase 4：页面图像；代理指标为实验性）\n",
         "> 说明：本报告把 PDF 逐页渲染为图片供**具备视觉能力的模型**判断"
         "留白/视觉重心/图文关系等 Level-3 问题。下面的像素代理指标"
         "（ink/上下半页比/最大空白带）是**粗略实验量**，**不是人类审美"
         "评分**，也**未并入 A 分**；仅供参考与后续研究（Phase 5）。\n",
         "| 页 | 墨迹占比 | 上/下半墨迹比 | 最大空白带 | 空白带位置 | 图片 |",
         "|---|---|---|---|---|---|"]
    imgs = res.get("images", [])
    for i, m in enumerate(res.get("proxies", [])):
        img = imgs[i] if i < len(imgs) else ""
        if "error" in m:
            L.append(f"| {m.get('page')} | — | — | — | — | {img} |")
            continue
        L.append(f"| {m['page']} | {m['ink_ratio']} | {m['top_bottom_ratio']} | "
                 f"{m['max_empty_band']} | {m['max_empty_pos']} | "
                 f"`{os.path.basename(img)}` |")
    L.append("")
    L.append("代理解读（仅供参考）：`上/下半墨迹比` 明显偏离 1 提示视觉重心"
             "偏上/偏下；`最大空白带` 偏大且落在页底/页中提示留白或空洞；"
             "这些都需人/视觉模型结合实际内容判断，程序不据此自动改。")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
