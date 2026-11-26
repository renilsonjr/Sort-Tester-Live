// The opening of the site (owner report, 2026-11-26: a dark pause of
// seconds before anything shows).
//
// Three guards: the preload list in index.html IS the real import graph,
// so the browser fetches every module at once instead of discovering them
// one round trip at a time; no module is imported under two different
// URLs, which makes the browser download and run it twice; and the page
// draws its own opening mark before any script runs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, normalize } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const html = readFileSync(join(root, 'index.html'), 'utf8');

// the graph, walked the way the browser walks it: each import's URL is
// path plus token, resolved against the importer
function importGraph() {
  const edges = new Map();   // file -> query it is imported with
  const variants = new Map(); // file -> Set of queries seen
  const seen = new Set();
  const walk = (file) => {
    if (seen.has(file)) return;
    seen.add(file);
    const src = readFileSync(join(root, file), 'utf8');
    for (const m of src.matchAll(/import[^;]*?['"](\.{1,2}\/[^'"]+)['"]/gs)) {
      const spec = m[1];
      const target = normalize(join(dirname(file), spec.split('?')[0]));
      const query = spec.includes('?') ? '?' + spec.split('?')[1] : '';
      edges.set(target, query);
      if (!variants.has(target)) variants.set(target, new Set());
      variants.get(target).add(query);
      walk(target);
    }
  };
  walk('src/app.js');
  walk('src/auth.js');
  return { edges, variants };
}

test('every module is named up front, and nothing else is', () => {
  const { edges } = importGraph();
  const wanted = [...edges.entries()].map(([f, q]) => f + q).sort();
  const listed = [...html.matchAll(/rel="modulepreload" href="([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(listed, wanted);
});

test('no module is imported under two different URLs', () => {
  const { variants } = importGraph();
  const doubled = [...variants.entries()].filter(([, qs]) => qs.size > 1).map(([f]) => f);
  // levels.js was, and the browser downloaded and ran it twice
  assert.deepEqual(doubled, []);
});

test('the page draws the opening mark itself, inside the app mount', () => {
  assert.match(html, /<main id="app"><div class="boot"[^>]*>/);
  assert.match(html, /class="boot-mark">RJ</);
  // the first render replaces #app's children, which removes it; the mark
  // must not live outside #app or it would stay behind the app forever
  assert.doesNotMatch(html, /<\/main>\s*<div class="boot"/);
});

test('the spin respects reduced motion', () => {
  assert.match(html, /prefers-reduced-motion: reduce[^}]*\.boot-mark \{ animation: none; \}/s);
});

test('every src file on disk is part of the graph or an entry', () => {
  // a module nobody imports is dead weight the page still preloads if
  // listed by hand; keeping the two in step starts with knowing the set
  const { edges } = importGraph();
  const onDisk = [];
  const dig = (d) => {
    for (const f of readdirSync(join(root, d))) {
      const p = join(d, f);
      if (statSync(join(root, p)).isDirectory()) dig(p);
      else if (f.endsWith('.js')) onDisk.push(normalize(p));
    }
  };
  dig('src');
  const reachable = new Set([...edges.keys(), 'src/app.js', 'src/auth.js']);
  const orphans = onDisk.filter((f) => !reachable.has(f));
  assert.deepEqual(orphans, []);
});
