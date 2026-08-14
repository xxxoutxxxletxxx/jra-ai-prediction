import sqlite3
from pathlib import Path

DB_PATH = Path("data/raw/race.db")
TABLE = "NL_RA_RACE"
OUTPUT = Path("data/output/NL_RA_RACE_inspection.txt")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

with OUTPUT.open("w", encoding="utf-8") as f:

    # ==============================
    # 基本情報
    # ==============================
    f.write("=== BASIC INFO ===\n\n")

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    f.write(f"rows: {cur.fetchone()[0]:,}\n\n")

    # ==============================
    # カラム一覧
    # ==============================
    f.write("=== COLUMNS ===\n\n")

    cur.execute(f"PRAGMA table_info({TABLE})")
    columns = cur.fetchall()

    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        f.write(
            f"{cid:3d} | "
            f"{name:40s} | "
            f"{dtype:10s} | "
            f"NOT NULL={notnull} | "
            f"PK={pk}\n"
        )

    # ==============================
    # 実データ5件
    # ==============================
    f.write("\n\n=== SAMPLE ROWS ===\n")

    cur.execute(f"SELECT * FROM {TABLE} LIMIT 5")
    rows = cur.fetchall()

    names = [c[1] for c in columns]

    for i, row in enumerate(rows, 1):

        f.write(f"\n\n--- ROW {i} ---\n")

        for name, value in zip(names, row):
            f.write(f"{name}: {repr(value)}\n")

    # ==============================
    # 各カラムの値の種類
    # ==============================
    f.write("\n\n=== COLUMN VALUE SUMMARY ===\n")

    for name in names:

        f.write(f"\n\n### {name}\n")

        try:
            cur.execute(
                f'SELECT COUNT(DISTINCT "{name}") FROM {TABLE}'
            )
            distinct = cur.fetchone()[0]

            cur.execute(
                f'SELECT COUNT(*) FROM {TABLE} '
                f'WHERE "{name}" IS NULL OR "{name}" = \'\''
            )
            missing = cur.fetchone()[0]

            f.write(f"distinct: {distinct:,}\n")
            f.write(f"null/blank: {missing:,}\n")

            # 種類が少ない列だけ値を全部表示
            if distinct <= 30:

                cur.execute(
                    f'''
                    SELECT "{name}", COUNT(*)
                    FROM {TABLE}
                    GROUP BY "{name}"
                    ORDER BY COUNT(*) DESC
                    '''
                )

                for value, count in cur.fetchall():
                    f.write(f"  {repr(value)} : {count:,}\n")

            # 種類が多い場合は上位10件
            else:

                cur.execute(
                    f'''
                    SELECT "{name}", COUNT(*)
                    FROM {TABLE}
                    GROUP BY "{name}"
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                    '''
                )

                f.write("top 10:\n")

                for value, count in cur.fetchall():
                    f.write(f"  {repr(value)} : {count:,}\n")

        except Exception as e:
            f.write(f"ERROR: {e}\n")

conn.close()

print(f"完了: {OUTPUT}")