#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/update_$(date +%Y-%m-%d_%H%M%S).log"

exec > >(tee -a "$LOG_FILE") 2>&1

DRY_RUN=0
SKIP_JV=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_all.sh [--dry-run] [--skip-jv]

Options:
  --dry-run    予測とWeb生成まで実行し、git commit / git push は行いません
  --skip-jv    Windows側JV-Link更新をスキップし、既存の race.db を使用します
  -h, --help   このヘルプを表示します
EOF
}

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    --skip-jv)
      SKIP_JV=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

fail() {
  echo "FAILED"
  echo "ERROR: $1" >&2
  exit 1
}

ok() {
  echo "OK"
}

print_header() {
  echo
  echo "===================================="
  echo "$1"
  echo "===================================="
}

print_header "JRA AI WEEKLY UPDATE"

DB_PATH="$PROJECT_ROOT/data/raw/race.db"
LAST_DB_MTIME_FILE="$PROJECT_ROOT/.race_db_last_mtime"

if [[ "$SKIP_JV" -eq 0 ]]; then
  print_header "[1/7] JRA-VANデータ更新"
  if [[ ! -f "$PROJECT_ROOT/update_race.bat" ]]; then
    fail "Windows 側の update_race.bat が見つかりません。"
  fi

  echo "Windows で update_race.bat を実行してください。"
  echo "既存バッチの流れ:"
  echo "  1) JVLinkToSQLite.exe -m Exec"
  echo "  2) race.db 更新"
  echo "  3) \\Mac\Home\Documents\horse-racing-ml\data\raw\race.db へコピー"
  echo "Windows のバッチ完了後、この Mac 側の更新スクリプトを再実行してください。"

  if [[ -f "$DB_PATH" ]]; then
    echo "現在の Mac 側 race.db は存在しています: $DB_PATH"
    echo "更新完了の確認には、Windows 実行後に race.db の更新時刻が変わることを確認してください。"
  else
    fail "Mac 側の race.db がまだ存在しません。Windows の更新処理を完了させてください。"
  fi

  if [[ -f "$LAST_DB_MTIME_FILE" ]]; then
    previous_mtime="$(cat "$LAST_DB_MTIME_FILE")"
    current_mtime="$(stat -f %m "$DB_PATH" 2>/dev/null || echo 0)"
    if [[ "$current_mtime" -le "$previous_mtime" ]]; then
      fail "race.db の更新時刻が前回より新しくありません。Windows の更新処理をもう一度実行してください。"
    fi
  fi
  stat -f %m "$DB_PATH" > "$LAST_DB_MTIME_FILE"
  ok
else
  print_header "[1/7] JRA-VANデータ更新"
  echo "--skip-jv オプションが指定されたため Windows 更新をスキップします。"
  ok
fi

print_header "[2/7] race.db転送確認"
if [[ ! -s "$DB_PATH" ]]; then
  fail "race.db が存在しないか空です: $DB_PATH"
fi
if [[ ! -f "$PROJECT_ROOT/data/raw/.gitkeep" ]]; then
  echo "WARNING: data/raw/.gitkeep が見つかりませんが、DB の存在確認は完了しています。"
fi
ok

print_header "[3/7] AI予測"
python3 src/race_predict.py || fail "src/race_predict.py が失敗しました。"
ok

PREDICTIONS_FILE="$PROJECT_ROOT/output/predictions.csv"
if [[ ! -s "$PREDICTIONS_FILE" ]]; then
  fail "predictions.csv が生成されていません: $PREDICTIONS_FILE"
fi

echo "predictions.csv: $(wc -l < "$PREDICTIONS_FILE") lines"
ok

print_header "[4/7] Webデータ生成"
python3 scripts/build_site_data.py || fail "scripts/build_site_data.py が失敗しました。"
for required in "docs/data/latest.json" "docs/data/archive/index.json"; do
  if [[ ! -s "$PROJECT_ROOT/$required" ]]; then
    fail "Webデータ生成に失敗しました: $required"
  fi
done
ok

print_header "[5/7] 公開前チェック"
for required in \
  "docs/index.html" \
  "docs/style.css" \
  "docs/app.js" \
  "docs/data/latest.json"; do
  if [[ ! -s "$PROJECT_ROOT/$required" ]]; then
    fail "公開に必要なファイルが見つかりません: $required"
  fi
done

git status --short --branch || true

git diff --cached --name-only | grep -E '(^|/)(data/raw/|.*\.db$|.*\.sqlite$|.*\.sqlite3$|output/|models/|logs/|\.env$|__pycache__/|.*\.pyc$|.*\.DS_Store$)' >/dev/null && \
  fail "Stage済みファイルに race.db / 大容量データが含まれています。git add をやり直してください。" || true

git ls-files | grep -E '(^|/)(data/raw/|.*\.db$|.*\.sqlite$|.*\.sqlite3$|output/|models/|logs/|\.env$|__pycache__/|.*\.pyc$|.*\.DS_Store$)' >/dev/null && \
  echo "WARNING: local git tracking already contains ignored or historical large files; review before push." || true
ok

if [[ "$DRY_RUN" -eq 1 ]]; then
  print_header "[6/7] GitHub push (dry-run)"
  echo "--dry-run が指定されたため、git commit / git push は実行しません。"
  echo "GitHub へ push する前に、以下を手動で確認してください:"
  echo "  git status"
  echo "  git diff --cached --stat"
  ok
  print_header "[7/7] 完了"
  echo "===================================="
  echo "SUCCESS"
  echo "競馬AI予測サイトを更新しました（dry-run）"
  echo "===================================="
  exit 0
fi

print_header "[6/7] GitHub push"
if ! bash scripts/publish_predictions.sh; then
  fail "公開処理が失敗しました。"
fi
ok

print_header "[7/7] 完了"

echo "===================================="
echo "SUCCESS"
echo "競馬AI予測サイトを更新しました"
echo "===================================="

echo "対象開催日: $(python3 - <<'PY'
import csv
from pathlib import Path
p = Path('output/predictions.csv')
if not p.exists():
    print('不明')
    raise SystemExit
with p.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
if not rows:
    print('不明')
else:
    dates = sorted({r.get('race_date','').strip() for r in rows if r.get('race_date','').strip()})
    print(dates[-1] if dates else '不明')
PY
)"
echo "予測レース数: $(python3 - <<'PY'
import csv
from pathlib import Path
p = Path('output/predictions.csv')
if not p.exists():
    print('0')
    raise SystemExit
with p.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
print(len(rows))
PY
)"
echo "予測馬数: $(python3 - <<'PY'
import csv
from pathlib import Path
p = Path('output/predictions.csv')
if not p.exists():
    print('0')
    raise SystemExit
with p.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
print(len({(r.get('race_date','').strip(), r.get('idJyoCD','').strip(), r.get('idRaceNum','').strip(), r.get('Umaban','').strip()) for r in rows}))
PY
)"

echo "Git commit hash: $(git rev-parse --short HEAD 2>/dev/null || echo '未コミット')"
echo "GitHub Pages URL: https://xxxoutxxxletxxx.github.io/jra-ai-prediction/"
