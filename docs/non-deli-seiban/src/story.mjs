import { drawTicketCandidates } from './engine.mjs';

export const STORY_CONFIG = {
  initialMoney: 50000,
  initialStamina: 100,
  ticketCost: 3000,
  afterEventTicketCost: 3000,
  chekiCost: 2000,
  travelMinutes: 60,
  minPreparationMinutes: 30,
  maxPreparationMinutes: 120,
  firstAdmission: 12 * 60 + 45,
  firstEvent: 13 * 60,
  secondAdmission: 15 * 60 + 15,
  secondEvent: 15 * 60 + 30
};

export const PREPARATION_OPTIONS = [
  { minutes: 30, label: '最低限', satisfaction: 3 },
  { minutes: 45, label: 'まあヨシ', satisfaction: 5 },
  { minutes: 60, label: '普通に整った', satisfaction: 8 },
  { minutes: 75, label: 'かなり良い', satisfaction: 11 },
  { minutes: 90, label: '今日ビジュいい', satisfaction: 14 },
  { minutes: 105, label: '完璧に近い', satisfaction: 17 },
  { minutes: 120, label: '完全装備', satisfaction: 20 }
];

export const ARRIVAL_OPTIONS = [
  { time: 9 * 60, label: '09:00着', note: '先頭を本気で狙う' },
  { time: 9 * 60 + 30, label: '09:30着', note: '余裕を持って向かう' },
  { time: 10 * 60, label: '10:00着', note: '先頭圏内を狙う' },
  { time: 10 * 60 + 30, label: '10:30着', note: 'ほどほどに急ぐ' },
  { time: 11 * 60, label: '11:00着', note: '販売開始に合わせる' }
];

export const FREE_TIME_EVENTS = [
  { id: 'ramen', icon: '🍜', name: 'ラーメンを食べる', duration: 30, money: -1200, stamina: 10, satisfaction: 7, extra: ['隣のオタクが推しの話をしている。よく聞いたら全然違うグループだった。なぜか安心した。', '湯気の向こうに、午後への活力が見えた。'] },
  { id: 'gyudon', icon: '🥣', name: '牛丼を食べる', duration: 20, money: -700, stamina: 7, satisfaction: 4, extra: ['早い、うまい、午後に間に合う。', '紅しょうがを多めにした。今日はそういう日だ。'] },
  { id: 'cafe', icon: '☕', name: '意識高いカフェ', duration: 35, money: -1600, stamina: 5, satisfaction: 10, extra: ['推しと同じドリンクを頼んでいたことが後から判明した。', '一瞬だけ、人生が整った気がした。'] },
  { id: 'tower', icon: '💿', name: 'タワレコを徘徊', duration: 25, money: -1200, stamina: -3, satisfaction: 7, extra: ['買うものはないはずだった。気付けば知らないアイドルのCDを持っていた。', '試聴機の前で、時間だけが溶けた。'] },
  { id: 'gacha', icon: '◉', name: 'ガチャガチャ', duration: 15, money: -500, stamina: 0, satisfaction: 5, extra: ['欲しかった色は出なかった。でもこれはこれで味がある。', '小さなカプセルに午後の運を託した。'] },
  { id: 'gym', icon: '🏋', name: 'なぜかジムに行く', duration: 45, money: -1000, stamina: -15, satisfaction: 15, extra: ['リリイベとリリイベの間に筋トレを始めた。何を目指しているのかは誰にも分からない。', 'パンプアップした気がする。気のせいかもしれない。'] },
  { id: 'walk', icon: '🚶', name: '散歩する', duration: 30, money: 0, stamina: -5, satisfaction: 8, extra: ['道端の猫に3分見つめられた後、完全に無視された。', '知らない路地に、知らないアイドルのポスターがあった。'] },
  { id: 'rest', icon: '🪑', name: 'ベンチで休む', duration: 30, money: 0, stamina: 15, satisfaction: 1, extra: ['足が軽くなった。午後もまだ戦える。', '少し寝落ちした。起きたら入場の気配が近い。'] },
  { id: 'sns', icon: '📱', name: 'SNSを見る', duration: 15, money: 0, stamina: 0, satisfaction: 4, extra: ['推しが自分のいた場所の写真を投稿していた。', '他人への爆レス動画を見てしまった。でも、まあ元気そうでよかった。'] }
];

const ticketSatisfaction = (number) => {
  if (number === 1) return 35;
  if (number <= 3) return 30;
  if (number <= 9) return 25;
  if (number <= 19) return 16;
  if (number <= 39) return 10;
  if (number <= 69) return 5;
  if (number <= 99) return 1;
  return -3;
};

const arrivalStaminaCost = (arrivalTime) => {
  if (arrivalTime <= 9 * 60) return 18;
  if (arrivalTime <= 9 * 60 + 15) return 15;
  if (arrivalTime <= 9 * 60 + 30) return 12;
  if (arrivalTime <= 9 * 60 + 45) return 9;
  if (arrivalTime <= 10 * 60) return 7;
  if (arrivalTime <= 10 * 60 + 15) return 5;
  if (arrivalTime <= 10 * 60 + 30) return 3;
  return 1;
};

export function getFrontProbability(arrivalTime) {
  const minutesAfterTen = arrivalTime - 10 * 60;
  if (minutesAfterTen <= 0) return 1;
  if (minutesAfterTen >= 60) return 0.01;
  if (minutesAfterTen <= 30) return 1 - 0.25 * (minutesAfterTen / 30);
  const progress = (minutesAfterTen - 30) / 30;
  return 0.01 + 0.74 * Math.pow(1 - progress, 1.7);
}

export function moneySatisfactionModifier(spent) {
  if (spent <= 5000) return 10;
  if (spent <= 25000) return Math.round(10 - (spent - 5000) / 2500);
  if (spent <= 30000) return -Math.round((spent - 25000) / 1000);
  return -5 - Math.round(10 * (Math.exp((spent - 30000) / 9000) - 1));
}

export function staminaMultiplier(stamina) {
  if (stamina <= 0) return 0.2;
  if (stamina >= 20) return 1;
  return 0.2 + 0.8 * Math.pow((stamina - 1) / 19, 0.55);
}

export function storyTitle(story) {
  if (story.stamina <= 0) return '力尽きました';
  if (story.money <= 5000 && story.stamina <= 10) return '明日の俺、ごめん';
  if (story.money < 20000) return '散財';
  if (story.stamina <= 5) return '限界オタク';
  if (story.tickets.includes(1)) return '整番だけで全部許した';
  if (story.finalScore >= 150) return '完璧な休日';
  if (story.finalScore >= 95) return 'これがリリイベ';
  return '楽しかったからヨシ！';
}

export function createStory() {
  return {
    phase: 'preparation',
    time: 6 * 60,
    money: STORY_CONFIG.initialMoney,
    stamina: STORY_CONFIG.initialStamina,
    satisfaction: 0,
    preparationSatisfaction: 0,
    freeTimeSatisfaction: 0,
    partScores: [0, 0],
    tickets: [null, null],
    ticketCandidates: [],
    usedTickets: [new Set(), new Set()],
    frontBonus: false,
    bonusPart: null,
    afterEvent: false,
    latestEvent: '',
    finalScore: null
  };
}

function updateStatus(story, changes) {
  Object.assign(story, changes);
  story.stamina = Math.min(STORY_CONFIG.initialStamina, story.stamina);
  if (story.stamina <= 0) {
    story.stamina = 0;
    story.phase = 'game-over';
  }
  return story;
}

export function prepareStory(story, minutes) {
  const option = PREPARATION_OPTIONS.find((entry) => entry.minutes === minutes);
  if (!option) throw new Error('準備時間を選択してください');
  return updateStatus(story, {
    time: story.time + minutes,
    satisfaction: story.satisfaction + option.satisfaction,
    preparationSatisfaction: option.satisfaction,
    phase: 'departure',
    latestEvent: `${option.label}。鏡の前で小さくうなずいた。満足度 +${option.satisfaction}`
  });
}

export function travelToVenue(story, arrivalTime, random = Math.random) {
  const arrival = ARRIVAL_OPTIONS.find((entry) => entry.time === arrivalTime);
  if (!arrival || arrivalTime < story.time + STORY_CONFIG.travelMinutes) throw new Error('その時刻には到着できません');
  const frontBonus = random() < getFrontProbability(arrivalTime);
  const staminaCost = arrivalStaminaCost(arrivalTime);
  return updateStatus(story, {
    time: arrivalTime,
    stamina: story.stamina - staminaCost,
    frontBonus,
    bonusPart: frontBonus ? (random() < 0.5 ? 0 : 1) : null,
    phase: 'ticket-purchase',
    latestEvent: frontBonus ? '販売列の最前に到着。整番ボーナス獲得！' : `会場に到着。体力 -${staminaCost}`
  });
}

export function buyStoryTickets(story, random = Math.random) {
  if (story.money < STORY_CONFIG.ticketCost) throw new Error('コインが足りません');
  const ticketCandidates = drawTicketCandidates(story.usedTickets[0], 3, random, 'normal', story.bonusPart === 0);
  return updateStatus(story, {
    money: story.money - STORY_CONFIG.ticketCost,
    ticketCandidates,
    phase: 'ticket-1',
    latestEvent: story.frontBonus ? '最速で販売列に到着した！ どちらかの部で一桁確定。' : '1部・2部の整理番号を引く。'
  });
}

export function chooseStoryTicket(story, number, random = Math.random) {
  const part = story.phase === 'ticket-1' ? 0 : story.phase === 'ticket-2' ? 1 : null;
  if (part === null || !story.ticketCandidates.includes(number)) throw new Error('この整理番号は選べません');
  story.usedTickets[part].add(number);
  story.tickets[part] = number;
  if (part === 0) {
    story.ticketCandidates = drawTicketCandidates(story.usedTickets[1], 3, random, 'normal', story.bonusPart === 1);
    story.phase = 'ticket-2';
    story.latestEvent = `1部は${number}番。続いて2部の整理番号へ。`;
  } else {
    story.ticketCandidates = [];
    story.time = 11 * 60 + 30;
    story.phase = 'free-1';
    story.latestEvent = `2部は${number}番。開演までの時間をどう使う？`;
  }
  return story;
}

export function takeFreeTimeAction(story, eventId, random = Math.random) {
  const event = FREE_TIME_EVENTS.find((entry) => entry.id === eventId);
  if (!event || !['free-1', 'free-2'].includes(story.phase)) throw new Error('今はその行動を選べません');
  const bonus = random() < 0.28 ? 2 + Math.floor(random() * 7) : 0;
  const targetTime = story.phase === 'free-1' ? STORY_CONFIG.firstAdmission : STORY_CONFIG.secondAdmission;
  const nextPhase = story.phase === 'free-1' ? 'part-1' : 'part-2';
  const nextTime = Math.min(targetTime, story.time + event.duration);
  return updateStatus(story, {
    time: nextTime,
    money: story.money + event.money,
    stamina: story.stamina + event.stamina,
    satisfaction: story.satisfaction + event.satisfaction + bonus,
    freeTimeSatisfaction: story.freeTimeSatisfaction + event.satisfaction + bonus,
    phase: nextTime >= targetTime ? nextPhase : story.phase,
    latestEvent: `${event.extra[Math.floor(random() * event.extra.length)]} 満足度 +${event.satisfaction + bonus}`
  });
}

export function playStoryPart(story, part, random = Math.random) {
  const number = story.tickets[part];
  if (!number) throw new Error('整理番号がありません');
  const liveEvents = [
    ['好きな曲が来た。', 15], ['推しと目が合った気がする。', 15], ['レスをもらった。', 20], ['推しが歌詞を飛ばして笑った。', 8], ['前の人がデカい。', -10], ['爆レスが飛んできた。', 30], ['まさかの推し曲。', 25], ['PAトラブルが少しだけあった。', -5]
  ];
  const [message, liveScore] = liveEvents[Math.floor(random() * liveEvents.length)];
  const score = ticketSatisfaction(number) + 20 + liveScore;
  const isFirstPart = part === 0;
  story.partScores[part] = score;
  return updateStatus(story, {
    time: isFirstPart ? 14 * 60 : 16 * 60 + 20,
    satisfaction: story.satisfaction + score,
    phase: isFirstPart ? 'free-2' : 'after-event',
    latestEvent: `${isFirstPart ? '1部' : '2部'}：${message} 満足度 +${score}`
  });
}

export function chooseAfterEvent(story, action, random = Math.random) {
  if (action === 'home') return finishStory(story, '今日の現場はここまで。楽しいまま帰るのも悪くない。');
  if (action !== 'round') throw new Error('行動を選択してください');
  const staminaCost = 15 + Math.floor(random() * 11);
  const satisfaction = 10 + Math.floor(random() * 16);
  return updateStatus(story, {
    money: story.money - STORY_CONFIG.afterEventTicketCost,
    stamina: story.stamina - staminaCost,
    satisfaction: story.satisfaction + satisfaction,
    afterEvent: true,
    phase: 'cheki',
    latestEvent: `もう一つ現場を回した。満足度 +${satisfaction}、体力 -${staminaCost}`
  });
}

export function takeCheki(story, random = Math.random) {
  const satisfaction = 8 + Math.floor(random() * 13) + (random() < 0.12 ? 12 : 0);
  updateStatus(story, {
    money: story.money - STORY_CONFIG.chekiCost,
    satisfaction: story.satisfaction + satisfaction,
    latestEvent: `チェキを撮った。会話はたぶん成功。満足度 +${satisfaction}`
  });
  return finishStory(story, story.latestEvent);
}

export function finishStory(story, latestEvent = story.latestEvent) {
  const spent = STORY_CONFIG.initialMoney - story.money;
  const adjusted = story.satisfaction + moneySatisfactionModifier(spent);
  story.finalScore = story.stamina <= 0 ? Math.floor(story.satisfaction / 5) : Math.round(adjusted * staminaMultiplier(story.stamina));
  story.phase = story.stamina <= 0 ? 'game-over' : 'result';
  story.latestEvent = latestEvent;
  return story;
}