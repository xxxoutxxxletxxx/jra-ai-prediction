import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateScore, drawTicket, expectedBest } from '../docs/non-deli-seiban/src/engine.mjs';

test('期待BESTは最大抽選回数から計算する', () => {
  assert.equal(expectedBest(1), 50.5);
  assert.equal(Number(expectedBest(10).toFixed(1)), 9.2);
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

test('同じ良番は少ないチャンスほど高得点になる', () => {
  assert.ok(calculateScore(1, 5) > calculateScore(3, 5));
  assert.ok(calculateScore(3, 5) > calculateScore(10, 5));
  assert.ok(calculateScore(1, 3) > calculateScore(10, 3));
});

test('途中撤退は実際の抽選回数でScoreを上げない', () => {
  const earlyExitScore = calculateScore(10, 5);
  const maxDrawScore = calculateScore(10, 5);
  assert.equal(earlyExitScore, maxDrawScore);
  assert.ok(calculateScore(1, 5) > earlyExitScore);
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
