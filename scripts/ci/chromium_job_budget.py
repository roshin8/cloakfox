"""Limit original Ninja time to the remaining hosted job budget, reserving publication time."""
import importlib.util,json,os,sys,time
from pathlib import Path

def compile_seconds(requested,deadline,now,reserve=90*60):
 return max(0,min(requested,int(deadline-now-reserve)))

def execute(recipe,deadline):
 spec=importlib.util.spec_from_file_location('original_chromium_recipe',recipe)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 original=module.Pipeline.run
 def run(self,name,command,cwd=None,time_budget_seconds=None):
  if name=='framework':
   if not time_budget_seconds:raise ValueError('Missing original Ninja time budget')
   budget=compile_seconds(time_budget_seconds,deadline,time.time())
   record={'deadline':deadline,'compileSeconds':budget,'requestedSeconds':time_budget_seconds,'checkpointReserveSeconds':90*60}
   print('JOB BUDGET '+json.dumps(record),flush=True)
   target=Path(os.environ['RUNNER_TEMP'])/'checkpoint-out/job-budget.json';target.write_text(json.dumps(record,indent=2)+'\n')
   if budget==0:return False
   time_budget_seconds=budget
  return original(self,name,command,cwd,time_budget_seconds)
 module.Pipeline.run=run
 module.main()

if __name__=='__main__':
 recipe=Path(sys.argv.pop(1)).resolve()
 deadline=int(os.environ['CHROMIUM_JOB_DEADLINE'])
 execute(recipe,deadline)
