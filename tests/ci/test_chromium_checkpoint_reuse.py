import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[2]/'scripts/ci/chromium_checkpoint_reuse.py'
def load():
    spec=importlib.util.spec_from_file_location('reuse',PATH);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class CheckpointReuse(unittest.TestCase):
    def test_explicit_active_run_is_rejected_without_cold_fallback(self):
        m=load()
        with patch.object(m,'api',return_value={'status':'in_progress'}):
            with self.assertRaisesRegex(ValueError,'active'):
                m.resolve('owner/repo',12)

    def test_trusted_terminal_failed_parent_reuses_successful_segment_four(self):
        m=load();sha='a'*40
        run={'id':12,'status':'completed','conclusion':'failure','head_sha':sha,'run_attempt':1,
             'event':'workflow_dispatch','head_branch':'codex/chromium-intel-build','path':'.github/workflows/runner-survey.yml',
             'repository':{'full_name':'owner/repo'},'head_repository':{'full_name':'owner/repo'}}
        def artifact(id,name):return {'id':id,'name':name,'expired':False,'workflow_run':{'id':12,'head_sha':sha}}
        artifacts=[artifact(4,'chromium-workspace-4'),artifact(3,'chromium-workspace-3'),artifact(1,'chromium-host-tools-12-1')]
        jobs=[{'id':40,'name':'chromium-intel-build / source4 / segment','status':'completed','conclusion':'success'},
              {'id':30,'name':'chromium-intel-build / source3 / segment','status':'completed','conclusion':'success'}]
        def api(path):
            if '/artifacts?per_page=100' in path:return {'artifacts':artifacts}
            if '/jobs?' in path:return {'jobs':jobs}
            return run
        with patch.object(m,'api',side_effect=api),patch.object(m,'revision_key',return_value='b'*64):
            result=m.resolve('owner/repo',12)
        self.assertEqual(result['checkpoint-artifact'],'4')
        self.assertEqual(result['source-sha'],sha)
        self.assertEqual(result['segment-base'],'4')
        self.assertEqual(result['tools-artifact'],'1')

    def test_unsuccessful_source_and_foreign_artifact_are_rejected(self):
        m=load();sha='a'*40
        run={'id':12,'status':'completed','head_sha':sha,'run_attempt':1,'event':'workflow_dispatch',
             'head_branch':'codex/chromium-intel-build','path':'.github/workflows/runner-survey.yml',
             'repository':{'full_name':'owner/repo'},'head_repository':{'full_name':'evil/fork'}}
        with patch.object(m,'api',return_value=run):
            with self.assertRaisesRegex(ValueError,'trusted'):
                m.resolve('owner/repo',12)

    def producer_fixture(self):
        sha='a'*40
        run={'id':12,'status':'completed','head_sha':sha,'run_attempt':1,'event':'workflow_dispatch',
             'head_branch':'codex/chromium-intel-build','path':'.github/workflows/runner-survey.yml',
             'repository':{'full_name':'owner/repo'},'head_repository':{'full_name':'owner/repo'}}
        def artifact(id,name):return {'id':id,'name':name,'expired':False,'workflow_run':{'id':12,'head_sha':sha}}
        artifacts=[artifact(4,'chromium-workspace-8'),artifact(5,'chromium-checkpoint-producer-8'),artifact(1,'chromium-host-tools-12-1')]
        jobs=[{'name':'chromium-intel-build / source4 / segment','status':'completed','conclusion':'success'}]
        def api(path):
            if '/artifacts?' in path:return {'artifacts':artifacts}
            if '/jobs?' in path:return {'jobs':jobs}
            return run
        return run,artifacts,jobs,api

    def test_continuation_uses_original_source_and_logical_segment(self):
        m=load();run,artifacts,jobs,api=self.producer_fixture()
        record={'stage':4,'segment':8,'sourceSha':'c'*40,'key':'b'*64}
        with patch.object(m,'api',side_effect=api),patch.object(m,'lineage',return_value=record),patch.object(m,'revision_key',return_value='b'*64):
            result=m.resolve('owner/repo',12)
        self.assertEqual(result['source-sha'],'c'*40)
        self.assertEqual(result['segment-base'],'8')

    def test_expired_lineage_and_failed_source_cannot_be_reused(self):
        m=load();run,artifacts,jobs,api=self.producer_fixture()
        artifacts[1]['expired']=True
        with patch.object(m,'api',side_effect=api):
            with self.assertRaisesRegex(ValueError,'expired'):m.resolve('owner/repo',12)
        artifacts.pop(1);jobs[0]['conclusion']='failure'
        with patch.object(m,'api',side_effect=api):
            with self.assertRaisesRegex(ValueError,'No verified'):m.resolve('owner/repo',12)

    def test_incorrect_lineage_key_and_missing_tools_fail_closed(self):
        m=load();run,artifacts,jobs,api=self.producer_fixture()
        record={'stage':4,'segment':8,'sourceSha':'c'*40,'key':'wrong'}
        with patch.object(m,'api',side_effect=api),patch.object(m,'lineage',return_value=record),patch.object(m,'revision_key',return_value='b'*64):
            with self.assertRaisesRegex(ValueError,'source/input'):m.resolve('owner/repo',12)
            record['key']='b'*64;artifacts.pop()
            with self.assertRaisesRegex(ValueError,'host tools'):m.resolve('owner/repo',12)

    def test_explicit_checkpoint_four_starts_segment_five_without_cold_fallback(self):
        m=load()
        result={'checkpoint-artifact':'4','segment-base':'4','key':'key','source-sha':'a'*40}
        with patch.object(m,'resolve',return_value=result),patch.object(m.engine,'find',return_value={'found':'false','key':'key'}):
            chosen=m.choose('owner/repo',12)
        self.assertEqual(m.json.loads(chosen['segments']),list(range(5,17)))
        result['checkpoint-artifact']=''
        with patch.object(m,'resolve',return_value=result),patch.object(m.engine,'find',return_value={'found':'false','key':'key'}):
            with self.assertRaisesRegex(ValueError,'refusing cold'):m.choose('owner/repo',12)

    def test_lineage_zip_requires_digest_and_matching_controller(self):
        import io, zipfile, hashlib, json
        m=load();run,artifacts,jobs,api=self.producer_fixture()
        record={'workflowSha':run['head_sha'],'run':12,'runAttempt':1}
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as bundle:bundle.writestr('checkpoint-producer.json',json.dumps(record))
        data=buffer.getvalue();artifact={'id':5,'digest':'sha256:'+hashlib.sha256(data).hexdigest()}
        with patch.object(m.subprocess,'check_output',return_value=data):
            self.assertEqual(m.lineage('owner/repo',artifact,run),record)
            artifact['digest']='sha256:'+'0'*64
            with self.assertRaisesRegex(ValueError,'digest'):m.lineage('owner/repo',artifact,run)
            artifact['digest']='sha256:'+hashlib.sha256(data).hexdigest();run['run_attempt']=2
            with self.assertRaisesRegex(ValueError,'producer mismatch'):m.lineage('owner/repo',artifact,run)

    def test_completed_sdk_reuse_does_not_require_expired_intermediate_tools(self):
        m=load();run,artifacts,jobs,api=self.producer_fixture()
        artifacts.pop()
        jobs.append({'name':'chromium-intel-build / chromium-engine-complete','status':'completed','conclusion':'success'})
        record={'sourceSha':'c'*40,'key':'b'*64}
        with patch.object(m,'api',side_effect=api),patch.object(m,'lineage',return_value=record),patch.object(m,'revision_key',return_value='b'*64),patch.object(m.engine,'find',return_value={'found':'true'}):
            result=m.resolve('owner/repo',12)
        self.assertEqual(result['checkpoint-run'],'0')
        self.assertEqual(result['source-sha'],'c'*40)
