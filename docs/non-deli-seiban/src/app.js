import { calculateScore, chooseDrawCount, chooseVenue, claimTicket, commentForScore, drawTicketCandidates, expectedBest, scoreJudgment } from './engine.mjs';
import { clearHistory, fetchRanking, rankingNameError, readHistory, saveHistory, submitRanking, summarizeHistory } from './storage.mjs';

const app = document.querySelector('#app');
let state;
let transitionTimer;
let ranking = [];
let rankingStatus = 'idle';
let rankingError = '';
let submittingRanking = false;

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const delay = (callback, milliseconds) => { clearTimeout(transitionTimer); transitionTimer = setTimeout(callback, milliseconds); };
const formatNumber = (number) => `${number}番`;

function startGame() {
  const venue = chooseVenue();
  state = { venue, maxDrawsToday: chooseDrawCount(venue), actualDraws: 0, numbers: [], usedNumbers: new Set(), bestNumber: null, exitedEarly: false, releaseStep: 0, phase: 'venue-intro' };
  render();
  delay(() => {
    if (!state.venue.isReleaseDay) { state.phase = 'venue'; render(); return; }
    state.phase = 'release-intro';
    render();
    delay(() => { state.releaseStep = 1; render(); delay(() => { state.phase = 'venue'; render(); }, 900); }, 900);
  }, 850);
}

function beginDraw() {
  if (state.actualDraws >= state.maxDrawsToday) return finishLive();
  state.phase = 'draw-zone';
  render();
}

function chooseDrawZone(zone) {
  state.selectedZone = zone;
  state.ticketChoices = drawTicketCandidates(state.usedNumbers);
  state.phase = 'choose-ticket';
  render();
}

function chooseTicket(number) {
  state.numbers.push(claimTicket(state.usedNumbers, number));
  state.actualDraws += 1;
  state.bestNumber = Math.min(...state.numbers);
  state.ticketChoices = [];
  state.phase = 'ticket';
  render();
}

function stopDrawing() {
  state.exitedEarly = state.actualDraws < state.maxDrawsToday;
  finishLive();
}

function finishLive() {
  saveCurrentPlay();
  state.phase = 'live';
  render();
  delay(() => {
    if (state.bestNumber <= 3) return showSpecialEnding();
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
    delay(() => { state.specialStep = 2; render(); delay(() => { state.phase = 'result'; render(); }, state.bestNumber === 1 ? 1500 : 1100); }, 900);
  }, 850);
}

function render() {
  app.innerHTML = `${header()}${state ? renderPhase() : renderStart()}`;
}

function header() {
  return `<header class="topbar">${state ? '<button class="home-button" data-action="home" aria-label="ホームへ戻る">⌂ <span>ホーム</span></button>' : '<span></span>'}<span class="brand">リリイベGO</span></header>`;
}

function renderStart() {
  return `<section class="screen start-screen"><p class="eyebrow">CYNHN RELEASE EVENT</p><h1>リリイベ<br><em>GO</em></h1><p class="lead">引ける回数に対して、どれだけ良い整理番号を引けるか。<br>今日の運を、30秒で試そう。</p><button class="main-button" data-action="start">リリイベに行く</button><div class="home-actions"><button class="utility-button" data-action="history">過去成績</button><button class="utility-button" data-action="ranking">全国対戦</button></div><a class="home-game-link" href="../sweet-race-bet/">スイートレースBETへ</a><p class="tiny">整理番号は1〜100。会場ごとに引ける回数が変わります。</p></section>`;
}

function renderPhase() {
  if (state.phase === 'history') return renderHistory();
  if (state.phase === 'ranking') return renderRanking();
  if (state.phase === 'venue-intro') return `<section class="screen cinematic-screen venue-intro-screen"><p class="eyebrow">TODAY'S EVENT</p><p class="venue-intro-copy">本日の会場は――</p></section>`;
  if (state.phase === 'release-intro') return renderReleaseIntro();
  if (state.phase === 'venue') return renderVenue();
  if (state.phase === 'watching') return `<section class="screen story-screen waiting queue-view"><div class="scene queue-scene" aria-hidden="true"><span class="queue-tent"></span><span class="queue-rail"></span><span class="queue-heads"></span></div><p class="eyebrow">OBSERVING</p><div class="pulse-mark">…</div><p class="story-copy">購入列の様子を見ている……</p></section>`;
  if (state.phase === 'draw-count') return `<section class="screen story-screen"><p class="eyebrow">TODAY'S CHANCE</p><p class="story-copy">今日は</p><h2 class="draw-count">${state.maxDrawsToday}回</h2><p class="story-copy">入場券を引けそうだ。</p><button class="main-button" data-action="to-draw">入場券を引きに行く</button></section>`;
  if (state.phase === 'draw-zone') return renderDrawZone();
  if (state.phase === 'choose-ticket') return renderTicketChoices();
  if (state.phase === 'ticket') return renderTicket();
  if (state.phase === 'live') return `<section class="screen live-screen ${state.bestNumber <= 9 ? 'stage-only' : 'audience-view'}"><div class="scene live-scene" aria-hidden="true"><span class="stage-skyline"></span><span class="stage-roof"></span><span class="stage-lights"></span><span class="stage-tent tent-left"></span><span class="stage-tent tent-right"></span><span class="stage-platform"></span><span class="idol-silhouette"></span><span class="audience-silhouette"></span></div><div class="live-light"></div><p class="eyebrow">LIVE EVENT</p><h2>楽しいライブだった……</h2><p>今日の結果を振り返っています。</p></section>`;
  if (state.phase === 'special') return renderSpecialEnding();
  return renderResult();
}

function renderReleaseIntro() {
  return state.releaseStep === 0
    ? '<section class="screen cinematic-screen release-intro-screen"><p class="eyebrow">SPECIAL RELEASE DAY</p><p class="release-copy">今日は――<br><strong>リリース日当日。</strong></p></section>'
    : '<section class="screen cinematic-screen release-intro-screen"><div class="release-cd" aria-hidden="true"></div><p class="release-copy">購入列が長い。<br><strong>入場券は、たった1回。</strong></p></section>';
}

function renderSpecialEnding() {
  const isUltimate = state.bestNumber === 1;
  const numberText = state.specialStep === 0 ? state.bestNumber : state.specialStep === 1 ? '…………' : `${state.bestNumber}番!?`;
  const message = isUltimate ? '伝説の1番。最前列の景色が待っている。' : '一桁の神引き。今日は勝ち確。';
  return `<section class="screen special-screen ${isUltimate ? 'ultimate-number' : 'premium-number'}"><div class="special-lights" aria-hidden="true"><i></i><i></i><i></i></div><div class="special-confetti" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div><p class="eyebrow">${isUltimate ? 'ULTIMATE NUMBER' : 'PREMIUM NUMBER'}</p>${isUltimate ? '<span class="special-crown" aria-hidden="true">★</span>' : ''}<strong class="special-number">${numberText}</strong>${state.specialStep === 2 ? `<p class="special-burst">${message}</p>` : ''}</section>`;
}

function renderVenue() {
  const isTowerRecords = state.venue.name.includes('タワーレコード');
  const isLaLaport = state.venue.name.includes('ららぽーと');
  const scene = isTowerRecords
    ? '<div class="scene venue-scene tower-records-scene" aria-hidden="true"><span class="tower-building"></span><span class="tower-glass-tower"></span><span class="tower-sign">TOWER<br>RECORDS</span><span class="tower-road"></span></div>'
    : isLaLaport
      ? '<div class="scene venue-scene lalaport-scene" aria-hidden="true"><span class="lalaport-building"></span><span class="lalaport-sign">LaLaport</span><span class="lalaport-plaza"></span><span class="lalaport-trees"></span><span class="lalaport-walkway"></span></div>'
      : '<div class="scene venue-scene" aria-hidden="true"><span class="venue-building"></span><span class="venue-sign">RELEASE EVENT</span><span class="venue-sidewalk"></span></div>';
  const venueClass = isTowerRecords ? 'tower-records-view' : isLaLaport ? 'lalaport-view' : '';
  return `<section class="screen story-screen venue-view ${venueClass}">${scene}<p class="eyebrow">TODAY'S EVENT</p><p class="story-copy">本日のリリイベ会場は――</p><h2 class="venue-name">${escapeHtml(state.venue.name)}</h2><button class="text-button" data-action="watch">購入列の様子を見る</button></section>`;
}

function renderTicket() {
  const canDraw = state.actualDraws < state.maxDrawsToday;
  const remaining = state.maxDrawsToday - state.actualDraws;
  const isSingleDigit = state.numbers.at(-1) <= 9;
  return `<section class="screen ticket-screen ${isSingleDigit ? 'single-digit' : ''}"><p class="eyebrow">ADMISSION TICKET</p><div class="ticket-card"><span class="ticket-label">CYNHN / RELEASE EVENT</span><span class="ticket-number">${formatNumber(state.numbers.at(-1))}</span><span class="ticket-note">入場整理券</span></div><div class="draw-status"><span>最大 ${state.maxDrawsToday}回</span><strong>BEST ${formatNumber(state.bestNumber)}</strong><span>残り ${remaining}回</span></div><div class="actions">${canDraw ? '<button class="main-button" data-action="draw">もう1枚引く</button>' : ''}<button class="secondary-button" data-action="stop">ここでやめる</button></div><p class="tiny">同じ番号は出ません。良番を確保したら撤退もできます。</p></section>`;
}

function renderDrawZone() {
  const zones = ['左上', '右上', '中央', '左下', '右下'];
  return `<section class="screen draw-box-screen"><p class="eyebrow">DRAW A TICKET</p><h2>くじ箱の中、どこから引く？</h2><p class="draw-instruction">5つの場所から、手を入れる場所を選んでください。</p><div class="lottery-box" aria-label="整理券のくじ箱">${zones.map((zone) => `<button class="draw-zone zone-${zone}" data-zone="${zone}" aria-label="${zone}から引く"><span>${zone}</span></button>`).join('')}</div></section>`;
}

function renderTicketChoices() {
  return `<section class="screen choice-screen"><p class="eyebrow">YOUR HAND FOUND THREE</p><h2>3枚、手に当たった。</h2><p class="draw-instruction">この中から1枚だけ引く。</p><div class="ticket-choice-grid">${state.ticketChoices.map((number, index) => `<button class="ticket-choice" data-ticket="${number}"><span>整理券</span><strong>${index + 1}</strong><small>これを引く</small></button>`).join('')}</div></section>`;
}

function renderResult() {
  const score = calculateScore(state.maxDrawsToday, state.bestNumber);
  const expected = expectedBest(state.actualDraws);
  const comment = commentForScore(score, state.bestNumber);
  const registration = state.rankingRegistered
    ? '<p class="ranking-note">全国対戦へ登録しました。</p>'
    : `<div class="ranking-register"><p>このScoreで全国対戦に登録</p><div><input id="ranking-name" maxlength="40" placeholder="対戦名" aria-label="対戦名" ${submittingRanking ? 'disabled' : ''}><button class="utility-button" data-action="register-ranking" ${submittingRanking ? 'disabled' : ''}>${submittingRanking ? '登録中…' : '登録する'}</button></div><p class="form-error">${escapeHtml(rankingError)}</p></div>`;
  return `<section class="screen result-screen ${state.bestNumber === 1 ? 'jackpot' : ''}"><p class="eyebrow">RESULT</p><h2>リリイベ結果</h2><dl class="result-details"><div><dt>会場</dt><dd>${escapeHtml(state.venue.name)}</dd></div>${state.venue.isReleaseDay ? '<div><dt>特別条件</dt><dd>リリース日当日 / 1回勝負</dd></div>' : ''}<div><dt>本日の最大抽選回数</dt><dd>${state.maxDrawsToday}回</dd></div><div><dt>実際に引いた回数</dt><dd>${state.actualDraws}回</dd></div><div><dt>引いた整理番号</dt><dd>${state.numbers.map(formatNumber).join(' / ')}</dd></div><div><dt>BEST</dt><dd class="best-number">${formatNumber(state.bestNumber)}</dd></div><div><dt>期待BEST</dt><dd>約${expected.toFixed(1)}番</dd></div><div><dt>判定</dt><dd>${scoreJudgment(score)}</dd></div></dl>${state.exitedEarly ? '<p class="exit-note">良番を確保したので撤退</p>' : ''}<div class="score-box"><span>SCORE</span><strong>${score}</strong><p>${escapeHtml(comment)}</p></div>${registration}<div class="actions"><button class="main-button" data-action="restart">もう一度リリイベに行く</button><button class="utility-button" data-action="ranking">全国対戦を見る</button></div></section>`;
}

function renderHistory() {
  const history = readHistory();
  const summary = summarizeHistory(history);
  const rows = history.length ? history.map((record) => `<li><span>${new Date(record.playedAt).toLocaleDateString('ja-JP')}</span><strong>${record.score}</strong><span>${escapeHtml(record.venue)} / BEST ${record.bestNumber}番</span></li>`).join('') : '<li class="empty-state">まだリリイベの記録がありません。</li>';
  return `<section class="screen archive-screen"><p class="eyebrow">PLAY ARCHIVE</p><h2>過去成績</h2><div class="history-summary"><div><span>プレイ</span><b>${summary.plays}</b></div><div><span>最高Score</span><b>${summary.bestScore}</b></div><div><span>最良整番</span><b>${summary.bestNumber === 101 ? '-' : `${summary.bestNumber}番`}</b></div></div><ul class="history-list">${rows}</ul>${history.length ? '<button class="utility-button" data-action="clear-history">履歴を消去</button>' : ''}</section>`;
}

function renderRanking() {
  const content = rankingStatus === 'loading'
    ? '<p class="ranking-state">全国の整番を集計中……</p>'
    : rankingStatus === 'error'
      ? `<p class="form-error">${escapeHtml(rankingError)}</p><button class="utility-button" data-action="ranking">再読み込み</button>`
      : ranking.length
        ? `<ol class="ranking-list">${ranking.map((record) => `<li><span>${escapeHtml(record.player_name)}</span><strong>${record.score}</strong></li>`).join('')}</ol>`
        : '<p class="ranking-state">まだ記録がありません。最初のScoreを刻もう。</p>';
  return `<section class="screen archive-screen"><p class="eyebrow">NATIONAL SCORE MATCH</p><h2>スコア全国対戦</h2><p class="draw-instruction">同じ対戦名は最高Scoreのみを掲載します。</p>${content}</section>`;
}

function saveCurrentPlay() {
  if (state.saved) return;
  state.saved = true;
  saveHistory({ playedAt: new Date().toISOString(), venue: state.venue.name, maxDrawsToday: state.maxDrawsToday, actualDraws: state.actualDraws, bestNumber: state.bestNumber, score: calculateScore(state.maxDrawsToday, state.bestNumber), exitedEarly: state.exitedEarly });
}

async function openRanking() {
  if (!state) state = { phase: 'ranking' };
  else state.phase = 'ranking';
  rankingStatus = 'loading';
  rankingError = '';
  render();
  try {
    ranking = await fetchRanking();
    rankingStatus = 'ready';
  } catch (error) {
    rankingStatus = 'error';
    rankingError = '全国対戦を取得できませんでした。時間をおいて再試行してください。';
  }
  render();
}

async function registerRanking() {
  if (submittingRanking || !state) return;
  const playerName = String(document.querySelector('#ranking-name')?.value || '').trim();
  const error = rankingNameError(playerName);
  if (error) { rankingError = error; render(); return; }
  submittingRanking = true;
  rankingError = '';
  render();
  try {
    await submitRanking(playerName, calculateScore(state.maxDrawsToday, state.bestNumber));
    state.rankingRegistered = true;
  } catch (submitError) {
    rankingError = submitError.message || '全国対戦への登録に失敗しました。';
  }
  submittingRanking = false;
  render();
}

app.addEventListener('click', (event) => {
  const { action } = event.target.closest('[data-action]')?.dataset || {};
  const { zone } = event.target.closest('[data-zone]')?.dataset || {};
  const { ticket } = event.target.closest('[data-ticket]')?.dataset || {};
  if (zone) { chooseDrawZone(zone); return; }
  if (ticket) { chooseTicket(Number(ticket)); return; }
  if (!action) return;
  if (action === 'home') { clearTimeout(transitionTimer); state = undefined; rankingError = ''; render(); return; }
  if (action === 'start' || action === 'restart') startGame();
  if (action === 'watch') { state.phase = 'watching'; render(); delay(() => { state.phase = 'draw-count'; render(); }, 1200); }
  if (action === 'to-draw' || action === 'draw') beginDraw();
  if (action === 'stop') stopDrawing();
  if (action === 'history') { state = { phase: 'history' }; render(); }
  if (action === 'ranking') openRanking();
  if (action === 'register-ranking') registerRanking();
  if (action === 'clear-history' && window.confirm('過去成績をすべて削除しますか？')) { clearHistory(); render(); }
});

render();
