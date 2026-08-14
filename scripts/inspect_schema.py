#!/usr/bin/env python3
"""
race.db のスキーマと実データを確認するスクリプト（pandasなし）
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "raw" / "race.db"

def inspect_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # テーブル一覧を取得
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("=" * 80)
    print("Available tables:")
    print("=" * 80)
    for table in tables:
        print(f"  - {table[0]}")
    
    # NL_SE_RACE_UMA のスキーマ確認
    print("\n" + "=" * 80)
    print("NL_SE_RACE_UMA schema:")
    print("=" * 80)
    cursor.execute("PRAGMA table_info(NL_SE_RACE_UMA);")
    schema = cursor.fetchall()
    for col in schema:
        print(f"  {col[1]:30s} {col[2]}")
    
    # NL_RA_RACE のスキーマ確認
    print("\n" + "=" * 80)
    print("NL_RA_RACE schema:")
    print("=" * 80)
    cursor.execute("PRAGMA table_info(NL_RA_RACE);")
    schema = cursor.fetchall()
    for col in schema:
        print(f"  {col[1]:30s} {col[2]}")
    
    # NL_SE_RACE_UMA のサンプルデータ
    print("\n" + "=" * 80)
    print("NL_SE_RACE_UMA sample (first 3 rows):")
    print("=" * 80)
    cursor.execute("SELECT * FROM NL_SE_RACE_UMA LIMIT 3")
    cols = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    print("Columns:", cols)
    for i, row in enumerate(rows):
        print(f"\nRow {i+1}:")
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")
    
    # NL_RA_RACE のサンプルデータ
    print("\n" + "=" * 80)
    print("NL_RA_RACE sample (first 3 rows):")
    print("=" * 80)
    cursor.execute("SELECT * FROM NL_RA_RACE LIMIT 3")
    cols = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    print("Columns:", cols)
    for i, row in enumerate(rows):
        print(f"\nRow {i+1}:")
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")
    
    # データ期間を確認
    print("\n" + "=" * 80)
    print("Data date range:")
    print("=" * 80)
    cursor.execute("""
        SELECT 
            MIN(idYear) as min_year,
            MAX(idYear) as max_year,
            COUNT(*) as total_rows
        FROM NL_SE_RACE_UMA
    """)
    result = cursor.fetchone()
    print(f"Min year: {result[0]}, Max year: {result[1]}, Total rows: {result[2]}")
    
    # KakuteiJyuni の値を確認
    print("\n" + "=" * 80)
    print("KakuteiJyuni unique values (top 20):")
    print("=" * 80)
    cursor.execute("""
        SELECT 
            KakuteiJyuni,
            COUNT(*) as count
        FROM NL_SE_RACE_UMA
        GROUP BY KakuteiJyuni
        ORDER BY count DESC
        LIMIT 20
    """)
    results = cursor.fetchall()
    for val, count in results:
        print(f"  {val}: {count}")
    
    # レースIDの確認
    print("\n" + "=" * 80)
    print("Race ID columns sample (NL_SE_RACE_UMA):")
    print("=" * 80)
    cursor.execute("""
        SELECT DISTINCT
            idYear,
            idMonthDay,
            idJyoCD,
            idKaiji,
            idNichiji,
            idRaceNum
        FROM NL_SE_RACE_UMA
        LIMIT 5
    """)
    results = cursor.fetchall()
    for row in results:
        print(f"  {row}")
    
    # NL_RA_RACE のレースID確認
    print("\n" + "=" * 80)
    print("Race ID columns sample (NL_RA_RACE):")
    print("=" * 80)
    cursor.execute("""
        SELECT DISTINCT
            idYear,
            idMonthDay,
            idJyoCD,
            idKaiji,
            idNichiji,
            idRaceNum
        FROM NL_RA_RACE
        LIMIT 5
    """)
    results = cursor.fetchall()
    for row in results:
        print(f"  {row}")
    
    # NL_SE_RACE_UMA の行数
    print("\n" + "=" * 80)
    print("Table row counts:")
    print("=" * 80)
    cursor.execute("SELECT COUNT(*) FROM NL_SE_RACE_UMA")
    count = cursor.fetchone()[0]
    print(f"NL_SE_RACE_UMA: {count:,}")
    
    cursor.execute("SELECT COUNT(*) FROM NL_RA_RACE")
    count = cursor.fetchone()[0]
    print(f"NL_RA_RACE: {count:,}")
    
    conn.close()

if __name__ == "__main__":
    inspect_db()
