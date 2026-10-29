# Full fpgen GPU reference import

The offline importer reads only the bundled `fpgen-model-reference.zip`, verified
against `additions/cloakcfg/gpu-reference-source.json`. The source archive SHA256
is `6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936`.
Upstream is scrapfly/fingerprint-generator, model-2/2026, Apache-2.0; the existing
source metadata retains the complete license and attribution.

`reference_gpu_import.py --full` traverses every conditional browser/platform/GPU/
WebGL1/WebGL2 path. The separate generated evidence is
`additions/cloakcfg/gpu-full-reference-records.json.gz`, compressed with gzip level
9, no filename, and timestamp zero. Its SHA256 is
`54c9726596fab90c9c5e35ee59b236c8406dd16de7a8c3ab6623b273f2471ce5`.
The decoded canonical JSON SHA256 is
`d456d661abf8947714ca8ba4157e0d6ef3e421bd661e01eea31b753b5d968f6f`.

There are 886 conditional paths and 1,183 distinct observed contexts:

| Browser | Paths |
| --- | ---: |
| Chrome | 642 |
| Firefox | 106 |
| Edge | 91 |
| Opera | 38 |
| Yandex Browser | 5 |
| Safari | 3 |
| DuckDuckGo | 1 |

Every record remains `unvalidated-reference`. Forty-two paths have explicit
blockers, covering 65 incomplete contexts, seven empty context observations,
and four GPU/context owner mismatches. Counts describe context occurrences, so
multiple blockers can belong to one path. Owner mismatches block the individual
path; canonical context data can also occur under a legitimate owner elsewhere.
No WebGL1/WebGL2 cross product is synthesized. Token lineage, probabilities,
source hashes and actual paired observations remain intact.

The default importer still reproduces the original Firefox corpus and scalar
matrix without changes. The original corpus SHA256 remains
`8a5b474b1c7c296ce344cdbe6a4beb93c9a8c5428dfc6482287baaf6ecf65931`.

Reproduce and verify from the repository root:

```sh
firefox-src/.tools159/runtime-venv/bin/python scripts/reference_gpu_import.py additions/browser/components/cloakfox/fpgen-model-reference.zip --full --check
firefox-src/.tools159/runtime-venv/bin/python scripts/reference_gpu_import.py additions/browser/components/cloakfox/fpgen-model-reference.zip --check
firefox-src/.tools159/runtime-venv/bin/python -m unittest discover -s tests/fingerprint -p 'test*gpu_reference_import.py'
```

`load_full_catalog()` bounds compressed input to 4 MiB and decoded output to
64 MiB. Executable consumers independently pin the reviewed compressed hash;
loading reference evidence grants no native capability or privacy admission.
