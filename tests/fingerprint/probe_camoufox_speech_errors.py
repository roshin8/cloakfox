"""Native voice-error forwarding controls in disposable profiles, without audio I/O."""
import json
import os
from pathlib import Path
import tempfile
from probe_daily_defaults import launch


def main():
    original=os.environ.get('CLOAK_CONFIG')
    try:
        for configured in [False,True]:
            if configured: os.environ['CLOAK_CONFIG']=json.dumps({'voices':[]})
            else: os.environ.pop('CLOAK_CONFIG',None)
            with tempfile.TemporaryDirectory(prefix='cloakfox-voice-errors-') as tmp:
                profile=Path(tmp)/'profile'; profile.mkdir()
                d=launch(profile,Path(tmp)/'gecko.log')
                try:
                    for enabled in [True,False]:
                        got=d.execute_script("""
                          Services.prefs.setBoolPref('cloakfox.enabled', arguments[0]);
                          const registry=Cc['@mozilla.org/synth-voice-registry;1'].getService(Ci.nsISynthVoiceRegistry);
                          let count=0;
                          const observer={observe(subject,topic,data){if(data==='local-followup-error')count++;}};
                          Services.obs.addObserver(observer,'synth-voices-error');
                          try { registry.notifyVoicesError('local-followup-error'); }
                          finally { Services.obs.removeObserver(observer,'synth-voices-error'); }
                          return count;
                        """,enabled)
                        expected=0 if configured and enabled else 1
                        assert got==expected,{'configured':configured,'enabled':enabled,'count':got}
                        print('PASS:',json.dumps({'configured':configured,'enabled':enabled,'forwarded':got}))
                finally: d.quit()
    finally:
        if original is None: os.environ.pop('CLOAK_CONFIG',None)
        else: os.environ['CLOAK_CONFIG']=original

if __name__=='__main__': main()
