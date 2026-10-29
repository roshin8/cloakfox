"""Reject false-positive physical media acceptance receipts."""


def validate_report(report):
    try:
        runtime = report['runtime']
        if not runtime['version'].startswith('159.') or runtime['enabled'] is not True or runtime['fake'] is not False or runtime['permissionBypass'] is not False:
            raise ValueError('Requires protected Firefox159 and real permission-gated devices')
        if report['mediaSavedOrUploaded'] is not False:
            raise ValueError('Physical test media must remain ephemeral and local')
        for stage in ('camera','screen'):
            observed = report['results'][stage]
            if 'error' in observed or observed['liveUnmuted'] is not True or observed['videoTracks'] != 1:
                raise ValueError('Live real video capture did not succeed: '+stage)
            for field in ('frames','recordedBytes','videoWidth','videoHeight'):
                if type(observed[field]) is not int or observed[field] <= 0:
                    raise ValueError('Missing decoded/encoded media: '+stage+'/'+field)
            if type(observed['audioTracks']) is not int or observed['audioTracks'] != (1 if stage=='camera' else 0):
                raise ValueError('Wrong captured media track inventory')
            if stage=='camera' and (type(observed['audioSamplesObserved']) is not int or observed['audioSamplesObserved']<=0 or observed['audioVaries'] is not True):
                raise ValueError('No varying microphone audio samples observed')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Incomplete physical media receipt') from error
    return report
