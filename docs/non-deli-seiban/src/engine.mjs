export const venues = [
  { name: 'タワーレコード渋谷店', minDraws: 1, maxDraws: 3 },
  { name: 'タワーレコード新宿店', minDraws: 1, maxDraws: 3 },
  { name: 'HMV&BOOKS SHIBUYA', minDraws: 1, maxDraws: 2 },
  { name: '汐留シオサイト', minDraws: 1, maxDraws: 3 },
  { name: 'タワーレコード錦糸町店', minDraws: 2, maxDraws: 4 },
  { name: 'カメイドクロック', minDraws: 3, maxDraws: 6 },
  { name: 'ダイバーシティ東京 プラザ', minDraws: 3, maxDraws: 6 },
  { name: 'ららぽーと豊洲', minDraws: 4, maxDraws: 7 },
  { name: 'ららぽーと新三郷', minDraws: 10, maxDraws: 10 },
  { name: 'ららぽーと湘南平塚', minDraws: 10, maxDraws: 10 }
];

export const SCORE_BALANCE = {
  expectedScore: 50,
  expectedCurve: 50,
  specialBase: { 1: 150, 2: 120, 3: 105 },
  specialDifficultyBonus: { 1: 39, 2: 10, 3: 5 }
};

const randomInt = (random, min, max) => Math.floor(random() * (max - min + 1)) + min;

export function chooseVenue(random = Math.random) {
  return venues[Math.floor(random() * venues.length)];
}

export function chooseDrawCount(venue, random = Math.random) {
  return randomInt(random, venue.minDraws, venue.maxDraws);
}

export function drawTicket(usedNumbers, random = Math.random) {
  if (usedNumbers.size >= 100) throw new Error('整理番号を引けません');
  let number;
  do number = randomInt(random, 1, 100); while (usedNumbers.has(number));
  usedNumbers.add(number);
  return number;
}

export function drawTicketCandidates(usedNumbers, count = 3, random = Math.random) {
  if (usedNumbers.size + count > 100) throw new Error('整理番号の候補を出せません');
  const candidates = new Set();
  while (candidates.size < count) {
    const number = randomInt(random, 1, 100);
    if (!usedNumbers.has(number)) candidates.add(number);
  }
  return [...candidates];
}

export function claimTicket(usedNumbers, number) {
  if (!Number.isInteger(number) || number < 1 || number > 100 || usedNumbers.has(number)) throw new Error('この整理番号は選べません');
  usedNumbers.add(number);
  return number;
}

export function expectedBest(maxDrawsToday) {
  return 101 / (maxDrawsToday + 1);
}

function calculateSpecialScore(maxDrawsToday, bestNumber) {
  const difficulty = 10 - maxDrawsToday;
  const base = SCORE_BALANCE.specialBase[bestNumber];
  const bonus = SCORE_BALANCE.specialDifficultyBonus[bestNumber];
  return Math.round(base + difficulty * bonus);
}

export function calculateScore(maxDrawsToday, bestNumber) {
  const draws = Math.max(1, Math.min(10, Number(maxDrawsToday)));
  const best = Math.max(1, Math.min(100, Number(bestNumber)));
  if ([1, 2, 3].includes(best)) return calculateSpecialScore(draws, best);

  const performanceRatio = expectedBest(draws) / best;
  const score = SCORE_BALANCE.expectedScore + SCORE_BALANCE.expectedCurve * Math.tanh(Math.log(performanceRatio));
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function scoreJudgment(score) {
  if (score >= 100) return '異次元の上振れ';
  if (score >= 80) return 'かなり上振れ';
  if (score >= 60) return '上振れ';
  if (score >= 40) return '期待値通り';
  return '下振れ';
}

export function commentForScore(score, bestNumber, random = Math.random) {
  const comments = bestNumber <= 3
    ? ['最前番！ 最前番！ ＼オレモー！／ 声量がもう本番。', '整理券を掲げて、＼世界で一番かわいいよー！／', '1桁を見た瞬間、＼ハイ！ ハイ！ ハイ！／が止まらない。', '前方神番！ ＼フッフー！／ ＼フッフー！／ 開演前に燃え尽きた。', 'スタッフさんまだ呼んでないのに、＼超絶かわいい！／', '番号を見た瞬間、心の中の厄介がセンターに出てきた。', '最前を引いたので、今日は声帯を置いて帰ります。', 'その番号、家宝にします。額縁を買ってから帰る。', '＼行くぞー！／ と叫んだら、まだ会場の外だった。', '神番すぎて整理券が光って見える。たぶん光ってない。', '前方確保！ もうライブ後の感想戦を始めている。', '1桁は引くものじゃない、浴びるものだった。', '番号を二度見、三度見、スタッフさんも二度見。', '今日の運、全部ここに置いていく勢いでコールします。', '最前列の景色を想像して、開演前に涙腺が終わった。', '友達に送る前に、まず自分へ祝勝LINEを送った。', '神番を引いた人間の歩き方で、ゆっくり移動します。', '＼オイ！ オイ！／ まだ整理券を受け取っただけなのに大騒ぎ。', '番号が良すぎて、後方腕組み部を本日だけ休部します。', 'これはもうScoreではなく、現場からの表彰状。']
    : score >= 80
      ? ['＼オレモー！／ ＼オレモー！／ 整番で声が裏返った。', '前方確保！ せーの、＼ハイ！ ハイ！ ハイ！ ハイ！／', '視界良好すぎて、開演前からコールの素振りしてる。', '＼超絶かわいい！／ まだ始まってないのに声帯が終了。', '前方、俺たちの勝ち！ ＼フッフー！／ ＼フッフー！／', '良番なので、入場前からアンコールの練習を始めます。', 'このScore、声量に換算すると120デシベル。', '前の方に行ける！ まず深呼吸、次にコール、最後に深呼吸。', '整番が良いだけで、歩幅までリズムに乗ってきた。', '今日の私は前方担当。異論は認めません。', '＼ハイせーの！／ を言いたいだけの人生だった。', '良番を引いたので、知らない人とも心の中で肩を組んでる。', 'この番号なら推しに見つかる。まず自分が落ち着け。', '会場までの道中、脳内ライブが止まらない。', 'Scoreが良すぎて、コンビニ店員にも報告しそう。', '前方の空気を吸う準備はできた。肺活量だけが不安。', '良番を引いた人の顔で、誰よりも堂々と列に並びます。', 'コールの予習は完璧。肝心の番号もかなり完璧。', 'この整番、今日一日のテンションを全部持っていった。', '＼まだいけるー！／ と叫びたい、まだ開演前だけど。']
      : score >= 40
        ? ['運、ちゃんと出勤してる。', '本日のオタク、標準装備。', '座席はないけど、立ち位置は悪くない。', '期待値くん、仕事が早い。', '可もなく不可もなく、でもコールは全力でいく。', 'この番号なら、前の人の肩越しに希望が見える。', 'ちょうどいい。人生も整番も、たぶんこのくらいがいい。', 'Scoreは普通、テンションは特大。', '番号を見て一瞬悩んだが、結局楽しそうなので勝ち。', '列には並べる。心も一応、前を向いている。', '良番ではないが、声を出す権利は全員にある。', '今日の目標、番号より大きい声を出すこと。', '期待値くんと握手して、現場へ向かいます。', 'このくらいの番号が一番コールに集中できる。', '微妙に良い。微妙だからこそ味がある。', '推しは番号順に好きになってくれるわけじゃない。たぶん。', '隣の人と一緒に盛り上がれたら、もう実質最前。', '整番は中盤、気持ちは開演直前から最高潮。', '今日は標準装備、でも声量だけは特別仕様。', '悪くないどころか、普通に楽しみになってきた。']
        : ['今日は後方腕組み部の活動日。', '整番だけが人生じゃない。たぶん。', '後ろから見る照明、逆にエモい。', '推しはどこから見ても推し。カメラもね。', '番号は後ろ、気持ちは前。体だけが追いついてこない。', 'これは景色を楽しむ回。双眼鏡の出番です。', '後方から全体を見渡す。そう、これは戦略的後退。', '神番の人、おめでとう。私は音響を信じる。', '列の後ろでも、コールの声は前に飛ばせる。たぶん。', '今日は照明と仲良くなる日。', '推しが見えない？ 心の目ならいつでも最前。', '番号を見た瞬間、後方腕組みのフォームに入った。', 'この悔しさは、次回の強運に積み立てます。', '最後列でも沸ける人が本物。今日は修行です。', '後ろから見る会場の一体感、これはこれで良い。', '視界は厳しいが、声量で存在感だけは出す。', '整番は遠い。でも推しへの気持ちは近い。', '今日は耳で楽しむライブ。鼓膜に全振りします。', '番号に負けるな、テンションで押し切れ。', '後方席のプロとして、落ち着いて楽しみます。'];
  return comments[Math.floor(random() * comments.length)];
}
