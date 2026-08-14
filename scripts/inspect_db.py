import sqlite3
from pathlib import Path


# ==============================
# パス設定
# ==============================

# inspect_db.py は scripts/ にある想定
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "data" / "raw" / "race.db"
OUTPUT_PATH = PROJECT_ROOT / "data" / "output" / "race_db_structure.txt"


# ==============================
# DB確認
# ==============================

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"race.db が見つかりません。\n"
        f"確認した場所: {DB_PATH}"
    )

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

print(f"DB: {DB_PATH}")
print(f"出力先: {OUTPUT_PATH}")
print("解析開始...")


# ==============================
# SQLite接続
# 読み取り専用
# ==============================

db_uri = f"file:{DB_PATH}?mode=ro"

conn = sqlite3.connect(db_uri, uri=True)
cur = conn.cursor()


# ==============================
# テーブル一覧取得
# ==============================

tables = cur.execute("""
    SELECT name, sql
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""").fetchall()


# ==============================
# 結果出力
# ==============================

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:

    f.write("JRA-VAN SQLite Database Structure\n")
    f.write("=" * 100 + "\n\n")

    f.write(f"DATABASE: {DB_PATH}\n")
    f.write(f"TABLE COUNT: {len(tables)}\n\n")

    for index, (table, create_sql) in enumerate(tables, start=1):

        print(f"[{index}/{len(tables)}] {table}")

        f.write("\n")
        f.write("=" * 100 + "\n")
        f.write(f"TABLE: {table}\n")
        f.write("=" * 100 + "\n\n")

        # ------------------------------
        # レコード数
        # ------------------------------

        try:
            count = cur.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

            f.write(f"ROWS: {count:,}\n\n")

        except Exception as e:
            f.write(f"ROWS: ERROR - {e}\n\n")


        # ------------------------------
        # CREATE TABLE文
        # ------------------------------

        f.write("CREATE TABLE:\n")
        f.write("-" * 100 + "\n")

        if create_sql:
            f.write(create_sql)
        else:
            f.write("(なし)")

        f.write("\n\n")


        # ------------------------------
        # カラム情報
        # ------------------------------

        f.write("COLUMNS:\n")
        f.write("-" * 100 + "\n")

        columns = cur.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()

        f.write(
            f"{'ID':>4} | "
            f"{'COLUMN NAME':50} | "
            f"{'TYPE':12} | "
            f"{'NOT NULL':8} | "
            f"{'PK':3}\n"
        )

        f.write("-" * 100 + "\n")

        for cid, name, dtype, notnull, default, pk in columns:

            f.write(
                f"{cid:4d} | "
                f"{name:50} | "
                f"{dtype:12} | "
                f"{notnull:^8} | "
                f"{pk:^3}\n"
            )

        f.write("\n")


        # ------------------------------
        # サンプルデータ
        # ------------------------------

        f.write("SAMPLE ROWS (LIMIT 3):\n")
        f.write("-" * 100 + "\n")

        try:
            rows = cur.execute(
                f'SELECT * FROM "{table}" LIMIT 3'
            ).fetchall()

            if not rows:
                f.write("(データなし)\n")

            else:
                # カラム名も一緒に出す
                column_names = [column[1] for column in columns]

                for row_number, row in enumerate(rows, start=1):

                    f.write(f"\n--- ROW {row_number} ---\n")

                    for column_name, value in zip(column_names, row):
                        f.write(
                            f"{column_name}: {repr(value)}\n"
                        )

        except Exception as e:
            f.write(f"ERROR: {e}\n")

        f.write("\n\n")


# ==============================
# 終了
# ==============================

conn.close()

print()
print("========================================")
print("解析完了！")
print(f"テーブル数: {len(tables)}")
print(f"出力ファイル: {OUTPUT_PATH}")
print("========================================")