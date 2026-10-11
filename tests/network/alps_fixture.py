"""Loopback BoringSSL server wrapper; ALPS transcript completes in real TLS."""
import json,os,select,subprocess,threading

class ALPSFixture:
    def __init__(self,certificate,key,settings=False,close_after_response=False):
        binary=os.environ.get('ALPS_SERVER')
        if not binary: raise RuntimeError('Build alps_server.cc against BoringSSL and set ALPS_SERVER')
        self.process=subprocess.Popen([binary,str(certificate),str(key)]+([settings if isinstance(settings,str) else 'settings'] if settings else [])+(['close'] if close_after_response else []),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        if not select.select([self.process.stdout],[],[],5)[0]:
            self.process.kill();self.process.wait(timeout=5);self.process.stdout.close()
            raise RuntimeError("ALPS server startup timed out")
        ready=self.process.stdout.readline()
        if not ready:
            self.process.wait(timeout=5);raise RuntimeError('ALPS server did not start')
        info=json.loads(ready);self.port=info['port'];self.ech_config=bytes.fromhex(info.get('echConfig',''));self.observed=[]
        def drain():
            for line in self.process.stdout:self.observed.append(json.loads(line))
        self.thread=threading.Thread(target=drain,daemon=True);self.thread.start()
    def close(self):
        self.process.terminate()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        self.thread.join(timeout=5);self.process.stdout.close()
