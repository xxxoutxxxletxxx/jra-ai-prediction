import sqlite3
from pathlib import Path

DB_PATH = Path("data/raw/race.db")
TABLE = "NL_SE_RACE_UMA"
OUTPUT = Path("data/output/NL_SE_RACE_UMA_inspection.txt")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

with OUTPUT.open("w", encoding="utf-8") as f:

    # ========================================
    # 1. 基本情報
    # ========================================
    f.write("=== BASIC INFO ===\n\n")

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    row_count = cur.fetchone()[0]
    f.write(f"rows: {row_count:,}\n\n")

    # ========================================
    # 2. 全カラム
    # ========================================
    f.write("=== COLUMNS ===\n\n")

    cur.execute(f"PRAGMA table_info({TABLE})")
    columns = cur.fetchall()
    names = [c[1] for c in columns]

    f.write(f"column count: {len(columns)}\n\n")

    for col in columns:
        cid, name, dtype, notnull, default, pk = col

        f.write(
            f"{cid:3d} | "
            f"{name:40s} | "
            f"{dtype:12s} | "
            f"NOT NULL={notnull} | "
            f"PK={pk}\n"
        )

    # ========================================
    # 3. 実データ10頭
    # ========================================
    f.write("\n\n=== SAMPLE 10 ROWS ===\n")

    cur.execute(f"SELECT * FROM {TABLE} LIMIT 10")
    rows = cur.fetchall()

    for i, row in enumerate(rows, 1):

        f.write(f"\n\n---------- HORSE {i} ----------\n")

        for name, value in zip(names, row):
            f.write(f"{name}: {repr(value)}\n")

    # ========================================
    # 4. 各カラムの概要
    # ========================================
    f.write("\n\n=== COLUMN SUMMARY ===\n")

    for name in names:

        f.write(f"\n\n### {name}\n")

        try:
            cur.execute(
                f'SELECT COUNT(DISTINCT "{name}") '
                f'FROM {TABLE}'
            )
            distinct = cur.fetchone()[0]

            cur.execute(
                f'''
                SELECT COUNT(*)
                FROM {TABLE}
                WHERE "{name}" IS NULL
                   OR CAST("{name}" AS TEXT) = ''
                '''
            )
            missing = cur.fetchone()[0]

            f.write(f"distinct: {distinct:,}\n")
            f.write(f"missing: {missing:,}\n")
            f.write(
                f"missing_rate: "
                f"{missing / row_count * 100:.2f}%\n"
            )

            # 種類が少ない列なら全種類を表示
            if distinct <= 30:

                cur.execute(
                    f'''
                    SELECT "{name}", COUNT(*)
                    FROM {TABLE}
                    GROUP BY "{name}"
                    ORDER BY COUNT(*) DESC
                    '''
                )

                f.write("values:\n")

                for value, count in cur.fetchall():
                    f.write(
                        f"  {repr(value)} : {count:,}\n"
                    )

            # 多い列は頻出上位10件
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
                    f.write(
                        f"  {repr(value)} : {count:,}\n"
                    )

        except Exception as e:
            f.write(f"ERROR: {e}\n")

conn.close()

print("==============================")
print("NL_SE_RACE_UMA inspection done")
print("==============================")
print(f"output: {OUTPUT}")