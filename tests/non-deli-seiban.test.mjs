import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateScore, claimTicket, drawTicket, drawTicketCandidates, DRAW_MODES, expectedBest, chooseVenue, numberWeight, releaseDayVenues, venues } from '../docs/non-deli-seiban/src/engine.mjs';
import { historyForMode, normalizeRanking, rankingNameMaxLength } from '../docs/non-deli-seiban/src/storage.mjs';

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
