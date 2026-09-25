export const HISTORY_KEY = 'sweet-race-bet-history-v1';

export function readHistory(storage = globalThis.localStorage) {
  if (!storage) return [];
  try {
    const value = JSON.parse(storage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

export function saveGameResult(result, storage = globalThis.localStorage) {
  if (!storage) return;
  const history = readHistory(storage);
  history.unshift(result);
  storage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 50)));
}

export function clearHistory(storage = globalThis.localStorage) {
  storage?.removeItem(HISTORY_KEY);
}

export function summarizeHistory(history) {
  return history.reduce((summary, game) => {
    const hitRate = game.betCount ? game.hitCount / game.betCount : 0;
    return {
      games: summary.games + 1,
      bestHitRate: Math.max(summary.bestHitRate, hitRate),
      bestMoney: Math.max(summary.bestMoney, game.finalMoney),
      maxPayout: Math.max(summary.maxPayout, game.maxPayout)
    };
  }, { games: 0, bestHitRate: 0, bestMoney: 0, maxPayout: 0 });
}
