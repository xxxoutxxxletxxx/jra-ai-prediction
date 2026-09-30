import { calculateScore, chooseDrawCount, chooseVenue, claimTicket, commentForScore, drawTicketCandidates, DRAW_MODES, expectedBest, scoreJudgment } from './engine.mjs';
import { clearHistory, fetchRanking, historyForMode, rankingNameError, rankingNameMaxLength, readHistory, saveHistory, submitRanking, summarizeHistory } from './storage.mjs?v=20261001-story-mode-v4';
import { ARRIVAL_OPTIONS, buyThirdEventTicket, chooseAfterEvent, chooseArrivalTime, chooseStoryTicket, continueCheki, continueFromFreeTime, continueFromLive, continueTicketDraw, continueToCheki, createStory, finishStory, finishThirdEvent, leavePartCheki, playStoryPart, PREPARATION_OPTIONS, prepareStory, redrawStoryTickets, revealStoryResult, skipThirdEventRecovery, STAMINA_CONFIG, STORY_CONFIG, storyTitle, takeCheki, takeFreeTimeAction, takeRescueMeal, takeThirdEventRecovery, travelToVenue, buyStoryTickets } from './story.mjs';

const app = document.querySelector('#app');
let state;
let transitionTimer;
let ranking = [];
let rankingStatus = 'idle';
let rankingError = '';
let submittingRanking = false;
let rankingMode = 'normal';
let historyMode = 'normal';

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const RANKING_MODES = [...Object.values(DRAW_MODES), { id: 'story', name: 'ストーリー' }];
const delay = (callback, milliseconds) => { clearTimeout(transitionTimer); transitionTimer = setTimeout(callback, milliseconds); };
const formatNumber = (number) => `${number}番`;
const scoreDrawsForState = () => state.exitedEarly ? state.actualDraws : state.maxDrawsToday;
const scoreForState = () => calculateScore(scoreDrawsForState(), state.bestNumber, state.venue?.isReleaseDay === true);

function startGame() {
  state = { phase: 'mode-select' };
  render();
}

function startStory() {
  state = { phase: 'story', mode: 'story', story: createStory() };
  render();
}

function beginGame(mode) {
  const venue = chooseVenue();
  const fever = Math.random() < 1 / 20;
  state = { venue, mode, chanceMode: fever, maxDrawsToday: chooseDrawCount(venue), actualDraws: 0, numbers: [], usedNumbers: new Set(), bestNumber: null, exitedEarly: false, releaseStep: 0, phase: 'venue-intro' };
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
  if (state.chanceMode && state.actualDraws === 0 && !state.chanceAnimationPlayed) {
    state.chanceAnimationPlayed = true;
    state.phase = 'chance-intro';
    render();
    delay(() => { state.phase = 'draw-zone'; render(); }, 2600);
    return;
  }
  state.phase = 'draw-zone';
  render();
}

function chooseDrawZone(zone) {
  state.selectedZone = zone;
  state.ticketChoices = drawTicketCandidates(state.usedNumbers, 3, Math.random, state.mode, state.chanceMode && state.actualDraws === 0);
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
    if (state.bestNumber <= 3 || (state.venue.isReleaseDay && state.bestNumber <= 9)) return showSpecialEnding();
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
    delay(() => { state.specialStep = 2; render(); delay(() => { state.phase = 'result'; render(); }, state.bestNumber === 1 ? 1900 : state.venue.isReleaseDay ? 1600 : 1100); }, state.venue.isReleaseDay ? 1200 : 900);
  }, state.venue.isReleaseDay ? 1100 : 850);
}

function render() {
  app.innerHTML = `${header()}${state ? renderPhase() : renderStart()}`;
}

function header() {
  return `<header class="topbar">${state ? '<button class="home-button" data-action="home" aria-label="ホームへ戻る">⌂ <span>ホーム</span></button>' : '<span></span>'}<span class="brand">リリイベGO</span></header>`;
}

function renderStart() {
  return `<section class="screen start-screen"><p class="eyebrow">CYNHN RELEASE EVENT</p><h1>リリイベ<br><em>GO</em></h1><p class="lead">引ける回数に対して、どれだけ良い整理番号を引けるか。<br>今日の運を、30秒で試そう。</p><button class="main-button" data-action="start">リリイベに行く</button><button class="story-start-button" data-action="start-story"><span>STORY MODE</span>ストーリーモードで遊ぶ</button><div class="home-actions"><button class="utility-button" data-action="history">過去成績</button><button class="utility-button" data-action="ranking">全国対戦</button></div><a class="home-game-link" href="../sweet-race-bet/">スイートレースBETへ</a><p class="tiny">整理番号は1〜100。会場ごとに引ける回数が変わります。</p></section>`;
}

function renderPhase() {
  if (state.phase === 'history') return renderHistory();
  if (state.phase === 'ranking') return renderRanking();
  if (state.phase === 'story') return renderStory();
  if (state.phase === 'venue-intro') return `<section class="screen cinematic-screen venue-intro-screen"><p class="eyebrow">TODAY'S EVENT</p><p class="venue-intro-copy">本日の会場は――</p></section>`;
  if (state.phase === 'mode-select') return renderModeSelect();
  if (state.phase === 'release-intro') return renderReleaseIntro();
  if (state.phase === 'venue') return renderVenue();
  if (state.phase === 'watching') return `<section class="screen story-screen waiting queue-view"><div class="scene queue-scene" aria-hidden="true"><span class="queue-tent"></span><span class="queue-rail"></span><span class="queue-heads"></span></div><p class="eyebrow">OBSERVING</p><div class="pulse-mark">…</div><p class="story-copy">購入列の様子を見ている……</p></section>`;
  if (state.phase === 'draw-count') return `<section class="screen story-screen"><p class="eyebrow">TODAY'S CHANCE</p><p class="story-copy">今日は</p><h2 class="draw-count">${state.maxDrawsToday}回</h2><p class="story-copy">入場券を引けそうだ。</p><button class="main-button" data-action="to-draw">入場券を引きに行く</button></section>`;
  if (state.phase === 'chance-intro') return renderChanceIntro();
  if (state.phase === 'draw-zone') return renderDrawZone();
  if (state.phase === 'choose-ticket') return renderTicketChoices();
  if (state.phase === 'ticket') return renderTicket();
  if (state.phase === 'live') return `<section class="screen live-screen ${state.bestNumber <= 9 ? 'stage-only' : 'audience-view'}"><div class="scene live-scene" aria-hidden="true"><span class="stage-skyline"></span><span class="stage-roof"></span><span class="stage-lights"></span><span class="stage-tent tent-left"></span><span class="stage-tent tent-right"></span><span class="stage-platform"></span><span class="idol-silhouette"></span><span class="audience-silhouette"></span></div><div class="live-light"></div><p class="eyebrow">LIVE EVENT</p><h2>楽しいライブだった……</h2><p>今日の結果を振り返っています。</p></section>`;
  if (state.phase === 'special') return renderSpecialEnding();
  return renderResult();
}

function formatStoryTime(minutes) {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function storyPosition(number) {
  if (number <= 9) return '最前濃厚';
  if (number <= 19) return '前方';
  if (number <= 39) return 'かなり見やすい';
  if (number <= 69) return '普通';
  return '後方';
}

function renderStoryHud(story) {
  return `<div class="story-hud"><div class="story-time"><span>時刻</span><strong>${formatStoryTime(story.time)}</strong></div><div><span>所持金</span><strong>${story.money.toLocaleString()}</strong></div><div><span>体力</span><strong>${story.stamina}</strong></div><div><span>満足度</span><strong>${story.satisfaction}</strong></div></div>`;
}

function renderStory() {
  const { story } = state;
  const scene = story.selectedFreeEvent?.scene || (story.phase.includes('cheki') ? 'cheki' : story.phase.includes('round') ? 'night' : story.phase.includes('part') || story.phase === 'live-result' ? 'live' : story.phase.includes('ticket') ? 'queue' : story.phase.includes('result') ? 'home-night' : story.phase === 'wake-up' ? 'bedroom' : story.phase === 'preparation' ? 'mirror' : story.phase === 'travel-intro' ? 'train' : story.phase.includes('after') ? 'dusk' : 'city');
  const hideHud = ['wake-up', 'result-intro', 'result', 'game-over'].includes(story.phase);
  return `<section class="screen story-mode-screen story-scene-${scene} phase-${story.phase}"><div class="story-scape" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>${hideHud ? '' : renderStoryHud(story)}<div class="story-content">${renderStoryContent(story)}</div></section>`;
}

function renderStoryContent(story) {
  const lines = (value) => escapeHtml(value).replaceAll('\n', '<br>');
  if (story.phase === 'wake-up') return `<div class="wake-clock">06:00</div><div class="wake-copy"><p>......朝か。</p><p>今日はリリイベだ。</p><p>何時に会場に行こうかな？</p></div><div class="arrival-list">${ARRIVAL_OPTIONS.map((option, index) => `<button class="arrival-choice" style="--reveal:${index}" data-story-action="arrival" data-story-value="${option.time}"><span>${option.label}</span><strong>${option.clock}</strong><small>${escapeHtml(option.note)}</small></button>`).join('')}</div>`;
  if (story.phase === 'preparation') return `<p class="eyebrow">MORNING ROUTINE</p><h2>どれくらい<br>準備しようか？</h2><p class="story-lead">${escapeHtml(story.latestEvent)}</p><div class="story-choice-grid">${PREPARATION_OPTIONS.map((option, index) => `<button class="story-choice" style="--reveal:${index}" data-story-action="prepare" data-story-value="${option.minutes}"><strong>${option.minutes}分</strong><span>${option.label}</span><small>満足度 +${option.satisfaction}<br>${option.detail}</small></button>`).join('')}</div>`;
  if (story.phase === 'travel-intro') return `<div class="cinema-copy"><p>電車に乗った。</p><p>まだ朝の街が、窓の外を流れている。</p><p>今日は長くなる。</p></div><button class="story-continue" data-story-action="travel">会場へ向かう</button>`;
  if (story.phase === 'ticket-purchase') return `<p class="eyebrow">SALES LINE</p><h2>${story.frontBonus ? '販売列の、いちばん前。' : '販売列に着いた。'}</h2><p class="story-lead">${escapeHtml(story.latestEvent)}</p><div class="story-ticket-purchase"><span>整理番号抽選</span><strong>3,000 COIN</strong><small>所持金がある限り、何度でも引ける。</small><button class="main-button" data-story-action="buy-tickets">引く</button></div>`;
  if (story.phase === 'ticket-1' || story.phase === 'ticket-2') { const label = story.phase === 'ticket-1' ? '1部' : '2部'; const bonus = story.bonusPart === (story.phase === 'ticket-1' ? 0 : 1); return `<p class="eyebrow">TICKET DRAW / ${label}</p><h2 class="${bonus ? 'ticket-jackpot-title' : ''}">${bonus ? '──確定。' : `${label}の整理番号`}</h2><p class="story-lead">${escapeHtml(story.latestEvent)}</p><div class="story-ticket-grid ${bonus ? 'single-digit-draw' : ''}">${story.ticketCandidates.map((number, index) => `<button class="story-ticket" style="--reveal:${index}" data-story-action="ticket" data-story-value="${number}"><span>整理券 ${index + 1}</span><strong aria-hidden="true">?</strong><small>これを引く</small></button>`).join('')}</div>`; }
  if (story.phase === 'ticket-review') { const hasFinishedBothParts = story.drawPart === 1; const canRedraw = hasFinishedBothParts && story.money >= 3000; const nextLabel = hasFinishedBothParts ? 'これで行く' : '2部も引く'; return `<p class="eyebrow">TICKET CHECK</p><h2>手の中の、今日。</h2><div class="ticket-summary"><span>1部 <b>${story.tickets[0] ?? '---'}番</b></span><span>2部 <b>${story.tickets[1] ?? '---'}番</b></span></div><p class="story-lead">${escapeHtml(story.latestEvent)}</p><div class="story-after-actions">${hasFinishedBothParts ? `<button class="secondary-button" data-story-action="redraw" ${canRedraw ? '' : 'disabled'}>もう一回引く<br><small>1部・2部 / 3,000 COIN</small></button>` : ''}<button class="main-button" data-story-action="ticket-next">${nextLabel}</button></div>`; }
  if (story.phase === 'free-1' || story.phase === 'free-2') { const label = story.phase === 'free-1' ? '1部まで' : '2部まで'; return `<p class="eyebrow">FREE TIME</p><h2>${label}<br>何をする？</h2><p class="story-lead">選べるのは、一つだけ。</p><div class="free-choice-grid">${story.freeChoices.map((entry, index) => `<button class="free-choice" style="--reveal:${index}" data-story-action="free" data-story-value="${entry.id}"><b>${escapeHtml(entry.name)}</b><span>${entry.money ? `${entry.money.toLocaleString()} COIN` : '無料'}</span></button>`).join('')}</div>`; }
  if (story.phase === 'free-result') { const entry = story.selectedFreeEvent; return `<div class="free-result"><p class="eyebrow">FREE TIME</p><h2>${escapeHtml(entry.name)}</h2><p class="scene-story-copy">${lines(story.latestEvent)}</p><div class="delta-row"><span>COIN <b>${entry.money >= 0 ? '+' : ''}${entry.money.toLocaleString()}</b></span><span>STAMINA <b>${entry.stamina >= 0 ? '+' : ''}${entry.stamina}</b></span><span>SATISFACTION <b>+${entry.satisfaction}</b></span></div></div><button class="story-continue" data-story-action="free-next">リリイベへ</button>`; }
  if (story.phase === 'part-1' || story.phase === 'part-2') { const part = story.phase === 'part-1' ? 0 : 1; const label = part === 0 ? '1部' : '2部'; return `<div class="admission-copy"><p>${label}、入場の時間。</p><div class="story-part-card"><span>最良整理番号</span><strong>${story.tickets[part]}番</strong><p>${storyPosition(story.tickets[part])}。今まで引いた中で、いちばん早い番号で入場する。</p></div></div><button class="main-button" data-story-action="play-part" data-story-value="${part}">${label}へ入場する</button>`; }
  if (story.phase === 'live-result') { const score = story.partScores[story.lastPart]; const copy = score >= 7500 ? '──これを見るために来た。' : score >= 5500 ? '今日来てよかった。' : score >= 3000 ? 'めちゃくちゃ良かった。' : '楽しかった。'; return `<div class="live-result-copy score-tier-${score >= 7500 ? 'ultimate' : score >= 5500 ? 'great' : score >= 3000 ? 'good' : 'small'}"><p>${escapeHtml(story.latestEvent)}</p><strong>+${score.toLocaleString()}</strong><span>${copy}</span></div><button class="story-continue" data-story-action="live-next">チェキ会へ</button>`; }
  if (story.phase === 'part-cheki') { const part = story.chekiPart; const label = part === 2 ? '3現場目' : `${part + 1}部`; const available = story.benefitTickets[part === 2 ? 2 : 0]; const count = story.chekiCounts[part]; const buyButton = part === 2 && available === 0 ? `<button class="main-button" data-story-action="buy-third-ticket" ${story.money < STORY_CONFIG.chekiCost ? 'disabled' : ''}>特典券を買う<br><small>${STORY_CONFIG.chekiCost.toLocaleString()} COIN</small></button>` : ''; return `<p class="eyebrow">${label.toUpperCase()} CHEKI</p><h2>何枚、撮る？</h2><div class="cheki-current"><span>現在</span><strong>${count}</strong><span>枚</span></div><p class="story-lead">${part < 2 ? '1部・2部共通の' : '3現場目専用の'}特典券 ${available}枚。</p><div class="story-after-actions"><button class="secondary-button" data-story-action="leave-part-cheki">この部はやめる</button>${buyButton || `<button class="main-button" data-story-action="part-cheki" ${available === 0 ? 'disabled' : ''}>特典券を使って<br>チェキを撮る</button>`}</div>`; }
  if (story.phase === 'part-cheki-result') return `<div class="cheki-result ${story.chekiCount > 10 ? 'over-ten' : ''}"><span>${story.chekiPart + 1}部チェキ ${story.chekiCounts[story.chekiPart]}枚目 / 合計${story.chekiCount}枚</span><strong>+${story.latestEvent.match(/\+([\d,]+)/)?.[1] || 0}</strong><p>特典券を1枚使った。</p></div><div class="story-after-actions"><button class="secondary-button" data-story-action="leave-part-cheki">この部はやめる</button><button class="main-button" data-story-action="continue-part-cheki">続ける</button></div>`;
  if (story.phase === 'after-event-intro') return `<div class="cinema-copy after-copy"><p>......終わった。</p><p>楽しかった。</p><p>でも、まだ帰るには早い気がする。</p><p>このあと、別の現場もある。</p><p>どうしよう。</p></div><div class="story-after-actions after-delayed"><button class="secondary-button" data-story-action="after" data-story-value="home">今日は帰る</button><button class="main-button" data-story-action="after" data-story-value="round">現場を回す<br><small>3,000 COIN</small></button></div>`;
  if (story.phase === 'recovery') { const recoveryCost = STAMINA_CONFIG.thirdEventRecoveryCost; const canRecover = story.money >= recoveryCost; return `<p class="eyebrow">BETWEEN EVENTS</p><h2>次の現場の前に、<br>カフェで休もう。</h2><p class="story-lead">${escapeHtml(story.latestEvent)}</p><div class="story-ticket-purchase"><span>カフェ休憩</span><strong>${recoveryCost.toLocaleString()} COIN / 体力 +${STAMINA_CONFIG.thirdEventRecovery}</strong><small>座って呼吸を整える。満足度 +${STAMINA_CONFIG.thirdEventRecoverySatisfaction}</small><div class="story-after-actions"><button class="secondary-button" data-story-action="skip-third-recovery">休憩せず向かう</button><button class="main-button" data-story-action="third-recovery" ${canRecover ? '' : 'disabled'}>カフェで休んで向かう<br><small>${canRecover ? `${recoveryCost.toLocaleString()} COIN` : 'コインが足りない'}</small></button></div></div>`; }
  if (story.phase === 'third-live') return `<div class="third-live-copy"><p class="eyebrow">THIRD EVENT / LIVE</p><strong>最後の現場。</strong><span>ここまで来た。</span><p>${escapeHtml(story.latestEvent)}</p></div><button class="story-continue" data-story-action="third-live-finish">最後の曲まで浴びる</button>`;
  if (story.phase === 'third-live-result') return `<div class="third-live-result-copy"><span>THIRD EVENT COMPLETE</span><strong>+${story.thirdEventScore.toLocaleString()}</strong><p>光が弾けて、歓声が夜を揺らした。</p><b>今日の最後に、最高の景色。</b></div><button class="story-continue" data-story-action="cheki-intro">物販へ向かう</button>`;
  if (story.phase === 'cheki-intro') return `<div class="cinema-copy"><p>ライブが終わった。</p><p>物販列ができている。</p><p>3現場目専用の特典券を、買えるだけ買える。</p><p>......1枚くらいなら。</p></div><div class="story-after-actions after-delayed"><button class="secondary-button" data-story-action="finish-story">帰る</button><button class="main-button" data-story-action="buy-third-ticket" ${story.money < STORY_CONFIG.chekiCost ? 'disabled' : ''}>特典券を買う<br><small>${STORY_CONFIG.chekiCost.toLocaleString()} COIN / そのまま撮影</small></button></div>`;
  if (story.phase === 'cheki') return `<p class="eyebrow">CHEKI BOOTH</p><h2>何枚、撮る？</h2><div class="cheki-count">${story.chekiCount}<small>枚</small></div><p class="story-lead">財布は軽い。記憶は重い。</p><div class="story-after-actions"><button class="secondary-button" data-story-action="finish-story">帰る</button><button class="main-button" data-story-action="cheki">もう1枚撮る<br><small>2,000 COIN</small></button></div>`;
  if (story.phase === 'cheki-ten') return `<div class="cheki-ten-copy"><p>......10枚撮った。</p><strong>まだ撮る？</strong></div><div class="story-after-actions"><button class="secondary-button" data-story-action="finish-story">帰る</button><button class="main-button" data-story-action="cheki-next">撮る。</button></div>`;
  if (story.phase === 'cheki-result') return `<div class="cheki-result ${story.chekiCount > 10 ? 'over-ten' : ''}"><span>${story.chekiCount}枚目</span><strong>+${story.latestEvent.match(/\+(\d+)/)?.[1] || 0}</strong><p>${story.chekiCount > 10 ? '止まらない。' : 'もう一枚だけ。'}</p></div><div class="story-after-actions"><button class="secondary-button" data-story-action="finish-story">帰る</button><button class="main-button" data-story-action="cheki-next">もう1枚撮る</button></div>`;
  if (story.phase === 'result-intro') return `<div class="cinema-copy result-intro-copy"><p>長い1日が終わった。</p><p>財布は軽い。</p><p>身体も重い。</p><p>でも──</p></div><button class="story-continue" data-story-action="reveal-result">振り返る</button>`;
  if (story.phase === 'rescue') return `<div class="game-over-copy rescue-copy"><p>......無理だ。</p><p>身体が動かない。</p><strong>薬膳鍋なら、まだ。</strong><small>5,000コインで体力を全回復する。</small></div><button class="story-continue" data-story-action="rescue-meal">薬膳鍋を食べる</button>`;
  const gameOver = story.phase === 'game-over';
  if (gameOver) return `<div class="game-over-copy"><p>......無理だ。</p><p>身体が動かない。</p><strong>力尽きた。</strong><small>最終満足度は、ここまでの20%になる。</small></div><button class="story-continue" data-story-action="reveal-game-over-result">力尽きた結果を見る</button>`;
  const storyRegistration = state.rankingRegistered ? '<p class="ranking-note">ストーリースコアを全国対戦へ登録しました。</p>' : `<div class="ranking-register"><p>ストーリーモードの全体スコアを全国対戦へ登録</p><div><input id="story-ranking-name" maxlength="${rankingNameMaxLength('story')}" placeholder="対戦名" aria-label="ストーリー対戦名" ${submittingRanking ? 'disabled' : ''}><button class="utility-button" data-story-action="register-story-ranking" ${submittingRanking ? 'disabled' : ''}>${submittingRanking ? '登録中…' : '登録する'}</button></div><p class="form-error">${escapeHtml(rankingError)}</p></div>`;
  return `<p class="eyebrow">TODAY'S SATISFACTION</p><h2>${storyTitle(story)}</h2><div class="story-result-score"><span>今日の満足度</span><strong>${story.finalScore.toLocaleString()}</strong></div><p class="story-result-copy">${escapeHtml(story.biggestMoment)}</p><dl class="story-result-details"><div><dt>残金</dt><dd>${story.money.toLocaleString()}コイン</dd></div><div><dt>総出費</dt><dd>${story.totalSpent.toLocaleString()}コイン</dd></div><div><dt>残り体力</dt><dd>${story.stamina}</dd></div><div><dt>1部 / 2部整理番号</dt><dd>${story.tickets[0]}番 / ${story.tickets[1]}番</dd></div><div><dt>整番を引いた回数</dt><dd>${story.ticketDrawCount}回</dd></div><div><dt>1部 / 2部満足度</dt><dd>${story.partScores[0].toLocaleString()} / ${story.partScores[1].toLocaleString()}</dd></div><div><dt>FREE TIME満足度</dt><dd>${story.freeTimeSatisfaction.toLocaleString()}</dd></div><div><dt>現場回し</dt><dd>${story.afterEvent ? 'した' : 'しなかった'}</dd></div><div><dt>1部チェキ</dt><dd>${story.chekiCounts[0]}枚</dd></div><div><dt>2部チェキ</dt><dd>${story.chekiCounts[1]}枚</dd></div><div><dt>3現場目チェキ</dt><dd>${story.chekiCounts[2]}枚</dd></div></dl>${storyRegistration}<div class="actions"><button class="main-button" data-action="start-story">もう一度ストーリーモードで遊ぶ</button><button class="utility-button" data-action="ranking">全国対戦を見る</button></div>`;
}

function handleStoryAction(action, value) {
  const { story } = state;
  if (action === 'arrival') chooseArrivalTime(story, Number(value));
  if (action === 'prepare') prepareStory(story, Number(value));
  if (action === 'travel') travelToVenue(story);
  if (action === 'buy-tickets') buyStoryTickets(story);
  if (action === 'ticket') chooseStoryTicket(story, Number(value));
  if (action === 'ticket-next') continueTicketDraw(story);
  if (action === 'redraw') redrawStoryTickets(story);
  if (action === 'free') takeFreeTimeAction(story, value);
  if (action === 'free-next') continueFromFreeTime(story);
  if (action === 'play-part') playStoryPart(story, Number(value));
  if (action === 'live-next') continueFromLive(story);
  if (action === 'after') chooseAfterEvent(story, value);
  if (action === 'third-recovery') takeThirdEventRecovery(story);
  if (action === 'skip-third-recovery') skipThirdEventRecovery(story);
  if (action === 'third-live-finish') finishThirdEvent(story);
  if (action === 'cheki-intro') continueToCheki(story);
  if (action === 'cheki-next') continueCheki(story);
  if (action === 'cheki') takeCheki(story);
  if (action === 'part-cheki') takeCheki(story);
  if (action === 'continue-part-cheki') continueCheki(story);
  if (action === 'leave-part-cheki') leavePartCheki(story);
  if (action === 'reveal-result') revealStoryResult(story);
  if (action === 'reveal-game-over-result') revealStoryResult(story);
  if (action === 'rescue-meal') takeRescueMeal(story);
  if (action === 'buy-third-ticket') buyThirdEventTicket(story);
  if (action === 'register-story-ranking') registerStoryRanking();
  if (action === 'finish-story') finishStory(story);
  render();
}

function renderModeSelect() {
  const modes = Object.values(DRAW_MODES).map((mode) => `<button class="mode-choice mode-${mode.id}" data-mode="${mode.id}"><strong>${mode.name}</strong><span>${mode.description}</span></button>`).join('');
  return `<section class="screen mode-screen"><p class="eyebrow">CHOOSE YOUR LUCK</p><h2>抽選モードを選ぶ</h2><p class="draw-instruction">若い番号への追い風を選択できます。</p><div class="mode-choice-grid">${modes}</div><p class="tiny">たまにいいことがあるかも。。。</p></section>`;
}

function renderChanceIntro() {
  return `<section class="screen chance-screen"><div class="chance-rays" aria-hidden="true"></div><div class="chance-confetti" aria-hidden="true">${'<i></i>'.repeat(18)}</div><div class="chance-flash" aria-hidden="true"></div><p class="eyebrow">LUCKY BREAK</p><p class="chance-copy">運命が、動き出す。</p><strong class="chance-title">確変突入</strong><p class="chance-subcopy">最初の一枚に、特別な予感。</p></section>`;
}

function renderReleaseIntro() {
  return state.releaseStep === 0
    ? '<section class="screen cinematic-screen release-intro-screen"><div class="release-rays" aria-hidden="true"></div><div class="release-sparkles" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><p class="eyebrow">SPECIAL RELEASE DAY</p><p class="release-copy">今日は――<br><strong>リリース日当日。</strong></p><p class="release-subcopy">特別な一日が、はじまる。</p></section>'
    : '<section class="screen cinematic-screen release-intro-screen"><div class="release-rays" aria-hidden="true"></div><div class="release-sparkles" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><div class="release-cd" aria-hidden="true"></div><p class="release-copy">購入列が長い。<br><strong>入場券は、たった1回。</strong></p><p class="release-subcopy">一度きりの神引きに挑め。</p></section>';
}

function renderSpecialEnding() {
  const isUltimate = state.bestNumber === 1;
  const { isReleaseDay } = state.venue;
  const numberText = state.specialStep === 0 ? state.bestNumber : state.specialStep === 1 ? '…………' : `${state.bestNumber}番!?`;
  const message = isUltimate ? '伝説の1番。最前列の景色が待っている。' : isReleaseDay ? 'リリース日限定の一桁。今日は完全勝利。' : '一桁の神引き。今日は勝ち確。';
  return `<section class="screen special-screen ${isUltimate ? 'ultimate-number' : 'premium-number'} ${isReleaseDay ? 'release-day-number' : ''}"><div class="special-lights" aria-hidden="true"><i></i><i></i><i></i></div><div class="special-confetti" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div><p class="eyebrow">${isReleaseDay ? 'RELEASE DAY MIRACLE' : isUltimate ? 'ULTIMATE NUMBER' : 'PREMIUM NUMBER'}</p>${isUltimate ? '<span class="special-crown" aria-hidden="true">★</span>' : ''}<strong class="special-number">${numberText}</strong>${state.specialStep === 2 ? `<p class="special-burst">${message}</p>` : ''}</section>`;
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
  const score = scoreForState();
  const expected = expectedBest(state.actualDraws);
  const comment = commentForScore(score, state.bestNumber);
  const registration = state.rankingRegistered
    ? '<p class="ranking-note">全国対戦へ登録しました。</p>'
    : `<div class="ranking-register"><p>${escapeHtml(DRAW_MODES[state.mode].name)}の全国対戦に登録</p><div><input id="ranking-name" maxlength="${rankingNameMaxLength(state.mode)}" placeholder="対戦名" aria-label="対戦名" ${submittingRanking ? 'disabled' : ''}><button class="utility-button" data-action="register-ranking" ${submittingRanking ? 'disabled' : ''}>${submittingRanking ? '登録中…' : '登録する'}</button></div><p class="form-error">${escapeHtml(rankingError)}</p></div>`;
  return `<section class="screen result-screen ${state.bestNumber === 1 ? 'jackpot' : ''}"><p class="eyebrow">RESULT</p><h2>リリイベ結果</h2><dl class="result-details"><div><dt>会場</dt><dd>${escapeHtml(state.venue.name)}</dd></div><div><dt>抽選モード</dt><dd>${escapeHtml(DRAW_MODES[state.mode].name)}${state.chanceMode ? ' / 確変発動' : ''}</dd></div>${state.venue.isReleaseDay ? '<div><dt>特別条件</dt><dd>リリース日当日 / 1回勝負</dd></div>' : ''}<div><dt>本日の最大抽選回数</dt><dd>${state.maxDrawsToday}回</dd></div><div><dt>実際に引いた回数</dt><dd>${state.actualDraws}回</dd></div><div><dt>引いた整理番号</dt><dd>${state.numbers.map(formatNumber).join(' / ')}</dd></div><div><dt>BEST</dt><dd class="best-number">${formatNumber(state.bestNumber)}</dd></div><div><dt>期待値</dt><dd>約${expected.toFixed(1)}番</dd></div><div><dt>判定</dt><dd>${scoreJudgment(score)}</dd></div></dl>${state.exitedEarly ? '<p class="exit-note">良番を確保したので撤退</p>' : ''}<div class="score-box"><span>SCORE</span><strong>${score}</strong><p>${escapeHtml(comment)}</p></div>${registration}<div class="actions"><button class="main-button" data-action="restart">もう一度リリイベに行く</button><button class="utility-button" data-action="ranking">全国対戦を見る</button></div></section>`;
}

function renderHistory() {
  const history = historyForMode(readHistory(), historyMode);
  const summary = summarizeHistory(history);
  const rows = history.length ? history.map((record) => `<li><span>${new Date(record.playedAt).toLocaleDateString('ja-JP')}</span><strong>${record.score}</strong><span>${escapeHtml(record.venue)} / BEST ${record.bestNumber}番</span></li>`).join('') : '<li class="empty-state">まだリリイベの記録がありません。</li>';
  const tabs = Object.values(DRAW_MODES).map((mode) => `<button class="ranking-mode-tab ${historyMode === mode.id ? 'active' : ''}" data-history-mode="${mode.id}">${escapeHtml(mode.name)}</button>`).join('');
  return `<section class="screen archive-screen"><p class="eyebrow">PLAY ARCHIVE</p><h2>過去成績</h2><div class="ranking-mode-tabs">${tabs}</div><p class="draw-instruction">${escapeHtml(DRAW_MODES[historyMode].name)}のプレイ記録</p><div class="history-summary"><div><span>プレイ</span><b>${summary.plays}</b></div><div><span>最高Score</span><b>${summary.bestScore}</b></div><div><span>最良整番</span><b>${summary.bestNumber === 101 ? '-' : `${summary.bestNumber}番`}</b></div></div><ul class="history-list">${rows}</ul>${history.length ? '<button class="utility-button" data-action="clear-history">このモードの履歴を消去</button>' : ''}</section>`;
}

function renderRanking() {
  const tabs = RANKING_MODES.map((mode) => `<button class="ranking-mode-tab ${rankingMode === mode.id ? 'active' : ''}" data-ranking-mode="${mode.id}">${escapeHtml(mode.name)}</button>`).join('');
  const content = rankingStatus === 'loading'
    ? '<p class="ranking-state">全国の整番を集計中……</p>'
    : rankingStatus === 'error'
      ? `<p class="form-error">${escapeHtml(rankingError)}</p><button class="utility-button" data-action="ranking">再読み込み</button>`
      : ranking.length
        ? `<ol class="ranking-list">${ranking.map((record) => `<li><span>${escapeHtml(record.player_name)}</span><strong>${record.score}</strong></li>`).join('')}</ol>`
        : '<p class="ranking-state">まだ記録がありません。最初のScoreを刻もう。</p>';
  const rankingLabel = RANKING_MODES.find((mode) => mode.id === rankingMode)?.name || rankingMode;
  return `<section class="screen archive-screen"><p class="eyebrow">NATIONAL SCORE MATCH</p><h2>スコア全国対戦</h2><div class="ranking-mode-tabs">${tabs}</div><p class="draw-instruction">${escapeHtml(rankingLabel)}部門。同じ対戦名は最高Scoreのみを掲載します。</p>${content}</section>`;
}

function saveCurrentPlay() {
  if (state.saved) return;
  state.saved = true;
  saveHistory({ playedAt: new Date().toISOString(), mode: state.mode, venue: state.venue.name, maxDrawsToday: state.maxDrawsToday, actualDraws: state.actualDraws, bestNumber: state.bestNumber, score: scoreForState(), exitedEarly: state.exitedEarly });
}

async function openRanking(mode = 'normal') {
  if (!state) state = { phase: 'ranking' };
  else state.phase = 'ranking';
  rankingMode = mode;
  rankingStatus = 'loading';
  rankingError = '';
  render();
  try {
    ranking = await fetchRanking(rankingMode);
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
  const error = rankingNameError(playerName, state.mode);
  if (error) { rankingError = error; render(); return; }
  submittingRanking = true;
  rankingError = '';
  render();
  try {
    await submitRanking(playerName, scoreForState(), state.mode);
    state.rankingRegistered = true;
  } catch (submitError) {
    rankingError = submitError.message || '全国対戦への登録に失敗しました。';
  }
  submittingRanking = false;
  render();
}

async function registerStoryRanking() {
  if (submittingRanking || state?.story?.finalScore == null) return;
  const playerName = String(document.querySelector('#story-ranking-name')?.value || '').trim();
  const error = rankingNameError(playerName, 'story');
  if (error) { rankingError = error; render(); return; }
  submittingRanking = true;
  rankingError = '';
  render();
  try {
    await submitRanking(playerName, state.story.finalScore, 'story');
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
  const { mode } = event.target.closest('[data-mode]')?.dataset || {};
  const { rankingMode: selectedRankingMode } = event.target.closest('[data-ranking-mode]')?.dataset || {};
  const { historyMode: selectedHistoryMode } = event.target.closest('[data-history-mode]')?.dataset || {};
  const { storyAction, storyValue } = event.target.closest('[data-story-action]')?.dataset || {};
  if (zone) { chooseDrawZone(zone); return; }
  if (ticket) { chooseTicket(Number(ticket)); return; }
  if (mode) { beginGame(mode); return; }
  if (selectedRankingMode) { openRanking(selectedRankingMode); return; }
  if (selectedHistoryMode) { historyMode = selectedHistoryMode; render(); return; }
  if (storyAction) { handleStoryAction(storyAction, storyValue); return; }
  if (!action) return;
  if (action === 'home') { clearTimeout(transitionTimer); state = undefined; rankingError = ''; render(); return; }
  if (action === 'start' || action === 'restart') startGame();
  if (action === 'start-story') startStory();
  if (action === 'watch') { state.phase = 'watching'; render(); delay(() => { state.phase = 'draw-count'; render(); }, 1200); }
  if (action === 'to-draw' || action === 'draw') beginDraw();
  if (action === 'stop') stopDrawing();
  if (action === 'history') { historyMode = state?.mode || 'normal'; state = { phase: 'history' }; render(); }
  if (action === 'ranking') openRanking(state?.mode || 'normal');
  if (action === 'register-ranking') registerRanking();
  if (action === 'clear-history' && window.confirm(`${DRAW_MODES[historyMode].name}の過去成績をすべて削除しますか？`)) { clearHistory(historyMode); render(); }
});

render();
