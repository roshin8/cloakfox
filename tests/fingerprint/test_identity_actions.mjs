import assert from 'node:assert/strict';
import test from 'node:test';
import { forgetContainerData, pruneContainerRestoreState } from '../../additions/browser/components/cloakfox/CloakfoxIdentityActions.sys.mjs';

const tab = (id, label) => ({ userContextId: id, entries: [{ url: label }] });
const closed = (id, label) => ({ state: tab(id, label) });

test('prunes default container including missing UCID without erasing mixed windows or unrelated selected tab', () => {
  const keep = tab(2, 'keep');
  const state = { windows: [{ tabs: [tab(0, 'remove'), keep], selected: 2,
    _closedTabs: [closed(0, 'remove closed'), closed(2, 'keep closed')] }],
    _closedWindows: [{ tabs: [{ entries: [] }, tab(2, 'keep window')], selected: 1 }],
    cookies: [{ originAttributes: {}, value: 'remove' },
      { originAttributes: { userContextId: 2 }, value: 'keep' }] };
  pruneContainerRestoreState(state, 0);
  assert.deepEqual(state.windows[0].tabs, [keep]);
  assert.equal(state.windows[0].selected, 1);
  assert.equal(state.windows[0]._closedTabs.length, 1);
  assert.equal(state._closedWindows[0].tabs[0].userContextId, 2);
  assert.equal(state._closedWindows[0].selected, 1);
  assert.equal(state.cookies[0].value, 'keep');
  assert.equal(state.cookies.length, 1);
});

test('prunes saved/closed groups, empty windows and nested deferred sessions', () => {
  const state = { windows: [{ tabs: [tab(4, 'gone')] }, { tabs: [tab(3, 'kept')] }],
    selectedWindow: 2,
    savedGroups: [{ id: 'mixed', tabs: [closed(4, 'gone'), closed(3, 'kept')] },
      { id: 'gone', tabs: [closed(4, 'gone')] }],
    _closedWindows: [{ tabs: [tab(3, 'kept')], closedGroups: [
      { id: 'mixed', tabs: [closed(4, 'gone'), closed(3, 'kept')] }] }],
    lastSessionState: { windows: [{ tabs: [tab(4, 'gone')] }] } };
  pruneContainerRestoreState(state, 4);
  assert.equal(state.windows.length, 1);
  assert.equal(state.selectedWindow, 1);
  assert.equal(state.savedGroups.length, 1);
  assert.equal(state.savedGroups[0].tabs.length, 1);
  assert.equal(state._closedWindows[0].closedGroups[0].tabs.length, 1);
  assert.equal(state.lastSessionState.windows.length, 0);
});

function harness(failedFlags = 0) {
  const events = [];
  const deps = {
    exists: id => id === 0 || id === 4,
    preflight: () => events.push('preflight'),
    acquire: () => { events.push('lock'); return () => events.push('unlock'); },
    closeTabs: async () => events.push('closed'),
    pruneRestore: () => events.push('pruned'),
    clearData: async () => { events.push('cleared'); return failedFlags; },
    rotate: () => events.push('rotated'),
  };
  return { events, deps };
}

test('rejects invalid, coerced, nonexistent IDs and missing confirmation before side effects', async () => {
  for (const id of [-1, '4', NaN, Infinity, 1.5, 999]) {
    const { deps, events } = harness();
    await assert.rejects(forgetContainerData(id, { confirmed: true }, deps));
    assert.deepEqual(events, []);
  }
  const { deps, events } = harness();
  await assert.rejects(forgetContainerData(4, {}, deps));
  assert.deepEqual(events, []);
});

test('waits for close and clear before rotating; always releases lock', async () => {
  const { deps, events } = harness();
  let finish;
  deps.clearData = () => new Promise(resolve => { finish = resolve; events.push('clearing'); });
  const pending = forgetContainerData(4, { confirmed: true }, deps);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(events, ['preflight', 'lock', 'closed', 'pruned', 'clearing']);
  finish(0);
  assert.deepEqual(await pending, { userContextId: 4, cleared: true, appearanceChanged: true });
  assert.deepEqual(events.slice(-4), ['closed', 'pruned', 'rotated', 'unlock']);
});

test('partial clear failure retains seeds and explains destructive partial effects', async () => {
  const { deps, events } = harness(16);
  await assert.rejects(forgetContainerData(4, { confirmed: true }, deps), /Some data may already be removed.*appearance was not changed/);
  assert.equal(events.includes('rotated'), false);
  assert.equal(events.at(-1), 'unlock');
});

test('concurrent same-container forget cannot start a second clear', async () => {
  const { deps } = harness();
  let finish;
  deps.clearData = () => new Promise(resolve => { finish = resolve; });
  const pending = forgetContainerData(4, { confirmed: true }, deps);
  await new Promise(resolve => setImmediate(resolve));
  await assert.rejects(forgetContainerData(4, { confirmed: true }, deps), /already/);
  finish(0);
  await pending;
});

test('retains unrelated closed records when the last open tab belonged to target', () => {
  const state = { _closedWindows: [{ tabs: [tab(4, 'gone')], selected: 1,
    _closedTabs: [closed(3, 'keep undo-close')] }] };
  pruneContainerRestoreState(state, 4);
  assert.equal(state._closedWindows.length, 1);
  assert.equal(state._closedWindows[0]._closedTabs[0].state.userContextId, 3);
  assert.equal(state._closedWindows[0].selected, 0);
});

test('uses native removal callback for late-update bookkeeping and preserves selected neighbor', () => {
  const entries = [closed(4, 'gone'), closed(3, 'kept')];
  const removed = [];
  const root = { windows: [{ tabs: [tab(3, 'left'), tab(4, 'selected'), tab(3, 'right')],
    selected: 2, _closedTabs: entries }] };
  pruneContainerRestoreState(root, 4, (_win, list, i) => removed.push(...list.splice(i, 1)));
  assert.equal(removed[0].state.userContextId, 4);
  assert.equal(root.windows[0].selected, 2);
  assert.equal(root.windows[0].tabs[1].entries[0].url, 'right');
});

test('restore preflight rejection leaves tabs and data untouched', async () => {
  const { deps, events } = harness();
  deps.preflight = () => { throw new Error('Restore in progress'); };
  await assert.rejects(forgetContainerData(4, { confirmed: true }, deps), /Restore in progress/);
  assert.deepEqual(events, []);
});

test('accepts legacy numeric-string IDs in restore records while action IDs stay strict', () => {
  const root = { windows: [{ tabs: [tab('4', 'gone'), tab(3, 'kept')], selected: 1 }] };
  pruneContainerRestoreState(root, 4);
  assert.equal(root.windows[0].tabs.length, 1);
  assert.equal(root.windows[0].tabs[0].userContextId, 3);
});


test('successful forget clears typed bounce exceptions only after native data clear succeeds',async()=>{
 const {deps,events}=harness();
 deps.clearBounceExceptions=id=>events.push(['bounce-cleared',id]);
 await forgetContainerData(4,{confirmed:true},deps);
 const index=events.findIndex(event=>Array.isArray(event)&&event[0]==='bounce-cleared');
 assert.deepEqual(events[index],['bounce-cleared',4]);
 assert.ok(index>events.indexOf('cleared'));assert.ok(index<events.indexOf('rotated'));
 const failed=harness(16);failed.deps.clearBounceExceptions=()=>assert.fail('Failed native clear must not remove typed grants');
 await assert.rejects(forgetContainerData(4,{confirmed:true},failed.deps));
});
