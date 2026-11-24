# 演示样本说明（08）

本目录不预置 PDF，避免把生成物当"真实论文"。

重建方式（确定性，无随机）：
```
python examples/tools/make_demo.py --out examples/demo
```
产出 `demo.pdf`（2 页、23 个块，每块文本带 `[[Pn]]` 真值标记）与 `truth.json`（阅读顺序）。

`truth.json` 已随包提供，可直接对 `examples/expected/reflow` 复算指标：
```
python eval/metrics.py --out_dir examples/expected/reflow --truth examples/expected/truth.json --base_dir examples/expected/baseline
```
