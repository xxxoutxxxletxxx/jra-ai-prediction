import sqlite3
import csv
from pathlib import Path


# ==========================================
# パス
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "data" / "raw" / "race.db"
OUTPUT_TXT = PROJECT_ROOT / "data" / "output" / "course_info_all.txt"
OUTPUT_CSV = PROJECT_ROOT / "data" / "output" / "course_info_all.csv"


# ==========================================
# DB確認
# ==========================================

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"race.db が見つかりません: {DB_PATH}"
    )

OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)

print(f"DB: {DB_PATH}")
print("コース情報を取得します...")


# ==========================================
# 読み取り専用でSQLite接続
# ==========================================

db_uri = f"file:{DB_PATH}?mode=ro"
conn = sqlite3.connect(db_uri, uri=True)

cur = conn.cursor()


# ==========================================
# NL_CS_COURSE 全件取得
# ==========================================

rows = cur.execute("""
    SELECT
        JyoCD,
        Kyori,
        TrackCD,
        KaishuDate,
        CourseEx
    FROM NL_CS_COURSE
    ORDER BY
        JyoCD,
        TrackCD,
        CAST(Kyori AS INTEGER),
        KaishuDate
""").fetchall()

print(f"取得件数: {len(rows)}")


# ==========================================
# TXT出力
# ==========================================

with open(OUTPUT_TXT, "w", encoding="utf-8") as f:

    f.write("JRA-VAN COURSE INFORMATION\n")
    f.write("=" * 100 + "\n")
    f.write(f"TOTAL COURSES: {len(rows)}\n")
    f.write("=" * 100 + "\n\n")

    for i, row in enumerate(rows, start=1):

        jyo_cd, kyori, track_cd, kaishu_date, course_ex = row

        f.write("=" * 100 + "\n")
        f.write(f"COURSE {i}\n")
        f.write("=" * 100 + "\n")

        f.write(f"JyoCD      : {jyo_cd}\n")
        f.write(f"Kyori      : {kyori}m\n")
        f.write(f"TrackCD    : {track_cd}\n")
        f.write(f"KaishuDate : {kaishu_date}\n")

        f.write("\nCOURSE DESCRIPTION:\n")
        f.write("-" * 100 + "\n")

        if course_ex:
            f.write(course_ex.strip())
        else:
            f.write("(説明なし)")

        f.write("\n\n")


# ==========================================
# CSVも出力
# ==========================================

with open(
    OUTPUT_CSV,
    "w",
    encoding="utf-8-sig",
    newline=""
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "JyoCD",
        "Kyori",
        "TrackCD",
        "KaishuDate",
        "CourseEx"
    ])

    writer.writerows(rows)


# ==========================================
# 終了
# ==========================================

conn.close()

print()
print("=" * 60)
print("出力完了！")
print(f"TXT: {OUTPUT_TXT}")
print(f"CSV: {OUTPUT_CSV}")
print("=" * 60)