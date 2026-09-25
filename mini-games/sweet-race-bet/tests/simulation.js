import { generateRace, simulateRace } from '../src/engine.js';

const races = 10000;
const wins = Array(8).fill(0);
const oddsBuckets = new Map([['1.4-3.9', [0, 0]], ['4.0-7.9', [0, 0]], ['8.0+', [0, 0]]]);
let oddsTotal = 0;
for (let index = 0; index < races; index += 1) {
  const result = simulateRace(generateRace(Math.random), Math.random);
  const winner = result.horses.find((horse) => horse.finalPosition === 1);
  wins[winner.number - 1] += 1;
  for (const horse of result.horses) {
    oddsTotal += horse.odds;
    const key = horse.odds < 4 ? '1.4-3.9' : horse.odds < 8 ? '4.0-7.9' : '8.0+';
    oddsBuckets.get(key)[1] += 1;
    if (horse.finalPosition === 1) oddsBuckets.get(key)[0] += 1;
  }
}
console.log(JSON.stringify({ races, winRateByNumber: wins.map((value) => Number((value / races).toFixed(4))), averageOdds: Number((oddsTotal / (races * 8)).toFixed(2)), oddsBuckets: Object.fromEntries([...oddsBuckets].map(([key, [winsInBucket, count]]) => [key, { count, winRate: Number((winsInBucket / count).toFixed(4)) }])) }, null, 2));
