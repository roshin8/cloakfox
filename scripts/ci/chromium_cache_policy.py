"""Bind Clang module caching to the already verified continuation identity."""
import argparse
import json
from pathlib import Path


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
    with args.github_env.open('a') as stream:
        for key,value in values.items():stream.write(f'{key}={value}\n')
