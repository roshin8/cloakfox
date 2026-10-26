#!/usr/bin/env python3
"""Trace the full setup's bounded xcrun calls without compiling Chromium."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import metal_toolchain


def traced(argv, directory):
    stamp=time.monotonic()
    def event(**fields):
        with (directory/'commands.jsonl').open('a') as stream:
            stream.write(json.dumps({'argv':argv,'elapsed':round(time.monotonic()-stamp,3),**fields})+'\n')
        print(json.dumps(fields),flush=True)
    event(state='starting')
    child=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
    try:
        try:
            output,_=child.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            event(state='slow',pid=child.pid)
            # Record executable names only; no command-line arguments or env.
            listing=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,comm='],text=True,timeout=10)
            (directory/f'processes-{child.pid}.txt').write_text(listing)
            family={child.pid}
            rows=[line.split(None,2) for line in listing.splitlines()]
            for _ in range(5):
                family.update(int(row[0]) for row in rows if len(row)==3 and int(row[1]) in family)
            for pid in sorted(family)[:5]:
                with (directory/f'sample-{pid}.txt').open('w') as trace:
                    subprocess.run(['/usr/bin/sample',str(pid),'2'],stdout=trace,stderr=subprocess.STDOUT,timeout=10)
            output,_=child.communicate(timeout=max(1,120-(time.monotonic()-stamp)))
        event(state='finished',exitCode=child.returncode)
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode,argv,output=output)
        return output.strip()
    except BaseException:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.communicate()
        event(state='failed',exitCode=child.returncode)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=True)
    report={'shaderCompileAndLink':False}
    try:
        report=metal_toolchain.verify(args.directory,lambda argv:traced(argv,args.directory))
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        (args.directory/'diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
