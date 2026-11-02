# A_soft 指标可辨识性体检（2026-11-02）

- 样本：**90 篇 / 1502 页**，dpi=50，像素层，角色用 pixel-proxy 粗分
- 角色构成：body×1297, dense×91, near-empty×15, sparse×99

## 1　判定表

| 指标 | 篇内损失极差 | 分层后(body) | 原始篇内 CV | 跨篇 CV | 判定 | 依据 |
|---|---|---|---|---|---|---|
| `ink_ratio` | 0.322 | 0.0385 | 0.2747 | 0.2502 | **stratify** | 损失极差 0.322 里大半来自页类型：只看 body 页只剩 0.0385 → 必须按角色分层 |
| `max_gap` | 0.2831 | 0.0 | 0.4304 | 0.3125 | **merge** | 与 ['top_blank'] 秩相关 ≥0.8，且分层后变异很小（CV=0.0493）→ 同一件事算两遍 |
| `top_bottom_ratio` | 0.4681 | 0.2968 | 0.4668 | 2.7541 | **keep** | 篇内损失极差 0.4681（分层后 0.2968）：能真正挪动 A |
| `top_blank` | 0.1994 | 0.0989 | 0.1131 | 0.2998 | **stratify** | 损失极差 0.1994 里大半来自页类型：只看 body 页只剩 0.0989 → 必须按角色分层 |
| `bottom_blank` | 0.0 | 0.0 | 0.0775 | 0.506 | **drop** | 篇内损失极差仅 0.0（<0.10）→ 近似常数，同稿比较里自动抵消，只抬高 A 的绝对值 |
| `left_blank` | 0.0049 | 0.0049 | 0.0113 | 0.3419 | **drop** | 篇内损失极差仅 0.0049（<0.10）→ 近似常数，同稿比较里自动抵消，只抬高 A 的绝对值 |
| `right_blank` | 0.1297 | 0.0106 | 0.1128 | 0.2786 | **merge** | 与 ['left_blank'] 秩相关 ≥0.8，且分层后变异很小（CV=0.0094）→ 同一件事算两遍 |
| `band` | None | None | 0.9821 | 1.3145 | **threshold-only** | 权重已为 0；但高值端（≥0.40）仍是 giant_content 的判据，属阈值型指标，不应做连续分 |

## 2　冗余（body 页，Spearman |ρ| ≥ 0.8）

- `left_blank` × `right_blank` = 0.876
- `max_gap` × `top_blank` = 0.837

## 3　全页秩相关矩阵（含页类型混杂）

| 对 | ρ |
|---|---|
| `left_blank` × `right_blank` | 0.842 |
| `max_gap` × `top_blank` | 0.746 |
| `ink_ratio` × `right_blank` | -0.639 |
| `ink_ratio` × `left_blank` | -0.516 |
| `bottom_blank` × `right_blank` | 0.423 |
| `ink_ratio` × `bottom_blank` | -0.362 |
| `bottom_blank` × `left_blank` | 0.313 |
| `ink_ratio` × `max_gap` | -0.303 |
| `top_blank` × `left_blank` | 0.302 |
| `max_gap` × `right_blank` | 0.274 |
| `ink_ratio` × `band` | 0.272 |
| `top_blank` × `right_blank` | 0.253 |

## 4　读法

- `drop`：篇内几乎不变，同稿比较里是常数 → 只是把 A 的绝对值抬高
- `merge`：与别的指标重复，算两遍等于偷偷加权
- `stratify`：变异主要来自页类型（整页图/空白页），必须按角色分层
- `threshold-only`：连续分没用，但高值端的阈值判据仍有效（门控/报告）
- `keep`：同角色内有连续变异，可进 A_soft 连续分
