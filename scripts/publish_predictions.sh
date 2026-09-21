#!/usr/bin/env bash
#
# 予測パイプラインを実行し、GitHub Pages 用サイトデータを更新して安全に git push するスクリプト。
#
# ルール:
#   - race.db / JRA-VAN 元データ / 学習データ / output/ は commit しない
#   - GitHub Pages で公開するのは docs/ と安全なソースコードのみ
#
# 使い方:
#   bash scripts/publish_predictions.sh

set -eu

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "エラー: このディレクトリは Git リポジトリではありません。" >&2
  echo "GitHub に公開する前に、GitHub でリポジトリを作成してから以下を実行してください:" >&2
  echo "  git init" >&2
  echo "  git remote add origin <YOUR_GITHUB_REPO_URL>" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "エラー: GitHub remote が未設定です。" >&2
  echo "  git remote add origin <YOUR_GITHUB_REPO_URL>" >&2
  exit 1
fi

echo "================================================================"
echo "[1/6] 検証済みRanker本番予測を実行します"
echo "================================================================"
python3 -m src.ranker_production_predict

echo ""
echo "================================================================"
echo "[2/6] build_site_data.py を実行します"
echo "================================================================"
python3 scripts/build_site_data.py

echo ""
echo "================================================================"
echo "[3/6] 公開に必要なファイルを確認します"
echo "================================================================"
REQUIRED_FILES=(
  "docs/index.html"
  "docs/style.css"
  "docs/app.js"
  "docs/data/latest.json"
)

for f in "${REQUIRED_FILES[@]}"; do
  if [ ! -s "$f" ]; then
    echo "エラー: 必要な公開ファイルが存在しないか空です: $f" >&2
    exit 1
  fi
  echo "OK: $f"
done

TODAY="$(date +%Y-%m-%d)"

echo ""
echo "================================================================"
echo "[4/6] 公開可能なファイルを git add"
echo "================================================================"
# 競馬予測の巨大なローカル生成物や DB はコミットしない
# GitHub Pages で公開するのは docs/ と安全なソースコードのみ

git add \ 
  README.md \
  .gitignore \
  docs/ \
  scripts/ \
  src/ \
  pyproject.toml \
  requirements.txt

echo ""
echo "================================================================"
echo "[5/6] git commit"
echo "================================================================"
if git diff --cached --quiet; then
  echo "コミット対象の変更がありません。commit をスキップします。"
else
  git commit -m "Update public prediction site ${TODAY}"
fi

echo ""
echo "================================================================"
echo "[6/6] git push"
echo "================================================================"
if git push; then
  echo "push に成功しました。"
else
  echo "警告: git push に失敗しました。ローカル生成物はそのまま残します。" >&2
  echo "network / GitHub の設定を確認してから、後ほど 'git push' を再実行してください。" >&2
  exit 1
fi

echo ""
echo "完了しました。"
