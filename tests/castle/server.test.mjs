import assert from 'node:assert/strict';
import { test } from 'node:test';
import { once } from 'node:events';
import { mkdtemp, readdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createLabServer } from './server.mjs';

async function lab(t, options = {}) {
  const reportsDir = await mkdtemp(join(tmpdir(), 'castle-lab-'));
  const server = createLabServer({ reportsDir, ...options });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(async () => {
    await new Promise(resolve => server.close(resolve));
    await rm(reportsDir, { recursive: true, force: true });
  });
  const url = `http://127.0.0.1:${server.address().port}`;
  const post = (body, headers = {}) => fetch(`${url}/api/evaluate`, {
    method: 'POST', headers: { origin: url, 'content-type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  return { url, post, reportsDir };
}

// These catch leaked credentials and false readiness when configuration is absent.
test('configuration reports missing keys without exposing the API secret', async t => {
  const { url, post } = await lab(t, { apiSecret: 'secret-sentinel' });
  const config = await (await fetch(`${url}/api/config`)).json();
  assert.equal(config.ready, false);
  assert.deepEqual(config.missing, ['CASTLE_PUBLISHABLE_KEY']);
  assert.ok(!JSON.stringify(config).includes('secret-sentinel'));
  assert.equal((await post({ requestToken: 'opaque-token', label: 'Firefox' })).status, 503);
});

test('evaluation sends real telemetry context and saves results without tokens or cookies', async t => {
  let sent;
  const { url, post, reportsDir } = await lab(t, {
    publishableKey: 'pk-test', apiSecret: 'secret-sentinel', clientIp: '8.8.8.8',
    fetchImpl: async (url, options) => {
      sent = { url, options, body: JSON.parse(options.body) };
      return Response.json({ id: 'event-1', policy: { action: 'allow' },
        scores: { bot: { score: 0.42 } }, signals: { spoofed_device: {} } });
    },
  });
  const response = await post({ requestToken: 'opaque-token', label: 'Cloakfox', email: 'test@example.com' }, {
    'user-agent': 'Firefox fixture', 'accept-language': 'en-US,en;q=0.9',
    cookie: 'session=private', authorization: 'Bearer private', 'x-forwarded-for': '1.1.1.1',
  });
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.response.signals.spoofed_device instanceof Object, true);
  assert.equal(sent.url, 'https://api.castle.io/v1/filter');
  assert.equal(sent.options.headers.Authorization, `Basic ${Buffer.from(':secret-sentinel').toString('base64')}`);
  assert.equal(sent.body.request_token, 'opaque-token');
  assert.equal(sent.body.type, '$registration');
  assert.equal(sent.body.status, '$attempted');
  assert.equal(sent.body.params.email, 'test@example.com');
  assert.equal(sent.body.context.ip, '8.8.8.8');
  assert.equal(sent.body.context.headers['user-agent'], 'Firefox fixture');
  assert.equal(sent.body.context.headers['accept-language'], 'en-US,en;q=0.9');
  assert.equal(sent.body.context.headers.cookie, true);
  assert.equal(sent.body.context.headers.authorization, true);
  assert.equal(sent.body.context.headers.origin, url);
  assert.equal(sent.body.context.headers.host, new URL(url).host);
  assert.equal(sent.body.context.headers['content-type'], 'application/json');
  assert.equal(sent.body.context.headers['x-forwarded-for'], undefined);
  const files = await readdir(reportsDir);
  assert.equal(files.length, 1);
  const saved = await readFile(join(reportsDir, files[0]), 'utf8');
  for (const value of ['opaque-token', 'secret-sentinel', 'session=private', 'Bearer private', 'test@example.com']) {
    assert.ok(!saved.includes(value));
  }
  const history = await (await fetch(`${url}/api/results`)).json();
  assert.equal(history[0].label, 'Cloakfox');
});

test('rejects cross-origin requests before spending Castle quota', async t => {
  const { post } = await lab(t, { publishableKey: 'pk-test', apiSecret: 'secret',
    fetchImpl: () => assert.fail('must not call Castle') });
  assert.equal((await post({ requestToken: 'opaque-token' }, { origin: 'https://elsewhere.example' })).status, 403);
});

test('rejects empty and mock tokens instead of presenting simulated browser measurements', async t => {
  const { post } = await lab(t, { publishableKey: 'pk-test', apiSecret: 'secret',
    fetchImpl: () => assert.fail('must not call Castle') });
  for (const requestToken of ['', 'test|device:firefox_on_mac', null]) {
    assert.equal((await post({ requestToken, label: 'Firefox' })).status, 400);
  }
});

test('Castle errors and transport failures never become an allow verdict', async t => {
  for (const fetchImpl of [async () => Response.json({ type: 'invalid_request_token' }, { status: 422 }),
    async () => { throw new Error('network failure'); }]) {
    const { post, reportsDir } = await lab(t, { publishableKey: 'pk-test', apiSecret: 'secret', fetchImpl });
    const response = await post({ requestToken: 'opaque-token', label: 'Firefox' });
    assert.equal(response.status, 502);
    assert.equal((await response.json()).response, undefined);
    assert.deepEqual(await readdir(reportsDir), []);
  }
});

test('loopback context is clearly identified and forged proxy headers are ignored', async t => {
  const { url } = await lab(t);
  const config = await (await fetch(`${url}/api/config`, { headers: { 'x-forwarded-for': '8.8.8.8' } })).json();
  assert.equal(config.clientIp, '127.0.0.1');
  assert.equal(config.ipSource, 'loopback');
});
