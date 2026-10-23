"""Bind Clang module caching to the already verified continuation identity."""
import argparse
import os
import subprocess
import json
from pathlib import Path


def compile_jobs(cpu_count, memory_bytes):
    # The measured Intel runs had three compiler workers and <6 GiB peak build RSS.
    # Use the fourth advertised core only on the measured >=14 GiB host class.
    return max(1,min(cpu_count,4 if memory_bytes>=14*1024**3 else 3))


def settings(receipt, context, engine_key, source_sha):
    record=json.loads(Path(receipt).read_text())
    identity=record.get('identity',{})
    if record.get('schemaVersion')!=1 or identity.get('gitSha')!=source_sha or not identity.get('hostBuildInputs'):
        raise ValueError('Missing original source/host checkpoint identity')
    # Archive bytes change each segment; compilation identity must not.
    Path(context).write_text(json.dumps({'engineKey':engine_key,'identity':identity},sort_keys=True,separators=(',',':'))+'\n')
    return {'CCACHE_DIRECT':'true','CCACHE_DEPEND':'true','CCACHE_SLOPPINESS':'modules',
            'CCACHE_COMPILERCHECK':'content','CCACHE_EXTRAFILES':str(context)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--context',type=Path,required=True)
    parser.add_argument('--key',required=True)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--github-env',type=Path,required=True)
    args=parser.parse_args()
    values=settings(args.receipt,args.context,args.key,args.source_sha)
    memory=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))
    values['CHROMIUM_COMPILE_JOBS']=str(compile_jobs(os.cpu_count() or 1,memory))
    with args.github_env.open('a') as stream:
        for key,value in values.items():stream.write(f'{key}={value}\n')
