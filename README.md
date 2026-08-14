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

