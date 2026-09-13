"""剔除規則 R-a / R-b / R-c(套用在相關去重後的清單上)。"""
import pandas as pd

RULES = ["cum90", "top20", "top40", "top80", "permpos"]


def apply_rule(rule: str, kept: list, gain_mean: pd.Series, perm_mean: pd.Series,
               rank_mean: pd.Series) -> list:
    g = gain_mean.reindex(kept).fillna(0)
    if rule == "cum90":
        g = g.sort_values(ascending=False)
        share = g / max(g.sum(), 1e-12)
        cum = share.cumsum()
        n = int((cum < 0.90).sum()) + 1
        return list(g.index[:n])
    if rule.startswith("top"):
        k = int(rule[3:])
        return list(rank_mean.reindex(kept).sort_values().index[:k])
    if rule == "permpos":
        p = perm_mean.reindex(kept)
        return list(p[p > 0].index)
    raise ValueError(rule)
