import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const config = readFileSync(new URL('../../settings/cloakfox.cfg', import.meta.url), 'utf8');
// AutoConfig pref() writes the user branch; defaultPref() writes only defaults.
// A new context models each startup; the saved user branch survives restart.
function startup(saved = {}) {
  const user = { ...saved };
  const defaults = {};
  vm.runInNewContext(config, {
    pref: (key, value) => { user[key] = value; },
    defaultPref: (key, value) => { defaults[key] = value; },
  });
  return { user, defaults, effective: { ...defaults, ...user } };
}

test('fresh profiles enable URL protection and avoid outgoing search suggestions', () => {
  const { effective } = startup();
  for (const key of ['browser.safebrowsing.malware.enabled',
    'browser.safebrowsing.phishing.enabled', 'dom.security.https_only_mode']) {
    assert.equal(effective[key], true, key);
  }
  assert.equal(effective['browser.search.suggest.enabled'], false);
  assert.equal(effective['browser.urlbar.suggest.searches'], false);
});

test('ordinary browser choices survive two startups including protective exceptions and search opt-in', () => {
  const choices = {
    'browser.safebrowsing.malware.enabled': false,
    'browser.safebrowsing.phishing.enabled': false,
    'dom.security.https_only_mode': false,
    'browser.search.suggest.enabled': true,
    'browser.urlbar.suggest.searches': true,
    'browser.urlbar.suggest.history': false,
    'browser.urlbar.suggest.bookmark': false,
    'browser.urlbar.suggest.topsites': false,
    'browser.urlbar.maxRichResults': 4,
    'browser.newtabpage.enabled': false,
    'browser.newtabpage.activity-stream.feeds.topsites': false,
    'signon.rememberSignons': false,
    'browser.formfill.enable': false,
    'reader.parse-on-load.enabled': false,
    'browser.tabs.warnOnClose': false,
    'browser.tabs.tabmanager.enabled': false,
    'layout.spellcheckDefault': 2,
    'ui.prefersReducedMotion': 1,
    'privacy.userContext.ui.enabled': false,
    'browser.uiCustomization.state': '{"placements":{}}',
  };
  let profile = startup(choices);
  profile = startup(profile.user);
  for (const [key, value] of Object.entries(choices)) {
    assert.equal(profile.effective[key], value, key);
  }
});

test('native OS reduced-motion choice is not overridden on a fresh profile', () => {
  assert.equal(startup().effective['ui.prefersReducedMotion'], undefined);
});

test('mandatory RFP and container invariants are restored at startup', () => {
  const { effective } = startup({
    'privacy.resistFingerprinting': true,
    'privacy.userContext.enabled': false,
  });
  assert.equal(effective['privacy.resistFingerprinting'], false);
  assert.equal(effective['privacy.userContext.enabled'], true);
});

test('native exact-host routing defaults on while an explicit opt-out survives restart', () => {
  const key = 'privacy.containers.switchDuringNavigation.enabled';
  assert.equal(startup().effective[key], true);
  const first = startup({ [key]: false });
  assert.equal(startup(first.user).effective[key], false);
});
