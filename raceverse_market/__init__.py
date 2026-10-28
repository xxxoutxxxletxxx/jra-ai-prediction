"""RACEVERSE 市場比較・オッズ帯・カテゴリ別分析(検証専用)。

既存の raceverse / src のモデル・学習コードは変更せず、Walk-Forward予測の読み取りと
カテゴリ別補正の検証だけを行う。出力は reports/raceverse/market_analysis/ に集約する。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "raceverse" / "market_analysis"
PREDICTIONS_CSV = ROOT / "reports" / "raceverse" / "backtest_202509_202609" / "predictions.csv"
PRETEST_DIR = OUT_DIR / "pretest"
M3_DIR = OUT_DIR / "m3"
TEST_START = "2025-09-06"
TEST_END = "2026-08-30"
