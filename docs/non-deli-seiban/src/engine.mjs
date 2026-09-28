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
    ? ['？？？？？', '最前確定演出', '今日の運、全部使った。', '入場券を二度見した。', 'おめでとうございます。あなたが最前管理です。']
    : score >= 80
      ? ['これは上振れ。', '購入列を見た瞬間から今日は違った。', '勝ちです。', '視界良好。']
      : score >= 40
        ? ['悪くない。', 'まあこんなもんでしょう。', '期待値通りのオタク。']
        : ['まあライブは楽しかったし……', '整番だけが人生じゃない。', '後ろから見るCYNHNもいいよね。', '今日は音を聴きに来たということで。'];
  return comments[Math.floor(random() * comments.length)];
}
