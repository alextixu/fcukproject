# 2026-06-16 ~ 06-17　微軟 Qlib 量化平台調研 + 課堂報告(一晚完成)

**做了什麼**(23:50 → 01:26)
- clone Qlib、建 venv、自寫 `run_demo.py` 跑官方流程:`Alpha158` 158 因子 → LightGBM → SignalRecord / SigAnaRecord(IC) → PortAnaRecord(TopkDropout,topk=50、n_drop=5,回測 2017-01-01 ~ 2020-08-01,CSI300 基準);`kernels=1` 避開 Windows 多進程 MemoryError。
- `build_slides.py`(python-pptx)自動產生兩份 13 頁簡報:`Qlib_專題報告.pptx`(CSI300 版)與 `Qlib_專題報告_台股.pptx`(台股版)。

**實測結果**(`demo_results.txt`)
- IC 0.0499、ICIR 0.401、Rank IC 0.0515;含成本超額年化 12.72%、資訊比率 1.446、最大回撤 −6.62%。台股版:IC 0.033、年化 +21.85%(與 0050 比較)。

**產出**
- `microsoft/run_demo.py`、`demo_results.txt`、`build_slides.py`、兩份 pptx / pdf、slide PNG。
