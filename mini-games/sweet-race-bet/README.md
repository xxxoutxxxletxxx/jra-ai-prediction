# Sweet Race Bet

完全架空の競馬風ミニゲームです。ゲーム内通貨のみを使い、実在の競走馬・競馬場・団体・ロゴは使用していません。

## 起動

依存関係はありません。フォルダ内で次を実行してください。

```sh
python3 -m http.server 4173
```

ブラウザで http://localhost:4173 を開きます。

## テスト

```sh
npm test
npm run simulate
```

`src/engine.js` は、馬生成、オッズ、レースシミュレーション、BET、払戻をUIから分離しています。内部パラメータは通常画面に公開されません。
