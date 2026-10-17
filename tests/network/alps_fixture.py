"""Loopback BoringSSL server wrapper; ALPS transcript completes in real TLS."""
import json,os,select,subprocess,tempfile,threading
from pathlib import Path

class ALPSFixture:
    def __init__(self,certificate,key,settings=False,close_after_response=False):
        binary=os.environ.get('ALPS_SERVER')
        if not binary: raise RuntimeError('Build alps_server.cc against BoringSSL and set ALPS_SERVER')
        configured=os.environ.get('ALPS_FIXTURE_LOG_DIR') or os.environ.get('REPORT_DIR')
        directory=Path(configured) if configured else Path(tempfile.mkdtemp(prefix='cloakfox-alps-helper-'))
        directory.mkdir(parents=True,exist_ok=True)
        self.stdout_log=tempfile.NamedTemporaryFile(mode='w',prefix='alps-fixture-',suffix='.stdout.jsonl',dir=directory,delete=False)
        self.stderr_log=open(self.stdout_log.name.replace('.stdout.jsonl','.stderr.log'),'w')
        self.observed=[]
        self.thread=None
        self.process=None
        try:
            self.process=subprocess.Popen([binary,str(certificate),str(key)]+([settings if isinstance(settings,str) else 'settings'] if settings else [])+(['close'] if close_after_response else []),stdout=subprocess.PIPE,stderr=self.stderr_log,text=True)
            if not select.select([self.process.stdout],[],[],5)[0]:
                raise RuntimeError('ALPS server startup timed out')
            ready=self.process.stdout.readline()
            self.stdout_log.write(ready);self.stdout_log.flush()
            if not ready: raise RuntimeError('ALPS server did not start')
            info=json.loads(ready);self.port=info['port'];self.ech_config=bytes.fromhex(info.get('echConfig',''))
            def drain():
                for line in self.process.stdout:
                    self.stdout_log.write(line);self.stdout_log.flush()
                    self.observed.append(json.loads(line))
            self.thread=threading.Thread(target=drain,daemon=True);self.thread.start()
        except BaseException:
            self.close()
            raise
    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
            if self.thread is not None:self.thread.join(timeout=5)
            self.process.stdout.close()
        self.stdout_log.close();self.stderr_log.close()
