#!/usr/bin/env python3
"""本命馬の買い目判定ルール（モデル非依存の共通ロジック）。

12ヶ月 walk-forward バックテスト（2025-09〜2026-08、v0統計モデル 3,234レース /
LightGBM Ranker 高賞金宇宙 1,627レース）のオッズ帯別分析に基づく。

ルール:
  - 単勝オッズ 3.0倍未満:
      「どう見たって勝つ」水準のみ賭ける。モデル予測勝率 40% 以上を要求する。
      （閾値 0.30/0.35/0.40/0.45 をテストし、0.40 が両モデルで実勝率42〜53%・
        ROI 83.4%/91.9% と最もバランスが良かった）
  - 単勝オッズ 5.0倍以上 20.0倍未満:
      回収率を見込めるボリューム帯として無条件で本命買い。
  - 上記以外（3.0〜5.0倍、20.0倍以上）:
      両帯域ともバックテストで ROI が最悪（61〜69% / 0〜59%）のため見送り。

判定にはハッシュ乱数などの揺らぎを含まない、モデルの生出力確率を使うこと。
"""

from __future__ import annotations

LOW_ODDS_LIMIT = 3.0          # このオッズ未満は「堅い本命」ゾーン
MID_ODDS_MIN = 5.0            # ボリューム帯の下限
MID_ODDS_MAX = 20.0           # ボリューム帯の上限（この倍率以上は見送り）
LOW_ODDS_MIN_PROBABILITY = 0.40  # 3倍未満の本命に要求する予測勝率

BET_LOW_ODDS = "BET_LOW_ODDS_HIGH_PROB"
BET_VOLUME_ZONE = "BET_VOLUME_ZONE"
SKIP_LOW_ODDS_LOW_PROB = "SKIP_LOW_ODDS_LOW_PROB"
SKIP_MID_LOW_ODDS = "SKIP_MID_LOW_ODDS"
SKIP_HIGH_ODDS = "SKIP_HIGH_ODDS"
SKIP_NO_ODDS = "SKIP_NO_ODDS"

REASONS = {
    BET_LOW_ODDS: "オッズ3倍未満かつ予測勝率40%以上の堅い本命",
    BET_VOLUME_ZONE: "オッズ5〜20倍のボリューム帯",
    SKIP_LOW_ODDS_LOW_PROB: "オッズ3倍未満だが予測勝率40%未満のため見送り",
    SKIP_MID_LOW_ODDS: "オッズ3〜5倍は回収率が低い帯域のため見送り",
    SKIP_HIGH_ODDS: "オッズ20倍以上は回収率が低い帯域のため見送り",
    SKIP_NO_ODDS: "オッズ未取得のため見送り",
}


def decide_bet(win_odds: float | None, predicted_probability: float | None) -> tuple[bool, str]:
    """本命1頭に対する単勝購入判定を返す。

    Args:
        win_odds: 単勝オッズ（倍率。10倍スケールのDB生値ではないこと）。
        predicted_probability: モデルの予測勝率（0〜1）。

    Returns:
        (購入するか, 理由コード) のタプル。
    """
    if win_odds is None or win_odds <= 0:
        return False, SKIP_NO_ODDS
    probability = predicted_probability if predicted_probability is not None else 0.0

    if win_odds < LOW_ODDS_LIMIT:
        if probability >= LOW_ODDS_MIN_PROBABILITY:
            return True, BET_LOW_ODDS
        return False, SKIP_LOW_ODDS_LOW_PROB
    if MID_ODDS_MIN <= win_odds < MID_ODDS_MAX:
        return True, BET_VOLUME_ZONE
    if win_odds < MID_ODDS_MIN:
        return False, SKIP_MID_LOW_ODDS
    return False, SKIP_HIGH_ODDS


def reason_text(reason_code: str) -> str:
    """理由コードの日本語説明を返す。"""
    return REASONS.get(reason_code, reason_code)
