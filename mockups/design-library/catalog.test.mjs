import {test} from 'node:test';
import assert from 'node:assert/strict';
import {screens,filterScreens} from './catalog.mjs';

test('inventory covers app flows and keeps undecided screens distinguishable',()=>{
 for(const id of ['entry','login','register','save-id','lost','guest-home','home','practice','study','name','picker','question','correct','incorrect','timeout','stop','results','log','log-empty','ranked','leaderboard','profile','tickets'])assert.ok(screens.some(s=>s.id===id),id);
 assert.equal(new Set(screens.map(s=>s.id)).size,screens.length);
 for(const screen of screens){assert.ok(screen.source);assert.ok(['existing','approved','concept'].includes(screen.status));}
 for(const id of ['ranked','leaderboard','profile','tickets'])assert.equal(screens.find(s=>s.id===id).status,'concept');
});
test('filters combine source category and case-insensitive user search',()=>{
 assert.ok(filterScreens('  LOGIN  ','all').some(s=>s.id==='login'));
 assert.ok(filterScreens('','existing').length>0);
 assert.ok(filterScreens('','existing').every(s=>s.status==='existing'));
 assert.equal(filterScreens('<script>','all').length,0);
 assert.ok(filterScreens('','all').length===screens.length);
});
