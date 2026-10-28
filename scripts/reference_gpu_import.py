#!/usr/bin/env python3
"""Import pinned fpgen Firefox GPU evidence, entirely offline.

Usage: python3 scripts/reference_gpu_import.py /path/to/model-release.zip [--check]
Requires zstandard for bounded decompression. Never imports fpgen: importing that
package can download unverified data. Observations are not executable profiles.
The model's Apache-2.0 license and attribution live in gpu-reference-source.json.
"""
import argparse
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "additions/cloakcfg/gpu-reference-source.json"
OUTPUT = ROOT / "additions/cloakcfg/gpu-reference-records.json"
MATRIX_OUTPUT = ROOT / "additions/cloakcfg/gpu-reference-matrix.json"
BACKEND_SOURCE = ROOT / "additions/cloakcfg/gpu-reference-backend.json"
MEMBER_BOUNDS = {"fingerprint-network.json.zst": 4 << 20,
                 "values.json.zst": 1 << 20, "values.dat.zst": 256 << 20}
PARENTS = {"browser": [], "platformInfo": ["browser"],
           "gpu": ["browser", "platformInfo"],
           "webgl": ["browser", "platformInfo", "gpu"],
           "webgl2": ["browser", "platformInfo", "gpu", "webgl"]}


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("non-finite JSON number")

    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding or nesting") from exc


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _bounded_archive(path, pin):
    # Pin arguments are an internal test seam. The CLI only uses the reviewed,
    # checked-in pin; it cannot bless an arbitrary download with its own hashes.
    import zstandard

    expected = pin["archive"]
    if path.stat().st_size > 4 << 20 or path.stat().st_size != expected["size"]:
        raise ValueError("archive size does not match pin or bound")
    archive = path.read_bytes()
    if _digest(archive) != expected["sha256"]:
        raise ValueError("archive sha256 does not match pin")
    if set(pin["files"]) != set(MEMBER_BOUNDS):
        raise ValueError("archive member names do not match expected safe names")
    result = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        infos = zf.infolist()
        if len(infos) != len(MEMBER_BOUNDS) or {i.filename for i in infos} != set(MEMBER_BOUNDS):
            raise ValueError("archive member names are unexpected or duplicate")
        for info in infos:
            member = pin["files"][info.filename]
            mode = stat.S_IFMT(info.external_attr >> 16)
            if mode not in (0, stat.S_IFREG) or info.flag_bits & 1:
                raise ValueError("archive member must be a regular unencrypted file")
            if not 0 < info.file_size <= 4 << 20 or info.file_size != member["size"]:
                raise ValueError("archive member size exceeds pin or bound")
            limit = member["decompressed_size"]
            if type(limit) is not int or not 0 < limit <= MEMBER_BOUNDS[info.filename]:
                raise ValueError("decompression size exceeds safe bound")
            compressed = zf.read(info)
            if _digest(compressed) != member["sha256"]:
                raise ValueError("archive member sha256 does not match pin")
            chunks, length = [], 0
            try:
                # Streaming enforces bounds even if the frame omits its size.
                with zstandard.ZstdDecompressor(max_window_size=16 << 20).stream_reader(io.BytesIO(compressed)) as reader:
                    while True:
                        chunk = reader.read(min(1 << 20, limit + 1 - length))
                        if not chunk:
                            break
                        length += len(chunk)
                        if length > limit:
                            raise ValueError("decompression size exceeds pinned bound")
                        chunks.append(chunk)
            except zstandard.ZstdError as exc:
                raise ValueError("invalid bounded zstd member") from exc
            raw = b"".join(chunks)
            if length != limit:
                raise ValueError("decompression size differs from pin")
            if _digest(raw) != member["decompressed_sha256"]:
                raise ValueError("decompressed sha256 does not match pin")
            result[info.filename.removesuffix(".zst")] = raw
    return result


class _Values:
    def __init__(self, index, data):
        if not isinstance(index, dict) or len(index) > 50000:
            raise ValueError("invalid values index")
        self.data, self.entries, self.cache = data, [], {}
        end = 0
        for offset, size in index.items():
            try:
                start = int(offset, 16)
            except (ValueError, TypeError) as exc:
                raise ValueError("invalid value offset") from exc
            if type(size) is not int or size < 1 or start != end or start + size > len(data):
                raise ValueError("value offset or size outside contiguous bounds")
            self.entries.append((start, size))
            end = start + size
        if end != len(data):
            raise ValueError("value index does not cover data bounds")

    def get(self, token):
        if token not in self.cache:
            try:
                if not isinstance(token, str) or not 1 <= len(token) <= 12:
                    raise ValueError("invalid index token")
                index = int.from_bytes(base64.b85decode(token), "big")
                start, size = self.entries[index]
            except (IndexError, TypeError, ValueError) as exc:
                raise ValueError("value token outside index bounds") from exc
            if size > 2 << 20:
                raise ValueError("GPU value exceeds safe record bound")
            self.cache[token] = _json(self.data[start:start + size])
        return self.cache[token]


def _distribution(nodes, name, evidence):
    node = nodes[name]
    branch = node["conditionalProbabilities"]
    try:
        for parent in node["parentNames"]:
            branch = branch[evidence[parent]]
    except (KeyError, TypeError) as exc:
        raise ValueError("missing conditional owner path for " + name) from exc
    if not isinstance(branch, dict) or not branch:
        raise ValueError("empty conditional distribution for " + name)
    for token, probability in branch.items():
        if token not in node["possibleValues"]:
            raise ValueError("conditional value not in node possibilities")
        if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 < probability <= 1:
            raise ValueError("invalid conditional probability")
    return branch


def _family(gpu):
    description = (gpu["vendor"] + " " + gpu["renderer"]).lower()
    for family in ("apple", "intel", "nvidia", "amd"):
        if family in description:
            return family
    return "amd" if "radeon" in description or "ati technologies" in description else "other"


def _os(platform):
    if "Windows" in platform:
        return "win"
    if "Macintosh" in platform:
        return "mac"
    if "Linux" in platform or "X11" in platform:
        return "lin"
    return "other"


def _context(observed, gpu):
    if observed == []:
        return {"observed": [], "staticCapabilities": None}
    required = {"params", "supportedExtensions", "extensions", "contextAttributes", "shaderPrecisionFormats", "vendor", "renderer"}
    if not isinstance(observed, dict) or not required <= observed.keys():
        raise ValueError("incomplete recorded GL context")
    if observed["vendor"] != gpu["vendor"] or observed["renderer"] != gpu["renderer"]:
        raise ValueError("GPU owner does not match recorded context pair")
    params = observed["params"]
    if not isinstance(params, dict) or not params:
        raise ValueError("invalid recorded GL parameters")
    static_params = {}
    for pname, param in params.items():
        if not pname.isdecimal() or not isinstance(param, dict) or not {"name", "type", "value"} <= param.keys():
            raise ValueError("invalid recorded GL parameter")
        name = param["name"]
        if name.startswith("MAX_") or name in ("ALIASED_LINE_WIDTH_RANGE", "ALIASED_POINT_SIZE_RANGE", "COMPRESSED_TEXTURE_FORMATS", "SUBPIXEL_BITS", "MIN_PROGRAM_TEXEL_OFFSET", "UNIFORM_BUFFER_OFFSET_ALIGNMENT"):
            static_params[pname] = param
    return {"observed": observed, "staticCapabilities": {
        "parameters": static_params,
        "supportedExtensions": observed["supportedExtensions"],
        "shaderPrecisionFormats": observed["shaderPrecisionFormats"]}}


def import_archive(path, pin=None):
    """Read a verified local archive and preserve actual conditional GL pairs."""
    pin = _json(SOURCE.read_bytes()) if pin is None else pin
    blobs = _bounded_archive(Path(path), pin)
    values = _Values(_json(blobs["values.json"]), blobs["values.dat"])
    network = _json(blobs["fingerprint-network.json"])
    nodes = {}
    for node in network["nodes"]:
        if node["name"] in nodes:
            raise ValueError("duplicate network node")
        nodes[node["name"]] = node
    for name, parents in PARENTS.items():
        if name not in nodes or nodes[name]["parentNames"] != parents:
            raise ValueError("unexpected conditional parent order for " + name)
        possible = nodes[name]["possibleValues"]
        if not isinstance(possible, list) or len(possible) != len(set(possible)) or len(possible) > 50000:
            raise ValueError("invalid node possibilities")
    browser = [token for token in nodes["browser"]["possibleValues"] if values.get(token) == "Firefox"]
    if len(browser) != 1:
        raise ValueError("expected one actual Firefox browser token")
    firefox = browser[0]
    browser_probability = _distribution(nodes, "browser", {})[firefox]
    contexts, records = {}, []

    def walk(name_index, evidence, probabilities):
        if name_index < len(PARENTS):
            name = list(PARENTS)[name_index]
            for token, probability in _distribution(nodes, name, evidence).items():
                walk(name_index + 1, {**evidence, name: token}, {**probabilities, name: probability})
            return
        gpu = values.get(evidence["gpu"])
        if not isinstance(gpu, dict) or set(gpu) != {"vendor", "renderer"} or not all(isinstance(v, str) for v in gpu.values()):
            raise ValueError("invalid recorded GPU label")
        platform = values.get(evidence["platformInfo"])
        if not isinstance(platform, str):
            raise ValueError("invalid recorded platform")
        gl = {}
        for name in ("webgl", "webgl2"):
            observation = values.get(evidence[name])
            context = _context(observation, gpu)
            context_id = "sha256:" + _digest(_canonical(observation))
            contexts[context_id] = context
            gl[name] = context_id
        record_id = "sha256:" + _digest(_canonical({"archive": pin["archive"]["sha256"], "tokens": evidence}))
        records.append({"id": record_id, "browser": "Firefox", "platform": platform,
            "os": _os(platform), "gpu": gpu, "family": _family(gpu), **gl,
            "sourceTokens": evidence, "probabilities": probabilities,
            "jointProbability": math.prod(probabilities.values()),
            "admission": "unvalidated-reference"})

    walk(1, {"browser": firefox}, {"browser": browser_probability})
    return {"schemaVersion": 1, "kind": "recorded-firefox-webgl-pairs",
        "source": {"tag": pin["tag"], "url": pin["url"], "archive": pin["archive"],
                   "files": pin["files"], "license": pin["license"]["spdx"]},
        "semantics": {"observed": "Exact source observations, including mutable initial state; never an active profile.",
            "staticCapabilities": "Unmodified recorded capability subset for native admission, not backend support.",
            "pairing": "Conditional network paths retain browser/platform/GPU/GL1/GL2 ownership; this is model evidence, not an individual device certificate.",
            "probabilities": "Original conditional edge probabilities; joint includes the Firefox browser prior.",
            "admission": "Every reference remains unvalidated until native operation and privacy checks pass."},
        "contexts": contexts, "records": sorted(records, key=lambda r: r["id"])}


def render(catalog):
    return json.dumps(catalog, sort_keys=True, indent=2, allow_nan=False) + "\n"


def scalar_screen(catalog):
    """Necessary scalar requirements only; passing never grants admission.

    The pinned report records uniform vectors (4096) separately from components
    (16384). Preserve those units and all measured scalar bounds. Other native
    requirements remain unevaluated; a limit is never silently clamped.
    """
    backend = _json(BACKEND_SOURCE.read_bytes())
    bounds = backend["bounds"]
    matrix = {"schemaVersion": 1, "sourceArchiveSha256": catalog["source"]["archive"]["sha256"],
        "kind": "necessary-scalar-screen-only", "backendBounds": bounds,
        "backendProvenance": backend["provenance"],
        "unevaluated": ["other capability parameters and ranges", "shader precision",
            "extension operations and formats", "context attributes", "resource allocation and shader execution",
            "API errors and mutable state", "readback privacy and imported-resource guards"],
        "families": {}, "records": {}}
    for record in catalog["records"]:
        blockers = []
        family = matrix["families"].setdefault(record["family"], {})
        for gl, required in bounds.items():
            context = catalog["contexts"][record[gl]]["observed"]
            if not context:
                blockers.append({"context": gl, "reason": "not-recorded"})
                continue
            family_gl = family.setdefault(gl, {})
            for pname, available in required.items():
                param = context["params"].get(pname)
                if param is None or type(param["value"]) not in (int, float):
                    blockers.append({"context": gl, "pname": pname, "reason": "missing-recorded-requirement"})
                    continue
                value = param["value"]
                stats = family_gl.setdefault(pname, {"minimum": value, "maximum": value})
                stats["minimum"] = min(stats["minimum"], value)
                stats["maximum"] = max(stats["maximum"], value)
                if value > available:
                    blockers.append({"context": gl, "pname": pname, "name": param["name"],
                                     "required": value, "available": available})
        matrix["records"][record["id"]] = {"family": record["family"], "admitted": False,
            "status": "unsupported-scalar-requirement" if blockers else "needs-native-validation",
            "blockers": blockers}
    return matrix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="already downloaded pinned model archive")
    parser.add_argument("--check", action="store_true", help="verify checked-in output without modifying it")
    args = parser.parse_args()
    try:
        catalog = import_archive(args.archive)
        for target, result in ((OUTPUT, render(catalog)), (MATRIX_OUTPUT, render(scalar_screen(catalog)))):
            if args.check:
                if target.read_text() != result:
                    raise ValueError("checked-in reference data differs from reproducible import: " + target.name)
            else:
                target.write_text(result)
        print(f"Verified {len(catalog['records'])} paired Firefox reference paths; executable admission is separate.")
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Reference import rejected: {exc}\n")


if __name__ == "__main__":
    main()
