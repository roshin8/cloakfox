import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assessLists } from '../../additions/browser/components/cloakfox/CloakfoxReleaseStatus.sys.mjs';
const input = {enabled: true, key: true, tables: 'goog-phish-proto;abc:checksum\n', expected: ['goog-phish-proto'], now: 1000000000, lastSuccess: 999999000};
test('real list state required, not configured preferences', () => {
  assert.equal(assessLists(input).state, 'ready');
  assert.equal(assessLists({...input, tables: ''}).state, 'unavailable');
  assert.equal(assessLists({...input, tables: 'goog-phish-proto;:checksum'}).state, 'unavailable');
  assert.equal(assessLists({...input, key: false}).state, 'missing-key');
  assert.equal(assessLists({...input, enabled: false}).state, 'disabled');
  assert.equal(assessLists({...input, lastSuccess: 1}).state, 'stale');
  assert.equal(assessLists({...input, lastSuccess: input.now + 1}).state, 'stale');
});
