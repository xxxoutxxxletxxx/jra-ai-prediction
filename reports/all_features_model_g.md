# Model G 実入力特徴量仕様書

この仕様書は既存コードと保存済み成果物の読み取り結果です。特徴量のKEEP/DROP/REBUILD/CHECKは判断していません。`human_decision`欄は空欄です。

- 実入力列（保存一覧の出現単位）: **443**
- ユニーク特徴量名: **388**
- 重複を含む特徴量名: **55**
- importance参照: `reports/backtest_phase6_G_cached_10_final/feature_importance.csv`
- LightGBM入力経路: `src/backtest.py:1182-1205`（カテゴリ列をone-hot化後にfit）
- 未勝利履歴: 通常のModel G baselineでは履歴filterを適用せず、履歴系は未勝利を含み得る。

## Course

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|91|course_first_corner_distance_m|当該コース形状のfirst corner distance m|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|1897.9770984649658|22.0||
|92|course_elevation_difference_m|当該コース形状のelevation difference m|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|2015.339687347412|29.0||
|93|course_final_straight_m|当該コース形状のfinal straight m|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|5633.410729408264|64.0||
|94|course_start_uphill|当該コース形状のstart uphill|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|95|course_start_downhill|当該コース形状のstart downhill|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|96|course_final_uphill|当該コース形状のfinal uphill|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|57.86610221862793|2.0||
|97|course_final_downhill|当該コース形状のfinal downhill|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|98|course_final_steep_hill|当該コース形状のfinal steep hill|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|99|course_rolling_terrain|当該コース形状のrolling terrain|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|100|course_mostly_flat|当該コース形状のmostly flat|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|262.01210021972656|6.0||
|101|course_gentle_corners|当該コース形状のgentle corners|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|309.70179748535156|7.0||
|102|course_tight_corners|当該コース形状のtight corners|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|103|course_up_down_transition_sentence_count|当該コース形状のup down transition sentence count|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|0.0|0.0||
|104|course_geometry_fit|当該コース形状のgeometry fit|入力行のcourse_*列をgeometry_valueで数値化。欠損は0.0。|当該レース|N/A|3489.358896255493|44.0||
## Course / Surface

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|186|racecourse_中京|競馬場カテゴリが『中京』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|40.18939971923828|1.0||
|187|racecourse_中山|競馬場カテゴリが『中山』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|188|racecourse_京都|競馬場カテゴリが『京都』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|189|racecourse_函館|競馬場カテゴリが『函館』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|190|racecourse_小倉|競馬場カテゴリが『小倉』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|191|racecourse_新潟|競馬場カテゴリが『新潟』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|551.2570934295654|12.0||
|192|racecourse_札幌|競馬場カテゴリが『札幌』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|171.69259643554688|5.0||
|193|racecourse_東京|競馬場カテゴリが『東京』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|36.26530075073242|1.0||
|194|racecourse_福島|競馬場カテゴリが『福島』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|493.21120262145996|10.0||
|195|racecourse_阪神|競馬場カテゴリが『阪神』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|196|racecourse_nan|競馬場カテゴリが『nan』であることを表す0/1列|元のカテゴリ列 racecourse を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|197|surface_芝|芝・ダート等の馬場種別が『芝』であることを表す0/1列|元のカテゴリ列 surface を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|198|surface_nan|芝・ダート等の馬場種別が『nan』であることを表す0/1列|元のカテゴリ列 surface を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
## Distance

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|29|last1_distance|対象馬の前走における distance|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|2302.6512126922607|39.0||
|30|last2_distance|対象馬の前々走における distance|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|208.28559684753418|5.0||
|31|last3_distance|対象馬の3走前における distance|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|88.91990280151367|2.0||
|32|current_distance|当該レースの距離|race_Kyori/Kyori または同一レース行数を使用。|当該レース|UNKNOWN|3081.3933181762695|66.0||
## Historical Performance

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|1|career_races|対象馬の予測レース時点までの通算races|馬ごとのstats（対象日以前に履歴へ反映済みの結果）を集計。率は分子/通算レース数、履歴なしは0.0。|全過去走（実装上履歴dequeは最大5走）|YES|12791.86939048767|113.0||
|2|career_wins|対象馬の予測レース時点までの通算wins|馬ごとのstats（対象日以前に履歴へ反映済みの結果）を集計。率は分子/通算レース数、履歴なしは0.0。|全過去走（実装上履歴dequeは最大5走）|YES|465.2116947174072|6.0||
|3|career_win_rate|対象馬の予測レース時点までの通算win rate|馬ごとのstats（対象日以前に履歴へ反映済みの結果）を集計。率は分子/通算レース数、履歴なしは0.0。|全過去走（実装上履歴dequeは最大5走）|YES|3168.4807891845703|52.0||
|4|career_places|対象馬の予測レース時点までの通算places|馬ごとのstats（対象日以前に履歴へ反映済みの結果）を集計。率は分子/通算レース数、履歴なしは0.0。|全過去走（実装上履歴dequeは最大5走）|YES|90.23629760742188|2.0||
|5|career_place_rate|対象馬の予測レース時点までの通算place rate|馬ごとのstats（対象日以前に履歴へ反映済みの結果）を集計。率は分子/通算レース数、履歴なしは0.0。|全過去走（実装上履歴dequeは最大5走）|YES|30999.513242721558|75.0||
|6|recent3_win_rate|直近3走における対象馬のwin rate|履歴から直近3走を取り出し、win/placeの平均。履歴不足は存在分のみで平均し、履歴なしは0.0。|直近3走|YES|798.2856025695801|16.0||
|7|recent3_place_rate|直近3走における対象馬のplace rate|履歴から直近3走を取り出し、win/placeの平均。履歴不足は存在分のみで平均し、履歴なしは0.0。|直近3走|YES|11593.966796875|8.0||
|8|recent5_win_rate|直近5走における対象馬のwin rate|履歴から直近5走を取り出し、win/placeの平均。履歴不足は存在分のみで平均し、履歴なしは0.0。|直近5走|YES|182.05170059204102|5.0||
|9|recent5_place_rate|直近5走における対象馬のplace rate|履歴から直近5走を取り出し、win/placeの平均。履歴不足は存在分のみで平均し、履歴なしは0.0。|直近5走|YES|34211.70217514038|22.0||
|10|races_last_180d|予測日から過去180日以内の出走回数|履歴に保持した過去レース日付を予測日との差で数える。|過去180日|YES|2301.498794555664|39.0||
|11|races_last_365d|予測日から過去365日以内の出走回数|履歴に保持した過去レース日付を予測日との差で数える。|過去365日|YES|66.11549949645996|3.0||
## Jockey

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|135|jockey_rides|予測時点までの騎手履歴に基づくjockey rides|jockey_stateを日付単位で更新し、率は平滑化（分子+1)/(騎乗数+5)。added valueは履歴平均。|騎手の過去全履歴（recentは最大30件）|N/A|0.0|0.0||
|136|jockey_win_rate|予測時点までの騎手履歴に基づくjockey win rate|jockey_stateを日付単位で更新し、率は平滑化（分子+1)/(騎乗数+5)。added valueは履歴平均。|騎手の過去全履歴（recentは最大30件）|N/A|14175.206993103027|62.0||
|137|jockey_top2_rate|予測時点までの騎手履歴に基づくjockey top2 rate|jockey_stateを日付単位で更新し、率は平滑化（分子+1)/(騎乗数+5)。added valueは履歴平均。|騎手の過去全履歴（recentは最大30件）|N/A|28523.781249046326|72.0||
|138|jockey_place_rate|予測時点までの騎手履歴に基づくjockey place rate|jockey_stateを日付単位で更新し、率は平滑化（分子+1)/(騎乗数+5)。added valueは履歴平均。|騎手の過去全履歴（recentは最大30件）|N/A|46154.71141242981|115.0||
|139|jockey_added_value|予測時点までの騎手履歴に基づくjockey added value|jockey_stateを日付単位で更新し、率は平滑化（分子+1)/(騎乗数+5)。added valueは履歴平均。|騎手の過去全履歴（recentは最大30件）|N/A|1672.4772968292236|27.0||
|140|recent_jockey_added_value|予測時点までの騎手履歴に基づくrecent jockey added value|jockey_stateを日付単位で更新し、率は平滑化（分子+1)/(騎乗数+5)。added valueは履歴平均。|騎手の過去全履歴（recentは最大30件）|N/A|415.50339698791504|13.0||
|141|jockey_form_trend|騎手のフォーム変化または乗替効果を表す想定の列（現コードでは常に0.0）|build_v1_features内で0.0を代入。履歴集計や乗替計算は行っていない。|N/A|N/A|0.0|0.0||
|142|jockey_change_added_value|騎手のフォーム変化または乗替効果を表す想定の列（現コードでは常に0.0）|build_v1_features内で0.0を代入。履歴集計や乗替計算は行っていない。|N/A|N/A|0.0|0.0||
## Opponent / Winner Strength

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|21|last1_winner_strength|対象馬の直近3走についてlast1 winner strengthを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|90.80509948730469|1.0||
|22|last2_winner_strength|対象馬の直近3走についてlast2 winner strengthを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|23|last3_winner_strength|対象馬の直近3走についてlast3 winner strengthを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|17.844499588012695|1.0||
|24|last1_field_strength|対象馬の直近3走についてlast1 field strengthを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|197.92109870910645|6.0||
|25|last2_field_strength|対象馬の直近3走についてlast2 field strengthを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|29.57110023498535|1.0||
|26|last3_field_strength|対象馬の直近3走についてlast3 field strengthを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|377.1798973083496|6.0||
|34|last1_winner_strength_v2|対象馬の直近3走についてlast1 winner strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|17.126100540161133|1.0||
|35|last2_winner_strength_v2|対象馬の直近3走についてlast2 winner strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|28.200300216674805|1.0||
|36|last3_winner_strength_v2|対象馬の直近3走についてlast3 winner strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|69.08539962768555|3.0||
|37|last1_field_strength_v2|対象馬の直近3走についてlast1 field strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|592.1326007843018|9.0||
|38|last2_field_strength_v2|対象馬の直近3走についてlast2 field strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|398.95190238952637|9.0||
|39|last3_field_strength_v2|対象馬の直近3走についてlast3 field strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|240.76190662384033|5.0||
|43|max_winner_strength_last3|対象馬の直近3走についてmax winner strength last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|44|mean_winner_strength_last3|対象馬の直近3走についてmean winner strength last3を集約した値|直近3走の履歴値を対象に平均。履歴不足時は空配列の既定値0.0。|直近3走|YES|276.39050102233887|6.0||
|45|weighted_winner_strength_last3|対象馬の直近3走についてweighted winner strength last3を集約した値|直近3走の履歴値を対象に重み付き平均（0.5,0.3,0.2）。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|53|opponent_history_missing_last3|対象馬の直近3走についてopponent history missing last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|54|last1_winner_max_race_class_before_target|対象馬の前走における winner max race class before target|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|55|last2_winner_max_race_class_before_target|対象馬の前々走における winner max race class before target|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|56|last3_winner_max_race_class_before_target|対象馬の3走前における winner max race class before target|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|57|last1_winner_best_win_class_before_target|対象馬の直近3走についてlast1 winner best win class before targetを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|58|last2_winner_best_win_class_before_target|対象馬の直近3走についてlast2 winner best win class before targetを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|59|last3_winner_best_win_class_before_target|対象馬の直近3走についてlast3 winner best win class before targetを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|60|last1_winner_max_prize_before_target|対象馬の前走における winner max prize before target|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|61|last2_winner_max_prize_before_target|対象馬の前々走における winner max prize before target|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|16.16659927368164|1.0||
|62|last3_winner_max_prize_before_target|対象馬の3走前における winner max prize before target|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|63|last1_winner_mean_prize_before_target|対象馬の前走における winner mean prize before target|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|11.805999755859375|1.0||
|64|last2_winner_mean_prize_before_target|対象馬の前々走における winner mean prize before target|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|65|last3_winner_mean_prize_before_target|対象馬の3走前における winner mean prize before target|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|19.326799392700195|1.0||
## Other

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|47|last1_field_max_strength_v2|対象馬の直近3走についてlast1 field max strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|28.369699478149414|1.0||
|48|last2_field_max_strength_v2|対象馬の直近3走についてlast2 field max strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|74.66485118865967|3.0||
|49|last3_field_max_strength_v2|対象馬の直近3走についてlast3 field max strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|44.51259994506836|3.0||
|50|last1_field_top3_mean_strength_v2|対象馬の直近3走についてlast1 field top3 mean strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|1820.2678899765015|38.0||
|51|last2_field_top3_mean_strength_v2|対象馬の直近3走についてlast2 field top3 mean strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|718.4754981994629|17.0||
|52|last3_field_top3_mean_strength_v2|対象馬の直近3走についてlast3 field top3 mean strength v2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|1118.5353031158447|19.0||
|157|last1_is_filly_mare_only|対象馬の前走における is filly mare only|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|158|last2_is_filly_mare_only|対象馬の前々走における is filly mare only|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|159|last3_is_filly_mare_only|対象馬の3走前における is filly mare only|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|161|female_only_to_open|当該レース条件のfemale only to open|race_conditionsのクラス・性別・年齢判定と、前走条件との差分。|当該レース＋前走|UNKNOWN|0.0|0.0||
|162|open_to_female_only|当該レース条件のopen to female only|race_conditionsのクラス・性別・年齢判定と、前走条件との差分。|当該レース＋前走|UNKNOWN|0.0|0.0||
|163|age_condition_change|当該レース条件のage condition change|race_conditionsのクラス・性別・年齢判定と、前走条件との差分。|当該レース＋前走|UNKNOWN|0.0|0.0||
|254|last1_class_unknown|対象馬の直近3走についてlast1 class unknownを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|255|last1_class_nan|対象馬の直近3走についてlast1 class nanを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|293|last2_class_unknown|対象馬の直近3走についてlast2 class unknownを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|294|last2_class_nan|対象馬の直近3走についてlast2 class nanを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|332|last3_class_unknown|対象馬の直近3走についてlast3 class unknownを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|333|last3_class_nan|対象馬の直近3走についてlast3 class nanを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
## Pace / Position

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|86|race_position_bias_last1|対象馬の直近3走についてrace position bias last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|87|race_position_bias_last2|対象馬の直近3走についてrace position bias last2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|88|race_position_bias_last3|対象馬の直近3走についてrace position bias last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|105|horse_expected_position|対象馬のhorse expected position|対象馬の履歴から平均・標準偏差、または同一geometryのadjusted performance平均を計算。履歴なしは0.0/0.5。|全保持履歴（最大5走）|YES|4428.836008071899|67.0||
|106|position_stability|対象馬のposition stability|対象馬の履歴から平均・標準偏差、または同一geometryのadjusted performance平均を計算。履歴なしは0.0/0.5。|全保持履歴（最大5走）|YES|0.0|0.0||
|107|frontness_mean|対象馬のfrontness mean|対象馬の履歴から平均・標準偏差、または同一geometryのadjusted performance平均を計算。履歴なしは0.0/0.5。|全保持履歴（最大5走）|UNKNOWN|0.0|0.0||
|108|frontness_std|対象馬のfrontness std|対象馬の履歴から平均・標準偏差、または同一geometryのadjusted performance平均を計算。履歴なしは0.0/0.5。|全保持履歴（最大5走）|UNKNOWN|0.0|0.0||
|109|front_density|当該レースの展開・位置取り構成を表すfront density|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|UNKNOWN|44.69420051574707|3.0||
|110|forward_density|当該レースの展開・位置取り構成を表すforward density|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|UNKNOWN|30.889500617980957|2.0||
|111|mid_density|当該レースの展開・位置取り構成を表すmid density|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|UNKNOWN|0.0|0.0||
|112|rear_density|当該レースの展開・位置取り構成を表すrear density|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|UNKNOWN|119.956298828125|3.0||
|113|expected_front_count|当該レースの展開・位置取り構成を表すexpected front count|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|UNKNOWN|204.2671012878418|5.0||
|114|expected_position_mean|当該レースの展開・位置取り構成を表すexpected position mean|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|YES|1238.6014022827148|30.0||
|115|expected_position_std|当該レースの展開・位置取り構成を表すexpected position std|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|YES|1134.1587982177734|15.0||
|116|gate_position_pct|コード上の特徴量 gate_position_pct|build_v1_featuresのvalues辞書から取得（詳細式は該当ブロックを参照）。|当該レースまたは過去履歴（名称から一意に確定不可）|YES|333.2567014694214|11.0||
|117|gate_x_expected_position|コード上の特徴量 gate_x_expected_position|build_v1_featuresのvalues辞書から取得（詳細式は該当ブロックを参照）。|当該レースまたは過去履歴（名称から一意に確定不可）|YES|449.9027099609375|12.0||
|118|position_bias_top5_v2|当該レースの展開・位置取り構成を表すposition bias top5 v2|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|YES|0.0|0.0||
|119|position_bias_top6_v2|当該レースの展開・位置取り構成を表すposition bias top6 v2|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|YES|392.7903995513916|8.0||
|120|position_bias_weighted_top6_v2|当該レースの展開・位置取り構成を表すposition bias weighted top6 v2|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|YES|6376.527627944946|81.0||
|121|position_bias_residual_v2|当該レースの展開・位置取り構成を表すposition bias residual v2|同一レース出走馬の過去位置取りからfrontnessを作り、平均・密度・上位入線馬との差を計算。|当該レース＋各馬の保持履歴|YES|5365.676523208618|90.0||
## Race Class / Strength

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|143|race_class_score|レース格に関するrace class score|race_conditionsでクラス名をラベル/スコア化（未勝利=0、未知は賞金fallback）。直近値は過去条件を集約。|当該レースまたは直近3走/過去勝利履歴|YES|224.0547981262207|3.0||
|144|current_race_class_score|レース格に関するcurrent race class score|race_conditionsでクラス名をラベル/スコア化（未勝利=0、未知は賞金fallback）。直近値は過去条件を集約。|当該レースまたは直近3走/過去勝利履歴|YES|0.0|0.0||
|145|last1_race_class_score|前走のレース格が『score』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|146|last2_race_class_score|前々走のレース格が『score』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|147|last3_race_class_score|3走前のレース格が『score』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|148|max_race_class_last3|対象馬の直近3走についてmax race class last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|149|mean_race_class_last3|対象馬の直近3走についてmean race class last3を集約した値|直近3走の履歴値を対象に平均。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|150|weighted_race_class_last3|対象馬の直近3走についてweighted race class last3を集約した値|直近3走の履歴値を対象に重み付き平均（0.5,0.3,0.2）。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|160|race_class_change|レース格に関するrace class change|race_conditionsでクラス名をラベル/スコア化（未勝利=0、未知は賞金fallback）。直近値は過去条件を集約。|当該レースまたは直近3走/過去勝利履歴|YES|33.755300521850586|2.0||
|164|race_first_prize|当該レースまたは直近3走・勝者履歴の賞金に関するrace first prize|race_Honsyokin0-4を円換算し、log1p・平均・最大・比率・差分などを計算。比率のゼロ除算は1.0。|当該レース／直近3走／勝者の対象レース以前の履歴|YES|7727.232168197632|54.0||
|165|race_second_prize|当該レースまたは直近3走・勝者履歴の賞金に関するrace second prize|race_Honsyokin0-4を円換算し、log1p・平均・最大・比率・差分などを計算。比率のゼロ除算は1.0。|当該レース／直近3走／勝者の対象レース以前の履歴|YES|0.0|0.0||
|166|race_third_prize|当該レースまたは直近3走・勝者履歴の賞金に関するrace third prize|race_Honsyokin0-4を円換算し、log1p・平均・最大・比率・差分などを計算。比率のゼロ除算は1.0。|当該レース／直近3走／勝者の対象レース以前の履歴|YES|803.9788904190063|10.0||
|167|race_total_top5_prize|当該レースまたは直近3走・勝者履歴の賞金に関するrace total top5 prize|race_Honsyokin0-4を円換算し、log1p・平均・最大・比率・差分などを計算。比率のゼロ除算は1.0。|当該レース／直近3走／勝者の対象レース以前の履歴|YES|356.53829765319824|5.0||
|168|race_first_prize_log|当該レースまたは直近3走・勝者履歴の賞金に関するrace first prize log|race_Honsyokin0-4を円換算し、log1p・平均・最大・比率・差分などを計算。比率のゼロ除算は1.0。|当該レース／直近3走／勝者の対象レース以前の履歴|YES|0.0|0.0||
|169|race_total_top5_prize_log|当該レースまたは直近3走・勝者履歴の賞金に関するrace total top5 prize log|race_Honsyokin0-4を円換算し、log1p・平均・最大・比率・差分などを計算。比率のゼロ除算は1.0。|当該レース／直近3走／勝者の対象レース以前の履歴|YES|0.0|0.0||
|170|last1_race_first_prize|対象馬の前走における race first prize|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|767.4922924041748|12.0||
|171|last2_race_first_prize|対象馬の前々走における race first prize|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|26.01849937438965|1.0||
|172|last3_race_first_prize|対象馬の3走前における race first prize|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|16.617900848388672|1.0||
|173|last1_race_first_prize_log|対象馬の前走における race first prize log|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|174|last2_race_first_prize_log|対象馬の前々走における race first prize log|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|175|last3_race_first_prize_log|対象馬の3走前における race first prize log|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|176|max_race_prize_last3|対象馬の直近3走についてmax race prize last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|94.66680145263672|2.0||
|177|mean_race_prize_last3|対象馬の直近3走についてmean race prize last3を集約した値|直近3走の履歴値を対象に平均。履歴不足時は空配列の既定値0.0。|直近3走|YES|211.8724946975708|5.0||
|178|weighted_race_prize_last3|対象馬の直近3走についてweighted race prize last3を集約した値|直近3走の履歴値を対象に重み付き平均（0.5,0.3,0.2）。履歴不足時は空配列の既定値0.0。|直近3走|YES|259.5249996185303|6.0||
|179|prize_change_from_last1|対象馬の直近3走についてprize change from last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|5713.745090484619|12.0||
|180|prize_change_from_last3_mean|対象馬の直近3走についてprize change from last3 meanを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|17647.1319065094|64.0||
|181|prize_ratio_vs_last1|対象馬の直近3走についてprize ratio vs last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|6486.998893737793|34.0||
|182|prize_ratio_vs_last3_mean|対象馬の直近3走についてprize ratio vs last3 meanを集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|15488.502010345459|147.0||
|199|grade_code_A|グレード区分が『A』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|200|grade_code_B|グレード区分が『B』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|201|grade_code_C|グレード区分が『C』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|202|grade_code_D|グレード区分が『D』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|203|grade_code_E|グレード区分が『E』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|204|grade_code_F|グレード区分が『F』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|205|grade_code_G|グレード区分が『G』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|206|grade_code_H|グレード区分が『H』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|207|grade_code_L|グレード区分が『L』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|208|grade_code_unknown|グレード区分が『unknown』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|209|grade_code_nan|グレード区分が『nan』であることを表す0/1列|元のカテゴリ列 grade_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|217|last1_class_grade:A\|condition:11|前走のグレード×条件コードが『A\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|218|last1_class_grade:A\|condition:12|前走のグレード×条件コードが『A\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|219|last1_class_grade:A\|condition:13|前走のグレード×条件コードが『A\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|220|last1_class_grade:A\|condition:14|前走のグレード×条件コードが『A\|condition:14』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|221|last1_class_grade:B\|condition:11|前走のグレード×条件コードが『B\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|222|last1_class_grade:B\|condition:12|前走のグレード×条件コードが『B\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|223|last1_class_grade:B\|condition:13|前走のグレード×条件コードが『B\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|224|last1_class_grade:B\|condition:14|前走のグレード×条件コードが『B\|condition:14』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|225|last1_class_grade:C\|condition:11|前走のグレード×条件コードが『C\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|226|last1_class_grade:C\|condition:12|前走のグレード×条件コードが『C\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|227|last1_class_grade:C\|condition:13|前走のグレード×条件コードが『C\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|228|last1_class_grade:C\|condition:14|前走のグレード×条件コードが『C\|condition:14』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|229|last1_class_grade:D\|condition:11|前走のグレード×条件コードが『D\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|230|last1_class_grade:D\|condition:12|前走のグレード×条件コードが『D\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|231|last1_class_grade:D\|condition:13|前走のグレード×条件コードが『D\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|232|last1_class_grade:E\|condition:11|前走のグレード×条件コードが『E\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|347.54460525512695|10.0||
|233|last1_class_grade:E\|condition:12|前走のグレード×条件コードが『E\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|234|last1_class_grade:E\|condition:13|前走のグレード×条件コードが『E\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|235|last1_class_grade:E\|condition:14|前走のグレード×条件コードが『E\|condition:14』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|236|last1_class_grade:E\|condition:18|前走のグレード×条件コードが『E\|condition:18』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|237|last1_class_grade:E\|condition:19|前走のグレード×条件コードが『E\|condition:19』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|238|last1_class_grade:F\|condition:18|前走のグレード×条件コードが『F\|condition:18』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|239|last1_class_grade:F\|condition:19|前走のグレード×条件コードが『F\|condition:19』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|240|last1_class_grade:G\|condition:18|前走のグレード×条件コードが『G\|condition:18』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|241|last1_class_grade:G\|condition:19|前走のグレード×条件コードが『G\|condition:19』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|242|last1_class_grade:H\|condition:18|前走のグレード×条件コードが『H\|condition:18』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|243|last1_class_grade:H\|condition:19|前走のグレード×条件コードが『H\|condition:19』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|244|last1_class_grade:L\|condition:11|前走のグレード×条件コードが『L\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|245|last1_class_grade:L\|condition:12|前走のグレード×条件コードが『L\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|246|last1_class_grade:L\|condition:13|前走のグレード×条件コードが『L\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|247|last1_class_grade:L\|condition:14|前走のグレード×条件コードが『L\|condition:14』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|248|last1_class_grade:unknown\|condition:11|前走のグレード×条件コードが『unknown\|condition:11』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|249|last1_class_grade:unknown\|condition:12|前走のグレード×条件コードが『unknown\|condition:12』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|250|last1_class_grade:unknown\|condition:13|前走のグレード×条件コードが『unknown\|condition:13』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|71.50950241088867|2.0||
|251|last1_class_grade:unknown\|condition:14|前走のグレード×条件コードが『unknown\|condition:14』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|252|last1_class_grade:unknown\|condition:18|前走のグレード×条件コードが『unknown\|condition:18』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|253|last1_class_grade:unknown\|condition:19|前走のグレード×条件コードが『unknown\|condition:19』であることを表す0/1列|元のカテゴリ列 last1_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|256|last2_class_grade:A\|condition:11|前々走のグレード×条件コードが『A\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|257|last2_class_grade:A\|condition:12|前々走のグレード×条件コードが『A\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|258|last2_class_grade:A\|condition:13|前々走のグレード×条件コードが『A\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|259|last2_class_grade:A\|condition:14|前々走のグレード×条件コードが『A\|condition:14』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|260|last2_class_grade:B\|condition:11|前々走のグレード×条件コードが『B\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|261|last2_class_grade:B\|condition:12|前々走のグレード×条件コードが『B\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|262|last2_class_grade:B\|condition:13|前々走のグレード×条件コードが『B\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|263|last2_class_grade:B\|condition:14|前々走のグレード×条件コードが『B\|condition:14』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|264|last2_class_grade:C\|condition:11|前々走のグレード×条件コードが『C\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|265|last2_class_grade:C\|condition:12|前々走のグレード×条件コードが『C\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|266|last2_class_grade:C\|condition:13|前々走のグレード×条件コードが『C\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|267|last2_class_grade:C\|condition:14|前々走のグレード×条件コードが『C\|condition:14』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|268|last2_class_grade:D\|condition:11|前々走のグレード×条件コードが『D\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|269|last2_class_grade:D\|condition:12|前々走のグレード×条件コードが『D\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|270|last2_class_grade:D\|condition:13|前々走のグレード×条件コードが『D\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|271|last2_class_grade:E\|condition:11|前々走のグレード×条件コードが『E\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|14.2524995803833|1.0||
|272|last2_class_grade:E\|condition:12|前々走のグレード×条件コードが『E\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|273|last2_class_grade:E\|condition:13|前々走のグレード×条件コードが『E\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|274|last2_class_grade:E\|condition:14|前々走のグレード×条件コードが『E\|condition:14』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|275|last2_class_grade:E\|condition:18|前々走のグレード×条件コードが『E\|condition:18』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|276|last2_class_grade:E\|condition:19|前々走のグレード×条件コードが『E\|condition:19』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|277|last2_class_grade:F\|condition:18|前々走のグレード×条件コードが『F\|condition:18』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|278|last2_class_grade:F\|condition:19|前々走のグレード×条件コードが『F\|condition:19』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|279|last2_class_grade:G\|condition:18|前々走のグレード×条件コードが『G\|condition:18』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|280|last2_class_grade:G\|condition:19|前々走のグレード×条件コードが『G\|condition:19』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|281|last2_class_grade:H\|condition:18|前々走のグレード×条件コードが『H\|condition:18』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|282|last2_class_grade:H\|condition:19|前々走のグレード×条件コードが『H\|condition:19』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|283|last2_class_grade:L\|condition:11|前々走のグレード×条件コードが『L\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|284|last2_class_grade:L\|condition:12|前々走のグレード×条件コードが『L\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|285|last2_class_grade:L\|condition:13|前々走のグレード×条件コードが『L\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|286|last2_class_grade:L\|condition:14|前々走のグレード×条件コードが『L\|condition:14』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|287|last2_class_grade:unknown\|condition:11|前々走のグレード×条件コードが『unknown\|condition:11』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|112.82760047912598|5.0||
|288|last2_class_grade:unknown\|condition:12|前々走のグレード×条件コードが『unknown\|condition:12』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|289|last2_class_grade:unknown\|condition:13|前々走のグレード×条件コードが『unknown\|condition:13』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|290|last2_class_grade:unknown\|condition:14|前々走のグレード×条件コードが『unknown\|condition:14』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|60.59859848022461|1.0||
|291|last2_class_grade:unknown\|condition:18|前々走のグレード×条件コードが『unknown\|condition:18』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|292|last2_class_grade:unknown\|condition:19|前々走のグレード×条件コードが『unknown\|condition:19』であることを表す0/1列|元のカテゴリ列 last2_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|295|last3_class_grade:A\|condition:11|3走前のグレード×条件コードが『A\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|296|last3_class_grade:A\|condition:12|3走前のグレード×条件コードが『A\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|297|last3_class_grade:A\|condition:13|3走前のグレード×条件コードが『A\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|298|last3_class_grade:A\|condition:14|3走前のグレード×条件コードが『A\|condition:14』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|299|last3_class_grade:B\|condition:11|3走前のグレード×条件コードが『B\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|300|last3_class_grade:B\|condition:12|3走前のグレード×条件コードが『B\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|301|last3_class_grade:B\|condition:13|3走前のグレード×条件コードが『B\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|302|last3_class_grade:B\|condition:14|3走前のグレード×条件コードが『B\|condition:14』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|303|last3_class_grade:C\|condition:11|3走前のグレード×条件コードが『C\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|304|last3_class_grade:C\|condition:12|3走前のグレード×条件コードが『C\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|305|last3_class_grade:C\|condition:13|3走前のグレード×条件コードが『C\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|306|last3_class_grade:C\|condition:14|3走前のグレード×条件コードが『C\|condition:14』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|307|last3_class_grade:D\|condition:11|3走前のグレード×条件コードが『D\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|308|last3_class_grade:D\|condition:12|3走前のグレード×条件コードが『D\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|309|last3_class_grade:D\|condition:13|3走前のグレード×条件コードが『D\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|310|last3_class_grade:E\|condition:11|3走前のグレード×条件コードが『E\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|311|last3_class_grade:E\|condition:12|3走前のグレード×条件コードが『E\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|312|last3_class_grade:E\|condition:13|3走前のグレード×条件コードが『E\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|313|last3_class_grade:E\|condition:14|3走前のグレード×条件コードが『E\|condition:14』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|314|last3_class_grade:E\|condition:18|3走前のグレード×条件コードが『E\|condition:18』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|315|last3_class_grade:E\|condition:19|3走前のグレード×条件コードが『E\|condition:19』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|316|last3_class_grade:F\|condition:18|3走前のグレード×条件コードが『F\|condition:18』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|317|last3_class_grade:F\|condition:19|3走前のグレード×条件コードが『F\|condition:19』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|318|last3_class_grade:G\|condition:18|3走前のグレード×条件コードが『G\|condition:18』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|319|last3_class_grade:G\|condition:19|3走前のグレード×条件コードが『G\|condition:19』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|320|last3_class_grade:H\|condition:18|3走前のグレード×条件コードが『H\|condition:18』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|321|last3_class_grade:H\|condition:19|3走前のグレード×条件コードが『H\|condition:19』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|322|last3_class_grade:L\|condition:11|3走前のグレード×条件コードが『L\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|323|last3_class_grade:L\|condition:12|3走前のグレード×条件コードが『L\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|324|last3_class_grade:L\|condition:13|3走前のグレード×条件コードが『L\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|325|last3_class_grade:L\|condition:14|3走前のグレード×条件コードが『L\|condition:14』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|326|last3_class_grade:unknown\|condition:11|3走前のグレード×条件コードが『unknown\|condition:11』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|327|last3_class_grade:unknown\|condition:12|3走前のグレード×条件コードが『unknown\|condition:12』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|328|last3_class_grade:unknown\|condition:13|3走前のグレード×条件コードが『unknown\|condition:13』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|329|last3_class_grade:unknown\|condition:14|3走前のグレード×条件コードが『unknown\|condition:14』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|140.95549964904785|4.0||
|330|last3_class_grade:unknown\|condition:18|3走前のグレード×条件コードが『unknown\|condition:18』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|331|last3_class_grade:unknown\|condition:19|3走前のグレード×条件コードが『unknown\|condition:19』であることを表す0/1列|元のカテゴリ列 last3_class_grade を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|334|race_class_label_G1|当該レースの格ラベルが『G1』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|335|race_class_label_G2|当該レースの格ラベルが『G2』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|336|race_class_label_G3|当該レースの格ラベルが『G3』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|337|race_class_label_LISTED|当該レースの格ラベルが『LISTED』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|338|race_class_label_OPEN|当該レースの格ラベルが『OPEN』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|339|race_class_label_UNKNOWN|当該レースの格ラベルが『UNKNOWN』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|340|race_class_label_nan|当該レースの格ラベルが『nan』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|341|race_class_label_G1|当該レースの格ラベルが『G1』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|342|race_class_label_G2|当該レースの格ラベルが『G2』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|343|race_class_label_G3|当該レースの格ラベルが『G3』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|344|race_class_label_LISTED|当該レースの格ラベルが『LISTED』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|345|race_class_label_OPEN|当該レースの格ラベルが『OPEN』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|346|race_class_label_UNKNOWN|当該レースの格ラベルが『UNKNOWN』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|347|race_class_label_nan|当該レースの格ラベルが『nan』であることを表す0/1列|元のカテゴリ列 race_class_label を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|348|last1_race_class_G1|前走のレース格が『G1』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|349|last1_race_class_G2|前走のレース格が『G2』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|350|last1_race_class_G3|前走のレース格が『G3』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|351|last1_race_class_LISTED|前走のレース格が『LISTED』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|352|last1_race_class_OPEN|前走のレース格が『OPEN』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|353|last1_race_class_UNKNOWN|前走のレース格が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|354|last1_race_class_nan|前走のレース格が『nan』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|355|last1_race_class_G1|前走のレース格が『G1』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|356|last1_race_class_G2|前走のレース格が『G2』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|357|last1_race_class_G3|前走のレース格が『G3』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|358|last1_race_class_LISTED|前走のレース格が『LISTED』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|359|last1_race_class_OPEN|前走のレース格が『OPEN』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|360|last1_race_class_UNKNOWN|前走のレース格が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|361|last1_race_class_nan|前走のレース格が『nan』であることを表す0/1列|元のカテゴリ列 last1_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|362|last2_race_class_G1|前々走のレース格が『G1』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|363|last2_race_class_G2|前々走のレース格が『G2』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|364|last2_race_class_G3|前々走のレース格が『G3』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|365|last2_race_class_LISTED|前々走のレース格が『LISTED』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|366|last2_race_class_OPEN|前々走のレース格が『OPEN』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|367|last2_race_class_UNKNOWN|前々走のレース格が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|368|last2_race_class_nan|前々走のレース格が『nan』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|369|last2_race_class_G1|前々走のレース格が『G1』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|370|last2_race_class_G2|前々走のレース格が『G2』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|371|last2_race_class_G3|前々走のレース格が『G3』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|372|last2_race_class_LISTED|前々走のレース格が『LISTED』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|373|last2_race_class_OPEN|前々走のレース格が『OPEN』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|374|last2_race_class_UNKNOWN|前々走のレース格が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|375|last2_race_class_nan|前々走のレース格が『nan』であることを表す0/1列|元のカテゴリ列 last2_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|376|last3_race_class_G1|3走前のレース格が『G1』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|377|last3_race_class_G2|3走前のレース格が『G2』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|378|last3_race_class_G3|3走前のレース格が『G3』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|379|last3_race_class_LISTED|3走前のレース格が『LISTED』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|380|last3_race_class_OPEN|3走前のレース格が『OPEN』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|381|last3_race_class_UNKNOWN|3走前のレース格が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|382|last3_race_class_nan|3走前のレース格が『nan』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|383|last3_race_class_G1|3走前のレース格が『G1』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|384|last3_race_class_G2|3走前のレース格が『G2』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|385|last3_race_class_G3|3走前のレース格が『G3』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|386|last3_race_class_LISTED|3走前のレース格が『LISTED』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|387|last3_race_class_OPEN|3走前のレース格が『OPEN』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|388|last3_race_class_UNKNOWN|3走前のレース格が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|389|last3_race_class_nan|3走前のレース格が『nan』であることを表す0/1列|元のカテゴリ列 last3_race_class を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
## Race Composition

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|33|field_size|当該レースの出走頭数|race_Kyori/Kyori または同一レース行数を使用。|当該レース|N/A|16500.95827293396|131.0||
|154|is_filly_mare_only|当該レース条件のis filly mare only|race_conditionsのクラス・性別・年齢判定と、前走条件との差分。|当該レース＋前走|UNKNOWN|0.0|0.0||
|155|is_2yo_only|当該レース条件のis 2yo only|race_conditionsのクラス・性別・年齢判定と、前走条件との差分。|当該レース＋前走|UNKNOWN|0.0|0.0||
|156|is_3yo_only|当該レース条件のis 3yo only|race_conditionsのクラス・性別・年齢判定と、前走条件との差分。|当該レース＋前走|UNKNOWN|0.0|0.0||
|210|condition_code_11|レース条件コードが『11』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|211|condition_code_12|レース条件コードが『12』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|563.9949054718018|11.0||
|212|condition_code_13|レース条件コードが『13』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|1203.2485065460205|17.0||
|213|condition_code_14|レース条件コードが『14』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|65.56189918518066|2.0||
|214|condition_code_18|レース条件コードが『18』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|215|condition_code_19|レース条件コードが『19』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|216|condition_code_nan|レース条件コードが『nan』であることを表す0/1列|元のカテゴリ列 condition_code を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|390|race_sex_condition_FEMALE_ONLY|当該レースの性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 race_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|391|race_sex_condition_OPEN_SEX|当該レースの性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 race_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|392|race_sex_condition_nan|当該レースの性別条件が『nan』であることを表す0/1列|元のカテゴリ列 race_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|393|race_sex_condition_FEMALE_ONLY|当該レースの性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 race_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|394|race_sex_condition_OPEN_SEX|当該レースの性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 race_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|395|race_sex_condition_nan|当該レースの性別条件が『nan』であることを表す0/1列|元のカテゴリ列 race_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|396|race_age_condition_TWO_YEAR_OLD_ONLY|当該レースの年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 race_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|397|race_age_condition_UNKNOWN|当該レースの年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 race_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|398|race_age_condition_nan|当該レースの年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 race_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|399|race_age_condition_TWO_YEAR_OLD_ONLY|当該レースの年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 race_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|400|race_age_condition_UNKNOWN|当該レースの年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 race_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|401|race_age_condition_nan|当該レースの年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 race_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|402|last1_sex_condition_FEMALE_ONLY|前走の性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|403|last1_sex_condition_OPEN_SEX|前走の性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|404|last1_sex_condition_UNKNOWN|前走の性別条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|405|last1_sex_condition_nan|前走の性別条件が『nan』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|406|last1_sex_condition_FEMALE_ONLY|前走の性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|407|last1_sex_condition_OPEN_SEX|前走の性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|408|last1_sex_condition_UNKNOWN|前走の性別条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|409|last1_sex_condition_nan|前走の性別条件が『nan』であることを表す0/1列|元のカテゴリ列 last1_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|410|last2_sex_condition_FEMALE_ONLY|前々走の性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|411|last2_sex_condition_OPEN_SEX|前々走の性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|412|last2_sex_condition_UNKNOWN|前々走の性別条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|413|last2_sex_condition_nan|前々走の性別条件が『nan』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|414|last2_sex_condition_FEMALE_ONLY|前々走の性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|415|last2_sex_condition_OPEN_SEX|前々走の性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|416|last2_sex_condition_UNKNOWN|前々走の性別条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|417|last2_sex_condition_nan|前々走の性別条件が『nan』であることを表す0/1列|元のカテゴリ列 last2_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|418|last3_sex_condition_FEMALE_ONLY|3走前の性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|419|last3_sex_condition_OPEN_SEX|3走前の性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|420|last3_sex_condition_UNKNOWN|3走前の性別条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|421|last3_sex_condition_nan|3走前の性別条件が『nan』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|422|last3_sex_condition_FEMALE_ONLY|3走前の性別条件が『FEMALE_ONLY』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|423|last3_sex_condition_OPEN_SEX|3走前の性別条件が『OPEN_SEX』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|424|last3_sex_condition_UNKNOWN|3走前の性別条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|425|last3_sex_condition_nan|3走前の性別条件が『nan』であることを表す0/1列|元のカテゴリ列 last3_sex_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|426|last1_age_condition_TWO_YEAR_OLD_ONLY|前走の年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 last1_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|427|last1_age_condition_UNKNOWN|前走の年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last1_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|428|last1_age_condition_nan|前走の年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 last1_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|429|last1_age_condition_TWO_YEAR_OLD_ONLY|前走の年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 last1_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|430|last1_age_condition_UNKNOWN|前走の年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last1_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|431|last1_age_condition_nan|前走の年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 last1_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|432|last2_age_condition_TWO_YEAR_OLD_ONLY|前々走の年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 last2_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|433|last2_age_condition_UNKNOWN|前々走の年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last2_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|434|last2_age_condition_nan|前々走の年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 last2_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|435|last2_age_condition_TWO_YEAR_OLD_ONLY|前々走の年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 last2_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|436|last2_age_condition_UNKNOWN|前々走の年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last2_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|437|last2_age_condition_nan|前々走の年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 last2_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|438|last3_age_condition_TWO_YEAR_OLD_ONLY|3走前の年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 last3_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|439|last3_age_condition_UNKNOWN|3走前の年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last3_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|440|last3_age_condition_nan|3走前の年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 last3_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|441|last3_age_condition_TWO_YEAR_OLD_ONLY|3走前の年齢条件が『TWO_YEAR_OLD_ONLY』であることを表す0/1列|元のカテゴリ列 last3_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|442|last3_age_condition_UNKNOWN|3走前の年齢条件が『UNKNOWN』であることを表す0/1列|元のカテゴリ列 last3_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
|443|last3_age_condition_nan|3走前の年齢条件が『nan』であることを表す0/1列|元のカテゴリ列 last3_age_condition を学習期間と評価月を結合した後に pandas.get_dummies(dummy_na=True) でone-hot化。|N/A|N/A|0.0|0.0||
## Recent Performance

|No|Feature|意味|計算|履歴|未勝利履歴|gain|split|判断|
|---:|---|---|---|---|---|---:|---:|---|
|12|last1_finish|対象馬の前走における finish|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|66233.60685539246|71.0||
|13|last2_finish|対象馬の前々走における finish|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|4242.764408111572|21.0||
|14|last3_finish|対象馬の3走前における finish|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|174.22560119628906|4.0||
|15|last1_margin|対象馬の前走における margin|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|118.41500091552734|4.0||
|16|last2_margin|対象馬の前々走における margin|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|17|last3_margin|対象馬の3走前における margin|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|18|best_margin_last3|対象馬の直近3走についてbest margin last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|511.73878479003906|3.0||
|19|mean_margin_last3|対象馬の直近3走についてmean margin last3を集約した値|直近3走の履歴値を対象に平均。履歴不足時は空配列の既定値0.0。|直近3走|YES|10285.308313369751|31.0||
|20|weighted_margin_last3|対象馬の直近3走についてweighted margin last3を集約した値|直近3走の履歴値を対象に重み付き平均（0.5,0.3,0.2）。履歴不足時は空配列の既定値0.0。|直近3走|YES|7361.657505989075|44.0||
|27|margin_x_winner_strength|コード上の特徴量 margin_x_winner_strength|build_v1_featuresのvalues辞書から取得（詳細式は該当ブロックを参照）。|当該レースまたは過去履歴（名称から一意に確定不可）|YES|83.40409851074219|1.0||
|28|margin_x_field_strength|コード上の特徴量 margin_x_field_strength|build_v1_featuresのvalues辞書から取得（詳細式は該当ブロックを参照）。|当該レースまたは過去履歴（名称から一意に確定不可）|YES|2127.6723985671997|22.0||
|40|last1_margin_x_winner_strength_v2|対象馬の前走における margin x winner strength v2|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|2706.604528427124|14.0||
|41|last2_margin_x_winner_strength_v2|対象馬の前々走における margin x winner strength v2|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|39.96590042114258|1.0||
|42|last3_margin_x_winner_strength_v2|対象馬の3走前における margin x winner strength v2|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|46|best_strong_opponent_performance_last3|対象馬の直近3走についてbest strong opponent performance last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|8930.00468635559|44.0||
|66|last1_raw_performance|対象馬の前走における raw performance|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|132143.1885471344|36.0||
|67|last2_raw_performance|対象馬の前々走における raw performance|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|6879.94980430603|33.0||
|68|last3_raw_performance|対象馬の3走前における raw performance|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|337.6285037994385|6.0||
|69|last1_position_advantage|対象馬の前走における position advantage|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|265.7129955291748|6.0||
|70|last2_position_advantage|対象馬の前々走における position advantage|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|869.2403936386108|26.0||
|71|last3_position_advantage|対象馬の3走前における position advantage|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|409.414005279541|12.0||
|72|last1_adjusted_performance|対象馬の前走における adjusted performance|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|2667.3683280944824|19.0||
|73|last2_adjusted_performance|対象馬の前々走における adjusted performance|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|2307.9833965301514|19.0||
|74|last3_adjusted_performance|対象馬の3走前における adjusted performance|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|210.42150497436523|3.0||
|75|best_adjusted_performance_last3|対象馬の直近3走についてbest adjusted performance last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|2727.0938720703125|21.0||
|76|mean_adjusted_performance_last3|対象馬の直近3走についてmean adjusted performance last3を集約した値|直近3走の履歴値を対象に平均。履歴不足時は空配列の既定値0.0。|直近3走|YES|59191.32723617554|90.0||
|77|weighted_adjusted_performance_last3|対象馬の直近3走についてweighted adjusted performance last3を集約した値|直近3走の履歴値を対象に重み付き平均（0.5,0.3,0.2）。履歴不足時は空配列の既定値0.0。|直近3走|YES|1273.1373805999756|17.0||
|78|hidden_strength_last1|対象馬の直近3走についてhidden strength last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|79|hidden_strength_last2|対象馬の直近3走についてhidden strength last2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|80|hidden_strength_last3|対象馬の直近3走についてhidden strength last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|81|max_hidden_strength_last3|対象馬の直近3走についてmax hidden strength last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|82|max_strong_against_bias_last3|対象馬の直近3走についてmax strong against bias last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|83|strong_against_bias_last1|対象馬の直近3走についてstrong against bias last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|84|strong_against_bias_last2|対象馬の直近3走についてstrong against bias last2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|85|strong_against_bias_last3|対象馬の直近3走についてstrong against bias last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|89|setup_improvement|コード上の特徴量 setup_improvement|build_v1_featuresのvalues辞書から取得（詳細式は該当ブロックを参照）。|当該レースまたは過去履歴（名称から一意に確定不可）|UNKNOWN|110.25669860839844|3.0||
|90|hidden_strength_x_race_strength|コード上の特徴量 hidden_strength_x_race_strength|build_v1_featuresのvalues辞書から取得（詳細式は該当ブロックを参照）。|当該レースまたは過去履歴（名称から一意に確定不可）|YES|9.386150360107422|1.0||
|122|strong_against_bias_v2_last1|対象馬の直近3走についてstrong against bias v2 last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|123|strong_against_bias_v2_last2|対象馬の直近3走についてstrong against bias v2 last2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|124|strong_against_bias_v2_last3|対象馬の直近3走についてstrong against bias v2 last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|125|setup_benefit_last1|対象馬の直近3走についてsetup benefit last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|15.277700424194336|1.0||
|126|setup_benefit_last2|対象馬の直近3走についてsetup benefit last2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|127|setup_benefit_last3|対象馬の直近3走についてsetup benefit last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|128|adjusted_performance_v2_last1|対象馬の直近3走についてadjusted performance v2 last1を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|129|adjusted_performance_v2_last2|対象馬の直近3走についてadjusted performance v2 last2を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|130|adjusted_performance_v2_last3|対象馬の直近3走についてadjusted performance v2 last3を集約した値|直近3走の履歴値を対象に直近3走の派生値。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|131|mean_adjusted_performance_v2_last3|対象馬の直近3走についてmean adjusted performance v2 last3を集約した値|直近3走の履歴値を対象に平均。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|132|best_adjusted_performance_v2_last3|対象馬の直近3走についてbest adjusted performance v2 last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|133|weighted_adjusted_performance_v2_last3|対象馬の直近3走についてweighted adjusted performance v2 last3を集約した値|直近3走の履歴値を対象に重み付き平均（0.5,0.3,0.2）。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|134|max_strong_against_bias_v2_last3|対象馬の直近3走についてmax strong against bias v2 last3を集約した値|直近3走の履歴値を対象にmax。履歴不足時は空配列の既定値0.0。|直近3走|YES|0.0|0.0||
|151|last1_margin_x_race_class|対象馬の前走における margin x race class|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|152|last2_margin_x_race_class|対象馬の前々走における margin x race class|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|153|last3_margin_x_race_class|対象馬の3走前における margin x race class|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|0.0|0.0||
|183|last1_margin_x_prize_strength|対象馬の前走における margin x prize strength|対象馬の履歴を新しい順に並べた直近1走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|4308.671380996704|14.0||
|184|last2_margin_x_prize_strength|対象馬の前々走における margin x prize strength|対象馬の履歴を新しい順に並べた直近2走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|181.5838966369629|4.0||
|185|last3_margin_x_prize_strength|対象馬の3走前における margin x prize strength|対象馬の履歴を新しい順に並べた直近3走目から値を取得。履歴不足は0またはunknownでfallback。|直近3走以内|YES|53.78729820251465|2.0||
