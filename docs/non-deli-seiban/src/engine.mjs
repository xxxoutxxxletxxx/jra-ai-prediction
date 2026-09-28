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
    ? ['え、スタッフさん番号見間違えてません？', '最前の空気、予約完了。', '今日の運、後払いできますか？', '整理券を財布に入れて三度見した。', 'あなた、入場の概念を破壊しました。']
    : score >= 80
      ? ['前方、あなたのために空いてた？', '今日だけ整番に愛されている。', '視界、あまりにも良好。', 'その番号、SNSに載せてもいいやつ。']
      : score >= 40
        ? ['運、ちゃんと出勤してる。', '本日のオタク、標準装備。', '座席はないけど、立ち位置は悪くない。', '期待値くん、仕事が早い。']
        : ['今日は後方腕組み部の活動日。', '整番だけが人生じゃない。たぶん。', '後ろから見る照明、逆にエモい。', '推しはどこから見ても推し。カメラもね。'];
  return comments[Math.floor(random() * comments.length)];
}
