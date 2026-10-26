import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
const source = fs.readFileSync('firefox-src/browser/base/content/browser-trustPanel.js', 'utf8');
const markup = fs.readFileSync('firefox-src/browser/components/controlcenter/content/trustPanel.inc.xhtml', 'utf8');
test('Trust Panel exposes both scopes before Clear', () => {
  assert.match(markup, /id="trustpanel-clear-cookie-scope"/);
  assert.match(markup, /value="container"/);
  assert.match(markup, /value="all"/);
});
for (const scope of ['container', 'all', 'invalid']) {
  test(`Trust Panel scope: ${scope}`, async () => {
    const start = source.indexOf('  async #clearSiteData()');
    assert.ok(start > 0, 'scoped async clear handler exists');
    const method = source.slice(start, source.indexOf('\n  #toggleTrackingProtection', start)).replaceAll('this.#', 'this._').replace('#clearSiteData', 'clearSiteData');
    const calls = [];
    const browser = {};
    const context = {
      gBrowser: { selectedBrowser: browser },
      document: { getElementById: () => ({ value: scope, disabled: false }) },
      SiteDataManager: { remove: async domain => calls.push(['all', domain]), updateSites: async () => {} },
      Services: { clearData: { deleteDataFromSite: (site, pattern, _user, flags, done) => { calls.push(['container', site, JSON.parse(JSON.stringify(pattern)), flags]); done(0); } } },
      Ci: { nsIClearDataService: { CLEAR_COOKIES: 1, CLEAR_DOM_STORAGES: 2, CLEAR_NETWORK_CACHE: 4, CLEAR_IMAGE_CACHE: 8, CLEAR_JS_CACHE: 16, CLEAR_CSS_CACHE: 32 } },
      console,
    };
    const handler = vm.runInNewContext(`({${method}})`, context);
    handler._clearSiteDataTarget = { browser, baseDomain: 'example.com', userContextId: 8, privateBrowsingId: 0 };
    handler._hidePopup = () => {};
    await handler.clearSiteData();
    assert.deepEqual(calls, scope === 'all' ? [['all', 'example.com']] : scope === 'container' ? [['container', 'example.com', {userContextId: 8, privateBrowsingId: 0}, 63]] : []);
  });
}
