import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateScore, claimTicket, drawTicket, drawTicketCandidates, DRAW_MODES, expectedBest, chooseVenue, numberWeight, releaseDayVenues, venues } from '../docs/non-deli-seiban/src/engine.mjs';
import { historyForMode, normalizeRanking, rankingNameMaxLength } from '../docs/non-deli-seiban/src/storage.mjs';
import { buyStoryTickets, buyThirdEventTicket, chooseAfterEvent, chooseArrivalTime, chooseStoryTicket, continueTicketDraw, createStory, finishStory, finishThirdEvent, FREE_TIME_EVENTS, generateFreeTimeChoices, getChekiSatisfaction, getFrontProbability, moneySatisfactionModifier, playStoryPart, prepareStory, redrawStoryTickets, revealStoryResult, SATISFACTION_CONFIG, skipThirdEventRecovery, STAMINA_CONFIG, STORY_CONFIG, staminaMultiplier, takeFreeTimeAction, takePartCheki, takeRescueMeal, takeThirdEventRecovery, travelToVenue } from '../docs/non-deli-seiban/src/story.mjs';

test('期待BESTは最大抽選回数から計算する', () => {
  assert.equal(expectedBest(1), 50.5);
  assert.equal(Number(expectedBest(10).toFixed(1)), 9.2);
});

test('通常会場は仕様どおり26会場で、発売日限定会場は3会場ある', () => {
  assert.equal(venues.length, 26);
  assert.equal(releaseDayVenues.length, 3);
  assert.ok(venues.every((venue) => venue.minDraws >= 1 && venue.maxDraws <= 10 && venue.works.length > 0));
});

test('発売日判定は一度だけ行い、限定会場は1回勝負になる', () => {
  const releaseVenue = chooseVenue(() => 0);
  assert.equal(releaseVenue.isReleaseDay, true);
  assert.equal(releaseVenue.minDraws, 1);
  assert.equal(releaseVenue.maxDraws, 1);
  const regularVenue = chooseVenue(() => 0.5);
  assert.equal(regularVenue.isReleaseDay, false);
});

test('同じ番号は同一プレイで重複しない', () => {
  const used = new Set();
  const randomValues = [0, 0, 0.01, 0.02];
  const random = () => randomValues.shift() ?? 0.5;
  const first = drawTicket(used, random);
  const second = drawTicket(used, random);
  assert.equal(first, 1);
  assert.equal(second, 2);
  assert.equal(used.size, 2);
});

test('ストーリーモードの全国対戦は専用部門として集計する', () => {
  const ranking = normalizeRanking([
    { player_name: '[RIRIEVENT-GO:STORY] あお', score: 12000 },
    { player_name: '[RIRIEVENT-GO:STORY] あお', score: 15000 },
    { player_name: '[RIRIEVENT-GO] あお', score: 99999 }
  ], 'story');
  assert.deepEqual(ranking.map((record) => [record.player_name, record.score]), [['あお', 15000]]);
});

test('候補3枚は未使用かつ重複せず、選んだ1枚だけが確定する', () => {
  const used = new Set([1, 2]);
  const randomValues = [0, 0.01, 0.02, 0.03];
  const random = () => randomValues.shift() ?? 0.5;
  const candidates = drawTicketCandidates(used, 3, random);
  assert.deepEqual(candidates, [3, 4, 5]);
  assert.equal(used.size, 2);
  claimTicket(used, candidates[1]);
  assert.deepEqual([...used].sort((left, right) => left - right), [1, 2, 4]);
});

test('抽選モードはノーマル均等、フィーバー2倍、パラダイス5倍の傾斜を持つ', () => {
  assert.deepEqual(Object.keys(DRAW_MODES), ['normal', 'fever', 'paradise']);
  assert.equal(numberWeight(1, 'normal'), 1);
  assert.equal(numberWeight(1, 'fever'), 2);
  assert.equal(numberWeight(100, 'fever'), 1);
  assert.equal(numberWeight(1, 'paradise'), 5);
  assert.equal(numberWeight(100, 'paradise'), 1);
});

test('確変候補は最初の3枚をすべて一桁に固定する', () => {
  const candidates = drawTicketCandidates(new Set(), 3, () => 0.1, 'paradise', true);
  assert.equal(candidates.length, 3);
  assert.ok(candidates.every((number) => number <= 9));
  assert.equal(new Set(candidates).size, 3);
});

test('ストーリーの最初の整番抽選は無条件で一桁になる', () => {
  const story = createStory();
  buyStoryTickets(story, () => 0.9);
  assert.ok(story.ticketCandidates.every((number) => number <= 9));
});

test('2部も引くは追加料金なしで、通常抽選には一桁確定チャンスがある', () => {
  const story = createStory();
  buyStoryTickets(story, () => 0.9);
  const moneyAfterPartOne = story.money;
  assert.equal(story.benefitTickets[0], 0);
  chooseStoryTicket(story, story.ticketCandidates[0]);
  continueTicketDraw(story, () => 0.9);
  assert.equal(story.money, moneyAfterPartOne);
  assert.equal(story.benefitTickets[0], 1);

  const retry = createStory();
  retry.ticketDrawCount = 1;
  buyStoryTickets(retry, () => 0.09);
  assert.ok(retry.ticketCandidates.every((number) => number <= 9));
});

test('ストーリーモードは早い会場到着ほど販売列先頭の確率が高い', () => {
  assert.equal(getFrontProbability(10 * 60), 1);
  assert.equal(getFrontProbability(11 * 60), 0.01);
  assert.ok(getFrontProbability(10 * 60 + 15) > getFrontProbability(10 * 60 + 30));
  assert.ok(getFrontProbability(10 * 60 + 30) > getFrontProbability(10 * 60 + 45));
});

test('ストーリーモードの販売列先頭ボーナスは片方の部を一桁候補にする', () => {
  const story = createStory();
  chooseArrivalTime(story, 10 * 60);
  prepareStory(story, 60);
  travelToVenue(story, undefined, () => 0);
  assert.equal(story.frontBonus, true);
  assert.equal(story.bonusPart, 0);
  buyStoryTickets(story, () => 0.1);
  assert.ok(story.ticketCandidates.every((number) => number <= 9));
  chooseStoryTicket(story, story.ticketCandidates[0], () => 0.1);
  assert.equal(story.phase, 'ticket-review');
});

test('ストーリーモードは引いた整番の最小値で入場する', () => {
  const story = createStory();
  story.phase = 'ticket-1';
  story.ticketCandidates = [62];
  chooseStoryTicket(story, 62);
  story.phase = 'ticket-1';
  story.ticketCandidates = [8];
  chooseStoryTicket(story, 8);
  assert.equal(story.tickets[0], 8);
  assert.deepEqual(story.ticketHistory[0], [62, 8]);
});

test('整番の引き直しは1部の後に2部も必ず抽選する', () => {
  const story = createStory();
  buyStoryTickets(story, () => 0.5);
  chooseStoryTicket(story, story.ticketCandidates[0]);
  continueTicketDraw(story, () => 0.5);
  chooseStoryTicket(story, story.ticketCandidates[0]);
  redrawStoryTickets(story, () => 0.5);
  assert.equal(story.phase, 'ticket-1');
  chooseStoryTicket(story, story.ticketCandidates[0]);
  continueTicketDraw(story, () => 0.5);
  assert.equal(story.phase, 'ticket-2');
});

test('特典券チェキは券を1枚消費し、満足度と疲労を発生させる', () => {
  const story = createStory();
  story.phase = 'part-cheki';
  story.chekiPart = 0;
  story.benefitTickets[0] = 1;
  takePartCheki(story);
  assert.equal(story.benefitTickets[0], 0);
  assert.equal(story.chekiCounts[0], 1);
  assert.equal(story.stamina, 99);
  assert.equal(story.satisfaction, 800);
});

test('1部と2部は共通の特典券を消費する', () => {
  const story = createStory();
  story.phase = 'part-cheki';
  story.chekiPart = 1;
  story.benefitTickets[0] = 1;
  takePartCheki(story);
  assert.equal(story.benefitTickets[0], 0);
  assert.equal(story.chekiCounts[1], 1);
});

test('体力0では薬膳鍋で全回復して中断地点へ戻れる', () => {
  const story = createStory();
  story.money = 8000;
  story.stamina = 1;
  story.phase = 'part-cheki';
  story.chekiPart = 0;
  story.benefitTickets[0] = 1;
  takePartCheki(story);
  assert.equal(story.phase, 'rescue');
  takeRescueMeal(story);
  assert.equal(story.money, 3000);
  assert.equal(story.stamina, 100);
  assert.equal(story.phase, 'part-cheki-result');
});

test('3現場目の前は休憩するか、そのまま向かえる', () => {
  const story = createStory();
  story.phase = 'recovery';
  story.stamina = 40;
  takeThirdEventRecovery(story);
  assert.equal(story.stamina, 75);
  assert.equal(story.money, 50000 - STAMINA_CONFIG.thirdEventRecoveryCost);
  assert.equal(story.satisfaction, STAMINA_CONFIG.thirdEventRecoverySatisfaction * 100);
  assert.equal(story.phase, 'third-live');

  const skipped = createStory();
  skipped.phase = 'recovery';
  skipped.stamina = 40;
  skipThirdEventRecovery(skipped);
  assert.equal(skipped.stamina, 40);
  assert.equal(skipped.phase, 'third-live');
});

test('3現場目で体力が尽きそうなら薬膳鍋の前に休憩を挟む', () => {
  const story = createStory();
  story.phase = 'after-event-intro';
  story.stamina = 30;
  chooseAfterEvent(story, 'round', () => 0);
  assert.equal(story.stamina, 0);
  assert.equal(story.phase, 'recovery');
  takeThirdEventRecovery(story);
  assert.equal(story.stamina, 35);
  assert.equal(story.phase, 'third-live');
});

test('体力上限は150、薬膳鍋の回復量は100', () => {
  const rested = createStory();
  rested.phase = 'recovery';
  rested.stamina = 140;
  takeThirdEventRecovery(rested);
  assert.equal(rested.stamina, STORY_CONFIG.maxStamina);

  const rescued = createStory();
  rescued.money = 8000;
  rescued.phase = 'part-cheki';
  rescued.stamina = 1;
  rescued.chekiPart = 0;
  rescued.benefitTickets[0] = 1;
  takePartCheki(rescued);
  takeRescueMeal(rescued);
  assert.equal(rescued.stamina, 100);
});

test('3現場目のライブ終了は派手な満足度加算になり、特典券を購入できる', () => {
  const story = createStory();
  story.phase = 'third-live';
  story.stamina = 50;
  finishThirdEvent(story);
  assert.equal(story.phase, 'third-live-result');
  assert.equal(story.thirdEventScore, 9000);
  assert.equal(story.satisfaction, 9000);

  story.phase = 'cheki-intro';
  buyThirdEventTicket(story);
  assert.equal(story.money, 48000);
  assert.equal(story.benefitTickets[2], 0);
  assert.equal(story.phase, 'part-cheki-result');
  assert.equal(story.benefitTickets[2], 0);
  assert.equal(story.chekiCounts[2], 1);
  assert.equal(story.satisfaction, 800);
  story.phase = 'part-cheki';
  buyThirdEventTicket(story);
  assert.equal(story.chekiCounts[2], 2);
  assert.equal(story.chekiCount, 2);
});

test('満足度ブーストは部をまたいだチェキ合計11枚目から発動する', () => {
  const story = createStory();
  story.phase = 'part-cheki';
  story.chekiPart = 1;
  story.chekiCounts[0] = 10;
  story.chekiCount = 10;
  story.benefitTickets[0] = 1;
  takePartCheki(story);
  assert.equal(story.chekiCount, 11);
  assert.equal(story.satisfaction, getChekiSatisfaction(11) * 100);
  assert.ok(story.satisfaction > getChekiSatisfaction(10) * 100);
});

test('力尽きた場合は満足度の20%でリザルトへ進む', () => {
  const story = createStory();
  story.stamina = 0;
  story.satisfaction = 12345;
  finishStory(story);
  assert.equal(story.phase, 'game-over');
  assert.equal(story.finalScore, 2469);
  revealStoryResult(story);
  assert.equal(story.phase, 'result');
});

test('最速ルートは整番を引く頃には体力が危険域まで削られる', () => {
  const story = createStory();
  chooseArrivalTime(story, 9 * 60);
  prepareStory(story, 120);
  travelToVenue(story, undefined, () => 0.9);
  buyStoryTickets(story, () => 0.5);
  assert.ok(story.stamina >= 8 && story.stamina <= 15);
});

test('FREE TIMEは食事と無料行動を含む4択になる', () => {
  const choices = generateFreeTimeChoices(undefined, () => 0.2);
  assert.equal(choices.length, 4);
  assert.ok(choices.some((choice) => choice.category === 'food'));
  assert.ok(choices.some((choice) => choice.money === 0));
  assert.equal(new Set(choices.map((choice) => choice.id)).size, 4);
});

test('1部・2部ライブとFREE TIMEの満足度は5倍になる', () => {
  const live = createStory();
  live.phase = 'part-1';
  live.tickets[0] = 1;
  playStoryPart(live, 0, () => 0);
  assert.equal(live.partScores[0], (42 + 20 + 15) * 100 * SATISFACTION_CONFIG.partMultiplier);

  const free = createStory();
  free.phase = 'free-1';
  free.freeChoices = [FREE_TIME_EVENTS.find((event) => event.id === 'ramen')];
  takeFreeTimeAction(free, 'ramen');
  assert.equal(free.freeTimeSatisfaction, 18 * 100 * SATISFACTION_CONFIG.freeTimeMultiplier);
});

test('チェキは11枚目以降で満足度が急増する', () => {
  assert.equal(getChekiSatisfaction(10), 8);
  assert.ok(getChekiSatisfaction(11) > 8);
  assert.ok(getChekiSatisfaction(15) > getChekiSatisfaction(12));
});

test('ストーリーモードの出費と体力の最終補正は危険域で厳しくなる', () => {
  assert.ok(moneySatisfactionModifier(5000) > moneySatisfactionModifier(30000));
  assert.ok(moneySatisfactionModifier(30000) > moneySatisfactionModifier(45000));
  assert.equal(staminaMultiplier(20), 1);
  assert.ok(staminaMultiplier(5) < staminaMultiplier(10));
  assert.equal(staminaMultiplier(0), 0.2);
});

test('全国対戦は同じ名前の最高Scoreだけを参照する', () => {
  const ranking = normalizeRanking([
    { player_name: '[RIRIEVENT-GO] すず', score: 95 },
    { player_name: '[RIRIEVENT-GO] すず', score: 210 },
    { player_name: '[RIRIEVENT-GO] あお', score: 180 },
    { player_name: '別ゲームの記録', score: 9999 }
  ]);
  assert.deepEqual(ranking.map((record) => [record.player_name, record.score]), [['すず', 210], ['あお', 180]]);
});

test('全国対戦は抽選モードごとに記録を分離する', () => {
  const records = [
    { player_name: '[RIRIEVENT-GO] すず', score: 210 },
    { player_name: '[RIRIEVENT-GO:FEVER] すず', score: 320 },
    { player_name: '[RIRIEVENT-GO:PARADISE] あお', score: 410 }
  ];
  assert.deepEqual(normalizeRanking(records, 'normal').map((record) => record.player_name), ['すず']);
  assert.deepEqual(normalizeRanking(records, 'fever').map((record) => record.player_name), ['すず']);
  assert.deepEqual(normalizeRanking(records, 'paradise').map((record) => record.player_name), ['あお']);
  assert.equal(rankingNameMaxLength('normal'), 25);
  assert.equal(rankingNameMaxLength('fever'), 19);
  assert.equal(rankingNameMaxLength('paradise'), 16);
});

test('過去成績はモードごとに表示を分離し、旧記録はノーマル扱いになる', () => {
  const history = [
    { score: 90 },
    { mode: 'fever', score: 110 },
    { mode: 'paradise', score: 140 }
  ];
  assert.deepEqual(historyForMode(history, 'normal').map((record) => record.score), [90]);
  assert.deepEqual(historyForMode(history, 'fever').map((record) => record.score), [110]);
  assert.deepEqual(historyForMode(history, 'paradise').map((record) => record.score), [140]);
});

test('同じ良番は少ないチャンスほど高得点になる', () => {
  assert.ok(calculateScore(1, 5) > calculateScore(3, 5));
  assert.ok(calculateScore(3, 5) > calculateScore(10, 5));
  assert.ok(calculateScore(1, 3) > calculateScore(10, 3));
});

test('途中撤退は実際の抽選回数をScoreの基準にする', () => {
  const earlyExitScore = calculateScore(1, 5);
  const maxDrawScore = calculateScore(10, 5);
  assert.ok(earlyExitScore > maxDrawScore);
});

test('リリース当日の1桁は通常日より高いScoreになる', () => {
  for (let number = 1; number <= 9; number += 1) {
    assert.ok(calculateScore(1, number, true) > calculateScore(1, number));
  }
  assert.equal(calculateScore(1, 10, true), calculateScore(1, 10));
});

test('1回チャンスの1番が理論上の最高Scoreになる', () => {
  const best = calculateScore(1, 1);
  assert.equal(best, 501);
  for (let draws = 1; draws <= 10; draws += 1) {
    for (let number = 1; number <= 100; number += 1) {
      assert.ok(best >= calculateScore(draws, number));
    }
  }
});

test('特殊番号と通常番号の境界を確認する', () => {
  assert.ok(calculateScore(5, 2) > 100);
  assert.ok(calculateScore(5, 3) > 100);
  assert.ok(calculateScore(5, 4) <= 100);
  assert.ok(calculateScore(10, 10) < 70);
  assert.ok(calculateScore(1, 20) >= 80);
});
