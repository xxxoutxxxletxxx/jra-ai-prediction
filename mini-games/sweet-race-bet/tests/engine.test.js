import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptRescue, buildFinishOrderProbabilities, buildPlaceProbabilities, calculateBetOdds, createGame, generateRace, makeRandom, placeBet, RESCUE_AMOUNT, settleBet, settleRescue, shouldGameOverAfterRescue, shouldTriggerRescue, simulateRace } from '../src/engine.js';

const race = () => generateRace(makeRandom(0.42));

test('レースは常に8頭で同名なし', () => {
  const current = race();
  assert.equal(current.horses.length, 8);
  assert.equal(new Set(current.horses.map((horse) => horse.name)).size, 8);
});

test('内部パラメータは指定範囲内', () => {
  for (const horse of race().horses) {
    for (const key of ['strength', 'venueAffinity', 'distanceAffinity', 'trackAffinity', 'condition']) assert.ok(horse[key] >= 20 && horse[key] <= 100);
  }
});

test('レース結果はstrengthに基づく着順を持つ', () => {
  const result = simulateRace(race(), makeRandom(0.55));
  assert.deepEqual(result.horses.map((horse) => horse.finalPosition).sort((a, b) => a - b), [1, 2, 3, 4, 5, 6, 7, 8]);
});

test('オッズは正の値', () => assert.ok(race().horses.every((horse) => horse.odds > 0)));

test('全券種の確率空間を共通の336通りから生成する', () => {
  const orders = buildFinishOrderProbabilities(race().horses);
  const epsilon = 1e-9;
  assert.equal(orders.length, 336);
  assert.ok(Math.abs(orders.reduce((sum, order) => sum + order.probability, 0) - 1) < epsilon);
  const placeSum = Array.from({ length: 8 }, (_, index) => index + 1).reduce((sum, number) => sum + orders.filter((order) => [order.first, order.second, order.third].includes(number)).reduce((part, order) => part + order.probability, 0), 0);
  const quinellaCount = new Set(orders.map((order) => [order.first, order.second].sort((a, b) => a - b).join(','))).size;
  const trioCount = new Set(orders.map((order) => [order.first, order.second, order.third].sort((a, b) => a - b).join(','))).size;
  assert.ok(Math.abs(placeSum - 3) < epsilon);
  assert.equal(quinellaCount, 28);
  assert.equal(trioCount, 56);
  assert.ok(calculateBetOdds(race().horses, 'win', [1]) > 0);
});

test('複勝は3着以内確率の合計が3で、確率に応じたオッズになる', () => {
  const { horses } = race();
  const orders = buildFinishOrderProbabilities(horses);
  const placeProbabilities = buildPlaceProbabilities(horses);
  const values = horses.map((horse) => placeProbabilities[horse.number]);
  const placeOdds = horses.map((horse) => calculateBetOdds(horses, 'place', [horse.number]));
  const strengthTotal = horses.reduce((sum, horse) => sum + horse.strength, 0);

  assert.equal(values.length, 8);
  assert.ok(Math.abs(horses.reduce((sum, horse) => sum + horse.strength / strengthTotal, 0) - 1) < 1e-9);
  assert.ok(Math.abs(values.reduce((sum, probability) => sum + probability, 0) - 3) < 1e-9);
  assert.ok(Math.abs(orders.reduce((sum, order) => sum + order.probability, 0) - 1) < 1e-9);
  assert.equal(placeOdds.length, 8);
  for (let index = 0; index < horses.length; index += 1) {
    const expectedOdds = Number(Math.min(99.9, Math.max(1.1, 0.8 / values[index])).toFixed(1));
    assert.equal(placeOdds[index], expectedOdds);
  }
  assert.ok(placeOdds.every((odds) => odds >= 1.1 && odds <= 99.9));
  for (let index = 0; index < horses.length; index += 1) {
    for (let nextIndex = index + 1; nextIndex < horses.length; nextIndex += 1) {
      if (values[index] > values[nextIndex]) assert.ok(placeOdds[index] <= placeOdds[nextIndex]);
    }
  }
});

test('複勝は3着以内なら購入馬のオッズで払い戻される', () => {
  const current = race();
  const result = simulateRace(current, makeRandom(0.55));
  const placedHorse = result.horses.find((horse) => horse.finalPosition === 3);
  const placeOdds = calculateBetOdds(current.horses, 'place', [placedHorse.number]);
  const settled = settleBet(9000, { horseNumbers: [placedHorse.number], amount: 1000, modeKey: 'place', odds: placeOdds }, result);

  assert.equal(settled.hit, true);
  assert.equal(settled.payout, Math.round(1000 * placeOdds));
});

test('BETは所持金を超えられない', () => {
  assert.equal(placeBet(1000, 1, 1001).ok, false);
  assert.equal(placeBet(1000, 1, 0).ok, false);
  assert.equal(placeBet(1000, 1, 500).money, 500);
});

test('10000円BETは所持金が足りない場合に拒否される', () => {
  assert.equal(placeBet(9999, 1, 10000).ok, false);
  assert.equal(placeBet(10000, 1, 10000).money, 0);
});

test('救済イベントは0円かつ1回未使用なら発生する', () => {
  assert.equal(shouldTriggerRescue(0, 5, false), true);
  assert.equal(shouldTriggerRescue(100, 5, false), false);
  assert.equal(shouldTriggerRescue(0, 5, true), false);
});

test('救済金は20000円で一度だけ受け取れる', () => {
  const rescue = acceptRescue(0);
  assert.deepEqual(rescue, { money: RESCUE_AMOUNT, borrowedAmount: RESCUE_AMOUNT, rescueUsed: true, rescueStatus: 'active' });
});

test('救済金は20000円以上なら返却され、未満なら返却失敗になる', () => {
  assert.deepEqual(settleRescue(32400, RESCUE_AMOUNT), { money: 12400, rescueStatus: 'repaid', repaid: RESCUE_AMOUNT });
  assert.deepEqual(settleRescue(19999, RESCUE_AMOUNT), { money: 19999, rescueStatus: 'failed', repaid: 0 });
});

test('救済利用後に0円ならゲームオーバー', () => {
  assert.equal(shouldGameOverAfterRescue(0, 4, true), true);
  assert.equal(shouldGameOverAfterRescue(100, 4, true), false);
});

test('的中時のみ払戻される', () => {
  const current = race();
  const result = simulateRace(current, makeRandom(0.55));
  const winner = result.horses.find((horse) => horse.finalPosition === 1);
  const hit = settleBet(9000, { horseNumbers: [winner.number], amount: 1000, modeKey: 'win', odds: 2 }, result);
  const miss = settleBet(9000, { horseNumbers: [winner.number === 1 ? 2 : 1], amount: 1000, modeKey: 'win', odds: 2 }, result);
  assert.equal(hit.hit, true);
  assert.equal(hit.money, 9000 + hit.payout);
  assert.equal(miss.payout, 0);
});

test('10,000レースのシミュレーションが完走する', () => {
  let totalOdds = 0;
  for (let index = 0; index < 10000; index += 1) {
    const result = simulateRace(generateRace(Math.random), Math.random);
    totalOdds += result.horses.reduce((sum, horse) => sum + horse.odds, 0);
  }
  assert.ok(totalOdds > 0);
});

test('ゲーム初期値は10000円で第1レース', () => {
  const game = createGame(makeRandom(0.1));
  assert.deepEqual({ money: game.money, raceNumber: game.raceNumber }, { money: 10000, raceNumber: 1 });
});
