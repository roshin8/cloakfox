"""Select repository-owned completed checkpoint jobs; never weaken source identity."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('engine_artifact', Path(__file__).with_name('engine_artifact.py'))
engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
api = engine.api


def revision_key(sha):
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('Invalid source revision')
    if subprocess.run(['git','cat-file','-e',sha+'^{commit}'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        subprocess.run(['git','fetch','--no-tags','--depth=1','origin',sha],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    return engine.input_key(ROOT,'chromium',sha)


def artifact_owned(artifact, run):
    return (not artifact.get('expired') and artifact.get('workflow_run',{}).get('id')==run['id']
            and artifact.get('workflow_run',{}).get('head_sha')==run['head_sha'])


def all_pages(path, field):
    rows=[]
    for page in range(1,11):
        result=api(path+('&' if '?' in path else '?')+f'per_page=100&page={page}')
        rows.extend(result[field])
        if len(result[field])<100:return rows
    raise ValueError('Producer metadata pagination exceeded bound')


def lineage(repository, artifact, run):
    if artifact.get('size_in_bytes',0)>1024*1024:
        raise ValueError('Oversized checkpoint lineage artifact')
    data=subprocess.check_output(['gh','api',f'repos/{repository}/actions/artifacts/{artifact["id"]}/zip'],timeout=90)
    if len(data)>1024*1024:raise ValueError('Oversized checkpoint lineage download')
    digest=artifact.get('digest')
    if not digest or digest!='sha256:'+hashlib.sha256(data).hexdigest():
        raise ValueError('Checkpoint lineage digest mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files=[i for i in archive.infolist() if Path(i.filename).name=='checkpoint-producer.json']
        if len(files)!=1 or files[0].file_size>65536:
            raise ValueError('Invalid checkpoint lineage file set')
        value=json.loads(archive.read(files[0]))
    if (value.get('workflowSha')!=run['head_sha'] or str(value.get('run'))!=str(run['id'])
            or value.get('runAttempt')!=run['run_attempt']):
        raise ValueError('Checkpoint lineage producer mismatch')
    return value


def resolve(repository, run_id):
    run=api(f'repos/{repository}/actions/runs/{int(run_id)}')
    if run.get('status')!='completed':raise ValueError('Producer run is still active; do not duplicate it')
    if not engine.trusted_run(run,repository,'chromium'):raise ValueError('Producer is not trusted')
    artifacts=all_pages(f'repos/{repository}/actions/runs/{int(run_id)}/artifacts','artifacts')
    jobs=all_pages(f'repos/{repository}/actions/runs/{int(run_id)}/jobs','jobs')
    all_artifacts=artifacts
    artifacts=[a for a in artifacts if artifact_owned(a,run)]
    # A complete SDK needs no expired intermediate checkpoint/tool artifacts.
    if engine.completed_gate(jobs,'chromium'):
        records=[a for a in artifacts if re.fullmatch('chromium-checkpoint-producer-[1-9][0-9]*',a['name'])]
        record=lineage(repository,max(records,key=lambda a:int(a['name'].rsplit('-',1)[1])),run) if records else None
        sha=record['sourceSha'] if record else run['head_sha']
        key=revision_key(sha)
        if record and record.get('key')!=key:raise ValueError('SDK lineage source/input mismatch')
        if engine.find(repository,'chromium',key)['found']=='true':
            return {'source-sha':sha,'key':key,'checkpoint-run':'0','checkpoint-artifact':'',
                    'checkpoint-name':'','segment-base':'0','tools-artifact':'','tools-name':''}
    candidates=[]
    for a in artifacts:
        match=re.fullmatch('chromium-workspace-([1-9][0-9]*)',a['name'])
        if match:candidates.append((int(match[1]),a))
    for number,artifact in sorted(candidates,reverse=True):
        records=[a for a in artifacts if a['name']==f'chromium-checkpoint-producer-{number}']
        if len(records)>1:raise ValueError('Ambiguous checkpoint lineage')
        if not records and any(a['name']==f'chromium-checkpoint-producer-{number}' for a in all_artifacts):
            raise ValueError('Required checkpoint lineage expired or foreign')
        record=lineage(repository,records[0],run) if records else None
        stage=record['stage'] if record else number
        if type(stage) is not int or not 1<=stage<=12:raise ValueError('Invalid producer stage')
        name='source' if stage==1 else f'source{stage}'
        source_jobs=[j for j in jobs if j.get('name','').split(' / ')[-2:]==[name,'segment']]
        if not any(j.get('status')=='completed' and j.get('conclusion')=='success' for j in source_jobs):continue
        sha=record['sourceSha'] if record else run['head_sha']
        key=revision_key(sha)
        if record and (record.get('segment')!=number or record.get('key')!=key):
            raise ValueError('Checkpoint lineage source/input mismatch')
        tools=[a for a in artifacts if a['name']==f'chromium-host-tools-{run_id}-{run["run_attempt"]}']
        if len(tools)!=1:raise ValueError('Missing exact producer host tools')
        return {'checkpoint-run':str(run_id),'checkpoint-artifact':str(artifact['id']),
                'checkpoint-name':artifact['name'],'source-sha':sha,'key':key,
                'segment-base':str(number),'tools-artifact':str(tools[0]['id']),
                'tools-name':tools[0]['name']}
    if engine.completed_gate(jobs,'chromium'):
        records=[a for a in artifacts if re.fullmatch('chromium-checkpoint-producer-[1-9][0-9]*',a['name'])]
        record=lineage(repository,max(records,key=lambda a:int(a['name'].rsplit('-',1)[1])),run) if records else None
        sha=record['sourceSha'] if record else run['head_sha']
        key=revision_key(sha)
        if record and record.get('key')!=key:raise ValueError('SDK lineage source/input mismatch')
        return {'source-sha':sha,'key':key,'checkpoint-run':'0','checkpoint-artifact':'',
                'checkpoint-name':'','segment-base':'0','tools-artifact':'','tools-name':''}
    raise ValueError('No verified successful source checkpoint available; refusing cold restart')


def find_partial(repository,key):
    runs=api(f'repos/{repository}/actions/runs?status=completed&per_page=20')['workflow_runs']
    for run in runs[:20]:
        if not engine.trusted_run(run,repository,'chromium'):continue
        try:result=resolve(repository,run['id'])
        except ValueError:continue
        if result['key']==key:return result
    return None


def choose(repository,run_id=0):
    if run_id:
        result=resolve(repository,run_id)
        sdk=engine.find(repository,'chromium',result['key'])
        if not result['checkpoint-artifact'] and sdk['found']!='true':
            raise ValueError('Completed SDK unavailable; refusing cold restart')
        return {**result,**sdk,'segments':json.dumps(list(range(int(result['segment-base'])+1,int(result['segment-base'])+13)))}
    key=engine.input_key(ROOT,'chromium')
    sdk=engine.find(repository,'chromium',key)
    result={'source-sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'checkpoint-run':'0','checkpoint-artifact':'','checkpoint-name':'',
            'segment-base':'0','tools-artifact':'','tools-name':''}
    if sdk['found']!='true':result=find_partial(repository,key) or result
    return {**result,**sdk,'segments':json.dumps(list(range(int(result['segment-base'])+1,int(result['segment-base'])+13)))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True)
    parser.add_argument('--run',type=int,default=0)
    args=parser.parse_args()
    engine.outputs(choose(args.repository,args.run))
