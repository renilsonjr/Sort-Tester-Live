const KEY = 'sortTest.shiftLog.v1';
const CAP = 200;

export function createShiftLog(storage) {
  let available = true;

  try {
    if (!storage) throw new Error('no storage');
    const existing = storage.getItem(KEY);
    storage.setItem(KEY, existing === null ? '[]' : existing);
  } catch {
    available = false;
  }

  function read() {
    if (!available) return [];
    try {
      const raw = storage.getItem(KEY);
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        // JSON.parse failed or data is not array - not a storage error
        return [];
      }
    } catch {
      // getItem threw - storage is broken
      available = false;
      return [];
    }
  }

  return {
    get available() {
      return available;
    },
    all() {
      return read();
    },
    append(summary) {
      if (!available) return false;
      try {
        storage.setItem(KEY, JSON.stringify([summary, ...read()].slice(0, CAP)));
        return true;
      } catch {
        available = false;
        return false;
      }
    },
    clear() {
      if (!available) return;
      try {
        storage.removeItem(KEY);
      } catch {
        available = false;
      }
    },
  };
}
