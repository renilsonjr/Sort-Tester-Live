// Just enough of a page for a screen to wire itself to, with no browser.
//
// Every lookup finds an element, every data-* attribute has a value, and
// every listener is kept so a test can press it. Nothing is drawn and no
// HTML is parsed: this is for finding a screen that throws when it is built
// or pressed -- a name that did not arrive, a call that no longer exists --
// not for checking what a screen looks like.
export function standInPage({ data = () => 'a1', value = 'K7Q2MX' } = {}) {
  const handlers = [];
  const element = () => {
    const made = {
      value, checked: true, hidden: false, disabled: false,
      textContent: '', innerHTML: '', className: '', isConnected: true,
      dataset: new Proxy({}, { get: (_all, key) => data(key) }),
      classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
      querySelector: () => element(),
      querySelectorAll: () => [element()],
      closest: () => element(),
      addEventListener: (_type, handler) => handlers.push(handler),
      setAttribute() {}, removeAttribute() {},
      after() {}, prepend() {}, append() {}, remove() {},
      focus() {}, select() {},
    };
    Object.defineProperty(made, 'firstElementChild', { get: () => element() });
    return made;
  };
  // Press everything, including what each press wires up. Screens lead back
  // to one another, so the limit is what ends it.
  async function pressEverything(limit = 600) {
    const event = () => ({ preventDefault() {}, stopPropagation() {}, target: element(), currentTarget: element(), key: 'Enter' });
    for (let pressed = 0; pressed < handlers.length && pressed < limit; pressed += 1) {
      await handlers[pressed](event());
    }
    // the lists a screen loads finish after the screen is drawn
    await new Promise((resolve) => setImmediate(resolve));
  }
  return { element, handlers, pressEverything };
}
