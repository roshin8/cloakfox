import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCameraNicknames, serializeCameraNicknames, cameraDisplayName } from '../../additions/browser/components/cloakfox/CloakfoxCameraNames.sys.mjs';

test('nicknames preserve the real source and do not change unmatched cameras', () => {
 const names = parseCameraNicknames('{"OBS Virtual Camera":"Desk setup"}');
 assert.equal(cameraDisplayName('OBS Virtual Camera', names), 'Desk setup · OBS Virtual Camera');
 assert.equal(cameraDisplayName('FaceTime HD Camera', names), 'FaceTime HD Camera');
 assert.equal(cameraDisplayName('OBS Virtual Camera', {'OBS Virtual Camera':'OBS Virtual Camera'}), 'OBS Virtual Camera');
});
test('corrupt preferences fall back to original names', () => {
 for (const value of ['bad', 'null', '[]', '42', '{"OBS Virtual Camera":3}']) {
  assert.equal(cameraDisplayName('OBS Virtual Camera', parseCameraNicknames(value)), 'OBS Virtual Camera');
 }
 assert.equal(cameraDisplayName('toString', parseCameraNicknames('{}')), 'toString');
});
test('saving trims names and rejects ambiguous or unsafe entries', () => {
 assert.equal(serializeCameraNicknames([[' OBS Virtual Camera ', ' Desk setup ']]), '{"OBS Virtual Camera":"Desk setup"}');
 assert.equal(serializeCameraNicknames([]), '{}');
 for (const rows of [[['','Desk']], [['OBS','']], [['OBS','Desk'],['OBS','Other']], [['OBS','a\nb']], [['OBS','x'.repeat(81)]], [['OBS','\u202eCamera']]]) {
  assert.throws(() => serializeCameraNicknames(rows));
 }
});
