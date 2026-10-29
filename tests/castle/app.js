/* global Castle */
const byId = id => document.getElementById(id);
let castle;
let sdkReady = false;

function score(response, name) {
  const value = response.scores?.[name]?.score;
  return typeof value === 'number' ? String(Math.round(value * 100)) : '—';
}

function action(response) {
  return response.policy?.action || response.action || 'No policy action';
}

function download(report) {
  const a = document.createElement('a');
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
  a.href = url;
  a.download = `castle-${report.id}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function show(report) {
  const container = byId('latest');
  container.replaceChildren();
  const title = document.createElement('h3');
  title.textContent = report.label;
  container.append(title);
  const metrics = document.createElement('div');
  metrics.className = 'metrics';
  for (const [label, value] of [['Bot / 100', score(report.response, 'bot')],
    ['Abuse / 100', score(report.response, 'account_abuse')], ['Policy', action(report.response)]]) {
    const item = document.createElement('div');
    const number = document.createElement('strong');
    number.textContent = value;
    const caption = document.createElement('span');
    caption.textContent = label;
    item.append(number, caption);
    metrics.append(item);
  }
  container.append(metrics);
  const signals = Object.keys(report.response.signals || {});
  const list = document.createElement('ul');
  list.className = 'signals';
  for (const signal of signals.length ? signals : ['No exposed signals returned.']) {
    const li = document.createElement('li');
    li.textContent = signal;
    list.append(li);
  }
  const context = document.createElement('p');
  context.className = 'hint';
  context.textContent = `${new Date(report.measuredAt).toLocaleString()} · IP ${report.clientIp} (${report.ipSource}) · SDK ${report.sdkVersion}`;
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Full saved response';
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(report, null, 2);
  details.append(summary, pre);
  container.append(list, context, details);
}

async function refresh() {
  const response = await fetch('/api/results');
  if (!response.ok) throw new Error('Could not load saved runs.');
  const reports = await response.json();
  byId('runs').replaceChildren();
  for (const report of reports) {
    const row = document.createElement('tr');
    for (const value of [report.label, score(report.response, 'bot'), score(report.response, 'account_abuse'),
      action(report.response), Object.keys(report.response.signals || {}).join(', ') || 'None returned']) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.append(cell);
    }
    const cell = document.createElement('td');
    const view = document.createElement('button');
    view.className = 'secondary'; view.textContent = 'View'; view.onclick = () => show(report);
    const save = document.createElement('button');
    save.className = 'secondary'; save.textContent = 'JSON'; save.onclick = () => download(report);
    cell.append(view, ' ', save); row.append(cell); byId('runs').append(row);
  }
  if (!reports.length) {
    const row = document.createElement('tr'); const cell = document.createElement('td');
    cell.colSpan = 6; cell.textContent = 'Saved measurements will appear here.';
    row.append(cell); byId('runs').append(row);
  } else show(reports[0]);
}

async function initialize() {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error('Could not read lab configuration.');
  const config = await response.json();
  byId('setup').className = config.ipSource === 'loopback' || !config.ready ? 'warning' : '';
  if (!config.ready) {
    byId('connection').textContent = 'Sandbox keys needed';
    byId('setup').textContent = `Add ${config.missing.join(' and ')} to tests/castle/.env, then restart the server and reload. Get both keys from the same Castle sandbox environment.`;
  } else {
    if (typeof Castle === 'undefined') throw new Error('Castle SDK did not load. Run npm install in tests/castle, then reload.');
    castle = Castle.configure({ pk: config.publishableKey, wUrl: '/vendor/cw.js',
      swUrl: '/vendor/csw.js', dwUrl: '/vendor/dw.js' });
    sdkReady = true;
    byId('run').disabled = false;
    byId('connection').textContent = `SDK ${config.sdkVersion} initialized`;
    byId('setup').textContent = config.ipSource === 'loopback'
      ? 'Using 127.0.0.1: public IP reputation and location checks are incomplete. Set CASTLE_CLIENT_IP to this browser’s actual public egress IP, restart, and reload for network-aware testing.'
      : `Castle will evaluate IP ${config.clientIp}. Keep the browser’s network unchanged during comparisons. Use keys from a sandbox environment.`;
  }
  await refresh();
}

byId('measure').addEventListener('submit', async event => {
  event.preventDefault();
  if (!sdkReady) return;
  byId('run').disabled = true;
  byId('status').textContent = 'Collecting a fresh token and asking Castle…';
  try {
    const requestToken = await Promise.race([Promise.resolve(castle.createRequestToken()),
      new Promise((_, reject) => setTimeout(() => reject(new Error('Castle token collection timed out. Reload and check browser script/worker settings.')), 15000))]);
    const response = await fetch('/api/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requestToken, label: byId('label').value, email: byId('email').value }) });
    const report = await response.json();
    if (!response.ok) throw new Error([report.error, report.upstreamStatus, report.upstreamError].filter(Boolean).join(' · '));
    await refresh();
    byId('status').textContent = 'Measurement saved.';
  } catch (error) { byId('status').textContent = error.message; }
  finally { byId('run').disabled = false; }
});
byId('refresh').addEventListener('click', () => refresh().catch(error => { byId('status').textContent = error.message; }));
initialize().catch(error => { byId('connection').textContent = 'Setup needs attention'; byId('setup').textContent = error.message; });
