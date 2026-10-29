from library_audit_common import observed_gpu_recognized

def complete():
 return {'canvasWebgl':{'$hash':'a'*64,'parameters':{'UNMASKED_RENDERER_WEBGL':'NVIDIA reference','MAX_TEXTURE_SIZE':16384,'MAX_VIEWPORT_DIMS':[32767,32767],'MAX_ELEMENT_INDEX':4294967294,'MAX_TEXTURE_LOD_BIAS':2}},'trash':{'trashBin':[]}}

def test_requires_real_webgl_collection():
 assert not observed_gpu_recognized({'trash':{'trashBin':[]}})
 assert not observed_gpu_recognized({'canvasWebgl':{'parameters':{}},'trash':{'trashBin':[]}})
 assert observed_gpu_recognized(complete())

def test_requires_complete_parameters_and_explicit_warning_collection():
 for key in list(complete()['canvasWebgl']['parameters']):
  value=complete();del value['canvasWebgl']['parameters'][key];assert not observed_gpu_recognized(value)
 value=complete();del value['trash'];assert not observed_gpu_recognized(value)
 value=complete();del value['canvasWebgl']['$hash'];assert not observed_gpu_recognized(value)

def test_actual_warnings_reject_but_unrelated_warnings_are_preserved():
 for name in ['suspicious gpu','suspicious capabilities']:
  value=complete();value['trash']['trashBin']=[{'value':name}];assert not observed_gpu_recognized(value)
 value=complete();value['trash']['trashBin']=[{'value':'unrelated warning'}];assert observed_gpu_recognized(value)
