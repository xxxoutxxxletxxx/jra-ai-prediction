#!/usr/bin/env python3
"""Audit prediction, accuracy, and ROI associations for the production Ranker."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ranker_walk_forward_backtest as wf
from src.backtest import RANKER_MARGIN_CORRECTION_FEATURES
from src.ranker_feature_audit import aggregate_vector, encoded_mapping, fit_model


DEFAULT_OUTPUT = ROOT / "reports" / "ranker_current_feature_impact_2026-09.md"


def roi(rows: pd.DataFrame) -> float:
    return float(rows["win_payout"].sum() / (len(rows) * 100) * 100) if len(rows) else float("nan")


def fmt(value: float, digits: int = 2) -> str:
    return "-" if pd.isna(value) else f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def classify_roi(delta: float, positive_months: int) -> str:
    if delta >= 10 and positive_months >= 7:
        return "プラス傾向"
    if delta <= -10 and positive_months <= 5:
        return "マイナス傾向"
    return "混在・不明確"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    feature_list = pd.read_csv(ROOT / "reports" / "ranker_5y_feature_list.csv")
    features = list(RANKER_MARGIN_CORRECTION_FEATURES)
    categories = feature_list.set_index("feature_name")["category"].to_dict()

    frame, loaded_features = wf.load_frame(features)
    if loaded_features != features:
        raise RuntimeError("特徴量キャッシュから95特徴量を読み込めません")

    months = wf.month_starts(wf.TEST_START, wf.TEST_END)
    records: list[dict] = []
    importance_gain: defaultdict[str, float] = defaultdict(float)
    permutation_impact: defaultdict[str, list[float]] = defaultdict(list)
    permutation_hit_impact: defaultdict[str, list[float]] = defaultdict(list)

    for month_index, prediction_month in enumerate(months):
        prediction_end = prediction_month + pd.DateOffset(months=1)
        training_start = prediction_month - pd.DateOffset(years=5)
        training = frame[(frame["date"] >= training_start) & (frame["date"] < prediction_month)].copy()
        test = frame[(frame["date"] >= prediction_month) & (frame["date"] < prediction_end)].copy().reset_index(drop=True)

        calibration_start = prediction_month - pd.DateOffset(months=wf.CALIBRATION_MONTHS)
        calibration_train = training[training["date"] < calibration_start]
        calibration = training[training["date"] >= calibration_start].copy().reset_index(drop=True)
        calibration_scores = wf.ranker_scores(calibration_train, calibration, features)
        temperature, _ = wf.select_temperature(calibration, calibration_scores)

        model, _, test_x = fit_model(training, test, features)
        mapping = encoded_mapping(training, test, features)
        scores = model.predict(test_x, raw_score=True)
        probabilities = wf.softmax_by_race(scores, test["race_id"], temperature)
        ranks = pd.Series(probabilities).groupby(test["race_id"]).rank(method="first", ascending=False).astype(int)
        contributions = model.booster_.predict(test_x, pred_contrib=True)[:, :-1]

        for feature, value in aggregate_vector(model.booster_.feature_importance("gain"), mapping).items():
            importance_gain[feature] += value

        baseline_brier = float(np.mean((test["target"].to_numpy() - probabilities) ** 2))
        baseline_top_indexes = pd.Series(probabilities, index=test.index).groupby(test["race_id"]).idxmax()
        baseline_month_hit = float(test.loc[baseline_top_indexes, "target"].mean())
        rng = np.random.default_rng(wf.SEED + month_index)
        for feature in features:
            indexes = [index for index, mapped in enumerate(mapping) if mapped == feature]
            permuted = test_x.copy()
            order = rng.permutation(len(permuted))
            permuted[:, indexes] = permuted[order][:, indexes]
            perturbed = wf.softmax_by_race(model.predict(permuted, raw_score=True), test["race_id"], temperature)
            permutation_impact[feature].append(float(np.mean((test["target"].to_numpy() - perturbed) ** 2) - baseline_brier))
            perturbed_top_indexes = pd.Series(perturbed, index=test.index).groupby(test["race_id"]).idxmax()
            perturbed_hit = float(test.loc[perturbed_top_indexes, "target"].mean())
            permutation_hit_impact[feature].append((baseline_month_hit - perturbed_hit) * 100)

        for index, row in test.iterrows():
            shap = aggregate_vector(contributions[index], mapping)
            record = {
                "month": prediction_month.strftime("%Y-%m"),
                "race_id": row["race_id"],
                "target": int(row["target"]),
                "prediction_rank": int(ranks.iloc[index]),
                "win_payout": float(row["win_payout"]),
            }
            record.update({f"shap_{feature}": shap.get(feature, 0.0) for feature in features})
            records.append(record)
        print(f"{prediction_month:%Y-%m}: {test['race_id'].nunique()} races")

    result = pd.DataFrame(records)
    top1 = result[result["prediction_rank"] == 1].copy()
    baseline_roi = roi(top1)
    baseline_hit = float(top1["target"].mean() * 100)
    rows = []
    for feature in features:
        column = f"shap_{feature}"
        values = result[column]
        top_values = top1[column]
        low_cut, high_cut = top_values.quantile([0.25, 0.75])
        low = top1[top_values <= low_cut]
        high = top1[top_values >= high_cut]
        high_roi, low_roi = roi(high), roi(low)
        monthly_deltas = []
        for _, group in top1.groupby("month"):
            month_values = group[column]
            month_low, month_high = month_values.quantile([0.25, 0.75])
            monthly_deltas.append(roi(group[month_values >= month_high]) - roi(group[month_values <= month_low]))
        winner_mean = float(top1.loc[top1["target"] == 1, column].mean())
        loser_mean = float(top1.loc[top1["target"] == 0, column].mean())
        rows.append({
            "feature": feature,
            "category": categories.get(feature, "course_wakuban"),
            "mean_abs_shap": float(values.abs().mean()),
            "gain": importance_gain[feature],
            "permutation_brier": float(np.mean(permutation_impact[feature])),
            "permutation_hit_pt": float(np.mean(permutation_hit_impact[feature])),
            "winner_minus_loser_shap": winner_mean - loser_mean,
            "high_roi": high_roi,
            "low_roi": low_roi,
            "roi_delta": high_roi - low_roi,
            "positive_months": int(sum(delta > 0 for delta in monthly_deltas)),
        })
    audit = pd.DataFrame(rows)
    audit["prediction_rank"] = audit["mean_abs_shap"].rank(method="min", ascending=False).astype(int)
    audit["accuracy_rank"] = audit["permutation_hit_pt"].rank(method="min", ascending=False).astype(int)
    audit["roi_label"] = [classify_roi(row.roi_delta, row.positive_months) for row in audit.itertuples()]

    prediction_top = audit.nlargest(15, "mean_abs_shap")
    accuracy_top = audit.nlargest(15, "permutation_hit_pt")
    accuracy_negative = audit.nsmallest(10, "permutation_hit_pt")
    roi_positive = audit[audit["roi_label"] == "プラス傾向"].nlargest(15, "roi_delta")
    roi_negative = audit[audit["roi_label"] == "マイナス傾向"].nsmallest(15, "roi_delta")

    def influence_rows(source: pd.DataFrame) -> list[list[object]]:
        return [[row.prediction_rank, f"`{row.feature}`", row.category, fmt(row.mean_abs_shap, 4), f"{row.permutation_hit_pt:+.3f}"] for row in source.itertuples()]

    def roi_rows(source: pd.DataFrame) -> list[list[object]]:
        return [[f"`{row.feature}`", fmt(row.high_roi), fmt(row.low_roi), f"{row.roi_delta:+.2f}", f"{row.positive_months}/12"] for row in source.itertuples()]

    all_rows = []
    for row in audit.sort_values("prediction_rank").itertuples():
        accuracy_direction = "改善" if row.permutation_hit_pt > 0 else "悪化/寄与なし"
        all_rows.append([
            row.prediction_rank, f"`{row.feature}`", row.category, fmt(row.mean_abs_shap, 4),
            row.accuracy_rank, f"{row.permutation_hit_pt:+.3f}", accuracy_direction,
            f"{row.roi_delta:+.1f}", row.positive_months, row.roi_label,
        ])

    report = f"""# 過去5年Ranker {len(features)}特徴量の影響分析

## 結論

- **予想を最も動かす特徴量**は、クラス適合済み近走パフォーマンス、調整済み近走パフォーマンス、対戦相手・レース強度に集中している。
- **的中率への寄与**は、各特徴量を月内でシャッフルしたときのAI本命的中率低下幅で評価した。正値はその特徴量が的中率を押し上げ、負値は当該期間では押し下げた可能性を示す。
- **回収率への影響**は因果推論ではなく、AI本命におけるSHAP寄与上位25%と下位25%の単勝ROI差である。高配当1件に左右されるため、12か月中7か月以上同方向かつROI差10pt以上のみ「傾向あり」とした。
- 対象は2025-09〜2026-08の月次walk-forward、各予測月より前の**直近5年間だけ**で学習、1着賞金800万円超、全{len(features)}特徴量。評価は{len(top1):,}レース。
- AI本命の基準成績は的中率 **{baseline_hit:.2f}%**、単勝ROI **{baseline_roi:.2f}%**。したがって、特徴量の改善だけで現状の期待収益がプラスになるとは言えない。

## 予想への影響が大きい特徴量

平均絶対SHAPが大きいほど、その特徴量がRankerスコアを大きく動かしている。

{markdown_table(["予想順位", "特徴量", "分類", "平均絶対SHAP", "本命的中率寄与(pt)"], influence_rows(prediction_top))}

## 的中精度への影響

### プラス寄与上位

{markdown_table(["予想順位", "特徴量", "分類", "平均絶対SHAP", "本命的中率寄与(pt)"], influence_rows(accuracy_top))}

### マイナスまたは寄与が確認できない特徴量

負値は、その列を崩した方がAI本命的中率が高かったことを意味する。ただし相関特徴量間で重要度が分散し、月ごとのレース数にも差があるため、単独削除の根拠にはしない。

{markdown_table(["予想順位", "特徴量", "分類", "平均絶対SHAP", "本命的中率寄与(pt)"], influence_rows(accuracy_negative))}

## 回収率への影響

### プラス傾向

{markdown_table(["特徴量", "高寄与ROI", "低寄与ROI", "差(pt)", "プラス月"], roi_rows(roi_positive)) if len(roi_positive) else "厳格条件を満たす特徴量はなかった。"}

### マイナス傾向

{markdown_table(["特徴量", "高寄与ROI", "低寄与ROI", "差(pt)", "プラス月"], roi_rows(roi_negative)) if len(roi_negative) else "厳格条件を満たす特徴量はなかった。"}

## 見解

1. 予想影響と収益影響は別物である。SHAP上位でも市場が同じ情報をオッズへ織り込んでいればROIは上がらない。
2. 的中面では本命的中率寄与上位を維持候補とし、負値の特徴量は相関群単位の除去テスト候補とするのが妥当である。Brier差も内部計算し、確率精度との方向が大きく矛盾しないか確認している。
3. ROI差が大きくても月次再現性が弱い特徴量は購入条件に使わない。プラス月数が7/12以上でも、次の12か月で再検証する必要がある。
4. 本分析は同一モデル内の関連性分析であり、特徴量の追加・削除による因果効果は個別ablationのwalk-forward比較でのみ確定できる。

## {len(features)}特徴量一覧

{markdown_table(["予想順位", "特徴量", "分類", "平均絶対SHAP", "的中寄与順位", "本命的中率差(pt)", "的中判定", "ROI差", "プラス月", "ROI判定"], all_rows)}

## 指標の定義と注意

- TreeSHAPは各馬のRankerスコアへの寄与。平均絶対値なので方向ではなく影響量を示す。
- 本命的中率差は、元モデルの的中率から当該特徴量を月内でシャッフルしたモデルの的中率を引き、12か月を単純平均した値。大きい正値ほどAI本命の選択に寄与する。
- ROI差はSHAP上位四分位ROIから下位四分位ROIを引いた値。オッズ・人気・他特徴量の交絡を含む。
- {len(features)}特徴量には強い相関があるため、個別順位は「独立した因果的重要度」ではない。
- 単勝払戻は100円購入基準。ROI 100%が損益分岐点。
"""
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()