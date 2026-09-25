import { acceptRescue, createGame, placeBet, settleBet, settleRescue, shouldGameOverAfterRescue, shouldTriggerRescue, simulateRace, titleForMoney } from './engine.js';
import { clearHistory, readHistory, saveGameResult, summarizeHistory } from './storage.js';

const app = document.querySelector('#app');
const confetti = document.querySelector('.confetti-layer');
let game = null;
let screen = 'start';
let selectedHorse = null;
let selectedAmount = 100;
let lastResult = null;

const coins = (value) => `${Math.round(value).toLocaleString('ja-JP')}コイン`;
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const horseIcon = (horse, className = '') => `<span class="horse-icon ${className}" style="--coat:${horse.icon.coat};--mane:${horse.icon.mane};--bib:${horse.icon.bib};--bib-text:${horse.icon.bibText}"><i class="neck"></i><i class="ear ear-back"></i><i class="ear ear-front"></i><i class="cap"></i><i class="mane"></i><i class="leg leg-back"></i><i class="leg leg-front"></i><i class="eye eye-near eye-${horse.icon.face}"></i><i class="muzzle"></i><i class="face face-${horse.icon.face}"></i><i class="bib">${horse.number}</i></span>`;
const header = (showMoney = true) => `<header class="topbar"><div class="brand-block">${screen !== 'start' ? '<button class="header-home" data-action="home">← スタートに戻る</button>' : ''}<div class="brand">🍬 スイート<span>レース</span>BET</div></div><div class="topbar-actions">${showMoney && game ? `<div class="money-pill">軍資金 ${coins(game.money)}</div>` : ''}</div></header>`;
const panel = (content, className = '') => `<section class="panel ${className}">${content}</section>`;

function render() {
  const views = { start: renderStart, history: renderHistory, bet: renderBet, race: renderRace, result: renderResult, rescue: renderRescueOffer, final: renderFinal, special: renderSpecialEnding };
  app.innerHTML = `${header(screen !== 'start' && screen !== 'history' && screen !== 'final')}${views[screen]()}`;
}

function renderStart() {
  return `<section class="hero"><span class="kicker">ぜんぶ架空のスイーツ競馬</span><h1>スイート<br>レース<small>BET</small></h1><p class="lede">かわいい8頭のスイーツホースから、今日の主役を予想しよう。軍資金はゲーム内の10,000コイン。5レースを遊んで、最後に笑うのは誰？</p><div class="actions"><button class="primary" data-action="start">ゲームスタート</button><button class="secondary" data-action="history">過去成績</button></div><p class="notice">遊び方：馬の情報とオッズを見て1頭にBET。的中すればオッズ分の払戻です。</p></section>`;
}

function renderHistory() {
  const history = readHistory();
  const summary = summarizeHistory(history);
  const rows = history.length ? history.map((record) => `<tr><td>${escapeHtml(new Date(record.playedAt).toLocaleString('ja-JP'))}</td><td>${coins(record.finalMoney)}</td><td>${record.profit >= 0 ? '+' : ''}${coins(record.profit)}</td><td>${record.betCount} / ${record.hitCount}</td><td>${record.betCount ? Math.round(record.hitCount / record.betCount * 100) : 0}%</td><td>${record.rescueUsed ? escapeHtml(record.rescueStatusLabel || '利用あり') : 'なし'}</td></tr>`).join('') : `<tr><td colspan="6" class="empty">まだプレイ記録がありません</td></tr>`;
  return `${panel(`<div class="section-title"><div><span class="kicker">ARCHIVE</span><h2>過去成績</h2></div><button class="ghost" data-action="home">スタートへ</button></div><div class="stat-grid"><div class="stat"><span>プレイ回数</span><b>${summary.games}</b></div><div class="stat stat-highlight"><span>最高的中率</span><b>${Math.round(summary.bestHitRate * 100)}%</b></div><div class="stat"><span>歴代最高所持金</span><b>${coins(summary.bestMoney)}</b></div><div class="stat"><span>歴代最大払戻</span><b>${coins(summary.maxPayout)}</b></div></div><div style="overflow:auto"><table class="history-table"><thead><tr><th>プレイ日時</th><th>最終所持金</th><th>収支</th><th>BET / 的中</th><th>的中率</th><th>救済イベント</th></tr></thead><tbody>${rows}</tbody></table></div><div class="actions" style="margin-top:20px"><button class="ghost" data-action="clear-history">過去成績をリセット</button></div>`)}`;
}

function raceInfo(race) { return `<div class="race-info"><div class="info-item"><span>開催月</span><b>${race.month}月</b></div><div class="info-item"><span>開催場</span><b>${race.venue}</b></div><div class="info-item"><span>距離</span><b>${race.distance}m</b></div><div class="info-item"><span>馬場</span><b>${race.track}</b></div></div>`; }
function horseCard(horse) { return `<button class="horse-card ${selectedHorse === horse.number ? 'selected' : ''}" data-horse="${horse.number}" style="--bib:${horse.icon.bib};--bib-text:${horse.icon.bibText}">${horse.number ? `<span class="horse-number">${horse.number}</span>` : ''}${horseIcon(horse)}<span class="horse-main"><span class="horse-name">${escapeHtml(horse.name)}</span><span class="horse-meta">${horse.age}歳 ${horse.gender} ・ 前走 ${horse.previousFinish}着</span><span class="horse-form">${escapeHtml(horse.conditionComment)}</span></span><span class="odds">${horse.odds.toFixed(1)}<small>単勝</small></span></button>`; }

function renderBet() {
  const race = game.currentRace;
  const selected = race.horses.find((horse) => horse.number === selectedHorse);
  return `${panel(`<div class="section-title"><div><span class="kicker">RACE ${game.raceNumber} / 5</span><h2>出走馬をチェック</h2></div><span class="money-pill">${coins(game.money)}</span></div>${raceInfo(race)}<div class="horse-grid">${race.horses.map(horseCard).join('')}</div><div class="bet-panel"><h3>${selected ? `${escapeHtml(selected.name)}にBET` : 'まずは馬を選ぼう'}</h3><div class="bet-controls"><button class="chip ${selectedAmount === 100 ? 'active' : ''}" data-amount="100">100コイン</button><button class="chip ${selectedAmount === 500 ? 'active' : ''}" data-amount="500">500コイン</button><button class="chip ${selectedAmount === 1000 ? 'active' : ''}" data-amount="1000">1,000コイン</button><button class="chip ${selectedAmount === 2000 ? 'active' : ''}" data-amount="2000">2,000コイン</button><button class="chip ${selectedAmount === 5000 ? 'active' : ''}" data-amount="5000">5,000コイン</button><button class="chip ${selectedAmount === 10000 ? 'active' : ''}" data-amount="10000" ${game.money < 10000 ? 'disabled' : ''}>10,000コイン</button><button class="chip ${selectedAmount === game.money ? 'active' : ''}" data-amount="max">MAX</button><input class="amount-input" id="amount" type="number" min="1" max="${game.money}" value="${selectedAmount}" aria-label="BET額"></div><p class="notice ${selected && selectedAmount > game.money ? 'error' : ''}">${selected ? `${escapeHtml(selected.name)}に${coins(selectedAmount)} BET` : 'BETなしでレースを見ることもできます。'}</p><div class="actions"><button class="primary" data-action="confirm-bet">BETしてレースへ</button><button class="ghost" data-action="skip-bet">BETせず見る</button></div></div>`)}`;
}

function renderRace() {
  const race = game.resolvedRace;
  return `${panel(`<div class="section-title"><div><span class="kicker">RACE ${game.raceNumber} / 5</span><h2>${escapeHtml(race.venue)} ${race.distance}m</h2></div><span class="race-live">LIVE</span></div><div class="race-banner" id="race-banner">まもなくスタート！</div><div class="race-track">${race.horses.map((horse) => `<div class="track-lane"><div class="runner" data-runner="${horse.number}">${horseIcon(horse)}</div></div>`).join('')}</div><div class="race-commentary" id="race-commentary">ゲートが開く、その瞬間を待とう！</div>`)}`;
}

function renderResult() {
  const race = game.resolvedRace;
  const settlement = lastResult;
  const betHorse = game.currentBet && race.horses.find((horse) => horse.number === game.currentBet.horseNumber);
  const message = !game.currentBet ? '<h2>今回は見送りました</h2><p>じっくりレースを楽しみました。</p>' : settlement.hit ? `<h2>🎉 的中！！ 🎉</h2><p>${escapeHtml(betHorse.name)}が1着！ ${coins(game.currentBet.amount)} → ${coins(settlement.payout)}</p>` : `<h2>ざんねん……！</h2><p>次のレースで取り返そう！</p>`;
  return `${panel(`<div class="section-title"><div><span class="kicker">RESULT</span><h2>第${game.raceNumber}レース 結果</h2></div></div><div class="payout ${settlement.hit ? 'hit' : ''}">${message}</div><div class="result-list">${race.horses.map((horse) => `<div class="result-row ${horse.finalPosition === 1 ? 'winner' : ''}"><span class="position">${horse.finalPosition}着</span>${horseIcon(horse)}<strong>${escapeHtml(horse.name)}</strong><span>${horse.odds.toFixed(1)}倍</span></div>`).join('')}</div><div class="actions" style="margin-top:22px"><button class="primary" data-action="next">${game.raceNumber === 5 ? '最終リザルトへ' : `第${game.raceNumber + 1}レースへ`}</button></div>`)}`;
}

function renderRescueOffer() {
  return `${panel(`<div class="rescue-screen"><div class="mystery-mark">？？？</div><div class="mystery-man" aria-hidden="true"><span class="mystery-hat">★</span><span class="mystery-face">⌐■‿■</span><span class="mystery-bag">C</span></div><span class="kicker">CONTINUE EVENT</span><h2>謎の男があらわれた！</h2><p>「おやおや……全部なくなっちゃったのかい？」</p><p>「しょうがないなぁ。今回だけ、20,000コイン貸してあげよう！」</p><div class="actions"><button class="primary" data-action="accept-rescue">20,000コイン借りる</button><button class="ghost" data-action="decline-rescue">今回はやめておく</button></div></div>`)}`;
}

function renderSpecialEnding() {
  const isGameOver = game.rescueStatus === 'gameover';
  const title = isGameOver ? 'GAME OVER' : game.rescueStatus === 'repaid' ? '返却成功！' : '返却失敗！';
  const text = isGameOver ? 'おーい！！全部使っちゃったのか～～～！？' : game.rescueStatus === 'repaid' ? 'へへっ、ちゃんと返してくれるとはね！ またどこかで会おう！' : '待て～～～！20,000コイン～～～！';
  return `${panel(`<div class="chase-ending"><span class="kicker">${isGameOver ? 'GAME OVER' : 'SPECIAL RESULT'}</span><h2>${title}</h2><div class="chase-stage" aria-label="あなたと謎の男の追いかけっこ"><span class="chase-line line-one"></span><span class="chase-line line-two"></span><div class="person runner-character"><span class="person-label">あなた</span><span class="person-head"></span><span class="person-body"></span><span class="person-arm arm-front"></span><span class="person-arm arm-back"></span><span class="person-leg leg-front"></span><span class="person-leg leg-back"></span></div><div class="person mystery-chaser"><span class="person-label">謎の男</span><span class="person-head sunglasses"></span><span class="person-body suit"></span><span class="person-arm arm-front"></span><span class="person-arm arm-back"></span><span class="person-leg leg-front"></span><span class="person-leg leg-back"></span><span class="person-bag">C</span></div></div><p>${text}</p><p>${isGameOver ? 'うわ～～～～！！' : game.rescueStatus === 'repaid' ? 'また遊ぼうね！' : '次は計画的に遊ぼう！'}</p><div class="actions"><button class="primary" data-action="start">もう一度遊ぶ</button><button class="secondary" data-action="history">過去成績</button></div></div>`)}`;
}

function renderFinal() {
  const profit = game.money - game.initialMoney;
  return `${panel(`<div class="hero" style="box-shadow:none;border:0;background:transparent;padding:30px 10px"><span class="kicker">GAME CLEAR</span><h2>${titleForMoney(game.money, game.rescueStatus)}</h2><p class="lede">5レースおつかれさまでした。あなたの最終成績です。</p><div class="stat-grid"><div class="stat"><span>初期資金</span><b>${coins(game.initialMoney)}</b></div><div class="stat"><span>最終所持金</span><b>${coins(game.money)}</b></div><div class="stat"><span>収支</span><b>${profit >= 0 ? '+' : ''}${coins(profit)}</b></div><div class="stat"><span>BET回数</span><b>${game.betCount}</b></div><div class="stat"><span>的中回数 / 的中率</span><b>${game.hitCount} / ${game.betCount ? Math.round(game.hitCount / game.betCount * 100) : 0}%</b></div><div class="stat"><span>最大払戻</span><b>${coins(game.maxPayout)}</b></div></div><div class="result-list">${game.records.map((record) => `<div class="result-row"><strong>第${record.raceNumber}R</strong><span>${record.bet ? escapeHtml(record.bet.name) : '見送り'}</span><span>${record.winner}</span><span>${record.hit ? `+${coins(record.payout)}` : '-'}</span></div>`).join('')}</div><div class="actions" style="margin-top:22px"><button class="primary" data-action="start">もう一度遊ぶ</button><button class="secondary" data-action="history">過去成績</button></div></div>`)}`;
}

function startGame() { game = createGame(Math.random); screen = 'bet'; selectedHorse = null; selectedAmount = 100; render(); }
function confirmBet(skip = false) {
  const amountInput = document.querySelector('#amount');
  if (!skip) selectedAmount = Number(amountInput?.value || selectedAmount);
  const result = skip ? { ok: true, money: game.money, bet: null } : placeBet(game.money, selectedHorse, selectedAmount);
  if (!result.ok) { document.querySelector('.notice').textContent = result.reason; document.querySelector('.notice').classList.add('error'); return; }
  game.money = result.money; game.currentBet = result.bet; game.resolvedRace = simulateRace(game.currentRace, Math.random); screen = 'race'; render(); animateRace();
}
function animateRace() {
  const runners = [...document.querySelectorAll('[data-runner]')];
  const { horses } = game.resolvedRace;
  const orders = [
    horses.map((horse) => horse.number),
    horses.slice().sort((a, b) => ((a.number * 3) % 8) - ((b.number * 3) % 8)).map((horse) => horse.number),
    horses.slice().sort((a, b) => ((a.number + 5) % 8) - ((b.number + 5) % 8)).map((horse) => horse.number),
    horses.slice().sort((a, b) => a.finalPosition - b.finalPosition).map((horse) => horse.number)
  ];
  const stages = [
    [0, 'スタート！ 8頭が一斉に飛び出した！', '各馬きれいなスタートです。'],
    [950, '第1コーナー、先頭争いが激しい！', '前と後ろが一気に入れ替わっています！'],
    [2200, '向こう正面、横一線の大接戦！', '先頭集団が3頭に絞られました！'],
    [3550, '残り200m！ ここからが勝負！', '外から一気に伸びる馬がいる！'],
    [4850, 'ゴールイン！', '最後まで見逃せない大接戦でした！']
  ];
  const move = (stageIndex, text, commentary) => {
    const order = orders[Math.min(stageIndex, orders.length - 1)];
    const progress = [8, 25, 48, 71, 88][stageIndex];
    const spread = [2, 4, 4, 3, 1.2][stageIndex];
    order.forEach((number, rank) => {
      const runner = document.querySelector(`[data-runner="${number}"]`);
      if (runner) runner.style.left = `${progress + rank * spread}%`;
    });
    document.querySelector('#race-banner').textContent = text;
    document.querySelector('#race-commentary').textContent = commentary;
  };
  stages.forEach(([delay, text, commentary], index) => setTimeout(() => move(index, text, commentary), delay));
  setTimeout(() => {
    horses.forEach((horse) => {
      const runner = document.querySelector(`[data-runner="${horse.number}"]`);
      runner.style.left = `${90 + (9 - horse.finalPosition) * 0.8}%`;
    });
  }, 5050);
  setTimeout(revealResult, 5900);
}
function revealResult() { lastResult = settleBet(game.money, game.currentBet, game.resolvedRace); game.money = lastResult.money; game.betCount += game.currentBet ? 1 : 0; game.hitCount += lastResult.hit ? 1 : 0; game.maxPayout = Math.max(game.maxPayout, lastResult.payout); const winner = game.resolvedRace.horses.find((horse) => horse.finalPosition === 1); game.records.push({ raceNumber: game.raceNumber, bet: game.currentBet ? { name: game.currentRace.horses.find((horse) => horse.number === game.currentBet.horseNumber).name, amount: game.currentBet.amount } : null, winner: winner.name, hit: lastResult.hit, payout: lastResult.payout }); screen = 'result'; render(); if (lastResult.hit) { confetti.classList.add('active'); setTimeout(() => confetti.classList.remove('active'), 1500); } }
function saveCurrentResult() { saveGameResult({ playedAt: new Date().toISOString(), finalMoney: game.money, profit: game.money - game.initialMoney, betCount: game.betCount, hitCount: game.hitCount, maxPayout: game.maxPayout, rescueUsed: game.rescueUsed, rescueStatusLabel: game.rescueStatus === 'repaid' ? '20,000コイン返却成功' : game.rescueStatus === 'failed' ? '返却失敗' : game.rescueStatus === 'gameover' ? '救済資金も使い切ってGAME OVER' : 'なし' }); }
function nextRace() {
  if (game.raceNumber === 5) {
    const settlement = settleRescue(game.money, game.borrowedAmount);
    game.money = settlement.money;
    game.rescueStatus = settlement.rescueStatus || game.rescueStatus;
    saveCurrentResult();
    if (game.borrowedAmount && game.rescueStatus === 'failed') { screen = 'special'; render(); return; }
    screen = 'final'; render(); return;
  }
  game.raceNumber += 1;
  if (shouldGameOverAfterRescue(game.money, game.raceNumber, game.rescueUsed)) { game.rescueStatus = 'gameover'; saveCurrentResult(); screen = 'special'; render(); return; }
  if (shouldTriggerRescue(game.money, game.raceNumber, game.rescueUsed)) { screen = 'rescue'; render(); return; }
  game.currentRace = createGame(Math.random).currentRace; game.currentBet = null; selectedHorse = null; selectedAmount = Math.min(100, game.money); screen = 'bet'; render();
}
function acceptRescueOffer() { Object.assign(game, acceptRescue(game.money)); game.currentRace = createGame(Math.random).currentRace; game.currentBet = null; selectedHorse = null; selectedAmount = 100; screen = 'bet'; render(); }
function declineRescueOffer() { game.rescueUsed = true; game.rescueStatus = 'gameover'; saveCurrentResult(); screen = 'special'; render(); }

app.addEventListener('click', (event) => {
  const actionTarget = event.target.closest('[data-action]');
  const horseTarget = event.target.closest('[data-horse]');
  const amountTarget = event.target.closest('[data-amount]');
  const { action } = actionTarget?.dataset || {};
  const { horse } = horseTarget?.dataset || {};
  const { amount } = amountTarget?.dataset || {};
  if (horse) { selectedHorse = Number(horse); render(); return; }
  if (amount) { selectedAmount = amount === 'max' ? game.money : Number(amount); render(); return; }
  if (action === 'start') startGame();
  if (action === 'history') { screen = 'history'; render(); }
  if (action === 'home') { screen = 'start'; render(); }
  if (action === 'confirm-bet') confirmBet();
  if (action === 'skip-bet') confirmBet(true);
  if (action === 'reveal-result') revealResult();
  if (action === 'next') nextRace();
  if (action === 'accept-rescue') acceptRescueOffer();
  if (action === 'decline-rescue') declineRescueOffer();
  if (action === 'clear-history' && window.confirm('過去成績をすべて削除しますか？')) { clearHistory(); render(); }
});
app.addEventListener('input', (event) => { if (event.target.id === 'amount') selectedAmount = Number(event.target.value); });
render();
