import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const source = fs.readFileSync('firefox-src/browser/base/content/browser-siteIdentity.js', 'utf8');
const method = source.slice(source.indexOf('  async clearSiteData(event) {'), source.indexOf('  /**\n   * Handler for mouseclicks', source.indexOf('  async clearSiteData(event) {')));
for (const [choice, id] of [[0, 8], [0, 0], [1, 8], [2, 8]]) {
  test(`clear-site-data choice ${choice}, container ${id}`, async () => {
    const calls = [];
    const context = {
      window: {},
      gBrowser: { selectedBrowser: { contentPrincipal: { originAttributes: { userContextId: id, privateBrowsingId: 0 } } } },
      ContextualIdentityService: { getUserContextLabel: () => 'Sara SGO' },
      Services: {
        prompt: { BUTTON_TITLE_IS_STRING: 1, BUTTON_TITLE_CANCEL: 2, BUTTON_POS_0: 1, BUTTON_POS_1: 256, BUTTON_POS_2: 65536, BUTTON_POS_1_DEFAULT: 0x1000000,
          confirmEx: (...args) => { calls.push(['prompt', ...args]); return choice; } },
        clearData: { deleteDataFromSite: (...args) => { calls.push(['clear', ...args.slice(0, 4)]); args[4](0); } },
      },
      Ci: { nsIClearDataService: { CLEAR_COOKIES: 1, CLEAR_DOM_STORAGES: 2, CLEAR_NETWORK_CACHE: 4, CLEAR_IMAGE_CACHE: 8, CLEAR_JS_CACHE: 16, CLEAR_CSS_CACHE: 32 } },
      SiteDataManager: { getBaseDomainFromHost: () => 'example.com', remove: async domain => calls.push(['all', domain]), updateSites: async () => {} },
      PanelMultiView: { hidePopup: popup => popup.callback() },
    };
    const handler = vm.runInNewContext(`({${method}})`, context);
    handler._uriHasHost = true;
    handler._uri = { host: 'www.example.com' };
    handler._identityPopup = { addEventListener: (_, callback) => { handler._identityPopup.callback = callback; } };
    await handler.clearSiteData({ stopPropagation() {} });
    assert.equal(calls[0][0], 'prompt');
    assert.match(calls[0][3], /example.com/);
    if (choice === 0) {
      const clear = calls.find(c => c[0] === 'clear');
      assert.ok(clear, 'current-container option must clear scoped data');
      assert.deepEqual(JSON.parse(JSON.stringify(clear[2])), { userContextId: id, privateBrowsingId: 0 });
      assert.equal(clear[4], 63, 'only container-aware cookies and storage cleaners');
      assert.ok(!calls.some(c => c[0] === 'all'));
    } else if (choice === 2) {
      assert.deepEqual(calls.at(-1), ['all', 'example.com']);
    } else {
      assert.equal(calls.length, 1, 'Cancel must not clear data');
    }
  });
}
