import { createServer } from 'node:http';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, dirname } from 'node:path';
import { isIP } from 'node:net';
import { randomUUID } from 'node:crypto';

const root = dirname(fileURLToPath(import.meta.url));
const sdkVersion = '2.8.5';
const staticFiles = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/style.css': ['style.css', 'text/css; charset=utf-8'],
  ...Object.fromEntries(['castle.browser.js', 'cw.js', 'csw.js', 'dw.js', 'c.css'].map(name =>
    [`/vendor/${name}`, [`node_modules/@castleio/castle-js/dist/${name}`,
      name.endsWith('.css') ? 'text/css' : 'text/javascript'] ])),
};

export function createLabServer({ publishableKey = '', apiSecret = '', clientIp = '',
  reportsDir = join(root, 'reports'), fetchImpl = fetch } = {}) {
  if (clientIp && !isIP(clientIp)) throw new Error('CASTLE_CLIENT_IP must be an IP address.');
  const missing = [!publishableKey && 'CASTLE_PUBLISHABLE_KEY', !apiSecret && 'CASTLE_API_SECRET'].filter(Boolean);
  const config = { ready: missing.length === 0, missing, publishableKey, sdkVersion,
    clientIp: clientIp || '127.0.0.1', ipSource: clientIp ? 'configured' : 'loopback' };

  return createServer(async (req, res) => {
    const json = (status, value) => {
      res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff' });
      res.end(JSON.stringify(value));
    };
    const port = req.socket.localPort;
    if (![ `127.0.0.1:${port}`, `localhost:${port}` ].includes(req.headers.host)) {
      return json(403, { error: 'Open the lab through its localhost URL.' });
    }
    const origin = `http://${req.headers.host}`;
    if (req.headers.origin && req.headers.origin !== origin) {
      return json(403, { error: 'Cross-origin requests are not accepted.' });
    }
    try {
      const path = new URL(req.url, origin).pathname;
      if (req.method === 'GET' && path === '/api/config') return json(200, config);
      if (req.method === 'GET' && path === '/api/results') {
        let files;
        try { files = await readdir(reportsDir); }
        catch (error) { if (error.code === 'ENOENT') return json(200, []); throw error; }
        const results = await Promise.all(files.filter(name => name.endsWith('.json')).sort().reverse().slice(0, 30)
          .map(async name => JSON.parse(await readFile(join(reportsDir, name), 'utf8'))));
        return json(200, results);
      }
      if (req.method === 'POST' && path === '/api/evaluate') {
        if (req.headers.origin !== origin) return json(403, { error: 'A same-origin browser request is required.' });
        if (!config.ready) return json(503, { error: `Configure ${missing.join(', ')} in .env and restart.` });
        if (req.headers['content-type']?.split(';')[0].trim() !== 'application/json') {
          return json(415, { error: 'Send application/json.' });
        }
        let data = '';
        for await (const chunk of req) {
          data += chunk;
          if (Buffer.byteLength(data) > 131072) return json(413, { error: 'Request is too large.' });
        }
        let input;
        try { input = JSON.parse(data); } catch { return json(400, { error: 'Invalid JSON.' }); }
        if (!input || typeof input.requestToken !== 'string' || !input.requestToken.trim() ||
          input.requestToken.startsWith('test|')) {
          return json(400, { error: 'A fresh, real Castle browser token is required. Mock tokens are not measurements.' });
        }
        if (typeof input.label !== 'string' || !input.label.trim() || input.label.length > 100 ||
          (input.email !== undefined && (typeof input.email !== 'string' || input.email.length > 254))) {
          return json(400, { error: 'Supply a run label (1–100 characters) and an optional email.' });
        }
        // Preserve browser header context. Like Castle's SDK, represent sensitive
        // header presence with true; never send credentials or cookie values.
        // Ignore proxy headers the loopback client could forge.
        const headers = Object.fromEntries(Object.entries(req.headers).filter(([name]) =>
          name !== 'forwarded' && !name.startsWith('x-') && !name.startsWith('cf-'))
          .map(([name, value]) => [name,
            ['cookie', 'authorization', 'proxy-authorization'].includes(name) ? true : value]));
        const payload = { type: '$registration', status: '$attempted',
          request_token: input.requestToken, context: { ip: config.clientIp, headers },
          ...(input.email?.trim() ? { params: { email: input.email.trim() } } : {}) };
        let upstream, response;
        try {
          upstream = await fetchImpl('https://api.castle.io/v1/filter', {
            method: 'POST', headers: { Authorization: `Basic ${Buffer.from(`:${apiSecret}`).toString('base64')}`,
              'Content-Type': 'application/json' }, body: JSON.stringify(payload),
            signal: AbortSignal.timeout(15000), redirect: 'error',
          });
          response = await upstream.json();
        } catch {
          return json(502, { error: 'Castle could not be reached or returned an unreadable response. No verdict was recorded.' });
        }
        if (!upstream.ok) return json(502, { error: 'Castle rejected this request. Check sandbox keys and IP settings.',
          upstreamStatus: upstream.status,
          upstreamError: String(response?.type || response?.error?.type || 'unknown').slice(0, 100) });
        if (!response || typeof response !== 'object' || Array.isArray(response) || !response.scores) {
          return json(502, { error: 'Castle returned no scores. No verdict was recorded.' });
        }
        // Store Castle's response, never the submitted token/email or inbound cookies.
        const clean = JSON.parse(JSON.stringify(response, (key, value) =>
          /^(request_?token|api_?secret|authorization|password|cookie|email)$/i.test(key) ? '[redacted]' : value)
          .replaceAll(apiSecret, '[redacted]').replaceAll(input.requestToken, '[redacted]'));
        const report = { id: randomUUID(), measuredAt: new Date().toISOString(), label: input.label.trim(),
          sdkVersion, clientIp: config.clientIp, ipSource: config.ipSource,
          userAgent: req.headers['user-agent'] || '', response: clean };
        await mkdir(reportsDir, { recursive: true, mode: 0o700 });
        await writeFile(join(reportsDir, `${report.measuredAt.replaceAll(':', '-')}-${report.id}.json`),
          JSON.stringify(report, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
        return json(200, report);
      }
      if (req.method === 'GET' && staticFiles[path]) {
        const [file, type] = staticFiles[path];
        const content = await readFile(join(root, file));
        res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store',
          'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY' });
        return res.end(content);
      }
      return json(404, { error: 'Not found.' });
    } catch {
      return json(500, { error: 'Local lab error. Check dependencies and report-directory permissions.' });
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const port = Number(process.env.PORT || 8765);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('PORT must be 1–65535.');
  const server = createLabServer({ publishableKey: process.env.CASTLE_PUBLISHABLE_KEY,
    apiSecret: process.env.CASTLE_API_SECRET, clientIp: process.env.CASTLE_CLIENT_IP });
  server.on('error', error => { console.error(`Castle lab: ${error.code || 'startup error'}`); process.exitCode = 1; });
  server.listen(port, '127.0.0.1', () => console.log(`Castle lab: http://127.0.0.1:${port}`));
}
