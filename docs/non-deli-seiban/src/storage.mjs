export const HISTORY_KEY = 'ririevent-go-history-v1';
const RANKING_PREFIX = '[RIRIEVENT-GO] ';
const RANKING_MODE_PREFIXES = {
  normal: RANKING_PREFIX,
  fever: '[RIRIEVENT-GO:FEVER] ',
  paradise: '[RIRIEVENT-GO:PARADISE] ',
  story: '[RIRIEVENT-GO:STORY] '
};
const SUPABASE_URL = 'https://knfznjurrjoozdwhkffm.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_lKNG7O9cPnR_9dV_9BDUxg__j6c5vEX';
const LEADERBOARD_LIST_RPC_ENDPOINT = `${SUPABASE_URL}/rest/v1/rpc/get_leaderboard`;
const LEADERBOARD_RPC_ENDPOINT = `${SUPABASE_URL}/rest/v1/rpc/submit_leaderboard_entry`;

export function readHistory(storage = globalThis.localStorage) {
  if (!storage) return [];
  try {
    const history = JSON.parse(storage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(history) ? history : [];
  } catch {
    return [];
  }
}

export function saveHistory(record, storage = globalThis.localStorage) {
  if (!storage) return;
  storage.setItem(HISTORY_KEY, JSON.stringify([record, ...readHistory(storage)].slice(0, 50)));
}

export function historyForMode(history, mode = 'normal') {
  return history.filter((record) => (record.mode || 'normal') === mode);
}

export function clearHistory(mode = 'normal', storage = globalThis.localStorage) {
  if (!storage) return;
  const remaining = readHistory(storage).filter((record) => (record.mode || 'normal') !== mode);
  if (remaining.length) storage.setItem(HISTORY_KEY, JSON.stringify(remaining));
  else storage.removeItem(HISTORY_KEY);
}

export function summarizeHistory(history) {
  return history.reduce((summary, record) => ({
    plays: summary.plays + 1,
    bestScore: Math.max(summary.bestScore, record.score),
    bestNumber: Math.min(summary.bestNumber, record.bestNumber),
    earlyExits: summary.earlyExits + (record.exitedEarly ? 1 : 0)
  }), { plays: 0, bestScore: 0, bestNumber: 101, earlyExits: 0 });
}

function rankingPrefix(mode = 'normal') {
  if (!RANKING_MODE_PREFIXES[mode]) throw new Error('不明な全国対戦モードです');
  return RANKING_MODE_PREFIXES[mode];
}

export function rankingNameMaxLength(mode = 'normal') {
  return 40 - rankingPrefix(mode).length;
}

export function rankingNameError(value, mode = 'normal') {
  const name = String(value || '').trim();
  if (!name) return '対戦名を入力してください';
  if (!/^[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z0-9 _.-]+$/u.test(name)) return '日本語・ローマ字・数字・スペースで入力してください';
  const width = [...name].reduce((sum, character) => sum + (character.codePointAt(0) <= 0x7f ? 1 : 2), 0);
  const availableWidth = rankingNameMaxLength(mode);
  if (width > availableWidth) return `全角${Math.floor(availableWidth / 2)}文字、または半角${availableWidth}文字以内で入力してください`;
  return '';
}

function headers() {
  return { apikey: SUPABASE_PUBLISHABLE_KEY, Authorization: `Bearer ${SUPABASE_PUBLISHABLE_KEY}` };
}

export function normalizeRanking(records, mode = 'normal') {
  const prefix = rankingPrefix(mode);
  const bestByName = new Map();
  records
    .filter((record) => String(record.player_name || '').startsWith(prefix))
    .forEach((record) => {
      const playerName = record.player_name.slice(prefix.length);
      const current = bestByName.get(playerName);
      if (!current || Number(record.score) > Number(current.score)) bestByName.set(playerName, { ...record, player_name: playerName });
    });
  return [...bestByName.values()].sort((left, right) => Number(right.score) - Number(left.score) || String(left.player_name).localeCompare(String(right.player_name), 'ja')).slice(0, 100);
}

export async function fetchRanking(mode = 'normal') {
  const response = await fetch(LEADERBOARD_LIST_RPC_ENDPOINT, { method: 'POST', headers: headers() });
  if (!response.ok) throw new Error(`全国対戦の取得に失敗しました (${response.status})`);
  return normalizeRanking(await response.json(), mode);
}

export async function submitRanking(playerName, score, mode = 'normal') {
  const prefix = rankingPrefix(mode);
  const ranking = await fetchRanking(mode);
  const existing = ranking.find((record) => record.player_name === playerName);
  if (existing && Number(existing.score) >= score) return { skipped: true };
  const response = await fetch(LEADERBOARD_RPC_ENDPOINT, {
    method: 'POST',
    headers: { ...headers(), 'Content-Type': 'application/json', Prefer: 'return=representation' },
    body: JSON.stringify({ p_player_name: `${prefix}${playerName}`, p_score: score })
  });
  if (!response.ok) throw new Error(`全国対戦への登録に失敗しました (${response.status})`);
  return response.json();
}
