"""Schema2 contract tests; fake validators are not native capability evidence."""
import copy
import unittest
from engines.shared import engine_policy as policy

GROUPS=('identity','displayFonts','graphics','audioMedia','regionPermissions',
        'timingMath','inputHardening','mediaNetwork','storagePolicies','packagingServices')

def sample():
    snapshot={'schemaVersion':2,'engine':'chromium','engineVersion':'154.0.8037.98',
              'owner':{'containerId':0,'backendContainerId':'1','private':False,'privateSession':None},
              'revision':1,'enabled':True,'presentation':'same-window',
              'personaSeed':'ab'*32,'groups':{key:{'version':1,'config':{}} for key in GROUPS}}
    capabilities={'schemaVersion':2,'engine':'chromium','engineVersion':'154.0.8037.98',
                  'groups':dict.fromkeys(GROUPS,1),'presentations':{'same-window':1,'separate-window':1}}
    def validate(config):
        if config!={}:raise ValueError('Unsupported test configuration')
        return True
    return snapshot,capabilities,dict.fromkeys(GROUPS,validate)

class PolicyContract(unittest.TestCase):
    def validate(self,*args,**kwargs):
        self.assertTrue(hasattr(policy,'validate_policy'),'Complete policy contract is missing')
        kwargs.setdefault('expected_owner',sample()[0]['owner'])
        kwargs.setdefault('expected_revision',1)
        return policy.validate_policy(*args,**kwargs)

    def test_complete_contract_keeps_an_immutable_private_copy(self):
        value,caps,validators=sample();result=self.validate(value,caps,validators=validators)
        value['personaSeed']='cd'*32;caps['groups']['graphics']=0
        self.assertEqual(result.snapshot()['personaSeed'],'ab'*32)
        altered=result.snapshot();altered['groups']['graphics']['version']=9
        self.assertEqual(result.snapshot()['groups']['graphics']['version'],1)
        self.assertNotIn('abababab',repr(result))

    def test_missing_or_old_group_rejects_in_either_presentation(self):
        for mode in ('same-window','separate-window'):
            for name in GROUPS:
                for wrong in (None,0,2,True,'1'):
                    value,caps,validators=sample();value['presentation']=mode
                    if wrong is None:del caps['groups'][name]
                    else:caps['groups'][name]=wrong
                    with self.subTest(mode=mode,group=name,wrong=wrong),self.assertRaises(ValueError):
                        self.validate(value,caps,validators=validators)

    def test_self_reported_capability_cannot_replace_a_native_validator(self):
        value,caps,validators=sample()
        with self.assertRaises(ValueError):self.validate(value,caps)
        for name in GROUPS:
            missing=dict(validators);missing.pop(name)
            with self.subTest(name=name),self.assertRaises(ValueError):self.validate(value,caps,validators=missing)
        value['groups']['identity']['config']={'unrecognized':True}
        with self.assertRaises(ValueError):self.validate(value,caps,validators=validators)

    def test_group_config_failure_has_no_sensitive_exception_payload(self):
        value,caps,validators=sample()
        def fail(_):raise RuntimeError('private seed '+value['personaSeed'])
        validators['identity']=fail
        with self.assertRaises(ValueError) as raised:self.validate(value,caps,validators=validators)
        self.assertNotIn(value['personaSeed'],str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_unknown_missing_fields_and_wrong_scalar_types_reject(self):
        value,caps,validators=sample()
        bad=[]
        for key in list(value):
            item=copy.deepcopy(value);item.pop(key);bad.append(item)
        for key,wrong in [('schemaVersion',True),('revision',True),('revision',0),('revision',2147483648),
                          ('enabled',1),('engine','gecko'),('engineVersion','154.0.0.0'),
                          ('personaSeed','0'*63),('presentation','fallback'),('extra',True)]:
            item=copy.deepcopy(value);item[key]=wrong;bad.append(item)
        for item in bad:
            with self.subTest(value=item.keys()),self.assertRaises(ValueError):self.validate(item,caps,validators=validators)

    def test_default_container_mapping_and_private_ownership_are_strict(self):
        for private,session in [(True,None),(False,'01'*16),(True,'bad'),(True,True)]:
            value,caps,validators=sample();value['owner'].update(private=private,privateSession=session)
            with self.subTest(private=private,session=session),self.assertRaises(ValueError):self.validate(value,caps,validators=validators)
        for container,backend in [(0,'2'),(1,'1'),(True,'2'),(-1,'0'),('0','1')]:
            value,caps,validators=sample();value['owner'].update(containerId=container,backendContainerId=backend)
            with self.subTest(container=container),self.assertRaises(ValueError):self.validate(value,caps,validators=validators)
        value,caps,validators=sample();value['owner'].update(containerId=1,backendContainerId='2',private=True,privateSession='01'*16)
        self.validate(value,caps,validators=validators,expected_owner=value['owner'])

    def test_unknown_group_and_missing_protections_reject_even_master_off(self):
        for name in GROUPS:
            value,caps,validators=sample();value['enabled']=False;del value['groups'][name]
            with self.subTest(name=name),self.assertRaises(ValueError):self.validate(value,caps,validators=validators)
        value,caps,validators=sample();value['groups']['extra']={'version':1,'config':{}}
        with self.assertRaises(ValueError):self.validate(value,caps,validators=validators)

    def test_unsupported_presentation_never_uses_another_mode(self):
        value,caps,validators=sample();caps['presentations']['same-window']=0
        with self.assertRaises(ValueError):self.validate(value,caps,validators=validators)
        value['presentation']='separate-window';self.validate(value,caps,validators=validators)

    def test_non_json_and_oversized_payloads_reject_before_group_validation(self):
        for wrong in [float('nan'),float('inf'),b'bytes',object(),'x'*70000]:
            value,caps,validators=sample();value['groups']['graphics']['config']={'test':wrong}
            with self.subTest(kind=type(wrong).__name__),self.assertRaises(ValueError):self.validate(value,caps,validators=validators)

    def test_prepared_owner_and_revision_cannot_be_replayed_or_retargeted(self):
        value,caps,validators=sample()
        with self.assertRaises(ValueError):
            self.validate(value,caps,validators=validators,expected_revision=2)
        other=copy.deepcopy(value['owner']);other.update(containerId=1,backendContainerId='2')
        with self.assertRaises(ValueError):
            self.validate(value,caps,validators=validators,expected_owner=other)

    def test_acknowledgement_binds_exact_owner_and_revision_without_seed(self):
        value,caps,validators=sample();result=self.validate(value,caps,validators=validators)
        self.assertTrue(hasattr(result,'validate_ack'),'Revision-bound acknowledgement is missing')
        ack={key:copy.deepcopy(value[key]) for key in ('schemaVersion','engine','engineVersion','owner','revision')}
        result.validate_ack(ack)
        for key,wrong in [('revision',2),('revision',True),('engine','gecko'),('engineVersion','154.0.0.0'),('personaSeed',value['personaSeed'])]:
            bad=copy.deepcopy(ack);bad[key]=wrong
            with self.subTest(key=key),self.assertRaises(ValueError):result.validate_ack(bad)
        ack['owner']['private']=0
        with self.assertRaises(ValueError):result.validate_ack(ack)

    def test_false_or_ambiguous_native_validation_cannot_acknowledge_a_group(self):
        for result in (False,None,0,1,{},'ok'):
            value,caps,validators=sample();validators['graphics']=lambda _,result=result:result
            with self.subTest(result=result),self.assertRaises(ValueError):
                self.validate(value,caps,validators=validators)

    def test_callbacks_cannot_change_the_snapshot_seen_by_later_validators(self):
        value,caps,validators=sample()
        value['groups']['graphics']['config']={'forbidden':'must be validated'}
        def mutate(_):
            value['groups']['graphics']['config']={}
            return True
        validators['identity']=mutate
        with self.assertRaises(ValueError):self.validate(value,caps,validators=validators)

    def test_callbacks_cannot_replace_later_native_validators(self):
        value,caps,validators=sample()
        def reject(_):return False
        def mutate(_):
            validators['graphics']=lambda _:True
            return True
        validators['identity']=mutate;validators['graphics']=reject
        with self.assertRaises(ValueError):self.validate(value,caps,validators=validators)

    def test_total_node_budget_rejects_before_unbounded_serialization(self):
        from unittest.mock import patch
        value,caps,validators=sample()
        value['groups']['graphics']['config']={'huge':[['']*4096]*4096}
        with patch('json.dumps',side_effect=AssertionError('Oversized tree reached serialization')):
            with self.assertRaises(ValueError):self.validate(value,caps,validators=validators)

    def test_acknowledgement_uses_the_same_cumulative_resource_budget(self):
        from unittest.mock import patch
        value,caps,validators=sample();result=self.validate(value,caps,validators=validators)
        ack={key:copy.deepcopy(value[key]) for key in ('schemaVersion','engine','engineVersion','owner','revision')}
        ack['owner']['privateSession']=[['']*4096]*4096
        with patch('json.dumps',side_effect=AssertionError('Oversized ack reached serialization')):
            with self.assertRaises(ValueError):result.validate_ack(ack)

    def test_serialization_never_revisits_the_mutable_original(self):
        from unittest.mock import patch
        import json
        value,caps,validators=sample()
        dumps=json.dumps;first=True
        def mutate_then_encode(obj,*args,**kwargs):
            nonlocal first
            if first:
                first=False
                value['groups']['graphics']['config']={'forbidden':'added after bounded copy'}
            return dumps(obj,*args,**kwargs)
        with patch('json.dumps',side_effect=mutate_then_encode):
            result=self.validate(value,caps,validators=validators)
        self.assertEqual(result.snapshot()['groups']['graphics']['config'],{})
