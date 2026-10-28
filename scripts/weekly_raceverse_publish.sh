#!/usr/bin/env bash
#
# 最新データで RACEVERSE を再学習・予測し、予想サイト(GitHub Pages)へ公開する。
# 金曜・土曜に実行し、翌日と翌々日のレースを予測する。
#
# 使い方:
#   bash scripts/weekly_raceverse_publish.sh [--dry-run] [--date YYYY-MM-DD] [--days N] [--no-going]
#     --dry-run  予測とサイトデータ生成まで行い、commit / push はしない
#     --date     予測開始日(既定: 明日)
#     --days     予測日数(既定: 2)
#     --no-going 良/稍重/重/不良の馬場別予測を省略(高速)

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p logs
LOG_FILE="logs/weekly_raceverse_$(date +%Y-%m-%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

DRY_RUN=0
GOING=1
DAYS=2
START_DATE="$(date -v+1d +%Y-%m-%d)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --no-going) GOING=0; shift ;;
    --date) START_DATE="${2:?--date に YYYY-MM-DD が必要です}"; shift 2 ;;
    --days) DAYS="${2:?--days に数値が必要です}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

step() { echo; echo "===================================="; echo "$1"; echo "===================================="; }
fail() { echo "FAILED: $1" >&2; exit 1; }

DB_PATH="data/raw/race.db"
[[ -s "$DB_PATH" ]] || fail "race.db が見つかりません: $DB_PATH"
DB_AGE_HOURS=$(( ( $(date +%s) - $(stat -f %m "$DB_PATH") ) / 3600 ))
echo "予測対象: ${START_DATE} から ${DAYS} 日間"
echo "race.db 最終更新: ${DB_AGE_HOURS} 時間前"
if [[ "$DB_AGE_HOURS" -gt 36 ]]; then
  echo "WARNING: race.db が古いです。先にWindows側 update_race.bat でJRA-VANデータを更新してください。"
fi

step "[1/6] Ranker 本番予測(最新結果で再学習)"
"$PYTHON" -m src.ranker_production_predict --start-date "$START_DATE" --days "$DAYS" \
  || fail "src.ranker_production_predict"
[[ -s output/predictions.csv ]] || fail "output/predictions.csv が生成されていません(出馬表が未登録の可能性)"

step "[2/6] RACEVERSE 週次能力指標を最新週まで更新"
"$PYTHON" -m raceverse.adapters.existing_ability --weekly --append --end "$(date -v+1d +%Y-%m-%d)" \
  || fail "existing_ability --weekly --append"

step "[3/6] RACEVERSE 学習準備(キャッシュ更新)"
"$PYTHON" -m raceverse.cli --config configs/raceverse_weekly.yaml prepare || fail "raceverse prepare"

step "[4/6] RACEVERSE 予測"
OUT_DIR="reports/raceverse/predict_${START_DATE//-/}"
PREDICT_ARGS=(--date "$START_DATE" --days "$DAYS" --level pace)
if [[ "$GOING" -eq 1 ]]; then
  OUT_DIR="${OUT_DIR}_going_scenarios"
  PREDICT_ARGS+=(--going-scenarios)
fi
rm -rf "$OUT_DIR"
"$PYTHON" -m raceverse.cli --config configs/raceverse_weekly.yaml predict "${PREDICT_ARGS[@]}" --out "$OUT_DIR" \
  || fail "raceverse predict"
ls "$OUT_DIR"/*.json >/dev/null 2>&1 || fail "RACEVERSE予測が生成されていません(出馬表が未登録の可能性): $OUT_DIR"

step "[5/6] サイトデータ生成"
"$PYTHON" scripts/build_raceverse_site_data.py --reports-dir "$OUT_DIR" || fail "build_raceverse_site_data"
"$PYTHON" scripts/build_site_data.py || fail "build_site_data"
for f in docs/data/raceverse/latest.json docs/data/latest.json; do
  [[ -s "$f" ]] || fail "生成物がありません: $f"
done

step "[6/6] 公開(git commit / push)"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "--dry-run のため commit / push はスキップしました。"
  exit 0
fi
git add docs/data
if git diff --cached --quiet; then
  echo "公開データに変更がありません。"
else
  git commit -m "Publish RACEVERSE predictions for ${START_DATE}" \
    -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
fi
git push || fail "git push(ネットワーク/認証を確認して 'git push' を再実行してください)"

echo
echo "SUCCESS: https://xxxoutxxxletxxx.github.io/jra-ai-prediction/"
