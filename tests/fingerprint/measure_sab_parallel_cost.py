"""Measure SAB serialization cost with two parallel workers.

Run from any directory with --binary PATH. Uses temporary browser profiles;
does not modify installed preferences. Four paired runs are exploratory, not
a replacement for the twenty-pair release performance gate.
"""
import argparse
import json
import statistics
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_sharedarraybuffer_timing as fixture

SCRIPT = r"""
const done = arguments[arguments.length-1];
(async () => {
  const src = `onmessage = e => {
    const a = new Int32Array(e.data.buffer);
    if (!e.data.run) { postMessage('ready'); return; }
    for (let i=0; i<100000000; i++) Atomics.add(a, e.data.slot, 1);
    postMessage(Atomics.load(a, e.data.slot));
  }`;
  const url = URL.createObjectURL(new Blob([src], {type:'text/javascript'}));
  const workers = [new Worker(url), new Worker(url)];
  const buffer = new SharedArrayBuffer(128);
  const message = w => new Promise((resolve,reject) => {
    w.onmessage = e => resolve(e.data); w.onerror = e => reject(Error(e.message));
  });
  try {
    const ready = workers.map(message);
    workers.forEach(w => w.postMessage({buffer}));
    await Promise.all(ready);
    const results = workers.map(message);
    const start = performance.now();
    workers.forEach((w,i) => w.postMessage({buffer,run:true,slot:i*16}));
    const counts = await Promise.all(results);
    return {milliseconds:performance.now()-start,counts};
  } finally { workers.forEach(w=>w.terminate()); URL.revokeObjectURL(url); }
})().then(done,e=>done({error:String(e)}));
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', required=True)
parser.add_argument('--pairs', type=int, default=4)
args = parser.parse_args()
if args.pairs < 1:
    parser.error('--pairs must be positive')
fixture.PAGE = fixture.page_source()
server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), fixture.FixtureHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
samples = {False: [], True: []}
try:
    for pair in range(args.pairs):
        for serialized in ((False, True) if pair % 2 == 0 else (True, False)):
            with tempfile.TemporaryDirectory(prefix='cfx-parallel-cost-') as tmp:
                root = Path(tmp)
                profile = root/'profile'
                profile.mkdir()
                (profile/'user.js').write_text(fixture.profile_user_js(False) +
                    'user_pref("dom.workers.serialized-sab-access", ' +
                    str(serialized).lower() + ');\n')
                driver = fixture.make_driver(args.binary,profile,root/'driver.log')
                try:
                    driver.set_script_timeout(30)
                    driver.get(f'http://127.0.0.1:{server.server_port}/fixtures/probe.html?mode=idle')
                    result = driver.execute_async_script(SCRIPT)
                    assert result.get('counts') == [100000000,100000000], result
                    samples[serialized].append(result['milliseconds'])
                    print(json.dumps({'pair':pair,'serialized':serialized,**result}),flush=True)
                finally:
                    driver.quit()
    print(json.dumps({'samples':samples,'slowdown':statistics.median(samples[True])/statistics.median(samples[False])-1}),flush=True)
finally:
    server.shutdown()
    server.server_close()
    thread.join()
