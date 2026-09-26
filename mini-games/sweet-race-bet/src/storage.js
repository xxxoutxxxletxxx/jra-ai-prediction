export const HISTORY_KEY = 'sweet-race-bet-history-v1';
export const RANKING_KEY = 'sweet-race-bet-ranking-v1';
const SUPABASE_URL = 'https://knfznjurrjoozdwhkffm.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_lKNG7O9cPnR_9dV_9BDUxg__j6c5vEX';
const LEADERBOARD_ENDPOINT = `${SUPABASE_URL}/rest/v1/leaderboard`;

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

export function readRanking(storage = globalThis.localStorage) {
  if (!storage) return [];
  try {
    const value = JSON.parse(storage.getItem(RANKING_KEY) || '[]');
    return Array.isArray(value) ? value.sort((a, b) => b.finalMoney - a.finalMoney || new Date(a.playedAt) - new Date(b.playedAt)) : [];
  } catch {
    return [];
  }
}

export function saveRankingEntry(entry, storage = globalThis.localStorage) {
  if (!storage) return;
  const ranking = readRanking(storage).filter((record) => record.userName !== entry.userName);
  ranking.push(entry);
  ranking.sort((a, b) => b.finalMoney - a.finalMoney || new Date(a.playedAt) - new Date(b.playedAt));
  storage.setItem(RANKING_KEY, JSON.stringify(ranking.slice(0, 100)));
}

export function rankingNameError(value) {
  const name = String(value || '').trim();
  if (!name) return 'ユーザー名を入力してください';
  if (!/^[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z0-9 _.-]+$/u.test(name)) return '日本語・ローマ字・数字・スペースで入力してください';
  const width = [...name].reduce((sum, character) => sum + (character.codePointAt(0) <= 0x7f ? 1 : 2), 0);
  if (width > 40) return '全角20文字、または半角40文字以内で入力してください';
  return '';
}

function supabaseHeaders() {
  return {
    apikey: SUPABASE_PUBLISHABLE_KEY,
    Authorization: `Bearer ${SUPABASE_PUBLISHABLE_KEY}`
  };
}

export async function fetchLeaderboard() {
  const response = await fetch(`${LEADERBOARD_ENDPOINT}?select=id,player_name,score,created_at&order=score.desc,created_at.asc&limit=100`, { headers: supabaseHeaders() });
  if (!response.ok) throw new Error(`ランキング取得に失敗しました (${response.status})`);
  return response.json();
}

export async function submitLeaderboardEntry(playerName, score) {
  const response = await fetch(LEADERBOARD_ENDPOINT, {
    method: 'POST',
    headers: { ...supabaseHeaders(), 'Content-Type': 'application/json', Prefer: 'return=representation' },
    body: JSON.stringify({ player_name: playerName, score })
  });
  if (!response.ok) throw new Error(`ランキング登録に失敗しました (${response.status})`);
  return response.json();
}
