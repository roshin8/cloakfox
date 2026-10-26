import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'scripts/ci/chromium_job_budget.py';s=importlib.util.spec_from_file_location('budget',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Budget(unittest.TestCase):
 def test_remaining_job_time_reserves_checkpoint_and_never_extends_requested(self):
  self.assertEqual(m.compile_seconds(180*60,350*60,128*60),132*60)
  self.assertEqual(m.compile_seconds(180*60,350*60,30*60),180*60)
  self.assertEqual(m.compile_seconds(180*60,350*60,270*60),0)
 def test_wrapper_preserves_recipe_and_noncompiler_stages(self):
  import tempfile,os,json,hashlib
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'checkpoint-out').mkdir();recipe=root/'recipe.py'
   recipe.write_text("class Pipeline:\n def run(self,name,command,cwd=None,time_budget_seconds=None):\n  calls.append([name,time_budget_seconds]);return True\ncalls=[]\ndef main():\n p=Pipeline();p.run('prepare',[],None,None);p.run('framework',[],None,10800)\n import json,os\n from pathlib import Path\n Path(os.environ['RUNNER_TEMP'],'calls.json').write_text(json.dumps(calls))\n")
   before=hashlib.sha256(recipe.read_bytes()).hexdigest()
   with patch.dict(os.environ,{'RUNNER_TEMP':str(root)}),patch.object(m.time,'time',return_value=128*60):m.execute(recipe,350*60)
   self.assertEqual(json.loads((root/'calls.json').read_text()),[['prepare',None],['framework',132*60]])
   self.assertEqual(hashlib.sha256(recipe.read_bytes()).hexdigest(),before)
