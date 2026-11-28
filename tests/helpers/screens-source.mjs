import { readFileSync } from 'node:fs';

// The text of the app's screens, for the tests that read source as text.
//
// Every screen used to be in src/app.js, at the margin, and those tests
// find a function by name and read to its closing brace. The owner's and
// the player's screens now sit in files of their own, inside a factory,
// two spaces in. This hands back those files with the two spaces taken
// off, followed by app.js, so a function reads the same wherever it lives
// and a test does not have to know which file a screen moved to. The moved
// files come first because app.js keeps a short function of the same name
// as each way in (showProfile, showOwnerTools), and the screen itself is
// the one a test means.
//
// A test about one file in particular -- what it imports, what it hands to
// another -- should read that file itself instead.
const FACTORIES = ['ownerScreens.js', 'profileScreens.js'];

const read = (name) => readFileSync(new URL(`../../src/${name}`, import.meta.url), 'utf8');
const atTheMargin = (text) => text.replace(/^ {2}/gm, '');

export function screensSource() {
  return [...FACTORIES.map((name) => atTheMargin(read(name))), read('app.js')].join('\n');
}
