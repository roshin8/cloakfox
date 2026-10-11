"""Compile the canonical NSS helper and exercise the 0-RTT/HRR transition."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeEchOrder(unittest.TestCase):
    def test_early_data_is_not_a_retry_extension_anchor(self):
        patch = (ROOT / 'patches/cloakfox-network-conformance.patch').read_text()
        section = patch.split('+++ b/security/nss/lib/ssl/tls13ech.c\n', 1)[1].split('\n--- a/', 1)[0]
        source = '\n'.join(line[1:] for line in section.splitlines() if line.startswith(('+', ' ')))
        start = source.index('static SECStatus\ntls13_CloakfoxPlaceGreaseEch(')
        end = source.index('\n}', start) + 2
        method = source[start:end]
        harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
using SECStatus=int; using PRUint16=uint16_t; using PRUint8=uint8_t;
constexpr int SECSuccess=0,SECFailure=-1,SSL_MAX_EXTENSIONS=23;
enum { ssl_tls13_pre_shared_key_xtn=41,ssl_tls13_early_data_xtn=42 };
constexpr int ssl_tls13_encrypted_client_hello_xtn=65037;
struct sslBuffer { unsigned char* buf; unsigned int len; };
struct sslSocket {
  struct { bool cloakfoxChromeProfile=true; } opt;
  struct { struct { bool helloRetry=false; uint16_t cloakfoxEchAnchor=0; } hs; } ssl3;
};
SECStatus PK11_GenerateRandom(unsigned char* data,size_t length) {
  memset(data,0,length); return SECSuccess;
}
#define PORT_Alloc(n) static_cast<unsigned char*>(malloc(n))
#define PORT_Free free
#define PORT_Memcpy memcpy
'''
        checks = r'''
int main() {
  sslSocket socket;
  // Early data disappears in ClientHello2. The stable ALPN extension remains.
  unsigned char first[]={0,42,0,0,0,16,0,1,2,254,13,0,1,7};
  sslBuffer firstBuffer{first,sizeof(first)};
  assert(tls13_CloakfoxPlaceGreaseEch(&socket,&firstBuffer)==SECSuccess);
  assert(socket.ssl3.hs.cloakfoxEchAnchor==16);
  assert(first[4]==254 && first[5]==13);
  socket.ssl3.hs.helloRetry=true;
  unsigned char retry[]={0,16,0,1,2,254,13,0,1,7};
  sslBuffer retryBuffer{retry,sizeof(retry)};
  assert(tls13_CloakfoxPlaceGreaseEch(&socket,&retryBuffer)==SECSuccess);
  assert(retry[0]==254 && retry[1]==13 && retry[5]==0 && retry[6]==16);
  socket.opt.cloakfoxChromeProfile=false;
  unsigned char native[]={0,16,0,1,2,254,13,0,1,7};
  sslBuffer nativeBuffer{native,sizeof(native)};
  assert(tls13_CloakfoxPlaceGreaseEch(&socket,&nativeBuffer)==SECSuccess);
  assert(native[0]==0 && native[1]==16);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/'ech.cpp';exe=Path(temp)/'ech'
            src.write_text(harness+'\n'+method+'\n'+checks)
            result=subprocess.run([shutil.which('c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(exe)], capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            result=subprocess.run([str(exe)], capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
