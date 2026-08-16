# Race Class and Condition Mapping

この文書はバックテスト専用の対応表です。本番予測処理には使用しません。

| SourceCode | Meaning | Evidence | Example |
|---|---|---|---|
| `JyokenName` contains `新馬` | `NEWCOMER` | `NL_RA_RACE.JyokenName` の日本語条件名 | サラ系2歳新馬 |
| `JyokenName` contains `未勝利` | `MAIDEN` | 同上 | サラ系3歳未勝利 |
| `JyokenName` contains `1勝` or `500万` | `CLASS_1` | 条件名の明示文字列。旧制度名を別名として保持 | 3歳以上1勝クラス |
| `JyokenName` contains `2勝` or `1000万` | `CLASS_2` | 条件名の明示文字列。旧制度名を別名として保持 | 4歳以上2勝クラス |
| `JyokenName` contains `3勝` or `1600万` | `CLASS_3` | 条件名の明示文字列。旧制度名を別名として保持 | 3歳以上3勝クラス |
| `JyokenName` contains `2歳` | `TWO_YEAR_OLD_ONLY` | 条件名の年齢文字列 | サラ系2歳 |
| `JyokenName` contains `3歳上` or `3歳以上` | `THREE_AND_OLDER` | 条件名の年齢文字列 | サラ系3歳以上 |
| `JyokenName` contains `3歳` | `THREE_YEAR_OLD_ONLY` | 条件名の年齢文字列 | サラ系3歳 |
| `JyokenName` contains `4歳上` or `4歳以上` | `FOUR_AND_OLDER` | 条件名の年齢文字列 | サラ系4歳以上 |
| `GradeCD` non-empty | raw category only | 列の用途は確認できるが、コード対応表はリポジトリ内にない | `A`, `C`, `E`, `L` |
| `GradeCD=A` | `G1` | 2012年以降の中央10場で「桜花賞」「皐月賞」「優駿牝馬」「ジャパンカップ」等と照合 | 桜花賞、皐月賞 |
| `GradeCD=B` | `G2` | 2012年以降の中央10場で「フローラステークス」「中山記念」「札幌記念」等と照合 | 中山記念、札幌記念 |
| `GradeCD=C` | `G3` | 2012年以降の中央10場で「きさらぎ賞」「七夕賞」「小倉大賞典」等と照合 | きさらぎ賞、七夕賞 |
| `GradeCD=L` | `LISTED` | 列名とListed競走名の照合 | すばるステークス |
| `JyokenInfoSyubetuCD`, `JyokenInfoJyokenCD0..4` | raw category only | 条件コード列の存在は確認できるが、公式対応表未確認 | `11`, `12`, `000`, `703` |
| `RaceInfoHondai`/`JyokenName` contains `牝` or `牝馬` | `FEMALE_ONLY` | 実レース名「桜花賞」「中山牝馬ステークス」等と出走条件を照合 | 中山牝馬ステークス |
| `RaceInfoHondai`/`JyokenName` without female marker | `OPEN_SEX` | 女性限定マーカーがない場合の非限定カテゴリ。牡馬限定の意味は断定しない | 中山記念 |
| `SexCD` / `TokuUmaInfoSexCD` | `UNKNOWN` | 性別コード列は存在するが、公式の値対応を未確認 | `1`, `2`, `3` |

## UNKNOWN policy

コード値だけから `G1/G2/G3/OPEN/LISTED`、`FEMALE_ONLY`、`MALE_ONLY` を推測しない。対応表が確認できない値は raw code と `UNKNOWN` を保持する。牝馬限定の固定減点は行わない。

## race_class and race_strength

`race_class_label` / `race_class_score` は条件名から確定できた名目上の分類だけを表す。`race_strength` は単一の人為的スコアにせず、winner strength、field strength、着差、条件特徴量を独立してLightGBMへ渡す。

## Prize strength

`NL_RA_RACE.Honsyokin0..6` はスキーマコメントの「本賞金」、`Fukasyokin0..4` は「付加賞金」であり、出走馬結果テーブルの `NL_SE_RACE_UMA.Honsyokin` とは別のレース設定値として扱う。既知の2024年レース（例: G3金杯の1着設定値 `00430000`）との照合から、保存値は100円単位と確認し、特徴量では円へ変換する。`log1p`版も併用する。

賞金は `race_class` を置き換えず、連続的な `prize_strength` の入力として扱う。過去走・勝ち馬の賞金統計は、対象レース日より前に確定した過去レースだけで更新する。
