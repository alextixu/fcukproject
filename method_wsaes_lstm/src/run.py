"""用法: python src/run.py --index csi300 --wavelet full|causal|none [--quarters 2] [--epochs 600] [--seed 0] [--tag _s1]
照原文那一組: --optim sgd --lr 0.05 --epochs 5000 --layers 5 --no-early-stop --jobs 6 --tag _paper
輸出 results/<index>_<wavelet><tag>_metrics.csv、_preds.parquet(--no-preds 時不存預測檔)"""
import argparse, os, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, torch
from wsaes import run_index, HERE


def _work(job):
    a, q_ids, threads = job; torch.set_num_threads(threads)
    return run_index(a.index, a.models.split(","), a.wavelet, epochs=a.epochs, hidden=a.hidden, layers=a.layers, lr=a.lr, seed=a.seed, n_quarters=a.quarters,
                     optim=a.optim, early_stop=not a.no_early_stop, q_ids=q_ids, log=lambda s: print(s, flush=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--index", default="csi300"); ap.add_argument("--wavelet", default="full", choices=["full", "causal", "none"])
    ap.add_argument("--models", default="WSAEs-LSTM,WLSTM,LSTM,RNN,naive"); ap.add_argument("--quarters", type=int, default=None)
    ap.add_argument("--epochs", type=int, default=600); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--tag", default="")
    ap.add_argument("--optim", default="adam", choices=["adam", "sgd"]); ap.add_argument("--lr", type=float, default=1e-3); ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--layers", type=int, default=1); ap.add_argument("--no-early-stop", action="store_true"); ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--no-preds", action="store_true"); a = ap.parse_args()
    if a.jobs == 1: m, p = _work((a, None, 2))
    else:
        nq = a.quarters or 24
        with ProcessPoolExecutor(a.jobs) as ex: res = list(ex.map(_work, [(a, list(range(nq))[i::a.jobs], 1) for i in range(a.jobs)]))
        order = a.models.split(","); m = pd.concat([r[0] for r in res]); m = m.sort_values(["quarter", "model"], key=lambda c: c.map(order.index) if c.name == "model" else c).reset_index(drop=True)
        p = pd.concat([r[1] for r in res]).sort_values(["date", "model"]).reset_index(drop=True)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True); tag = f"{a.index}_{a.wavelet}{a.tag}"
    m.to_csv(os.path.join(HERE, "results", f"{tag}_metrics.csv"), index=False)
    if not a.no_preds: p.to_parquet(os.path.join(HERE, "results", f"{tag}_preds.parquet"))
    print(m.groupby("model")[["MAPE", "R", "TheilU", "dir_acc"]].mean().round(4).to_string()); print(m.groupby("model").ret_pct.sum().round(1).to_string())
