"""バックテスト評価関数(仕様11.4)。勝率の校正・LogLoss・Brier・着順指標・回収率。"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

EPS = 1e-9
CAL_BINS = [0.0, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 1.0001]


def power_normalize(df: pd.DataFrame, prob_col: str, gamma: float) -> pd.Series:
    """レース内で p^gamma を再正規化(確率の温度校正)。"""
    p = np.clip(df[prob_col].to_numpy(dtype=float), 1e-6, 1.0) ** gamma
    total = pd.Series(p, index=df.index).groupby(df["race_id"]).transform("sum")
    return pd.Series(p / total.to_numpy(), index=df.index)


def winner_logloss(df: pd.DataFrame, prob_col: str) -> float:
    """レース単位の多項ログ損失(勝ち馬の予測確率の-log平均)。"""
    winners = df[df["target"] == 1]
    return float(-np.log(np.clip(winners[prob_col].to_numpy(dtype=float), 1e-6, 1.0)).mean())


def fit_gamma(df: pd.DataFrame, prob_col: str, grid: List[float]) -> float:
    best, best_loss = 1.0, np.inf
    for gamma in grid:
        calibrated = df.assign(_p=power_normalize(df, prob_col, gamma))
        loss = winner_logloss(calibrated, "_p")
        if loss < best_loss:
            best, best_loss = gamma, loss
    return float(best)


def prob_metrics(df: pd.DataFrame, prob_col: str) -> Dict[str, float]:
    p = np.clip(df[prob_col].to_numpy(dtype=float), 1e-6, 1 - 1e-6)
    y = df["target"].to_numpy(dtype=float)
    races = df["race_id"].nunique()
    ranked = df.assign(_rank=df.groupby("race_id")[prob_col].rank(method="first", ascending=False))
    top1 = ranked[ranked["_rank"] == 1]
    top3_pred = ranked[ranked["_rank"] <= 3]
    actual_top3 = df[df["finish"] <= 3]
    captured = top3_pred[top3_pred["finish"] <= 3].shape[0]
    spearman = []
    for _, g in ranked.groupby("race_id"):
        if len(g) >= 4 and g["finish"].nunique() > 1:
            spearman.append(g["_rank"].corr(g["finish"], method="spearman"))
    return {
        "races": int(races), "horses": int(len(df)),
        "logloss_binary": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()),
        "brier_binary": float(((p - y) ** 2).mean()),
        "winner_logloss": winner_logloss(df, prob_col),
        "top1_hit_rate": float(top1["target"].mean()),
        "top3_recall": float(captured / max(len(actual_top3), 1)),
        "rank_spearman": float(np.nanmean(spearman)) if spearman else float("nan"),
        "top_prob_sum_check": float(df.groupby("race_id")[prob_col].sum().sub(1).abs().max()),
    }


def calibration_table(df: pd.DataFrame, prob_col: str, bins: Optional[List[float]] = None) -> pd.DataFrame:
    bins = bins or CAL_BINS
    cut = pd.cut(df[prob_col], bins=bins, right=False)
    table = df.groupby(cut, observed=True).agg(
        n=("target", "size"), mean_pred=(prob_col, "mean"), actual_rate=("target", "mean"))
    table["gap"] = table["mean_pred"] - table["actual_rate"]
    return table.reset_index().rename(columns={prob_col: "bin"})


def roi_summary(df: pd.DataFrame, prob_col: str, selector: Callable[[pd.DataFrame], pd.Series],
                payout_col: str = "win_payout") -> Dict[str, float]:
    """本命(確率最大)1頭を100円単勝。selector が True の行だけ購入。"""
    ranked = df.assign(_rank=df.groupby("race_id")[prob_col].rank(method="first", ascending=False))
    top1 = ranked[ranked["_rank"] == 1]
    chosen = top1[selector(top1)]
    investment = len(chosen) * 100.0
    returned = float(chosen[payout_col].sum())
    # 最大ドローダウン(購入順に累積損益)
    pnl = (chosen.sort_values(["date", "race_id"])[payout_col] - 100.0).cumsum()
    drawdown = float((pnl.cummax() - pnl).max()) if len(pnl) else 0.0
    return {"bets": int(len(chosen)), "investment": investment, "returned": returned,
            "roi_pct": float(returned / investment * 100) if investment else float("nan"),
            "max_drawdown": drawdown,
            "hit_rate": float((chosen[payout_col] > 0).mean()) if len(chosen) else float("nan")}


def ev_selector(prob_col: str, threshold: float) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda frame: (frame[prob_col] * frame["win_odds"]) >= threshold


def rule_selector(prob_col: str) -> Callable[[pd.DataFrame], pd.Series]:
    from src.betting_rules import decide_bet  # 既存AIと同一の購入ルール(読み取り専用)

    def select(frame: pd.DataFrame) -> pd.Series:
        return pd.Series([decide_bet(o, p)[0] for o, p in zip(frame["win_odds"], frame[prob_col])], index=frame.index)
    return select
