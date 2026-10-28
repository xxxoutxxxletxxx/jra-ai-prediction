#!/bin/bash
# ダブルクリックで、翌日・翌々日のレースを最新RACEVERSEで予測してサイトに公開する(金曜・土曜に実行)。
cd "$(dirname "$0")"
bash scripts/weekly_raceverse_publish.sh "$@"
status=$?
echo
if [ $status -eq 0 ]; then echo "完了しました。"; else echo "エラーで終了しました(コード $status)。ログは logs/ を確認してください。"; fi
read -n 1 -s -r -p "何かキーを押すと閉じます..."
exit $status
