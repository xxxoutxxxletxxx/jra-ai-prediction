# Phase 5.1 Runtime Summary

DataFrame直結Cached E/Fを実装。Parquetを70万行のlist[dict]へ戻さない。F 10/50/432はcached DataFrame経路で完走し、各々予測行110/631/5581。初回cache buildは約423.5秒、cached F 432は約31.7秒、prediction cache onlyはDB/LightGBMなしで5581行を取得。

Model Eは旧経路と概ね一致（LogLoss差約0.00018、AUC差約-0.00086）。

未完了: LightGBM学習済みModel Cacheの保存/再利用、学習DataFrameの全Raw DBロード除去、50/432の厳密な全指標回帰、Jockey/Best Profile追加。
