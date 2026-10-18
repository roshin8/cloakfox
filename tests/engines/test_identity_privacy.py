"""Owned native navigator/header/worker/Intl fixtures; no challenge websites."""
import copy
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore
from probe_cef_isolation import Companion

READ = """async function identity(){
 const n=navigator;const ua=n.userAgentData;
 return {ua:n.userAgent,appVersion:n.appVersion,platform:n.platform,cpu:n.hardwareConcurrency,memory:n.deviceMemory,
 language:n.language,languages:Array.from(n.languages),locale:Intl.NumberFormat().resolvedOptions().locale,
 timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
 winter:new Date('2026-01-15T12:00:00Z').getTimezoneOffset(),summer:new Date('2026-07-15T12:00:00Z').getTimezoneOffset(),
 epoch:Date.UTC(2026,0,15,12),explicit:Intl.DateTimeFormat('en-US',{timeZone:'UTC'}).resolvedOptions().timeZone,
 hints:ua?await ua.getHighEntropyValues(['architecture','bitness','platformVersion','model','fullVersionList','uaFullVersion','wow64']):null};}
"""
PRESET={'hardwareConcurrency':4,'deviceMemory':4,'languages':['fr-FR','fr'],'timezone':'Europe/Paris'}

class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.headers_by_path[self.path]=dict(self.headers)
        if self.path.startswith('/headers'):
            raw=json.dumps(dict(self.headers)).encode(); kind='application/json'
        elif self.path=='/worker.js':
            raw=(READ+"const first=identity();onmessage=async()=>postMessage({first:await first,current:await identity(),headers:await(await fetch('/headers')).json()});").encode();kind='application/javascript'
        elif self.path=='/shared.js':
            raw=(READ+"const first=identity();onconnect=e=>{const p=e.ports[0];p.onmessage=async()=>p.postMessage(await first);p.start()};").encode();kind='application/javascript'
        elif self.path=='/sw.js':
            raw=(READ+"const first=identity();oninstall=()=>skipWaiting();onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.waitUntil(first.then(v=>e.ports[0].postMessage(v)));").encode();kind='application/javascript'
        else:
            raw=('<!doctype html><script>'+READ+'globalThis.firstIdentity=identity();</script>').encode();kind='text/html'
        self.send_response(200);self.send_header('Content-Type',kind)
        self.send_header('Accept-CH','Sec-CH-UA-Arch, Sec-CH-UA-Bitness, Sec-CH-UA-Platform-Version, Sec-CH-UA-Model, Sec-CH-UA-Full-Version-List, Device-Memory, Sec-CH-Device-Memory')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def log_message(self,*args):pass

class IdentityPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('CLOAKFOX_CHROMIUM_BIN'):raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN')
        cls.binary=Path(os.environ['CLOAKFOX_CHROMIUM_BIN']);cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        cls.server.headers_by_path={}
        threading.Thread(target=cls.server.serve_forever,daemon=True).start();cls.url=f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.root=tempfile.TemporaryDirectory(prefix='cloakfox-identity-');self.store=PersonaStore(Path(self.root.name)/'personas');self.app=Companion(self.binary,Path(self.root.name))
    def tearDown(self):self.app.close();self.root.cleanup()
    def configured(self,container='1',preset=PRESET,enabled=True,**options):
        self.assertIn(self.app.ready.get('identityPrivacyVersion'),(1,2),'Native identity patch not present')
        config=self.store.get(container,'chromium')
        # Explicit test snapshot; controller-store validation/generation has separate tests.
        config['persona']['presentation']=copy.deepcopy(preset)
        config['persona']['options'].update({'navigator':True,'language':True,'timezone':True,**options})
        config['enabled']=enabled
        ack=self.app.rpc('applyConfig',config=config);self.assertTrue(ack['ok'],ack)
        browser=self.app.open(container,self.url,configRevision=config['revision'])
        return config,browser
    def read(self,browser):return self.app.evaluate(browser,'(async()=>{'+READ+'return identity()})()')
    def assert_masked(self,value,preset=PRESET):
        self.assertEqual(value['cpu'],preset['hardwareConcurrency']);self.assertEqual(value['memory'],preset['deviceMemory'])
        self.assertEqual(value['languages'],preset['languages']);self.assertEqual(value['language'],preset['languages'][0])
        self.assertEqual(value['locale'],preset['languages'][0]);self.assertEqual(value['timezone'],preset['timezone'])
        self.assertEqual(value['epoch'],1768478400000);self.assertEqual(value['explicit'],'UTC')
        self.assertIn('Chrome/154.',value['ua']);self.assertNotIn('Firefox',value['appVersion'])
        for name in ('architecture','bitness','platformVersion','model'):self.assertEqual(value['hints'][name],'')
    def test_browserforge_processor_counts_reach_all_realms_before_script(self):
        self.assertGreaterEqual(self.app.ready.get('identityPrivacyVersion',0),2,'BrowserForge CPU extension is not built')
        for count in (2,12,24):
            with self.subTest(count=count):
                preset={**PRESET,'hardwareConcurrency':count}
                _,browser=self.configured(str(100+count),preset=preset)
                page=self.app.evaluate(browser,'firstIdentity');self.assert_masked(page,preset)
                worker=self.app.evaluate(browser,"new Promise(r=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();r(e.data)};w.postMessage(1)})")
                self.assertEqual(worker['first'],page);self.assertEqual(worker['current'],page)
                shared=self.app.evaluate(browser,"new Promise(r=>{const w=new SharedWorker('/shared.js');w.port.onmessage=e=>r(e.data);w.port.start();w.port.postMessage(1);globalThis.keepShared=w})")
                self.assertEqual(shared,page)
                service=self.app.evaluate(browser,"(async()=>{const reg=await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;const c=new MessageChannel();const answer=new Promise(r=>c.port1.onmessage=e=>r(e.data));reg.active.postMessage(1,[c.port2]);return answer})()")
                self.assertEqual(service,page)

    def test_first_script_frames_workers_and_native_getters_agree(self):
        _,browser=self.configured();page=self.app.evaluate(browser,'firstIdentity');self.assert_masked(page)
        self.assertEqual(page['winter'],-60);self.assertEqual(page['summer'],-120)
        frame=self.app.evaluate(browser,"new Promise(r=>{const f=document.createElement('iframe');f.src='/';f.onload=async()=>r(await f.contentWindow.firstIdentity);document.body.append(f)})")
        self.assertEqual(frame,page)
        worker=self.app.evaluate(browser,"new Promise(r=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();r(e.data)};w.postMessage(1)})")
        self.assertEqual(worker['first'],page);self.assertEqual(worker['current'],page)
        worker_headers={k.lower():v for k,v in worker['headers'].items()}
        self.assertTrue(worker_headers['accept-language'].startswith('fr-FR,fr'))
        self.assertIn('Chrome/154.',worker_headers['user-agent'])
        for name in ('sec-ch-ua-arch','sec-ch-ua-bitness','sec-ch-ua-platform-version','sec-ch-ua-model'):
            if name in worker_headers:self.assertEqual(worker_headers[name],'""')
        shared=self.app.evaluate(browser,"new Promise(r=>{const w=new SharedWorker('/shared.js');w.port.onmessage=e=>r(e.data);w.port.start();w.port.postMessage(1);globalThis.keepShared=w})")
        self.assertEqual(shared,page)
        service=self.app.evaluate(browser,"(async()=>{const reg=await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;const w=reg.active;const c=new MessageChannel();const v=new Promise(r=>c.port1.onmessage=e=>r(e.data));w.postMessage(1,[c.port2]);return v})()")
        self.assertEqual(service,page)
        native=self.app.evaluate(browser,"({own:Object.hasOwn(navigator,'hardwareConcurrency'),getter:String(Object.getOwnPropertyDescriptor(Navigator.prototype,'hardwareConcurrency').get),frozen:Object.isFrozen(navigator.languages)})")
        self.assertFalse(native['own']);self.assertIn('[native code]',native['getter']);self.assertTrue(native['frozen'])
    def test_http_hints_and_languages_match_and_restart_restores_native(self):
        config,browser=self.configured()
        headers=self.app.evaluate(browser,"fetch('/headers').then(r=>r.json())")
        headers={k.lower():v for k,v in headers.items()}
        self.assertTrue(headers['accept-language'].startswith('fr-FR,fr'))
        self.assertIn('Chrome/154.',headers['user-agent'])
        for name in ('sec-ch-ua-arch','sec-ch-ua-bitness','sec-ch-ua-platform-version','sec-ch-ua-model'):
            self.assertEqual(headers.get(name),'""',headers)
        self.assertEqual(headers.get('sec-ch-device-memory',headers.get('device-memory')),'4')
        path='/navigation-headers?identity=masked'
        self.app.rpc('navigate',browser=browser,url=self.url+path[1:])
        for _ in range(100):
            if path in self.server.headers_by_path:break
            time.sleep(.03)
        navigation={k.lower():v for k,v in self.server.headers_by_path[path].items()}
        for name in ('sec-ch-ua-arch','sec-ch-ua-bitness','sec-ch-ua-platform-version','sec-ch-ua-model'):
            self.assertEqual(navigation.get(name),'""',navigation)
        self.assertEqual(navigation.get('sec-ch-device-memory',navigation.get('device-memory')),'4')
        self.app.close();self.app=Companion(self.binary,Path(self.root.name))
        config['enabled']=False;config['revision']+=1
        self.assertTrue(self.app.rpc('applyConfig',config=config)['ok'])
        restored=self.app.open('1',self.url,configRevision=config['revision'])
        baseline=self.app.open('99',self.url)
        self.assertEqual(self.read(restored),self.read(baseline),'Master-off retained previous presentation')
        restored_headers=self.app.evaluate(restored,"fetch('/headers').then(r=>r.json())")
        baseline_headers=self.app.evaluate(baseline,"fetch('/headers').then(r=>r.json())")
        self.assertEqual(restored_headers.get('Accept-Language'),baseline_headers.get('Accept-Language'))
    def test_containers_and_independent_toggles_do_not_contaminate(self):
        _,a=self.configured()
        preset={'hardwareConcurrency':8,'deviceMemory':8,'languages':['en-US','en'],'timezone':'America/New_York'}
        _,b=self.configured('2',preset)
        self.assert_masked(self.read(a));self.assert_masked(self.read(b),preset)
        self.assertEqual(self.read(b)['winter'],300);self.assertEqual(self.read(b)['summer'],240)
        config=self.store.get('3','chromium');config['persona']['presentation']=copy.deepcopy(PRESET)
        config['persona']['options'].update(navigator=False,language=False,timezone=False)
        self.assertTrue(self.app.rpc('applyConfig',config=config)['ok'])
        native=self.app.open('3',self.url,configRevision=config['revision']);baseline=self.app.open('99',self.url)
        self.assertEqual(self.read(native),self.read(baseline))
    def test_any_canonical_locale_and_zone_reach_the_page_and_headers(self):
        # The UTC offsets prove the zone itself reaches Intl/Date, not only the
        # reported id string. Three cases are DST-free and one observes DST, and
        # one list is a three-part language-Script-REGION tag whose reported
        # locale and language must round-trip exactly.
        cases=(('7',{'hardwareConcurrency':8,'deviceMemory':8,'languages':['ko-KR','ko'],'timezone':'Asia/Seoul'},-540,-540),
               ('8',{'hardwareConcurrency':4,'deviceMemory':8,'languages':['pt-BR','pt','en'],'timezone':'America/Sao_Paulo'},180,180),
               ('9',{'hardwareConcurrency':4,'deviceMemory':8,'languages':['zh-Hant-TW','zh-Hant','zh'],'timezone':'Asia/Taipei'},-480,-480),
               ('10',{'hardwareConcurrency':8,'deviceMemory':4,'languages':['sv-SE','sv'],'timezone':'Europe/Stockholm'},-60,-120))
        for container,preset,winter,summer in cases:
            with self.subTest(timezone=preset['timezone']):
                _,browser=self.configured(container,preset)
                page=self.read(browser);self.assert_masked(page,preset)
                self.assertEqual(page['winter'],winter);self.assertEqual(page['summer'],summer)
                headers={k.lower():v for k,v in self.app.evaluate(browser,"fetch('/headers').then(r=>r.json())").items()}
                self.assertTrue(headers['accept-language'].startswith(','.join(preset['languages'][:2])),headers['accept-language'])
                worker=self.app.evaluate(browser,"new Promise(r=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();r(e.data)};w.postMessage(1)})")
                self.assertEqual(worker['first'],page)

    def test_engine_refuses_an_unsupported_locale_or_zone(self):
        # The engine, not the store, is the authority for what it can render.
        # A refusal must be clean and fail closed: no container context, no
        # renderer, and never a silent fallback to the host language or zone.
        # CEF context creation has no error channel, so a value only the engine
        # can judge (an unknown locale, an unknown zone) surfaces as the
        # container-context refusal; a broken language list is still named
        # precisely by the embedded client, which needs no ICU for that.
        cases=(('11',{'languages':['xx-XX','xx']},'Cannot create container context'),
               ('12',{'timezone':'Mars/Olympus'},'Cannot create container context'),
               ('13',{'languages':['fr-FR','fr','fr-FR']},'Unsupported language list'),
               ('14',{'timezone':'mars/paris'},'Cannot create container context'))
        for container,changes,expected in cases:
            with self.subTest(changes=changes):
                config=self.store.get(container,'chromium')
                config['persona']['presentation']={**PRESET,**changes}
                config['persona']['options'].update({'navigator':True,'language':True,'timezone':True})
                ack=self.app.rpc('applyConfig',config=config)
                self.assertFalse(ack['ok'],ack)
                self.assertIn(expected,str(ack.get('error','')),ack)
                # The refusal left nothing behind: the same container still
                # accepts a persona this engine can render.
                retry=self.store.get(container,'chromium')
                retry['persona']['presentation']=dict(PRESET)
                retry['persona']['options'].update({'navigator':True,'language':True,'timezone':True})
                accepted=self.app.rpc('applyConfig',config=retry)
                self.assertTrue(accepted['ok'],accepted)

    def test_every_sampling_preset_is_accepted_by_the_engine(self):
        # Sampling may only ever produce personas this engine can render: a
        # preset it refuses would leave a container that can never start, and
        # an ICU data set that moves could quietly turn a preset into a refusal.
        from engines.shared.persona_config import LOCALE_PRESETS
        for index,(languages,timezone) in enumerate(LOCALE_PRESETS):
            with self.subTest(languages=languages,timezone=timezone):
                container=str(200+index)
                config=self.store.get(container,'chromium')
                config['persona']['presentation']={'hardwareConcurrency':4,'deviceMemory':4,
                    'languages':list(languages),'timezone':timezone}
                config['persona']['options'].update({'navigator':True,'language':True,'timezone':True})
                ack=self.app.rpc('applyConfig',config=config)
                self.assertTrue(ack['ok'],ack)

    def test_each_toggle_preserves_other_groups(self):
        baseline=self.read(self.app.open('99',self.url))
        for container,disabled in (('4','navigator'),('5','language'),('6','timezone')):
            _,browser=self.configured(container,**{disabled:False})
            actual=self.read(browser)
            if disabled=='navigator':
                for key in ('cpu','memory','hints'):self.assertEqual(actual[key],baseline[key])
            else:
                self.assertEqual(actual['cpu'],4);self.assertEqual(actual['memory'],4)
            if disabled=='language':
                for key in ('language','languages','locale'):self.assertEqual(actual[key],baseline[key])
            else:self.assertEqual(actual['languages'],PRESET['languages']);self.assertEqual(actual['locale'],'fr-FR')
            if disabled=='timezone':
                for key in ('timezone','winter','summer'):self.assertEqual(actual[key],baseline[key])
            else:self.assertEqual(actual['timezone'],'Europe/Paris')

    def test_language_toggle_restores_native_after_masked_profile_restart(self):
        config,_=self.configured()
        self.app.close();self.app=Companion(self.binary,Path(self.root.name))
        config['revision']+=1;config['persona']['options']['language']=False
        self.assertTrue(self.app.rpc('applyConfig',config=config)['ok'])
        browser=self.app.open('1',self.url,configRevision=config['revision'])
        baseline=self.read(self.app.open('99',self.url));actual=self.read(browser)
        for key in ('language','languages','locale'):self.assertEqual(actual[key],baseline[key])
        self.assertEqual(actual['timezone'],'Europe/Paris');self.assertEqual(actual['cpu'],4)
