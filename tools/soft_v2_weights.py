# -*- coding: utf-8 -*-
"""SOFT_SPEC v2 权重：**从客观响应导出**（不再使用人工成对比较 / BT 标定）。

背景（2026-11-11 用户决定）：此后不再新增人工打分类标定。原计划里
「30 对配对表做 BT 权重标定」取消，改由**受控退化实验的响应幅度**定权：

    响应_i = max_变体(无权重核损失_i) − 无权重核损失_i(baseline)
    w_i    = 响应_i^γ / Σ 响应_j^γ × Σ保留项现权重和(3.4)

- "无权重核损失" = `score.soft_metric_loss()` 的返回值 ÷ 该项当前 w，
  把权重剥掉，只留版面变差带来的几何响应，因此不循环论证。
- γ=1 线性；γ=0.5 压缩极端（对单一变体过拟合更稳）。默认 γ=0.5。
- 总量 3.4 保持与阶段 16 过渡草案一致 → A_soft 的绝对量级不变，
  只改内部相对结构，M1（主评分线）完全不受影响。

用法：
    python3 tools/soft_v2_weights.py                 # 打印两种 γ 的对比
    python3 tools/soft_v2_weights.py --gamma 0.5 --apply
    python3 tools/soft_v2_weights.py --check         # 代码/artifact 漂移校验
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from texopt import score as S  # noqa: E402

ART_SENS = os.path.join(ROOT, "metrics", "soft_sensitivity_20261102.json")
ART_OUT = os.path.join(ROOT, "metrics", "soft_v2_weights_20261111.json")

# 阶段 16 体检后保留的 3 项（band 阈值型 w=0，其余 4 项判死/冗余）
KEEP = ("max_gap", "ink_ratio", "top_bottom_ratio")
# 保留项现权重和（max_gap 1.4 + ink_ratio 1.0 + top_bottom_ratio 1.0）
TOTAL_W = 3.4
DEFAULT_GAMMA = 0.5


def responses(art_path: str = ART_SENS) -> dict[str, dict]:
    """每项指标：baseline 与各变体的**无权重**核损失，及响应幅度。"""
    art = json.load(open(art_path, encoding="utf-8"))
    variants = art["variants"]
    out: dict[str, dict] = {}
    for m in KEEP:
        w = S.SOFT_SPEC[m]["w"]
        rows = {}
        for name, row in variants.items():
            cell = row.get(m)
            if not cell or cell.get("loss") is None:
                continue
            rows[name] = round(cell["loss"] / w, 6)      # 剥掉权重，只留几何响应
        if not rows:
            continue
        base = rows.get("baseline", 0.0)
        worst_name = max(rows, key=lambda k: rows[k])
        out[m] = {
            "w_current": w,
            "baseline_unweighted": base,
            "max_unweighted": rows[worst_name],
            "worst_variant": worst_name,
            "response": round(max(0.0, rows[worst_name] - base), 6),
            "per_variant": dict(sorted(rows.items())),
        }
    return out


def weights(resp: dict[str, dict], gamma: float = DEFAULT_GAMMA,
            total: float = TOTAL_W) -> dict[str, float]:
    raw = {m: max(d["response"], 0.0) ** gamma for m, d in resp.items()}
    s = sum(raw.values())
    if s <= 0:
        raise SystemExit("响应幅度全为 0，无法导出权重")
    return {m: round(total * v / s, 3) for m, v in raw.items()}


def _fmt_table(resp: dict[str, dict], ws: dict[float, dict[str, float]]) -> str:
    lines = ["| 指标 | 现 w | baseline | 最坏变体 | 无权重响应 | " +
             " | ".join(f"w(γ={g})" for g in ws) + " |",
             "|---|---|---|---|---|" + "---|" * len(ws)]
    for m, d in resp.items():
        cells = [f"{ws[g][m]:.3f}" for g in ws]
        lines.append(f"| `{m}` | {d['w_current']} | {d['baseline_unweighted']:.3f} | "
                     f"{d['worst_variant']} {d['max_unweighted']:.3f} | "
                     f"{d['response']:.3f} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sens", default=ART_SENS)
    ap.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    resp = responses(args.sens)
    if not resp:
        raise SystemExit("artifact 里没有可用指标")
    both = {1.0: weights(resp, 1.0), args.gamma: weights(resp, args.gamma)}
    w = weights(resp, args.gamma)

    if args.check:
        if not os.path.exists(ART_OUT):
            print("没有落地 artifact，先跑 --apply")
            return 1
        art = json.load(open(ART_OUT, encoding="utf-8"))
        bad = []
        for m, v in art["weights"].items():
            code = S.SOFT_SPEC.get(m, {}).get("w")
            if code is None or abs(float(code) - float(v)) > 5e-3:
                bad.append(f"{m}: artifact={v} code={code}")
        if bad:
            print("漂移：")
            print("\n".join("  " + b for b in bad))
            print("（SOFT_SPEC v2 尚未落地时，这是预期漂移：artifact 已是客观口径，"
                  "代码里还是 v1 的人工值）")
            return 1
        print(f"一致（{len(art['weights'])} 项，γ={art['gamma']}）")
        return 0

    if args.json:
        print(json.dumps({"responses": resp, "weights": w}, ensure_ascii=False, indent=2))
        return 0

    print("## 客观响应（剥掉权重后的几何损失）\n")
    print(_fmt_table(resp, both))
    print(f"\n口径：γ={args.gamma}，Σw = {TOTAL_W}（与阶段 16 过渡草案一致，A 量级不变）")
    print("\n落地值：")
    for m, v in w.items():
        print(f"  {m:18s} {S.SOFT_SPEC[m]['w']} -> {v}")

    if args.apply:
        art = {
            "date": "2026-11-11",
            "method": "objective-response",
            "note": ("拒绝人工 BT 标定后的替代口径：权重 ∝ 受控退化实验的无权重响应^γ，"
                     "总量锚定阶段 16 过渡草案 3.4，A_soft 绝对量级不变；"
                     "v2 口径（max_gap 只计页中段 / ink_ratio 分层）落地后需重跑本工具刷新。"),
            "gamma": args.gamma,
            "total_w": TOTAL_W,
            "source": os.path.relpath(args.sens, ROOT),
            "retained": list(resp),
            "dropped": {"top_blank": "与 max_gap 冗余 0.837，响应 1/3.7",
                        "bottom_blank": "篇内损失极差 0.000",
                        "left_blank": "敏感性与可辨识性均接近 0",
                        "right_blank": "反应来自双栏而非质量",
                        "band": "阈值型，连续分无效（giant_content 判据保留）"},
            "responses": resp,
            "weights": w,
            "alternative_gamma1": weights(resp, 1.0),
        }
        with open(ART_OUT, "w", encoding="utf-8") as f:
            json.dump(art, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\n已写入 {os.path.relpath(ART_OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
