const VENUES = ['プリン競馬場', 'マカロン競馬場', 'ドーナツ競馬場', 'ショコラ競馬場', 'クッキー競馬場', 'キャラメル競馬場', 'パフェ競馬場', 'カステラ競馬場', 'ソーダ競馬場', 'キャンディ競馬場'];
const DISTANCES = [1000, 1200, 1400, 1600, 1800, 2000, 2400];
const TRACKS = ['良', '稍重', '重', '不良'];
const GENDERS = ['牡', '牝', 'セン'];
const NAME_HEADS = ['スター', 'ミルキー', 'ハッピー', 'スイート', 'ラッキー', 'ドリーム', 'キラキラ', 'ムーン', 'サニー', 'ピーチ', 'メロン', 'チョコ', 'シュガー', 'レインボー', 'ホイップ', 'ベリー', 'ソーダ', 'クッキー', 'プリティ', 'フローラ'];
const NAME_TAILS = ['ダッシュ', 'リボン', 'プリン', 'ロケット', 'スター', 'パフェ', 'キング', 'クイーン', 'ハート', 'ステップ', 'ソーダ', 'キャット', 'スパーク', 'ドロップ', 'マジック', 'ドリーム', 'カーニバル', 'ブリーズ', 'ポップ', 'フラワー'];
const COAT_COLORS = ['#8d5b3f', '#b87951', '#d39a69', '#5f423b', '#f0b78b', '#704b70', '#777d8f', '#c76e67'];
const MANE_COLORS = ['#3d2634', '#633d2e', '#fff3ce', '#283b55', '#7b3e67', '#46352c'];
const BIB_COLORS = ['#fffdf8', '#252535', '#e85c63', '#4d8de8', '#f3c84b', '#58b878', '#f28b3c', '#ee82a9'];
const BIB_TEXT_COLORS = ['#392f4d', '#ffffff', '#ffffff', '#ffffff', '#392f4d', '#ffffff', '#ffffff', '#ffffff'];
const ACCENTS = ['星', 'ハート', 'リボン', 'ほっぺ', '王冠', '花'];
const COMMENT_BY_LEVEL = {
  veryHigh: '絶好調！スタッフも自信満々',
  high: '動きは軽快。状態は良さそう',
  normal: 'いつも通り。まずまずの状態',
  low: '少し元気がないかも……',
  veryLow: '本調子にはもう一歩'
};

const randomBetween = (random, min, max) => min + random() * (max - min);
const randomInt = (random, min, max) => Math.floor(randomBetween(random, min, max + 1));
const pick = (random, values) => values[Math.floor(random() * values.length)];
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const ODDS_SLOPE = 1.4;
export const RESCUE_AMOUNT = 20000;

export function makeRandom(seed = Math.random()) {
  let state = Math.floor(seed * 2147483646) + 1;
  return () => {
    state = state * 16807 % 2147483647;
    return (state - 1) / 2147483646;
  };
}

function makeName(random, usedNames) {
  let name = '';
  do name = `${pick(random, NAME_HEADS)}${pick(random, NAME_TAILS)}`; while (usedNames.has(name));
  usedNames.add(name);
  return name;
}

function makeComment(condition) {
  if (condition >= 82) return COMMENT_BY_LEVEL.veryHigh;
  if (condition >= 67) return COMMENT_BY_LEVEL.high;
  if (condition >= 45) return COMMENT_BY_LEVEL.normal;
  if (condition >= 30) return COMMENT_BY_LEVEL.low;
  return COMMENT_BY_LEVEL.veryLow;
}

export function calculateOdds(horses) {
  const rawPopularity = horses.map((horse) => horse.strength * 0.7 + (9 - horse.previousFinish) / 8 * 100 * 0.3);
  const popularity = rawPopularity.map((score) => score ** ODDS_SLOPE);
  const total = popularity.reduce((sum, value) => sum + value, 0);
  return horses.map((horse, index) => ({
    ...horse,
    popularityScore: rawPopularity[index],
    marketProbability: popularity[index] / total,
    odds: Number(clamp(0.8 / (popularity[index] / total), 1.2, 35).toFixed(1))
  }));
}

export function generateRace(random = Math.random) {
  const venue = pick(random, VENUES);
  const distance = pick(random, DISTANCES);
  const track = pick(random, TRACKS);
  const usedNames = new Set();
  const horses = Array.from({ length: 8 }, (_, index) => {
    const condition = randomBetween(random, 20, 98);
    return {
      number: index + 1,
      name: makeName(random, usedNames),
      age: randomInt(random, 3, 7),
      gender: pick(random, GENDERS),
      previousFinish: randomInt(random, 1, 8),
      conditionComment: makeComment(condition),
      icon: { coat: pick(random, COAT_COLORS), mane: pick(random, MANE_COLORS), bib: BIB_COLORS[index], bibText: BIB_TEXT_COLORS[index], accent: pick(random, ACCENTS), face: pick(random, ['happy', 'calm', 'wink']) },
      strength: randomBetween(random, 24, 100),
      venueAffinity: randomBetween(random, 30, 100),
      distanceAffinity: randomBetween(random, 30, 100),
      trackAffinity: randomBetween(random, 30, 100),
      condition,
      _debugFactors: null,
      popularityScore: 0,
      marketProbability: 0,
      odds: 0,
      raceScore: 0,
      finalPosition: 0
    };
  });
  return { venue, month: randomInt(random, 1, 12), distance, track, horses: calculateOdds(horses) };
}

export function simulateRace(race, random = Math.random) {
  const ranked = race.horses.map((horse) => {
    const factors = {
      strength: randomBetween(random, 0.82, 1.18),
      venue: randomBetween(random, 0.82, 1.18),
      distance: randomBetween(random, 0.82, 1.18),
      track: randomBetween(random, 0.82, 1.18),
      condition: randomBetween(random, 0.82, 1.18)
    };
    const raceScore = horse.strength * factors.strength + horse.venueAffinity * factors.venue + horse.distanceAffinity * factors.distance + horse.trackAffinity * factors.track + horse.condition * factors.condition;
    return { ...horse, raceScore, _debugFactors: factors };
  }).sort((a, b) => b.raceScore - a.raceScore).map((horse, index) => ({ ...horse, finalPosition: index + 1 }));
  return { ...race, horses: ranked };
}

export function placeBet(money, selectedHorseNumber, amount) {
  if (!selectedHorseNumber || !Number.isFinite(amount) || amount <= 0 || amount > money) return { ok: false, reason: 'BET額または所持金を確認してください' };
  return { ok: true, money: money - amount, bet: { horseNumber: selectedHorseNumber, amount } };
}

export function settleBet(money, bet, resultRace) {
  if (!bet) return { money, payout: 0, hit: false };
  const winner = resultRace.horses.find((horse) => horse.finalPosition === 1);
  const hit = winner.number === bet.horseNumber;
  const payout = hit ? Math.round(bet.amount * resultRace.horses.find((horse) => horse.number === bet.horseNumber).odds) : 0;
  return { money: money + payout, payout, hit };
}

export function shouldTriggerRescue(money, raceNumber, rescueUsed) {
  return money === 0 && raceNumber <= 5 && !rescueUsed;
}

export function shouldGameOverAfterRescue(money, raceNumber, rescueUsed) {
  return money === 0 && raceNumber <= 5 && rescueUsed;
}

export function acceptRescue(money) {
  return { money: money + RESCUE_AMOUNT, borrowedAmount: RESCUE_AMOUNT, rescueUsed: true, rescueStatus: 'active' };
}

export function settleRescue(money, borrowedAmount) {
  if (!borrowedAmount) return { money, rescueStatus: null, repaid: 0 };
  if (money >= borrowedAmount) return { money: money - borrowedAmount, rescueStatus: 'repaid', repaid: borrowedAmount };
  return { money, rescueStatus: 'failed', repaid: 0 };
}

export function createGame(random = Math.random) {
  return { initialMoney: 10000, money: 10000, raceNumber: 1, betCount: 0, hitCount: 0, maxPayout: 0, records: [], currentRace: generateRace(random), currentBet: null, borrowedAmount: 0, rescueUsed: false, rescueStatus: null };
}

export function titleForMoney(money, rescueStatus = null) {
  if (rescueStatus === 'repaid') return '奇跡の生還';
  if (rescueStatus === 'failed') return '逃走中';
  if (rescueStatus === 'gameover') return '無一文 AGAIN';
  if (money === 0) return '無一文からの再出発';
  if (money >= 20000) return '天才予想家';
  if (money > 10000) return '勝ち組';
  if (money >= 8000) return '堅実派';
  return '次こそリベンジ';
}

export { COMMENT_BY_LEVEL, VENUES, DISTANCES, TRACKS };
