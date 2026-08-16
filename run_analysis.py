import sqlite3
import re

db_uri = 'file:data/raw/race.db?mode=ro'
conn = sqlite3.connect(db_uri, uri=True)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. tables
print("=== Tables & SQL ===")
cursor.execute("select name, sql from sqlite_master where type='table' order by name;")
tables = cursor.fetchall()
for t in tables:
    print(f"Table: {t['name']}")
    print(f"SQL: {t['sql']}\n")

# 2. pragma table_info
for t in ['NL_SE_RACE_UMA', 'NL_RA_RACE']:
    print(f"=== PRAGMA table_info('{t}') ===")
    cursor.execute(f"pragma table_info('{t}');")
    for r in cursor.fetchall():
        print(f"{r['cid']}|{r['name']}|{r['type']}|{r['notnull']}|{r['dflt_value']}|{r['pk']}")

# 3. Match columns and sample data (max 5 non-null)
pattern = re.compile(r'Race|Ketto|Grade|Jyoken|Course|Track|Kakutei|Chakusa|Umaban|Date|Hiduke|払戻|Haraimodoshi', re.IGNORECASE)
for t in ['NL_SE_RACE_UMA', 'NL_RA_RACE', 'NL_HR_PAY']:
    cursor.execute(f"pragma table_info('{t}');")
    cols = [r['name'] for r in cursor.fetchall()]
    matched_cols = [c for c in cols if pattern.search(c)]
    print(f"=== {t} matched columns samples (up to 5 non-null) ===")
    for mc in matched_cols:
        cursor.execute(f"select {mc} from {t} where {mc} is not null and {mc} \!= '' limit 5;")
        samples = [r[0] for r in cursor.fetchall()]
        print(f"{mc}: {samples}")

# 4. Total count & 2012-01-01 counts (by headMakeDate/YearMonthDay etc.)
# Let's inspect the actual columns related to date.
# NL_SE_RACE_UMA has headMakeDate, idYear, idMonthDay.
# NL_RA_RACE has headMakeDate, idYear, idMonthDay.
# Usually, the race date of the event is represented by idYear + idMonthDay (e.g., '2012' + '0105' = '20120105'). 
# Let's verify and count based on idYear and idMonthDay.
for t in ['NL_SE_RACE_UMA', 'NL_RA_RACE']:
    print(f"=== {t} Counts & Date Ranges ===")
    cursor.execute(f"select count(*) from {t};")
    total_cnt = cursor.fetchone()[0]
    print(f"Total count: {total_cnt}")
    
    # Count of races from 2012-01-01 onwards
    # Let's query using idYear >= '2012'
    cursor.execute(f"select count(*), max(idYear || idMonthDay) from {t} where idYear >= '2012';")
    cnt_2012, max_date = cursor.fetchone()
    print(f"Count from 2012-01-01 onwards (idYear >= 2012): {cnt_2012}")
    print(f"Max date (idYear || idMonthDay): {max_date}")

# 5. Index list
for t in ['NL_SE_RACE_UMA', 'NL_RA_RACE']:
    print(f"=== Indexes for {t} ===")
    cursor.execute(f"pragma index_list('{t}');")
    idx_list = cursor.fetchall()
    for idx in idx_list:
        print(f"Index name: {idx['name']}, Unique: {idx['unique']}")
        cursor.execute(f"pragma index_info('{idx['name']}');")
        for info in cursor.fetchall():
            print(f"  Col: {info['name']}")

# 6. Primary Key / Race Key Duplicate checks
# Usually, a race key is composed of: idYear + idMonthDay + idJyoCD + idKaiji + idNichiji + idRaceNum.
# Let's see if there are duplicates for this key.
for t in ['NL_RA_RACE']:
    print(f"=== {t} Key Duplicate check ===")
    query = """
    select idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum, count(*) as cnt 
    from NL_RA_RACE 
    group by idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum 
    having count(*) > 1 
    limit 10;
    """
    cursor.execute(query)
    dupes = cursor.fetchall()
    print(f"Duplicates (limit 10): {dupes}")

for t in ['NL_SE_RACE_UMA']:
    print(f"=== {t} Key (including Umaban) Duplicate check ===")
    query = """
    select idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum, Umaban, count(*) as cnt 
    from NL_SE_RACE_UMA 
    group by idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum, Umaban 
    having count(*) > 1 
    limit 10;
    """
    cursor.execute(query)
    dupes = cursor.fetchall()
    print(f"Duplicates (limit 10): {dupes}")

conn.close()
