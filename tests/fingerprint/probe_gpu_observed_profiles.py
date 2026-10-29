#!/usr/bin/env python3
"""Run full native profile acceptance for optional observed compatibility records."""
import os
from probe_gpu_reference_profiles import main
if __name__ == '__main__':
    os.environ['OBSERVED_GPU_MODE'] = '1'
    raise SystemExit(main())
