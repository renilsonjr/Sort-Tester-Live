import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const paths = ['src/quiz.js', 'src/i18n.js', 'src/shiftLog.js', 'src/questions.js', 'src/decks.js', 'src/belts.js', 'src/clock.js', 'src/destination.js'];
const { modules, cleanup } = await loadAppModules(paths);
after(cleanup);
const [quiz, i18n, shiftLog, questions, decks, belts, clocks, destination] = modules;
const { formatDestinationLabel } = destination;
const plusOne = questions.COMMON_CORE.find(card => card.id === 'destination-plus-one-gnd');
const ordinary = { ...plusOne, id: 'ordinary-control', destinationModifier: undefined, belt: 'ORANGE', why: 'Historical ordinary explanation.' };
const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8')
  .replace(/^import .+;\r?\n/gm, '').replace(/\nshowStart\(\);\s*$/, '');

// Only browser I/O is substituted: renderers, localization, recording and log
// serialization run unchanged. Workbook assertions cover rows, not a download.
function appHarness(values = new Map()) {
  let markup = '';
  let view;
  let frame;
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  function node(dataset = {}) {
    const handlers = new Map();
    return {
      dataset, isConnected: true, classList: { contains: () => false, toggle() {} },
      addEventListener: (event, handler) => handlers.set(event, handler),
      click() { handlers.get('click')?.(); }, focus() {}, setAttribute() {},
      querySelectorAll: () => [],
    };
  }
  function newView() {
    const nodes = new Map();
    const result = node();
    const languages = ['en', 'es'].map(language => node({ language }));
    result.querySelectorAll = selector => selector === '[data-language]' ? languages : [];
    result.querySelector = selector => {
      if (!nodes.has(selector)) nodes.set(selector, node());
      return nodes.get(selector);
    };
    result.languages = languages;
    return result;
  }
  const document = {
    documentElement: {}, hidden: false, addEventListener() {},
    getElementById: () => ({ replaceChildren() {} }),
    createElement: () => ({
      set innerHTML(value) { markup = value; view = newView(); },
      get content() { return { firstElementChild: view }; },
    }),
  };
  const XLSX = {
    utils: {
      json_to_sheet: (rows, options) => ({ rows, headers: options.header }),
      aoa_to_sheet: rows => ({ rows: [], headers: rows[0] }),
      book_new: () => ({}), book_append_sheet: (book, sheet, name) => { book[name] = sheet; },
    },
    write: book => book,
  };
  const context = {
    ...quiz, ...i18n, ...shiftLog, ...questions, ...decks, ...belts, ...clocks, ...destination,
    document, localStorage: storage, window: { scrollTo() {}, XLSX },
    requestAnimationFrame: callback => { frame = callback; return 1; }, cancelAnimationFrame() {},
    clearTimeout() {}, setTimeout: () => 1,
  };
  const evaluate = expression => runInNewContext(expression, context);
  evaluate(source);
  return {
    evaluate, values, get markup() { return markup; }, get view() { return view; },
    setRun(card) { context.testCard = card; evaluate("run = createRun({ name: 'Fictional test', cards: [testCard] });"); },
    tickExpired() { evaluate('clock = { remaining: () => 0, expired: () => true };'); frame(); },
  };
}

// Dropping the formatter or confusing destination with routing must fail here.
test('destination plus-one never changes the routing code', () => {
  assert.equal(typeof formatDestinationLabel, 'function');
  assert.equal(formatDestinationLabel('Ground', '+1'), 'Ground +1');
  assert.equal(formatDestinationLabel('Ground'), 'Ground');
  const run = quiz.createRun({ name: '', cards: [plusOne] });
  const response = quiz.answerCard(run, 'PURPLE', 1000);
  assert.equal(response.code, '109');
  assert.equal(response.destinationModifier, '+1');
  assert.equal(response.referenceVersion, 'twilight-2026-11-08-r1');
});

for (const outcome of ['correct', 'wrong', 'timeout']) test(`${outcome} records preserve the actual card metadata`, () => {
  const run = quiz.createRun({ name: '', cards: [plusOne] });
  const response = outcome === 'timeout' ? quiz.timeoutCard(run) : quiz.answerCard(run, outcome === 'correct' ? 'PURPLE' : 'ORANGE', 800);
  assert.equal(response.outcome, outcome);
  assert.equal(response.svc, 'GND');
  assert.equal(response.code, '109');
  assert.equal(response.destinationModifier, '+1');
  assert.equal(response.referenceVersion, plusOne.referenceVersion);
});

test('real quiz render and language toggle retain the destination marker', () => {
  const app = appHarness(); app.setRun(plusOne); app.evaluate('showCard();');
  assert.match(app.markup, /Ground \+1 &middot; NY/);
  assert.match(app.markup, /<div class="p-code">109<\/div>/);
  app.view.languages[1].click();
  assert.equal(app.view.querySelector('.p-line').textContent, 'Terrestre +1 · NY');
  assert.equal(app.evaluate('run.seconds'), 15);
});

for (const outcome of ['wrong', 'timeout']) test(`${outcome} destination survives feedback, saved reload and workbook rows`, () => {
  const app = appHarness(); app.setRun(plusOne); app.evaluate('showCard();');
  if (outcome === 'timeout') app.tickExpired();
  else app.evaluate("showFeedback(answerCard(run, 'ORANGE', 800));");
  assert.match(app.markup, /Ground \+1 &middot; NY/);
  assert.match(app.markup, /destination.*\+1.*PURPLE/i);
  app.view.languages[1].click();
  assert.match(app.markup, /Terrestre \+1 &middot; NY/);
  assert.match(app.markup, /destino.*\+1.*PURPLE/i);
  app.evaluate('showResults();');
  assert.match(app.markup, /Terrestre \+1 &middot; NY &middot; 109/);
  const reloaded = appHarness(app.values); reloaded.evaluate('showLog();');
  assert.match(reloaded.markup, /Terrestre \+1 &middot; NY &middot; 109/);
  const response = JSON.parse(app.values.get('sortTest.shiftLog.v1'))[0].missed[0];
  assert.equal(response.destinationModifier, '+1');
  assert.equal(response.referenceVersion, 'twilight-2026-11-08-r1');
  const row = reloaded.evaluate('buildWorkbook(log.all())').Missorts.rows[0];
  assert.equal(row.Service, 'Terrestre +1');
  assert.equal(row['Routing code'], '109');
  assert.equal(row.Outcome, outcome);
});

test('legacy saved responses retain historical fields and ordinary labels', () => {
  const legacy = { svc: 'GND', state: 'NY', code: '109', correctBelt: 'ORANGE', why: 'Historical ordinary explanation.', outcome: 'wrong', answered: 'BLUE', elapsedMs: 800 };
  const entry = { name: '', total: 1, correct: 0, totalMs: 800, takenAt: 1700000000000, missed: [legacy] };
  const values = new Map([['sortTest.shiftLog.v1', JSON.stringify([entry])]]);
  const app = appHarness(values); const before = values.get('sortTest.shiftLog.v1');
  app.evaluate('showLog();');
  assert.match(app.markup, /Ground &middot; NY &middot; 109/);
  const row = app.evaluate('buildWorkbook(log.all())').Missorts.rows[0];
  assert.equal(row.Service, 'Ground'); assert.equal(row['Routing code'], '109');
  assert.equal(values.get('sortTest.shiftLog.v1'), before);
  app.setRun(ordinary); app.evaluate("showFeedback(answerCard(run, 'BLUE', 800));");
  assert.match(app.markup, /Historical ordinary explanation\./);
});

test('bilingual modifier explanations precede generic and routing-ending branches', () => {
  const language = i18n.createLanguage();
  for (const code of ['109', '109 2S']) {
    const response = { ...plusOne, code, why: 'Stale generic explanation.' };
    assert.match(language.explanation(response), /destination.*\+1.*PURPLE/i);
    language.set('es'); assert.match(language.explanation(response), /destino.*\+1.*PURPLE/i); language.set('en');
  }
  language.set('es');
  assert.match(language.explanation({ ...ordinary, code: '109 2S' }), /2S.*BLUE/);
  assert.match(language.explanation({ ...ordinary, code: '150 1S' }), /1S.*PURPLE/);
});

test('Home renders Ground-only NY GOLD and correct air-service guidance in both languages', () => {
  const app = appHarness(); app.evaluate('showStart();');
  assert.match(app.markup, /<p>Ground<\/p>/);
  assert.match(app.markup, /2 Day Air and 3 Day Select.*ORANGE.*Next Day Air.*PURPLE/);
  app.view.languages[1].click();
  assert.match(app.markup, /<p>Terrestre<\/p>/);
  assert.match(app.markup, /Aéreo 2 días y Select 3 días.*ORANGE.*Aéreo 1 día.*PURPLE/);
});

test('ordinary picker shows selected run sizes without changing deck grouping', () => {
  const app = appHarness(); app.evaluate("showDeckPicker('');");
  for (const [id, count] of [['common-twilight-1', 14], ['common-twilight-2', 14], ['mixed-missorts', 16]]) {
    const card = app.markup.match(new RegExp(`data-deck="${id}"[\\s\\S]*?<span class="dmeta">([^<]+)`));
    assert.equal(card?.[1], `${count} cards · 15s each`);
    assert.ok(app.markup.indexOf(`data-deck="${id}"`) > app.markup.indexOf('Current quizzes · Twilight'));
  }
});


test('all four base services keep translated destination labels separate from workbook routes', () => {
  for (const [svc, english, spanish] of [
    ['GND', 'Ground +1', 'Terrestre +1'],
    ['NDA', 'Next Day Air +1', 'Aéreo 1 día +1'],
    ['2DA', '2 Day Air +1', 'Aéreo 2 días +1'],
    ['3DS', '3 Day Select +1', 'Select 3 días +1'],
  ]) {
    const app = appHarness(); app.setRun({ ...plusOne, svc });
    app.evaluate('showCard();');
    assert.ok(app.markup.includes(`${english} &middot; NY`));
    app.evaluate("showFeedback(answerCard(run, 'ORANGE', 800)); showResults();");
    assert.equal(app.evaluate('buildWorkbook(log.all())').Missorts.rows[0].Service, english);
    app.view.languages[1].click();
    assert.ok(app.markup.includes(`${spanish} &middot; NY &middot; 109`));
    const row = app.evaluate('buildWorkbook(log.all())').Missorts.rows[0];
    assert.equal(row.Service, spanish); assert.equal(row['Routing code'], '109');
  }
});

test('ordinary recording preserves provenance and leaves absent optional metadata absent', () => {
  const current = quiz.answerCard(quiz.createRun({ name: '', cards: [ordinary] }), 'ORANGE', 100);
  assert.equal(current.code, '109');
  assert.equal(current.referenceVersion, 'twilight-2026-11-08-r1');
  assert.equal(Object.hasOwn(current, 'destinationModifier'), false);
  const { referenceVersion, ...legacyCard } = ordinary;
  const legacy = quiz.timeoutCard(quiz.createRun({ name: '', cards: [legacyCard] }));
  assert.equal(Object.hasOwn(legacy, 'referenceVersion'), false);
  assert.equal(Object.hasOwn(legacy, 'destinationModifier'), false);
});

test('service and modifier text remain inert in card, feedback and missed-summary HTML', () => {
  const service = '<b data-security-probe>service</b>';
  const modifier = '<b data-security-probe>modifier</b>';
  const app = appHarness(); app.setRun({ ...plusOne, svc: service, destinationModifier: modifier });
  const escaped = () => {
    assert.ok(!app.markup.includes(service)); assert.ok(!app.markup.includes(modifier));
    assert.match(app.markup, /&lt;b data-security-probe&gt;service&lt;\/b&gt;/);
    assert.match(app.markup, /&lt;b data-security-probe&gt;modifier&lt;\/b&gt;/);
  };
  app.evaluate('showCard();'); escaped();
  app.view.languages[1].click();
  assert.equal(app.view.querySelector('.p-line').textContent, `${service} ${modifier} · NY`);
  app.evaluate("showFeedback(answerCard(run, 'ORANGE', 800));"); escaped();
  app.evaluate('showResults();'); escaped();
});
