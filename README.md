# 競馬AI予想

これは JRA 中央競馬向けの予測サイトです。機械学習モデルによる予想を参考情報として表示し、GitHub Pages で静的サイトとして公開する構成です。

## 概要

- 競馬予測を行う Python プロジェクトです
- 予測結果は機械学習モデルの参考情報として表示します
- `docs/` 配下の静的ファイルを GitHub Pages で公開します
- 予測対象のローカルデータ (`race.db` など) は GitHub へ含めません

## 安全な公開方針

本リポジトリには、公開に不要な大容量データや機密データを含めない前提です。

- `race.db` は GitHub へ push しません
- JRA-VAN の元データや学習用データはローカルに残すだけにします
- Web 公開に必要なものだけを `docs/` と安全なソースコードに保持します
- `output/` や `data/raw/` の大きな生成物は Git 管理対象外にします

## ローカルでの起動

```bash
python3 -m http.server 8000 --directory docs
```

ブラウザで `http://localhost:8000` を開いて確認してください。

## GitHub Pages での公開

GitHub リポジトリ側で次の設定を行います。

1. GitHub の `Settings` → `Pages` を開く
2. `Build and deployment` → `Deploy from a branch` を選択
3. `Branch` を `main`、`folder` を `/docs` に設定
4. 保存すると `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開されます

## 毎週の更新方法

ローカルでは次の手順で予測とサイト更新を行います。

```bash
python3 src/race_predict.py
python3 scripts/build_site_data.py
```

または、まとめて更新したい場合:

```bash
bash scripts/publish_predictions.sh
```

このスクリプトは、予測生成 → Web 用 JSON 生成 → `docs/` 更新 → Git への安全なコミットを行う構成です。

> `race.db`、JRA-VAN 元データ、学習用データ、巨大な履歴ファイルは commit 対象に含めません。

## バックテスト

本番予測や Web サイト生成とは独立して、月次 walk-forward 評価を実行できます。

```bash
python3 -m src.backtest --months 12
```

期間や出力先を指定する場合:

```bash
python3 -m src.backtest --start-month 2025-08 --end-month 2026-08 --out reports/backtest
```

評価月ごとに、その月の月初より前に確定したレースだけで現行の統計ベースモデルを再学習します。結果は `reports/backtest/` に保存され、`predictions.csv` 単体で条件別集計を再現できます。結果着順・払戻などのレース後確定列は特徴量から除外しています。DBのオッズ・人気が最終値の場合、発走前時点を厳密に再現できないため、レポートに注意書きを出します。PNGは `matplotlib` が利用可能な環境で生成されます。

AI予測1位と1番人気が異なる理由は、`predictions.csv` の `historical_wins`、`historical_races`、`historical_win_rate`、`favorite_probability`、`probability_margin_vs_favorite`、`reason_code`、`prediction_reason` で確認できます。現行モデルの判定ルールは、過去勝率（過去勝数 / 過去出走数）が主スコア、過去履歴がない馬は `1 / 出走頭数`、同率の場合は馬番の小さい順です。人気そのものをスコアに加えているわけではありません。

## リポジトリ構成

- `docs/`: GitHub Pages 公開用の静的サイト
- `scripts/`: 予測生成と公開用スクリプト
- `src/`: 予測ロジック
- `data/raw/`: ローカルの元データ置き場（`race.db` など、GitHub へは含めない）
- `output/`: ローカル生成物（Git 管理対象外）
- `models/`: 学習済みモデル保存先（必要に応じてローカルのみ）

## 必要な依存関係

```bash
pip install -r requirements.txt
```

## 免責事項

本サイトの予測は参考情報であり、的中や利益を保証するものではありません。予測の精度や表示内容は今後の改善対象ですが、公開用の静的サイト設定と更新フローは安全に維持します。

