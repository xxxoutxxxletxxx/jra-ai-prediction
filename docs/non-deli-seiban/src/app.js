import { calculateScore, chooseDrawCount, chooseVenue, claimTicket, commentForScore, drawTicketCandidates, DRAW_MODES, expectedBest, scoreJudgment } from './engine.mjs';
import { clearHistory, fetchRanking, historyForMode, rankingNameError, rankingNameMaxLength, readHistory, saveHistory, submitRanking, summarizeHistory } from './storage.mjs';
import { ARRIVAL_OPTIONS, chooseAfterEvent, chooseStoryTicket, createStory, finishStory, FREE_TIME_EVENTS, playStoryPart, PREPARATION_OPTIONS, prepareStory, STORY_CONFIG, storyTitle, takeCheki, takeFreeTimeAction, travelToVenue, buyStoryTickets } from './story.mjs';

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
const delay = (callback, milliseconds) => { clearTimeout(transitionTimer); transitionTimer = setTimeout(callback, milliseconds); };
const formatNumber = (number) => `${number}番`;
const scoreDrawsForState = () => state.exitedEarly ? state.actualDraws : state.maxDrawsToday;
const scoreForState = () => calculateScore(scoreDrawsForState(), state.bestNumber, state.venue?.isReleaseDay === true);

function startGame() {
  state = { phase: 'mode-select' };
  render();
}

function startStory() {
  state = { phase: 'story', story: createStory() };
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
  const content = renderStoryContent(story);
  return `<section class="screen story-mode-screen"><div class="story-cityscape" aria-hidden="true"><i></i><i></i><i></i><i></i></div>${renderStoryHud(story)}<div class="story-content">${content}</div></section>`;
}

function renderStoryContent(story) {
  const event = story.latestEvent ? `<p class="story-event">${escapeHtml(story.latestEvent)}</p>` : '';
  if (story.phase === 'preparation') return `<p class="eyebrow">06:00 / AT HOME</p><h2>今日は、どこまで仕上げる？</h2><p class="story-lead">準備の長さは満足度に、会場への到着時刻は体力と整番に影響する。</p><div class="story-choice-grid">${PREPARATION_OPTIONS.map((option) => `<button class="story-choice" data-story-action="prepare" data-story-value="${option.minutes}"><strong>${option.minutes}分</strong><span>${option.label}</span><small>身支度をする</small></button>`).join('')}</div>`;
  if (story.phase === 'departure') {
    const available = ARRIVAL_OPTIONS.filter((option) => option.time >= story.time + STORY_CONFIG.travelMinutes);
    return `<p class="eyebrow">${formatStoryTime(story.time)} / DEPARTURE</p><h2>いつ会場へ着く？</h2>${event}<p class="story-lead">早く着くほど先頭に近づく。でも、体力は削られる。</p><div class="story-action-list">${available.map((option) => `<button class="story-action" data-story-action="travel" data-story-value="${option.time}"><strong>${option.label}</strong><span>${escapeHtml(option.note)}</span></button>`).join('')}</div>`;
  }
  if (story.phase === 'ticket-purchase') return `<p class="eyebrow">${formatStoryTime(story.time)} / SALES LINE</p><h2>${story.frontBonus ? '販売列の、いちばん前。' : '販売列に到着した。'}</h2>${event}<div class="story-ticket-purchase"><span>1部・2部セット</span><strong>3,000 COIN</strong><button class="main-button" data-story-action="buy-tickets">整理番号を引く</button></div>`;
  if (story.phase === 'ticket-1' || story.phase === 'ticket-2') {
    const part = story.phase === 'ticket-1' ? '1部' : '2部';
    return `<p class="eyebrow">TICKET DRAW / ${part}</p><h2>${part}の整理番号を選ぶ</h2><p class="story-lead">手に当たった3枚。今日の景色を選ぼう。</p><div class="story-ticket-grid">${story.ticketCandidates.map((number, index) => `<button class="story-ticket" data-story-action="ticket" data-story-value="${number}"><span>整理券 ${index + 1}</span><strong>${number}</strong><small>これを引く</small></button>`).join('')}</div>`;
  }
  if (story.phase === 'free-1' || story.phase === 'free-2') {
    const label = story.phase === 'free-1' ? '1部まで' : '2部まで';
    return `<p class="eyebrow">${formatStoryTime(story.time)} / FREE TIME</p><h2>${label}、何をする？</h2>${event}<p class="story-lead">時間・お金・体力を見ながら、次の行動を選ぶ。</p><div class="story-action-list">${FREE_TIME_EVENTS.map((entry) => `<button class="story-action story-event-choice" data-story-action="free" data-story-value="${entry.id}"><b>${entry.icon} ${escapeHtml(entry.name)}</b><span>${entry.duration}分 / ${entry.money ? `${Math.abs(entry.money).toLocaleString()}コイン` : '無料'}</span></button>`).join('')}</div>`;
  }
  if (story.phase === 'part-1' || story.phase === 'part-2') {
    const part = story.phase === 'part-1' ? 0 : 1;
    const label = part === 0 ? '1部' : '2部';
    return `<p class="eyebrow">${formatStoryTime(part === 0 ? STORY_CONFIG.firstAdmission : STORY_CONFIG.secondAdmission)} / PRIORITY ENTRY</p><h2>${label}、入場の時間。</h2>${event}<div class="story-part-card"><span>整理番号</span><strong>${story.tickets[part]}番</strong><p>${storyPosition(story.tickets[part])}。ステージが近づいてくる。</p></div><button class="main-button" data-story-action="play-part" data-story-value="${part}">${label}へ入場する</button>`;
  }
  if (story.phase === 'after-event') return `<p class="eyebrow">${formatStoryTime(story.time)} / AFTER THE SHOW</p><h2>今日、まだ帰れる？</h2>${event}<p class="story-lead">楽しかった。体力と財布は、まだ少しだけ残っている。</p><div class="story-after-actions"><button class="secondary-button" data-story-action="after" data-story-value="home">今日は帰る</button><button class="main-button" data-story-action="after" data-story-value="round">もう一つ現場を回す<br><small>3,000コイン</small></button></div>`;
  if (story.phase === 'cheki') return `<p class="eyebrow">EXTRA EVENT</p><h2>せっかくだから、チェキを撮る？</h2>${event}<div class="story-after-actions"><button class="secondary-button" data-story-action="finish-story">今日はここまで</button><button class="main-button" data-story-action="cheki">チェキを撮る<br><small>2,000コイン</small></button></div>`;
  const spent = STORY_CONFIG.initialMoney - story.money;
  const gameOver = story.phase === 'game-over';
  return `<p class="eyebrow">${gameOver ? 'GAME OVER' : 'DAY RESULT'}</p><h2>${gameOver ? '限界だった。' : storyTitle(story)}</h2><p class="story-result-copy">${escapeHtml(story.latestEvent)}</p><div class="story-result-score"><span>最終満足度</span><strong>${story.finalScore}</strong></div><dl class="story-result-details"><div><dt>残金</dt><dd>${story.money.toLocaleString()}コイン</dd></div><div><dt>総出費</dt><dd>${spent.toLocaleString()}コイン</dd></div><div><dt>残り体力</dt><dd>${story.stamina}</dd></div><div><dt>1部整理番号</dt><dd>${story.tickets[0]}番</dd></div><div><dt>2部整理番号</dt><dd>${story.tickets[1]}番</dd></div><div><dt>1部満足度</dt><dd>${story.partScores[0]}</dd></div><div><dt>2部満足度</dt><dd>${story.partScores[1]}</dd></div><div><dt>自由時間満足度</dt><dd>${story.freeTimeSatisfaction}</dd></div></dl><button class="main-button" data-action="start-story">もう一度ストーリーモードで遊ぶ</button>`;
}

function handleStoryAction(action, value) {
  const { story } = state;
  if (action === 'prepare') prepareStory(story, Number(value));
  if (action === 'travel') travelToVenue(story, Number(value));
  if (action === 'buy-tickets') buyStoryTickets(story);
  if (action === 'ticket') chooseStoryTicket(story, Number(value));
  if (action === 'free') takeFreeTimeAction(story, value);
  if (action === 'play-part') playStoryPart(story, Number(value));
  if (action === 'after') chooseAfterEvent(story, value);
  if (action === 'cheki') takeCheki(story);
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
  const tabs = Object.values(DRAW_MODES).map((mode) => `<button class="ranking-mode-tab ${rankingMode === mode.id ? 'active' : ''}" data-ranking-mode="${mode.id}">${escapeHtml(mode.name)}</button>`).join('');
  const content = rankingStatus === 'loading'
    ? '<p class="ranking-state">全国の整番を集計中……</p>'
    : rankingStatus === 'error'
      ? `<p class="form-error">${escapeHtml(rankingError)}</p><button class="utility-button" data-action="ranking">再読み込み</button>`
      : ranking.length
        ? `<ol class="ranking-list">${ranking.map((record) => `<li><span>${escapeHtml(record.player_name)}</span><strong>${record.score}</strong></li>`).join('')}</ol>`
        : '<p class="ranking-state">まだ記録がありません。最初のScoreを刻もう。</p>';
  return `<section class="screen archive-screen"><p class="eyebrow">NATIONAL SCORE MATCH</p><h2>スコア全国対戦</h2><div class="ranking-mode-tabs">${tabs}</div><p class="draw-instruction">${escapeHtml(DRAW_MODES[rankingMode].name)}部門。同じ対戦名は最高Scoreのみを掲載します。</p>${content}</section>`;
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
