import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../../static/js/sessions.js', import.meta.url), 'utf8');
const loadSource = source.match(/export async function loadSessions\(\) \{[\s\S]*?\n\}/)[0].replace('export ', '');
const createSource = source.match(/export function createDirectChat\([^\n]+\{[\s\S]*?\n\}/)[0].replace('export ', '');

function harness({ hash = '', current = null, pending = null, defaultModel = true } = {}) {
  const selected = [], created = [], errors = [];
  const storage = new Map([['lastSessionId', 'old'], ['ody-session-active', '1']]);
  const sessions = [{ id: 'old', model: 'model', message_count: 12 }];
  const element = { classList: { add() {}, remove() {} }, focus() {} };
  const context = vm.createContext({
    console, _loadSessionsPromise: null, _sessionsInitialized: false,
    _sessionNavToken: 0, _suppressNextSessionLoading: false,
    _pendingChat: pending, _autoCreateInProgress: false, currentSessionId: current,
    sessions: [], API_BASE: '',
    window: { location: { hash, pathname: '/' }, innerWidth: 1000, chatModule: { showWelcomeScreen() {} } },
    history: { replaceState() {} },
    document: { getElementById: () => element, querySelectorAll: () => [] },
    Storage: { get: key => storage.get(key), remove: key => storage.delete(key) },
    sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    uiModule: { el: () => element, showError: error => errors.push(error) },
    _cleanupIncognitoSessions: async () => {}, _normalizeSessionsList: value => value,
    renderSessionList() {}, updateModelPicker() {},
    fetch: async url => ({ json: async () => url.endsWith('/api/sessions') ? sessions : defaultModel ? { endpoint_url: 'http://model', model: 'model' } : {} }),
    selectSession: async id => { selected.push(id); context.currentSessionId = id; },
  });
  vm.runInContext(createSource + '\n' + loadSource, context);
  const createDirectChat = context.createDirectChat;
  context.createDirectChat = (...args) => { created.push(args); return createDirectChat(...args); };
  return { context, selected, created, errors, load: () => context.loadSessions() };
}

test('fresh launch ignores a saved conversation and prepares a new draft even in a reused tab', async () => {
  const h = harness();
  await h.load();
  assert.deepEqual(h.errors, []);
  assert.deepEqual(h.selected, []);
  assert.equal(h.created.length, 1);
  await h.load();
  assert.equal(h.created.length, 1, 'background refresh must preserve the draft');
});

test('fresh launch without a default model stays on the welcome screen', async () => {
  const h = harness({ defaultModel: false });
  await h.load();
  assert.deepEqual(h.errors, []);
  assert.deepEqual(h.selected, []);
  assert.deepEqual(h.created, []);
});

test('an explicit conversation link opens its history', async () => {
  const h = harness({ hash: '#old' });
  await h.load();
  assert.deepEqual(h.errors, []);
  assert.deepEqual(h.selected, ['old']);
  assert.deepEqual(h.created, []);
});

test('history refresh preserves an active conversation or a pending draft', async () => {
  for (const options of [{ current: 'old' }, { pending: { model: 'model' } }]) {
    const h = harness(options);
    await h.load();
    assert.deepEqual(h.errors, []);
    assert.deepEqual(h.selected, []);
    assert.deepEqual(h.created, []);
  }
});

test('a non-chat deep link does not restore the previous conversation', async () => {
  const h = harness({ hash: '#document-test' });
  await h.load();
  assert.deepEqual(h.errors, []);
  assert.deepEqual(h.selected, []);
  assert.deepEqual(h.created, [], 'new-chat preparation must not clear the resource link');
});

test('choosing history during default-model lookup wins over startup', async () => {
  const h = harness();
  const fetch = h.context.fetch;
  h.context.fetch = async url => {
    if (url.endsWith('/api/default-chat')) h.context.currentSessionId = 'old';
    return fetch(url);
  };
  await h.load();
  assert.deepEqual(h.errors, []);
  assert.deepEqual(h.created, []);
  assert.equal(h.context.currentSessionId, 'old');
});
