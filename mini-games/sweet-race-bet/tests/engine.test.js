import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptRescue, createGame, generateRace, makeRandom, placeBet, RESCUE_AMOUNT, settleBet, settleRescue, shouldGameOverAfterRescue, shouldTriggerRescue, simulateRace } from '../src/engine.js';

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

test('randomFactorは独立したキーと値を持つ', () => {
  const result = simulateRace(race(), makeRandom(0.12));
  const factors = result.horses[0]._debugFactors;
  assert.deepEqual(Object.keys(factors).sort(), ['condition', 'distance', 'strength', 'track', 'venue']);
  assert.equal(new Set(Object.values(factors)).size, 5);
});

test('raceScore最大の馬が1着', () => {
  const result = simulateRace(race(), makeRandom(0.55));
  const winner = result.horses.find((horse) => horse.finalPosition === 1);
  assert.equal(winner.raceScore, Math.max(...result.horses.map((horse) => horse.raceScore)));
});

test('オッズは正の値', () => assert.ok(race().horses.every((horse) => horse.odds > 0)));
import { acceptRescue, createGame, generateRace, makeRandom, placeBet, RESCUE_AMOUNT, settleBet, settleRescue, shouldGameOverAfterRescue, shouldTriggerRescue, simulateRace } from '../src/engine.js';

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
  const hit = settleBet(9000, { horseNumber: winner.number, amount: 1000 }, result);
  const miss = settleBet(9000, { horseNumber: winner.number === 1 ? 2 : 1, amount: 1000 }, result);
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
