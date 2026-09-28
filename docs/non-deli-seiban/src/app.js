import { calculateScore, chooseDrawCount, chooseVenue, commentForScore, drawTicket, expectedBest, scoreJudgment } from './engine.mjs';

const app = document.querySelector('#app');
let state;
let transitionTimer;

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const delay = (callback, milliseconds) => { clearTimeout(transitionTimer); transitionTimer = setTimeout(callback, milliseconds); };
const formatNumber = (number) => `${number}番`;

function startGame() {
  const venue = chooseVenue();
  state = { venue, maxDrawsToday: chooseDrawCount(venue), actualDraws: 0, numbers: [], usedNumbers: new Set(), bestNumber: null, exitedEarly: false, phase: 'venue' };
  render();
}

function drawNumber() {
  if (state.actualDraws >= state.maxDrawsToday) return finishLive();
  state.numbers.push(drawTicket(state.usedNumbers));
  state.actualDraws += 1;
  state.bestNumber = Math.min(...state.numbers);
  state.phase = 'ticket';
  render();
}

function stopDrawing() {
  state.exitedEarly = state.actualDraws < state.maxDrawsToday;
  finishLive();
}

function finishLive() {
  state.phase = 'live';
  render();
  delay(() => {
    if (state.bestNumber === 1) return showSpecialEnding();
    state.phase = 'result';
    render();
  }, 1800);
}

function showSpecialEnding() {
  state.phase = 'special';
  state.specialStep = 0;
  render();
  delay(() => {
    state.specialStep = 1;
    render();
    delay(() => { state.specialStep = 2; render(); delay(() => { state.phase = 'result'; render(); }, 1000); }, 900);
  }, 850);
}

function render() {
  app.innerHTML = `${header()}${state ? renderPhase() : renderStart()}`;
}

function header() {
  return `<header class="topbar"><a class="back-link" href="../sweet-race-bet/">← スイートレースBET</a><span class="brand">NON-DELI / SEIBAN</span></header>`;
}

function renderStart() {
  return `<section class="screen start-screen"><p class="eyebrow">CYNHN RELEASE EVENT</p><h1>ノンデリ<br><em>整番ゲーム</em></h1><p class="lead">引ける回数に対して、どれだけ良い整理番号を引けるか。<br>今日の運を、30秒で試そう。</p><button class="main-button" data-action="start">リリイベに行く</button><p class="tiny">整理番号は1〜100。会場ごとに引ける回数が変わります。</p></section>`;
}

function renderPhase() {
  if (state.phase === 'venue') return `<section class="screen story-screen"><p class="eyebrow">TODAY'S EVENT</p><p class="story-copy">本日のリリイベ会場は――</p><h2 class="venue-name">${escapeHtml(state.venue.name)}</h2><button class="text-button" data-action="watch">購入列の様子を見る</button></section>`;
  if (state.phase === 'watching') return `<section class="screen story-screen waiting"><p class="eyebrow">OBSERVING</p><div class="pulse-mark">…</div><p class="story-copy">購入列の様子を見ている……</p></section>`;
  if (state.phase === 'draw-count') return `<section class="screen story-screen"><p class="eyebrow">TODAY'S CHANCE</p><p class="story-copy">今日は</p><h2 class="draw-count">${state.maxDrawsToday}回</h2><p class="story-copy">入場券を引けそうだ。</p><button class="main-button" data-action="to-draw">入場券を引きに行く</button></section>`;
  if (state.phase === 'ticket') return renderTicket();
  if (state.phase === 'live') return `<section class="screen live-screen"><div class="live-light"></div><p class="eyebrow">LIVE EVENT</p><h2>楽しいライブだった……</h2><p>今日の結果を振り返っています。</p></section>`;
  if (state.phase === 'special') return `<section class="screen special-screen"><p class="eyebrow">SPECIAL NUMBER</p><strong class="special-number">${state.specialStep === 0 ? '1' : state.specialStep === 1 ? '…………' : '1番？'}</strong>${state.specialStep === 2 ? '<p class="special-burst">最前確定演出</p>' : ''}</section>`;
  return renderResult();
}

function renderTicket() {
  const canDraw = state.actualDraws < state.maxDrawsToday;
  const remaining = state.maxDrawsToday - state.actualDraws;
  return `<section class="screen ticket-screen"><p class="eyebrow">ADMISSION TICKET</p><div class="ticket-card"><span class="ticket-label">CYNHN / RELEASE EVENT</span><span class="ticket-number">${formatNumber(state.numbers.at(-1))}</span><span class="ticket-note">入場整理券</span></div><div class="draw-status"><span>最大 ${state.maxDrawsToday}回</span><strong>BEST ${formatNumber(state.bestNumber)}</strong><span>残り ${remaining}回</span></div><div class="actions">${canDraw ? '<button class="main-button" data-action="draw">もう1枚引く</button>' : ''}<button class="secondary-button" data-action="stop">ここでやめる</button></div><p class="tiny">同じ番号は出ません。良番を確保したら撤退もできます。</p></section>`;
}

function renderResult() {
  const score = calculateScore(state.maxDrawsToday, state.bestNumber);
  const expected = expectedBest(state.maxDrawsToday);
  const comment = commentForScore(score, state.bestNumber);
  return `<section class="screen result-screen ${state.bestNumber === 1 ? 'jackpot' : ''}"><p class="eyebrow">RESULT</p><h2>リリイベ結果</h2><dl class="result-details"><div><dt>会場</dt><dd>${escapeHtml(state.venue.name)}</dd></div><div><dt>本日の最大抽選回数</dt><dd>${state.maxDrawsToday}回</dd></div><div><dt>実際に引いた回数</dt><dd>${state.actualDraws}回</dd></div><div><dt>引いた整理番号</dt><dd>${state.numbers.map(formatNumber).join(' / ')}</dd></div><div><dt>BEST</dt><dd class="best-number">${formatNumber(state.bestNumber)}</dd></div><div><dt>期待BEST</dt><dd>約${expected.toFixed(1)}番</dd></div><div><dt>判定</dt><dd>${scoreJudgment(score)}</dd></div></dl>${state.exitedEarly ? '<p class="exit-note">良番を確保したので撤退</p>' : ''}<div class="score-box"><span>SCORE</span><strong>${score}</strong><p>${escapeHtml(comment)}</p></div><button class="main-button" data-action="restart">もう一度リリイベに行く</button><a class="secondary-link" href="../sweet-race-bet/">スイートレースBETへ</a></section>`;
}

app.addEventListener('click', (event) => {
  const { action } = event.target.closest('[data-action]')?.dataset || {};
  if (!action) return;
  if (action === 'start' || action === 'restart') startGame();
  if (action === 'watch') { state.phase = 'watching'; render(); delay(() => { state.phase = 'draw-count'; render(); }, 1200); }
  if (action === 'to-draw') drawNumber();
  if (action === 'draw') drawNumber();
  if (action === 'stop') stopDrawing();
});

render();
