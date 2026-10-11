"""Capture installed Chrome's TLS/H2 and QUIC/H3 on disposable loopback fixtures.

This is a reference measurement, not a Cloakfox matching/pass claim. Chrome
trusts only the temporary fixture leaf's SPKI for this run; neither the system
keychain nor any existing browser profile is changed. ClientHello observations
exclude randoms, SNI, key material, tickets and GREASE values.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network"))
from h3_fixture import H3Fixtures, create_certificates
from wire_fixture import TLSFixture


def capture(binary, root, certificate, kind):
    """Require a real successful application exchange, not just a ClientHello."""
    spki = x509.load_pem_x509_certificate(certificate.read_bytes()).public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    pin = base64.b64encode(hashlib.sha256(spki).digest()).decode()
    key = certificate.with_name("leaf-key.pem")
    detailed = os.environ.get('CHROME_WIRE_DETAILS') == '1'
    fixture = TLSFixture(certificate, key, detailed=detailed,curve=os.environ.get('CHROME_WIRE_CURVE')) if kind == "h2" else H3Fixtures(certificate, key, count=1, detailed=detailed, alps=b"\x04\x04\x01\x00\x07\x00" if os.environ.get("CHROME_QUIC_ALPS")=="1" else None)
    try:
        port = fixture.server_address[1] if kind == "h2" else fixture.ports[0]
        args = [binary, "--headless=new", f"--user-data-dir={root}", "--no-first-run",
                "--disable-background-networking", "--disable-component-update",
                f"--ignore-certificate-errors-spki-list={pin}",
                "--host-resolver-rules=MAP chrome-wire.test 127.0.0.1",
                "--no-proxy-server", "--dump-dom"]
        if kind == "h3":
            args += ["--enable-quic", f"--origin-to-force-quic-on=chrome-wire.test:{port}"]
        # subprocess.run terminates and reaps Chrome on timeout. Capture noisy
        # display diagnostics, but do not persist unrelated background output.
        result = subprocess.run(args + [f"https://chrome-wire.test:{port}/"],
                                capture_output=True, timeout=25, check=True)
        expected = b"local-wire-ok" if kind == "h2" else b"local-http3-ok"
        assert expected in result.stdout, (kind, "Chrome did not load the fixture")
        if kind == "h2":
            records = [r for r in fixture.observed if r.get("pseudoHeaders")]
            assert records, "No actual H2 request observed"
            record = records[0]
            assert record["tlsVersion"] == "TLSv1.3" and record["protocol"] == "h2", record
            result={k: record[k] for k in ("hello", "settings", "windowUpdates", "pseudoHeaders")}
            if 'clientHellos' in record:result['clientHellos']=record['clientHellos']
            return result
        record = fixture.observed[0]
        if os.environ.get("CHROME_QUIC_ALPS")=="1":
            assert record.get("alpsClientEE"),record
        assert record["handshakes"] and record["alpn"] == ["h3"], record
        assert record["requests"] and record.get("settings") is not None, record
        result={"hello": record["clientHellos"][0],
                "transportParameters": record["transportParameters"][0], "settings": record["settings"]}
        if detailed:
            result.update(parameterDetails=record['parameterDetails'][0], initialPackets=record.get('initialPackets',[]))
        return result
    finally:
        fixture.close()


def comparable(record):
    # Modern Chrome permutes TLS extensions and QUIC parameters. Preserve raw
    # order in the artifact, and compare sets for these two randomized fields.
    out = {**record, "hello": {**record["hello"], "extensions": sorted(record["hello"]["extensions"])}}
    if 'shape' in out['hello']:
        # GREASE payload size and ECH padding vary; retain in the artifact,
        # rather than requiring repeated fresh random choices to be equal.
        del out['hello']['shape']
    out.pop('parameterDetails',None)
    out.pop('initialPackets',None)
    if "transportParameters" in out:
        out["transportParameters"] = sorted(out["transportParameters"], key=lambda pair: pair[0])
    if "pseudoHeaders" in out:
        # A favicon can reuse the session. Its count is not a handshake field.
        out["pseudoHeaders"] = sorted({tuple(headers) for headers in out["pseudoHeaders"]})
    return out


def main():
    binary = os.environ.get("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    version = subprocess.run([binary, "--version"], check=True, capture_output=True,
                             text=True, timeout=10).stdout.strip()
    report = {"version": version, "referenceOnly": True,
              "trust": "temporary loopback fixture leaf SPKI only",
              "limits": ["GREASE values normalized; only public presentation fields retained" if os.environ.get('CHROME_WIRE_DETAILS')=='1' else "GREASE stripped; extension payloads not compared",
                         "fresh sessions only; no resumption, 0-RTT or packet-scheduling comparison"]}
    with tempfile.TemporaryDirectory(prefix="cloakfox-chrome-reference-") as temp:
        root = Path(temp)
        _, certificate, _ = create_certificates(root, ["chrome-wire.test"])
        for kind in ("h2", "h3"):
            records = [capture(binary, root / f"{kind}-{repeat}", certificate, kind) for repeat in range(3)]
            assert all(comparable(r) == comparable(records[0]) for r in records), (kind, "Unstable reference structure", records)
            report[kind] = records
    target = Path(os.environ.get("CHROME_WIRE_REPORT", "/tmp/cloakfox-chrome-reference.json"))
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {version}; three fresh TLS/H2 and three fresh QUIC/H3 exchanges")
    print(f"Reference only, not proof of Cloakfox parity: {target}")


if __name__ == "__main__":
    main()
