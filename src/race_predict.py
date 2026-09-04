#!/usr/bin/env python3
"""
競馬予測システム MVP - デモ版
実際のDBスキーマに基づいて設計したデモンストレーション

ネットワーク制限のある環境で動作確認するため、
LightGBMの代わりにシンプルな統計ベースの予測を使用しています。
"""

import os
import sys
import time
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json
import csv

sys.path.insert(0, str(Path(__file__).parent))
from betting_rules import decide_bet, reason_text

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "raw" / "race.db"
COURSE_FEATURES_PATH = PROJECT_ROOT / "data" / "output" / "course_features_ver6.csv"
OUTPUT_DIR = PROJECT_ROOT / "output"
DOCS_DIR = PROJECT_ROOT / "docs"

OUTPUT_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# 処理統計
STATS = {}
JRA_CENTRAL_CODES = {'01', '02', '03', '04', '05', '06', '07', '08', '09', '10'}
JRA_COURSE_NAMES = {
    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
    '05': '東京', '06': '中山', '07': '中京', '08': '京都',
    '09': '阪神', '10': '小倉'
}


def normalize_jyo_code(value):
    """JRA場コードを安全に2桁文字列に正規化"""
    if value is None:
        return ''
    return str(value).strip().zfill(2) if str(value).strip() else ''


def normalize_umaban(value):
    """馬番を整数に正規化"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def get_jyo_name(value):
    """場コードから競馬場名を返す"""
    return JRA_COURSE_NAMES.get(normalize_jyo_code(value), str(value) if value is not None else '不明')


def load_race_data(min_year=2012):
    """race.dbからレースデータを読み込む"""
    logger.info("[1/8] Loading database...")
    start = time.time()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # NL_SE_RACE_UMA から必要なカラムのみ
        se_cols = [
            'idYear', 'idMonthDay', 'idJyoCD', 'idKaiji', 'idNichiji', 'idRaceNum',
            'Wakuban', 'Umaban', 'KettoNum', 'Bamei',
            'SexCD', 'Barei', 'TozaiCD', 'Futan', 'Blinker', 'KisyuCode', 'MinaraiCD', 
            'BaTaijyu', 'ZogenFugo', 'ZogenSa',
            'NyusenJyuni', 'KakuteiJyuni', 'IJyoCD', 'ChakusaCD', 'KyakusituKubun',
            'Odds', 'Time', 'TimeDiff', 'HaronTimeL3', 'HaronTimeL4',
            'Jyuni1c', 'Jyuni2c', 'Jyuni3c', 'Jyuni4c', 'Honsyokin', 'Fukasyokin',
            'headDataKubun'
        ]
        
        se_query = f"""
            SELECT {', '.join(se_cols)}
            FROM NL_SE_RACE_UMA
            WHERE idYear >= {min_year}
            ORDER BY idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum, Umaban
        """
        
        # データをディクショナリのリストに変換
        cursor = conn.cursor()
        cursor.execute(se_query)
        
        se_rows = []
        cols = [description[0] for description in cursor.description]
        for row in cursor.fetchall():
            se_rows.append(dict(zip(cols, row)))
        
        logger.info(f"    NL_SE_RACE_UMA: {len(se_rows):,} rows")
        STATS['se_rows'] = len(se_rows)
        
        # NL_RA_RACE
        ra_cols = [
            'idYear', 'idMonthDay', 'idJyoCD', 'idKaiji', 'idNichiji', 'idRaceNum',
            'RaceInfoYoubiCD', 'Kyori', 'TrackCD', 'GradeCD',
            'JyokenInfoSyubetuCD', 'CourseKubunCD', 'SyussoTosu', 'NyusenTosu',
            'TenkoBabaTenkoCD', 'TenkoBabaSibaBabaCD', 'TenkoBabaDirtBabaCD',
            'HaronTimeL3', 'HaronTimeL4', 'CornerInfo0Jyuni', 'CornerInfo1Jyuni',
            'CornerInfo2Jyuni', 'CornerInfo3Jyuni',
            'headDataKubun'
        ]
        
        ra_query = f"""
            SELECT {', '.join(ra_cols)}
            FROM NL_RA_RACE
            WHERE idYear >= {min_year}
            ORDER BY idYear, idMonthDay, idJyoCD, idKaiji, idNichiji, idRaceNum
        """
        
        cursor.execute(ra_query)
        
        ra_rows = []
        cols = [description[0] for description in cursor.description]
        for row in cursor.fetchall():
            ra_rows.append(dict(zip(cols, row)))
        
        logger.info(f"    NL_RA_RACE: {len(ra_rows):,} rows")
        STATS['ra_rows'] = len(ra_rows)
        
        conn.close()
        
        elapsed = time.time() - start
        logger.info(f"    Elapsed: {elapsed:.1f}s\n")
        
        return se_rows, ra_rows
        
    except sqlite3.OperationalError as e:
        logger.error(f"Database error: {e}")
        logger.info("    Creating demo data instead...\n")
        return create_demo_data()


def create_demo_data():
    """デモ用のサンプルデータを生成"""
    se_rows = []
    ra_rows = []
    
    # 10レースのデモデータを生成
    for race_idx in range(1, 11):
        year = 2025
        month_day = f"0{8 + race_idx // 10}{(race_idx % 10):02d}"
        jyo_cd = "01"
        
        race_key = {
            'idYear': year,
            'idMonthDay': month_day,
            'idJyoCD': jyo_cd,
            'idKaiji': '01',
            'idNichiji': '01',
            'idRaceNum': f"{race_idx:02d}"
        }
        
        # レース情報
        ra_rows.append({
            **race_key,
            'RaceInfoYoubiCD': '1',
            'Kyori': 1600,
            'TrackCD': '17',
            'GradeCD': '0',
            'JyokenInfoSyubetuCD': '0',
            'CourseKubunCD': '1',
            'SyussoTosu': 8,
            'NyusenTosu': 8,
            'TenkoBabaTenkoCD': '1',
            'TenkoBabaSibaBabaCD': '0',
            'TenkoBabaDirtBabaCD': '0',
            'HaronTimeL3': 35.2,
            'HaronTimeL4': 45.3,
            'CornerInfo0Jyuni': 1,
            'CornerInfo1Jyuni': 2,
            'CornerInfo2Jyuni': 3,
            'CornerInfo3Jyuni': 4,
            'headDataKubun': '7'
        })
        
        # 馬情報 (8頭)
        for horse_idx in range(1, 9):
            se_rows.append({
                **race_key,
                'Wakuban': horse_idx,
                'Umaban': f"{horse_idx:02d}",
                'KettoNum': 2000000 + race_idx * 100 + horse_idx,
                'Bamei': f"テスト馬{race_idx}-{horse_idx}",
                'SexCD': '1',
                'Barei': '02',
                'TozaiCD': '1',
                'Futan': 55 + horse_idx,
                'Blinker': '0',
                'KisyuCode': f"0{horse_idx:04d}",
                'MinaraiCD': '0',
                'BaTaijyu': 450 + horse_idx * 5,
                'ZogenFugo': '+',
                'ZogenSa': 10,
                'NyusenJyuni': horse_idx,
                'KakuteiJyuni': f"{horse_idx:02d}",
                'IJyoCD': '0',
                'ChakusaCD': '0',
                'KyakusituKubun': '0',
                'Odds': 5.0 * horse_idx,
                'Time': '01:36:42' if horse_idx == 1 else '',
                'TimeDiff': 0.0 if horse_idx == 1 else 1.0 * horse_idx,
                'HaronTimeL3': 35.2 + (horse_idx - 1) * 0.5,
                'HaronTimeL4': 45.3 + (horse_idx - 1) * 0.7,
                'Jyuni1c': horse_idx,
                'Jyuni2c': horse_idx,
                'Jyuni3c': horse_idx,
                'Jyuni4c': horse_idx,
                'Honsyokin': 500000 if horse_idx == 1 else 0,
                'Fukasyokin': 200000 if horse_idx == 1 else 0,
                'headDataKubun': '7'
            })
    
    STATS['se_rows'] = len(se_rows)
    STATS['ra_rows'] = len(ra_rows)
    
    return se_rows, ra_rows


def build_race_dataset(se_rows, ra_rows):
    """レースデータセット構築 - JRA中央競馬のみ"""
    logger.info("[2/8] Building race dataset (JRA central only)...")
    start = time.time()

    # レースIDでマージ
    race_dict = {}
    for ra in ra_rows:
        jyo_cd = normalize_jyo_code(ra.get('idJyoCD'))
        if jyo_cd not in JRA_CENTRAL_CODES:
            continue

        key = (int(ra['idYear']), str(ra['idMonthDay']), jyo_cd,
               str(ra['idKaiji']), str(ra['idNichiji']), str(ra['idRaceNum']))
        race_dict[key] = ra

    merged = []
    for se in se_rows:
        jyo_cd = normalize_jyo_code(se.get('idJyoCD'))
        if jyo_cd not in JRA_CENTRAL_CODES:
            continue

        key = (int(se['idYear']), str(se['idMonthDay']), jyo_cd,
               str(se['idKaiji']), str(se['idNichiji']), str(se['idRaceNum']))

        if key in race_dict:
            merged_row = {**se, **{f"{k}_race": v for k, v in race_dict[key].items()}}
        else:
            merged_row = se

        # idJyoCD を正規化し、競馬場名も保持
        merged_row['idJyoCD'] = jyo_cd
        merged_row['JyoName'] = get_jyo_name(jyo_cd)

        # race_date生成
        year = int(se['idYear'])
        month_day_str = str(se['idMonthDay']).zfill(4)
        month = int(month_day_str[:2])
        day = int(month_day_str[2:])

        try:
            merged_row['race_date'] = datetime(year, month, day)
        except ValueError:
            # 無効な日付の場合はスキップ
            continue

        # ターゲット
        try:
            kaku = merged_row.get('KakuteiJyuni', '')
            merged_row['target'] = 1 if str(kaku) == '01' else 0
        except:
            merged_row['target'] = 0

        merged.append(merged_row)

    # ソート
    merged.sort(key=lambda x: (x['KettoNum'], x['race_date']))

    elapsed = time.time() - start
    logger.info(f"    JRA central only: {len(merged):,} rows")
    logger.info(f"    Elapsed: {elapsed:.1f}s\n")
    STATS['merged_rows'] = len(merged)

    return merged


def build_historical_features(data):
    """過去走特徴量生成（シンプル版）"""
    logger.info("[3/8] Building historical features...")
    start = time.time()
    
    for row in data:
        row['prev_finish'] = None
        row['prev_time_diff'] = None
        row['last5_win_rate'] = 0.0
        row['last5_place_rate'] = 0.0
        row['days_since_last_race'] = 0
    
    elapsed = time.time() - start
    logger.info(f"    Features added: {len(data):,} rows")
    logger.info(f"    Elapsed: {elapsed:.1f}s\n")
    
    return data


def load_and_join_course_features(data):
    """コース特徴をJOIN"""
    logger.info("[4/8] Joining course features...")
    start = time.time()
    
    # course_features_ver6.csvを試す
    try:
        import csv
        course_dict = {}
        with open(COURSE_FEATURES_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['JyoCD'], row['Kyori_m'], row['TrackCD'])
                course_dict[key] = row
        
        for row in data:
            key = (row['idJyoCD'], str(row.get('Kyori', 1600)), row.get('TrackCD', '17'))
            if key in course_dict:
                for k, v in course_dict[key].items():
                    if k not in row:
                        row[f"{k}_course"] = v
        
        logger.info(f"    Course features joined: {len(data):,} rows")
    except Exception as e:
        logger.info(f"    Course features not found (OK for demo): {e}")
    
    elapsed = time.time() - start
    logger.info(f"    Elapsed: {elapsed:.1f}s\n")
    
    return data


def train_model_demo(data):
    """デモ用の簡易モデル（統計ベース）- 確定済み・結果有効なレースのみ"""
    logger.info("[5/8] Training model (demo)...")
    start = time.time()

    # 学習データフィルター: 2012年以降の確定済みレース（headDataKubun=='7'）のみ
    # さらに、KakuteiJyuniが有効（01〜19, 00は除外）であること
    confirmed = []
    for r in data:
        if r.get('headDataKubun') != '7':
            continue
        if int(r.get('idYear', 0)) < 2012:
            continue

        kaku = str(r.get('KakuteiJyuni', '')).strip()
        if kaku in {'', '00'}:
            continue
        if not kaku.isdigit() or len(kaku) != 2:
            continue

        confirmed.append(r)

    training_race_keys = set((r['idYear'], r['idMonthDay'], r['idJyoCD'], r['idKaiji'], r['idNichiji'], r['idRaceNum']) for r in confirmed)
    logger.info(f"    Training period: 2012-01-01 to {max((r['race_date'] for r in confirmed), default='N/A').strftime('%Y-%m-%d') if confirmed else 'N/A'}")
    logger.info(f"    Training races: {len(training_race_keys):,}")
    logger.info(f"    Training horses: {len(confirmed):,}")
    STATS['confirmed_races'] = len(training_race_keys)
    STATS['training_horses'] = len(confirmed)

    # 馬の特徴から簡易スコアを計算
    win_rates = {}
    for row in confirmed:
        ketto = row['KettoNum']
        is_win = row['target']

        if ketto not in win_rates:
            win_rates[ketto] = {'wins': 0, 'races': 0}

        win_rates[ketto]['races'] += 1
        if is_win:
            win_rates[ketto]['wins'] += 1

    elapsed = time.time() - start
    logger.info(f"    Model trained (demo mode)")
    logger.info(f"    Elapsed: {elapsed:.1f}s\n")

    return win_rates


def predict_upcoming(data, win_rates):
    """未確定レース予測 - 予測可能なもののみ"""
    logger.info("[6/8] Predicting upcoming races...")
    start = time.time()

    # 予測対象フィルター
    # 1. JRA中央10場のみ
    # 2. 結果未確定（headDataKubun != '7'）
    # 3. Umaban > 0（馬番が確定）
    # 4. 馬名がある（Bamei）
    # 5. これから開催されるレース（race_date >= 今日）
    today = datetime.now().date()

    upcoming = []
    for r in data:
        if normalize_jyo_code(r.get('idJyoCD')) not in JRA_CENTRAL_CODES:
            continue
        if str(r.get('headDataKubun', '')).strip() == '7':
            continue
        if normalize_umaban(r.get('Umaban')) <= 0:
            continue
        if not str(r.get('Bamei', '')).strip():
            continue
        race_date = r.get('race_date')
        if race_date is None or race_date.date() < today:
            continue
        upcoming.append(r)

    logger.info(f"    Prediction target venues: {sorted({normalize_jyo_code(r.get('idJyoCD')) for r in upcoming})}")
    logger.info(f"    Prediction target dates: {sorted({r['race_date'].date().isoformat() for r in upcoming})[:5]} ..." if upcoming else "    Prediction target dates: none")
    logger.info(f"    Prediction target races: {len({(r['idYear'], r['idMonthDay'], r['idJyoCD'], r['idKaiji'], r['idNichiji'], r['idRaceNum']) for r in upcoming}):,}")
    logger.info(f"    Prediction target horses: {len(upcoming):,}")

    STATS['upcoming_races'] = len({(r['idYear'], r['idMonthDay'], r['idJyoCD'], r['idKaiji'], r['idNichiji'], r['idRaceNum']) for r in upcoming})
    STATS['upcoming_horses'] = len(upcoming)

    # 簡易予測スコア
    for row in upcoming:
        ketto = row['KettoNum']

        # 過去成績から確率を計算（シンプル）
        if ketto in win_rates:
            wr = win_rates[ketto]
            prob = wr['wins'] / max(wr['races'], 1)
        else:
            # 過去成績がない場合は等確率
            prob = 0.125

        # 買い目判定には揺らぎを含まない生出力確率を保持する
        row['raw_win_probability'] = min(0.99, max(0.01, prob))
        row['predicted_win_probability'] = prob + (hash(ketto) % 100) / 2000.0
        row['predicted_win_probability'] = min(0.99, max(0.01, row['predicted_win_probability']))

    # ランク付け（レース内）
    races_dict = {}
    for row in upcoming:
        key = (row['idYear'], row['idMonthDay'], row['idJyoCD'],
               row['idKaiji'], row['idNichiji'], row['idRaceNum'])
        if key not in races_dict:
            races_dict[key] = []
        races_dict[key].append(row)

    for race_horses in races_dict.values():
        race_horses.sort(key=lambda x: x['predicted_win_probability'], reverse=True)
        for rank, horse in enumerate(race_horses, 1):
            horse['ai_rank'] = rank

    elapsed = time.time() - start
    logger.info(f"    Elapsed: {elapsed:.1f}s\n")

    return upcoming


def generate_outputs(predictions):
    """出力生成 - 予測対象のみ"""
    logger.info("[7/8] Writing outputs...")
    start = time.time()

    if not predictions:
        logger.warning("    No predictions to output")
        return

    # CSV
    csv_path = OUTPUT_DIR / "predictions.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'race_date', 'idJyoCD', '競馬場名', 'idRaceNum', 'Umaban', 'Bamei',
            'KisyuCode', 'predicted_win_probability', 'ai_rank', 'Odds', 'expected_value',
            'bet_decision', 'bet_reason_code', 'bet_reason'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for pred in predictions:
            odds = 0.0
            try:
                odds = float(str(pred.get('Odds', '0')).strip() or '0')
            except (TypeError, ValueError):
                odds = 0.0
            prob = float(pred.get('predicted_win_probability', 0.0) or 0.0)
            expected_value = (prob * (odds - 1.0)) if odds > 0 else 0.0
            row = {
                'race_date': str(pred['race_date'].date()),
                'idJyoCD': normalize_jyo_code(pred.get('idJyoCD')),
                '競馬場名': get_jyo_name(pred.get('idJyoCD')),
                'idRaceNum': pred.get('idRaceNum', ''),
                'Umaban': str(pred.get('Umaban', '')),
                'Bamei': pred.get('Bamei', ''),
                'KisyuCode': pred.get('KisyuCode', ''),
                'predicted_win_probability': f"{prob:.6f}",
                'ai_rank': pred.get('ai_rank', ''),
                'Odds': odds,
                'expected_value': f"{expected_value:.6f}"
            }
            # 本命（ai_rank=1）のみ買い目判定。OddsはDB生値の10倍スケール。
            if pred.get('ai_rank') == 1:
                bet, reason_code = decide_bet(odds / 10.0 if odds > 0 else None,
                                              pred.get('raw_win_probability'))
                row['bet_decision'] = 'BET' if bet else 'SKIP'
                row['bet_reason_code'] = reason_code
                row['bet_reason'] = reason_text(reason_code)
            writer.writerow(row)

    logger.info(f"    Saved predictions.csv ({len(predictions):,} rows)")
    
    # JSON
    json_path = OUTPUT_DIR / "predictions.json"
    json_data = {
        'generated_at': datetime.now().isoformat(),
        'races': []
    }
    
    races_dict = {}
    for pred in predictions:
        key = (pred['idYear'], pred['idMonthDay'], pred['idJyoCD'], 
               pred['idKaiji'], pred['idNichiji'], pred['idRaceNum'])
        if key not in races_dict:
            races_dict[key] = []
        races_dict[key].append(pred)
    
    for race_key, horses in races_dict.items():
        race_dict = {
            'date': str(horses[0]['race_date'].date()),
            'jyo': str(race_key[2]),
            'num': int(race_key[5]),
            'horses': []
        }
        
        for horse in sorted(horses, key=lambda x: x.get('ai_rank', 99)):
            horse_dict = {
                'umaban': int(horse.get('Umaban', 0)),
                'name': str(horse.get('Bamei', 'N/A')),
                'prob': round(float(horse.get('predicted_win_probability', 0)), 4),
                'rank': int(horse.get('ai_rank', 99))
            }
            if horse.get('Odds'):
                try:
                    horse_dict['odds'] = round(float(horse['Odds']), 2)
                except:
                    pass
            if horse.get('ai_rank') == 1:
                raw_odds = 0.0
                try:
                    raw_odds = float(str(horse.get('Odds', '0')).strip() or '0')
                except (TypeError, ValueError):
                    raw_odds = 0.0
                bet, reason_code = decide_bet(raw_odds / 10.0 if raw_odds > 0 else None,
                                              horse.get('raw_win_probability'))
                horse_dict['bet_decision'] = 'BET' if bet else 'SKIP'
                horse_dict['bet_reason'] = reason_text(reason_code)

            race_dict['horses'].append(horse_dict)
        
        json_data['races'].append(race_dict)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"    Saved predictions.json ({len(json_data['races'])} races)")
    
    # docs/index.html は scripts/build_site_data.py が生成するため、ここでは触れない
    
    elapsed = time.time() - start
    logger.info(f"    Elapsed: {elapsed:.1f}s\n")


def main():
    """メイン処理"""
    logger.info("=" * 80)
    logger.info("競馬予測システム MVP - デモ版")
    logger.info("=" * 80 + "\n")
    
    total_start = time.time()
    
    try:
        # 1. データ読み込み
        se_rows, ra_rows = load_race_data(min_year=2012)
        
        # 2. レースデータセット構築
        data = build_race_dataset(se_rows, ra_rows)
        
        # 3. 過去走特徴量
        data = build_historical_features(data)
        
        # 4. コース機能JOIN
        data = load_and_join_course_features(data)
        
        # 5. モデル学習
        win_rates = train_model_demo(data)
        
        # 6. 未確定レース予測
        predictions = predict_upcoming(data, win_rates)

        # 6.5 検証
        non_jra_count = sum(1 for p in predictions if normalize_jyo_code(p.get('idJyoCD')) not in JRA_CENTRAL_CODES)
        zero_umaban_count = sum(1 for p in predictions if normalize_umaban(p.get('Umaban')) == 0)
        confirmed_prediction_count = sum(1 for p in predictions if str(p.get('headDataKubun', '')).strip() == '7')

        logger.info("=== Validation ===")
        logger.info(f"Training period: 2012-01-01 to {max((r['race_date'] for r in data if str(r.get('headDataKubun', '')).strip() == '7' and int(r.get('idYear', 0)) >= 2012), default=datetime(2012, 1, 1)).strftime('%Y-%m-%d') if any(str(r.get('headDataKubun', '')).strip() == '7' and int(r.get('idYear', 0)) >= 2012 for r in data) else 'N/A'}")
        logger.info(f"Training races: {len({(r['idYear'], r['idMonthDay'], r['idJyoCD'], r['idKaiji'], r['idNichiji'], r['idRaceNum']) for r in data if str(r.get('headDataKubun', '')).strip() == '7' and int(r.get('idYear', 0)) >= 2012}):,}")
        logger.info(f"Training horses: {sum(1 for r in data if str(r.get('headDataKubun', '')).strip() == '7' and int(r.get('idYear', 0)) >= 2012):,}")

        pred_dates = sorted({r['race_date'].date().isoformat() for r in predictions})
        logger.info(f"Prediction target date: {pred_dates[0] if pred_dates else 'N/A'} to {pred_dates[-1] if pred_dates else 'N/A'}")
        logger.info(f"Prediction target venues: {sorted({normalize_jyo_code(r.get('idJyoCD')) for r in predictions})}")
        logger.info(f"Prediction target races: {len({(r['idYear'], r['idMonthDay'], r['idJyoCD'], r['idKaiji'], r['idNichiji'], r['idRaceNum']) for r in predictions}):,}")
        logger.info(f"Prediction target horses: {len(predictions):,}")
        logger.info(f"JRA central outside predictions = {non_jra_count}")
        logger.info(f"Umaban=0 predictions = {zero_umaban_count}")
        logger.info(f"Confirmed race predictions = {confirmed_prediction_count}")

        assert non_jra_count == 0, f"JRA中央10場以外の予測件数が0ではありません: {non_jra_count}"
        assert zero_umaban_count == 0, f"Umaban=0の予測件数が0ではありません: {zero_umaban_count}"
        assert confirmed_prediction_count == 0, f"結果確定済みレースの予測件数が0ではありません: {confirmed_prediction_count}"

        # 7. 出力生成
        generate_outputs(predictions)

        # 8. 完了
        logger.info("[8/8] Done!\n")

        total_elapsed = time.time() - total_start
        logger.info("=" * 80)
        logger.info(f"Total time: {total_elapsed:.1f}s")
        logger.info(f"Confirmed races: {STATS.get('confirmed_races', 0):,}")
        logger.info(f"Predicted horses: {len(predictions):,}")
        logger.info(f"Output: {OUTPUT_DIR}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
