"""RACEVERSE v0.6 設定。仕様書13章の設定例に対応する。暫定値は訓練側のみで調整する。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "raw" / "race.db"
CACHE_DIR = ROOT / "data" / "cache" / "raceverse"
REPORT_DIR = ROOT / "reports" / "raceverse"
DEFAULT_CONFIG_PATH = ROOT / "configs" / "raceverse.yaml"

PACE_BUCKETS = ["VERY_FAST", "FAST", "MIDDLE", "SLOW", "VERY_SLOW"]


@dataclass
class FormationConfig:
    max_history_runs: int = 10
    recency_weights: List[float] = field(default_factory=lambda: [10, 10, 9, 8, 7, 6, 5, 4, 3, 2])
    group_threshold: float = 0.08
    jockey_change_alpha: float = 0.40
    jockey_frontness_shrinkage_k: float = 30.0
    lead_rank_cut: int = 3  # 騎手の逃げペース傾向に使う「先頭付近」= 序盤順位がこの値以下


@dataclass
class PaceConfig:
    ridge_alpha: float = 1.0
    training_formation_draws: int = 16
    lead_tempo_shrinkage_k: float = 20.0
    train_start: str = "2017-01-01"
    min_train_races: int = 2000
    display_quantiles: List[float] = field(default_factory=lambda: [0.10, 0.30, 0.70, 0.90])
    min_residual_pool: int = 150
    truncation_quantiles: List[float] = field(default_factory=lambda: [0.001, 0.999])


@dataclass
class PaceImpactConfig:
    base_first_month: str = "2017-07-01"   # 実隊列ベース回帰の時系列OOFを始める月
    base_alpha: float = 1.0
    base_min_races: int = 1500
    backfit_iters: int = 30
    # 検証窓(2023-09〜2025-08, テスト前)で未知レースのeps説明力が最大の付近。scripts/raceverse_pace_impact_analysis.py で再現できる
    horse_lambda: Dict[str, float] = field(default_factory=lambda: {"lead": 8.0, "chase": 24.0, "front": 24.0})
    jockey_lambda: Dict[str, float] = field(default_factory=lambda: {"lead": 20.0, "chase": 30.0, "front": 30.0})
    presence_lambda: float = 20.0
    presence_min_n: int = 10
    impact_clip_sec: float = 1.0
    corr_min_events: int = 8
    corr_min_other: int = 30
    corr_reliability_k: float = 20.0


@dataclass
class TrackSpeedConfig:
    source_priority: Dict[str, float] = field(default_factory=lambda: {
        "previous_day": 1.0, "previous_week": 0.8, "previous_meet": 0.55, "previous_year_same_season": 0.4,
    })
    going_mismatch_weight: float = 0.35
    distance_band_mismatch_weight: float = 0.7
    layout_mismatch_weight: float = 0.8
    shrinkage_k: float = 2.0
    winsor_sigma: float = 3.0
    min_effective_samples: float = 3.0  # 前日+先週がこれ未満なら前開催も候補へ入れる
    recency_half_life_days: float = 14.0
    previous_week_window_days: int = 13
    previous_year_window_days: int = 3
    previous_meet_last_days: int = 2


@dataclass
class WinningTimeConfig:
    enabled: bool = True
    ridge_alpha: float = 10.0
    residual_floor_scale: float = 0.3
    train_start: str = "2022-09-01"
    min_train_races: int = 300


@dataclass
class PerformanceConfig:
    ridge_alpha: float = 50.0
    training_draws: int = 4
    margin_winsor: List[float] = field(default_factory=lambda: [0.005, 0.995])
    min_train_races: int = 300
    min_oof_races: int = 150
    young_age_max: int = 3
    layoff_days: int = 90
    level: str = "formation"  # production prediction level (formation_bias / pace_bias: コースバイアス追加版)


@dataclass
class CourseBiasConfig:
    """コース別の脚質・枠順バイアス統計(as-of)。比率 = 実績 / 期待(1/頭数, 複勝は3/頭数)をベイズ縮約する。"""
    enabled: bool = True
    k_win: List[float] = field(default_factory=lambda: [30.0, 20.0, 12.0, 12.0, 10.0])  # 上位集計→細かい条件の事前強さ(期待勝数単位)
    place_k_multiplier: float = 3.0     # 複勝は期待値が約3倍なので事前強さも比例させる
    k_dg: List[float] = field(default_factory=lambda: [30.0, 20.0, 12.0])
    k_joint: float = 15.0               # 脚質x枠グループの交互作用
    k_pace_root: float = 30.0
    k_pace_course: float = 15.0
    front_q: float = 0.30               # 序盤位置q以下=先行(先頭1頭は逃げ)
    stalk_q: float = 0.70               # q以下=差し、超=追込
    pace_edges_sec: List[float] = field(default_factory=lambda: [-0.35, 0.35])  # ペース偏差(秒): 速い/ミドル/遅い
    large_field: int = 12               # 枠順は頭数帯(小/大)ごとに集計
    min_field: int = 4


@dataclass
class CalibrationConfig:
    enabled: bool = True
    burn_in_months: int = 6
    window_months: int = 6
    gamma_grid: List[float] = field(default_factory=lambda: [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35, 1.5, 1.75, 2.0])


@dataclass
class BacktestConfig:
    test_start: str = "2025-09-01"
    test_end: str = "2026-09-01"
    n_simulations: int = 10_000
    odds_policy: str = "pre_bet_snapshot_only"
    require_strict_asof_features: bool = True


@dataclass
class RaceverseConfig:
    version: str = "0.6"
    n_simulations: int = 10_000
    random_seed: int = 42
    data_min_year: int = 2015
    refit_unit: str = "month"        # "month": 前月末までの結果で再学習 / "week": 先週までの結果で再学習
    ability_source: str = "monthly"  # "monthly": 既存の月次Ranker OOF / "weekly": 週次Ranker OOF(raceverse.adapters.existing_ability)
    baseline_first_month: str = "2016-01-01"
    baseline_alpha: float = 2.0
    formation: FormationConfig = field(default_factory=FormationConfig)
    pace: PaceConfig = field(default_factory=PaceConfig)
    pace_impact: PaceImpactConfig = field(default_factory=PaceImpactConfig)
    track_speed: TrackSpeedConfig = field(default_factory=TrackSpeedConfig)
    winning_time: WinningTimeConfig = field(default_factory=WinningTimeConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    course_bias: CourseBiasConfig = field(default_factory=CourseBiasConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _merge(obj: Any, values: Dict[str, Any]) -> None:
    names = {f.name for f in fields(obj)}
    for key, value in values.items():
        if key not in names:
            raise KeyError(f"unknown config key: {type(obj).__name__}.{key}")
        current = getattr(obj, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _merge(current, value)
        else:
            setattr(obj, key, value)


def load_config(path: Optional[Path] = None) -> RaceverseConfig:
    """YAMLがあれば既定値を上書きして読む。未知キーはエラー。"""
    config = RaceverseConfig()
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    if path.exists():
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _merge(config, data.get("raceverse", data))
    if config.refit_unit not in ("month", "week"):
        raise ValueError(f"refit_unit must be 'month' or 'week': {config.refit_unit}")
    if config.ability_source not in ("monthly", "weekly"):
        raise ValueError(f"ability_source must be 'monthly' or 'weekly': {config.ability_source}")
    return config
