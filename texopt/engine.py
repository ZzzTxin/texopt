# -*- coding: utf-8 -*-
"""编译引擎封装。

自动探测 TeX 工具链（优先 Windows TeX Live，兼容 WSL 挂载路径）。
注意：Windows 原生 exe 只能访问真实盘符，因此 tex 文件必须位于
/mnt/c 或 /mnt/d 之下（DrvFs），不能放在 WSL 原生文件系统里。

可靠性设计：WSL interop 调 Windows 引擎偶发“写完 PDF 不退出”，
因此统一走 Popen + 有界等待 + 强杀进程树，保证任何单步都不会无限挂起。
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache

# ---------------------------------------------------------------- 引擎探测

TEXLIVE_XE_GLOBS = [
    "/mnt/c/texlive/*/bin/windows/xelatex.exe",
    "/mnt/c/texlive/*/bin/*/xelatex",
]
TEXLIVE_INFO_GLOBS = [
    "/mnt/c/texlive/*/bin/windows/pdfinfo.exe",
    "/mnt/c/texlive/*/bin/*/pdfinfo",
]
TASKKILL = "/mnt/c/Windows/System32/taskkill.exe"


@lru_cache(maxsize=1)
def engine_paths() -> dict:
    """返回 {'xelatex': str, 'pdfinfo': str|None}。"""
    xe = next((p for g in TEXLIVE_XE_GLOBS for p in glob.glob(g)), None)
    info = next((p for g in TEXLIVE_INFO_GLOBS for p in glob.glob(g)), None)
    if xe is None:
        xe = shutil.which("xelatex") or shutil.which("xelatex.exe")
    if info is None:
        info = shutil.which("pdfinfo")
    return {"xelatex": xe, "pdfinfo": info}


def check_environment() -> list[str]:
    """返回环境问题清单，为空表示一切就绪。"""
    issues = []
    if not engine_paths()["xelatex"]:
        issues.append("找不到 XeLaTeX（已查 Windows TeX Live 与 PATH）")
    cwd = os.getcwd()
    for prefix in ("/mnt/c", "/mnt/d", "/mnt/e"):
        if cwd.startswith(prefix):
            break
    else:
        issues.append(
            f"当前目录 {cwd} 在 WSL 原生文件系统上，Windows 引擎无法写 PDF；"
            "请把项目放在 /mnt/c 或 /mnt/d 下运行"
        )
    return issues


def check_output_dir(outdir: str) -> list[str]:
    """校验输出目录（工作副本/PDF 落盘处）在 Windows 可写盘符下。

    Windows 原生引擎（xelatex.exe）只能写真实盘符；若 outdir 落在 WSL
    原生文件系统（如 /tmp、~/），编译会“成功不了”——这是个易踩的坑，
    因此提前拦截并给出可操作提示。"""
    p = os.path.abspath(outdir)
    for prefix in ("/mnt/c", "/mnt/d", "/mnt/e", "/mnt/f"):
        if p.startswith(prefix):
            return []
    return [f"输出目录 {p} 不在 Windows 盘符（/mnt/c、/mnt/d …）下，"
            "Windows 引擎无法在其中生成 PDF；请用 --outdir 指向 /mnt/c 或"
            "/mnt/d 下的目录"]


def kill_process_tree(pid: int):
    """强杀进程树：先 Windows taskkill /F /T，再本地 killpg 兜底。"""
    if os.path.isfile(TASKKILL):
        try:
            subprocess.run([TASKKILL, "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=15)
        except Exception:
            pass
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


# ---------------------------------------------------------------- 编译

@dataclass
class CompileResult:
    ok: bool                       # 编译成功且 PDF 生成
    returncode: int | None
    log: str = ""
    pdf_path: str | None = None
    first_error: str | None = None
    pages_from_log: int | None = None


PAGES_RE = re.compile(r"Output written on .*?\((\d+) pages?", re.S)


def _run_with_timeout(cmd: list, cwd: str, timeout: int):
    """Popen + 有界等待：任何情况都保证返回，绝不无限挂起。"""
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        kill_process_tree(p.pid)
        try:
            out, err = p.communicate(timeout=10)
        except Exception:
            out = err = b""
        return None, out, err


def compile_tex(tex_path: str, passes: int = 1, timeout: int = 45) -> CompileResult:
    """用 XeLaTeX 编译，cwd 设为 tex 所在目录（保证 Windows 引擎可写 PDF）。"""
    xe = engine_paths()["xelatex"]
    tex_path = os.path.abspath(tex_path)
    cwd = os.path.dirname(tex_path)
    name = os.path.basename(tex_path)
    cmd = [xe, "-interaction=nonstopmode", "-halt-on-error",
           "-file-line-error", name]

    combined = ""
    returncode = None
    for _ in range(max(1, min(int(passes), 3))):
        rc = None
        # Windows 引擎偶发“写完不退出”，超时强杀后自动重试一次（通常即过）
        for attempt in range(2):
            rc, out_b, err_b = _run_with_timeout(cmd, cwd, timeout)
            if rc is not None:
                break
            time.sleep(1.5)
        if rc is None:
            return CompileResult(
                ok=False, returncode=None, log=combined,
                first_error="编译超时（>%ss，重试后仍挂起），已强杀进程" % timeout,
            )
        returncode = rc
        combined += out_b.decode("utf-8", errors="replace") + "\n" \
            + err_b.decode("utf-8", errors="replace")
        if returncode != 0:
            break

    pdf = os.path.join(cwd, os.path.splitext(name)[0] + ".pdf")
    pdf_exists = os.path.isfile(pdf)

    first_error = None
    for line in combined.splitlines():
        s = line.strip()
        if s.startswith("!") or re.match(r"^.+\.tex:\d+:\s+.+$", s):
            first_error = s
            break

    m = PAGES_RE.search(combined)
    return CompileResult(
        ok=(returncode == 0 and pdf_exists),
        returncode=returncode,
        log=combined,
        pdf_path=pdf if pdf_exists else None,
        first_error=first_error,
        pages_from_log=int(m.group(1)) if m else None,
    )


# ---------------------------------------------------------------- PDF 层

def pdf_pages(pdf_path: str) -> int | None:
    """L3 感知：用 pdfinfo 读 PDF 真实页数（与编译日志交叉验证）。"""
    info = engine_paths()["pdfinfo"]
    if not info:
        return None
    pdf_path = os.path.abspath(pdf_path)
    try:
        rc, out_b, err_b = _run_with_timeout(
            [info, os.path.basename(pdf_path)],
            os.path.dirname(pdf_path), 30)
        if rc is None:
            return None
        out = out_b.decode("utf-8", errors="replace")
        m = re.search(r"^Pages:\s*(\d+)", out, re.M)
        return int(m.group(1)) if m else None
    except Exception:
        return None


# ---------------------------------------------------------------- 正文页数
# 会议口径：多数会议的页数上限是「正文页」（参考文献/附录不计）。texopt 因此
# 需要把「总页数」与「正文页数」分开——用 pdftotext 逐页找参考文献起始页。

PDETOTEXT_GLOBS = [
    "/mnt/c/texlive/*/bin/windows/pdftotext.exe",
    "/mnt/c/texlive/*/bin/*/pdftotext",
]
# 参考文献标题（与 datasets 的 measure_pdf.py 同源规则：行首≤4 字符 + references/bibliography）
REF_HEADING_RE = re.compile(
    r"(?im)^[^\n]{0,4}(?:\d+\.?\s*)?(references|bibliography)\b")
_CONTENT_CACHE: dict = {}


@lru_cache(maxsize=1)
def pdftotext_path() -> str | None:
    p = next((p for g in PDETOTEXT_GLOBS for p in glob.glob(g)), None)
    return p or shutil.which("pdftotext")


def content_pages(pdf_path: str, first_page: int = 2) -> dict | None:
    """估算正文页数区间（会议 page limit 的判定依据）。

    做法：一次 pdftotext 取全文（\f 分页），从第 first_page 页起找第一篇
    参考文献/致谢后的 References/Bibliography 标题页 k（跳过标题页噪声）。
      * k 存在：正文 = 第 1..k 页的部分内容 →
          下界 lower = k-1（完全在参考文献之前的页数）
          上界 upper = k（正文可能延伸到参考文献首页）
      * 找不到：无参考文献区 → lower = upper = 总页数。
    返回 {first_ref_page, lower, upper, pages, method}；工具缺失时返回 None。
    判定用「下界」以避免把合法论文误判为超页（真实论文常正好卡在上限）。
    """
    txt = pdftotext_path()
    if not txt or not os.path.isfile(pdf_path):
        return None
    pdf_path = os.path.abspath(pdf_path)
    try:
        st = os.stat(pdf_path)
        ckey = (pdf_path, st.st_mtime, st.st_size)
        if ckey in _CONTENT_CACHE:
            return _CONTENT_CACHE[ckey]
    except OSError:
        ckey = None
    total = pdf_pages(pdf_path)
    rc, out_b, _err = _run_with_timeout(
        [txt, "-layout", os.path.basename(pdf_path), "-"],   # 末位 "-" = 输出到 stdout
        os.path.dirname(pdf_path), 60)
    if rc is None:
        return None
    pages = out_b.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]                      # 末尾多出的空段
    k = None
    for i, text in enumerate(pages, start=1):
        if i < first_page:
            continue
        if REF_HEADING_RE.search(text or ""):
            k = i
            break
    n = total or len(pages)
    if k is None:
        info = {"first_ref_page": None, "lower": n, "upper": n,
                "pages": n, "method": "pdftotext 未找到参考文献标题，按全部页计"}
    else:
        info = {"first_ref_page": k, "lower": max(1, k - 1), "upper": k,
                "pages": n,
                "method": "pdftotext 逐页匹配参考文献标题（正文=第1..参考文献首页）"}
    if ckey is not None:
        _CONTENT_CACHE[ckey] = info
    return info


# ---------------------------------------------------------------- PDF 图形裁切
# 图形保真：图的唯一合法来源是原稿 PDF 本身——按坐标裁切原图原样嵌入，
# 不用 TikZ 重画、不换算坐标轴。这是「内容零改动」在图像层的落地手段。

PDFTOPPM_GLOBS = [
    "/mnt/c/texlive/*/bin/windows/pdftoppm.exe",
    "/mnt/c/texlive/*/bin/*/pdftoppm",
]


@lru_cache(maxsize=1)
def pdftoppm_path() -> str | None:
    p = next((p for g in PDFTOPPM_GLOBS for p in glob.glob(g)), None)
    return p or shutil.which("pdftoppm")


def extract_pdf_region(pdf_path: str, page: int, box, out_path: str,
                       dpi: int = 400) -> dict:
    """把 pdf 第 page 页的矩形区域裁切为 PNG，并给出可直接落地的 TeX 片段。

    box = (x0, y0, x1, y1)，单位 pt，原点在页面左上角（与 PDF 阅读器一致）。
    返回 {out, width_bp, height_bp, snippet, error}。
    """
    x0, y0, x1, y1 = [float(v) for v in box]
    tool = pdftoppm_path()
    if not tool:
        return {"error": "找不到 pdftoppm（TeX Live 应自带）"}
    if not os.path.isfile(pdf_path):
        return {"error": f"找不到 PDF：{pdf_path}"}
    w_pt, h_pt = x1 - x0, y1 - y0
    if w_pt <= 1 or h_pt <= 1:
        return {"error": "裁切框尺寸非法（需 x1>x0, y1>y0）"}
    scale = dpi / 72.0
    px, py = int(x0 * scale), int(y0 * scale)
    pw, ph = int(w_pt * scale), int(h_pt * scale)
    # Windows 原生 exe 只认真实盘符：cwd 设为 PDF 所在目录，参数用文件名
    pdf_abs = os.path.abspath(pdf_path)
    cwd = os.path.dirname(pdf_abs)
    pdf_name = os.path.basename(pdf_abs)
    out_abs = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
    prefix = os.path.splitext(os.path.basename(out_abs))[0] + "_part"
    cmd = [tool, "-png", "-r", str(dpi), "-x", str(px), "-y", str(py),
           "-W", str(pw), "-H", str(ph), "-f", str(page), "-l", str(page),
           pdf_name, prefix]
    rc, out_b, err_b = _run_with_timeout(cmd, cwd, 300)
    cand = sorted(glob.glob(os.path.join(cwd, prefix + "-*.png")))
    if not cand:
        return {"error": "pdftoppm 未产出图片"
                         + (f"（rc={rc}）" if rc is not None else "（超时）")}
    shutil.move(cand[0], out_abs)
    for extra in cand[1:]:
        try:
            os.remove(extra)
        except OSError:
            pass
    return {"out": out_path, "width_bp": round(w_pt, 1),
            "height_bp": round(h_pt, 1),
            "snippet": (f"\\includegraphics[width={w_pt:.1f}bp]"
                        f"{{{out_path}}}")}
