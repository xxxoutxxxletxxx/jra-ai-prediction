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
const ODDS_PROFILES = [
  { key: 'balanced', label: '大混戦' },
  { key: 'standard', label: '標準' },
  { key: 'favorite', label: '本命集中' }
];
export const RETURN_RATES = { win: 0.8, place: 0.8, quinella: 0.775, exacta: 0.75, trio: 0.75, trifecta: 0.725 };
export const ODDS_LIMITS = { min: 1.1, max: 9999.9 };
export const MIN_PLACE_ODDS = 1.1;
export const MAX_PLACE_ODDS = 99.9;
export const BET_MODES = {
  win: { key: 'win', label: '単勝', description: '1着を当てる', minHorses: 1, maxHorses: 1, payoutRate: RETURN_RATES.win },
  place: { key: 'place', label: '複勝', description: '3着以内を当てる', minHorses: 1, maxHorses: 1, payoutRate: RETURN_RATES.place },
  quinella: { key: 'quinella', label: '馬連', description: '1・2着の2頭を当てる', minHorses: 2, maxHorses: 2, payoutRate: RETURN_RATES.quinella },
  exacta: { key: 'exacta', label: '馬単', description: '1・2着を順番どおり当てる', minHorses: 2, maxHorses: 2, payoutRate: RETURN_RATES.exacta },
  trio: { key: 'trio', label: '三連複', description: '1・2・3着の3頭を当てる', minHorses: 3, maxHorses: 3, payoutRate: RETURN_RATES.trio },
  trifecta: { key: 'trifecta', label: '三連単', description: '1・2・3着を順番どおり当てる', minHorses: 3, maxHorses: 3, payoutRate: RETURN_RATES.trifecta }
};
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

export function calculateOdds(horses, profile = ODDS_PROFILES[1]) {
  const total = horses.reduce((sum, horse) => sum + horse.strength, 0);
  return horses.map((horse, index) => ({
    ...horse,
    popularityScore: horse.strength,
    marketProbability: horse.strength / total,
    odds: Number(clamp(RETURN_RATES.win / (horse.strength / total), ODDS_LIMITS.min, ODDS_LIMITS.max).toFixed(1))
  }));
}

export function buildFinishOrderProbabilities(horses) {
  const totalStrength = horses.reduce((sum, horse) => sum + horse.strength, 0);
  const probabilities = [];
  horses.forEach((first) => horses.forEach((second) => {
    if (second.number === first.number) return;
    horses.forEach((third) => {
      if (third.number === first.number || third.number === second.number) return;
      probabilities.push({ first: first.number, second: second.number, third: third.number, probability: first.strength / totalStrength * second.strength / (totalStrength - first.strength) * third.strength / (totalStrength - first.strength - second.strength) });
    });
  }));
  return probabilities;
}

export function buildPlaceProbabilities(horses) {
  return buildFinishOrderProbabilities(horses).reduce((probabilities, order) => {
    for (const horseNumber of [order.first, order.second, order.third]) {
      probabilities[horseNumber] = (probabilities[horseNumber] || 0) + order.probability;
    }
    return probabilities;
  }, {});
}

const sameNumbers = (left, right) => left.slice().sort((a, b) => a - b).join(',') === right.slice().sort((a, b) => a - b).join(',');

export function calculateBetOdds(horses, modeKey, horseNumbers) {
  const mode = BET_MODES[modeKey] || BET_MODES.win;
  const selected = horseNumbers.map(Number);
  if (modeKey === 'place') {
    const placeProbability = buildPlaceProbabilities(horses)[selected[0]];
    const rawPlaceOdds = RETURN_RATES.place * 3 / placeProbability;
    return Number(clamp(rawPlaceOdds, MIN_PLACE_ODDS, MAX_PLACE_ODDS).toFixed(1));
  }
  const probability = buildFinishOrderProbabilities(horses).reduce((sum, order) => {
    const topTwo = [order.first, order.second];
    const topThree = [order.first, order.second, order.third];
    const hit = modeKey === 'win' ? order.first === selected[0] : modeKey === 'place' ? topThree.includes(selected[0]) : modeKey === 'quinella' ? sameNumbers(selected, topTwo) : modeKey === 'exacta' ? selected.join(',') === topTwo.join(',') : modeKey === 'trio' ? sameNumbers(selected, topThree) : selected.join(',') === topThree.join(',');
    return sum + (hit ? order.probability : 0);
  }, 0);
  return Number(clamp(mode.payoutRate / probability, ODDS_LIMITS.min, ODDS_LIMITS.max).toFixed(1));
}

export function generateRace(random = Math.random) {
  const venue = pick(random, VENUES);
  const distance = pick(random, DISTANCES);
  const track = pick(random, TRACKS);
  const oddsProfile = random() < 0.35 ? ODDS_PROFILES[0] : random() < 0.54 ? ODDS_PROFILES[1] : ODDS_PROFILES[2];
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
  return { venue, month: randomInt(random, 1, 12), distance, track, oddsProfile: oddsProfile.label, horses: calculateOdds(horses, oddsProfile) };
}

export function simulateRace(race, random = Math.random) {
  const remaining = race.horses.slice();
  const ranked = [];
  while (remaining.length) {
    const totalStrength = remaining.reduce((sum, horse) => sum + horse.strength, 0);
    let cursor = random() * totalStrength;
    const selectedIndex = remaining.findIndex((horse) => { cursor -= horse.strength; return cursor <= 0; });
    ranked.push(remaining.splice(Math.max(selectedIndex, 0), 1)[0]);
  }
  return { ...race, horses: ranked.map((horse, index) => ({ ...horse, raceScore: horse.strength, _debugFactors: null, finalPosition: index + 1 })) };
}

export function placeBet(money, selectedHorseNumbers, amount, modeKey = 'win', race = null) {
  const mode = BET_MODES[modeKey] || BET_MODES.win;
  const horseNumbers = Array.isArray(selectedHorseNumbers) ? selectedHorseNumbers : [selectedHorseNumbers];
  if (horseNumbers.length < mode.minHorses || horseNumbers.length > mode.maxHorses || new Set(horseNumbers).size !== horseNumbers.length || !Number.isFinite(amount) || amount <= 0 || amount > money) return { ok: false, reason: `${mode.label}の選択頭数とBET額を確認してください` };
  const odds = race ? calculateBetOdds(race.horses, modeKey, horseNumbers) : 1;
  return { ok: true, money: money - amount, bet: { horseNumbers, amount, modeKey, odds } };
}

export function settleBet(money, bet, resultRace) {
  if (!bet) return { money, payout: 0, hit: false };
  const mode = BET_MODES[bet.modeKey] || BET_MODES.win;
  const positions = resultRace.horses.slice().sort((a, b) => a.finalPosition - b.finalPosition).map((horse) => horse.number);
  const selected = bet.horseNumbers;
  const hit = mode.key === 'win'
    ? selected[0] === positions[0]
    : mode.key === 'place'
      ? positions.slice(0, 3).includes(selected[0])
      : mode.key === 'quinella'
        ? selected.slice().sort((a, b) => a - b).join(',') === positions.slice(0, 2).slice().sort((a, b) => a - b).join(',')
        : mode.key === 'exacta'
          ? selected.join(',') === positions.slice(0, 2).join(',')
          : mode.key === 'trio'
            ? sameNumbers(selected, positions.slice(0, 3))
            : selected.join(',') === positions.slice(0, 3).join(',');
  const odds = bet.odds || calculateBetOdds(resultRace.horses, bet.modeKey, selected);
  const payout = hit ? Math.round(bet.amount * odds) : 0;
  return { money: money + payout, payout, hit, odds: hit ? payout / bet.amount : 0 };
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
  return { initialMoney: 10000, money: 10000, raceNumber: 1, betCount: 0, hitCount: 0, maxPayout: 0, records: [], currentRace: generateRace(random), currentBet: null, betMode: 'win', borrowedAmount: 0, rescueUsed: false, rescueStatus: null };
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
