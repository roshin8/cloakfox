import unittest
from real_media_checks import validate_report


def report():
    video = {'videoTracks':1,'frames':3,'liveUnmuted':True,'recordedBytes':2048,'videoWidth':640,'videoHeight':480}
    return {'mediaSavedOrUploaded':False,'runtime':{'version':'159.0-beta.1','enabled':True,'fake':False,'permissionBypass':False},
            'results':{'camera':dict(video,audioTracks=1,audioSamplesObserved=256,audioVaries=True),'screen':dict(video,audioTracks=0)}}


class RealMediaChecks(unittest.TestCase):
    def test_both_real_paths_require_positive_capture_metrics(self):
        validate_report(report())
        for stage,field,value in [('camera','frames',0),('camera','audioVaries',False),('screen','recordedBytes',0),('screen','liveUnmuted',False),('camera','audioSamplesObserved',0)]:
            r=report();r['results'][stage][field]=value
            with self.assertRaises(ValueError): validate_report(r)

    def test_fake_or_bypassed_or_unprotected_device_is_not_a_pass(self):
        for field,value in [('fake',True),('permissionBypass',True),('enabled',False),('version','158.0')]:
            r=report();r['runtime'][field]=value
            with self.assertRaises(ValueError): validate_report(r)

    def test_chooser_error_or_missing_stage_is_not_a_pass(self):
        r=report();r['results']['screen']={'error':'NotAllowedError'}
        with self.assertRaises(ValueError): validate_report(r)
        del r['results']['screen']
        with self.assertRaises(ValueError): validate_report(r)

    def test_media_persistence_or_non_integer_metrics_are_rejected(self):
        r=report();r['mediaSavedOrUploaded']=True
        with self.assertRaises(ValueError): validate_report(r)
        r=report();r['results']['camera']['frames']=True
        with self.assertRaises(ValueError): validate_report(r)
