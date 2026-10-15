"""Execute the production resolver guard against isolated proxy providers.

This validates route classification and cancellation, not a MASQUE tunnel.
The loopback browser probes cover HTTP CONNECT allocation and negotiation.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest


class RequiredProxyRoutes(unittest.TestCase):
    def test_http_connection_and_failover_boundary(self):
        root = Path(__file__).resolve().parents[2]
        patch = (root / "patches/cloakfox-turn-proxy-privacy.patch").read_text()
        additions = "\n".join(line[1:] for line in patch.splitlines()
                              if line.startswith("+") and not line.startswith("+++"))
        start = additions.index("static nsresult CloakfoxRequiredProxyRoute")
        end = additions.index("\n}", start) + len("\n}")
        helper = additions[start:end]
        # The connection gate checks the actual transport, replacement checks
        # its new route, and redirect inheritance makes the constraint sticky.
        self.assertIn("mConnectionInfo ? mConnectionInfo->ProxyInfo() : nullptr", additions)
        self.assertIn("CloakfoxRequiredProxyRoute(mProxyResolveFlags, mProxyInfo)", additions)
        self.assertIn("CloakfoxRequiredProxyRoute(mProxyResolveFlags, pi)", additions)
        self.assertIn("replacement->mProxyResolveFlags |=", additions)
        self.assertIn("!(mProxyResolveFlags & nsIProtocolProxyService::RESOLVE_REQUIRE_PROXY)", additions)
        source = r'''
#include <cassert>
#include <string>
using nsresult = int;
using nsAutoCString = std::string;
constexpr int NS_OK = 0, NS_ERROR_PROXY_CONNECTION_REFUSED = -1;
#define NS_FAILED(status) ((status) < 0)
struct nsIProtocolProxyService { static constexpr unsigned RESOLVE_REQUIRE_PROXY = 64; };
struct nsIProxyInfo {
  const char* type;
  bool fail = false;
  int GetType(nsAutoCString& out) { out = type; return fail ? -2 : 0; }
};
''' + helper + r'''
int main() {
  for (const char* type : {"http", "https", "masque", "socks", "socks4"}) {
    nsIProxyInfo proxy{type};
    assert(CloakfoxRequiredProxyRoute(64, &proxy) == NS_OK);
  }
  // Effectively-direct skips resolution and leaves the connection route null.
  assert(CloakfoxRequiredProxyRoute(64, nullptr) < 0);
  // PROXY failure can hand a populated DIRECT head to the replacement channel.
  nsIProxyInfo direct{"direct"}, unknown{"unknown"}, malformed{"http", true};
  assert(CloakfoxRequiredProxyRoute(64, &direct) < 0);
  assert(CloakfoxRequiredProxyRoute(64, &unknown) < 0);
  assert(CloakfoxRequiredProxyRoute(64, &malformed) < 0);
  // Native unprotected channels retain null/DIRECT behavior.
  assert(CloakfoxRequiredProxyRoute(0, nullptr) == NS_OK);
  assert(CloakfoxRequiredProxyRoute(0, &direct) == NS_OK);
}
'''
        with tempfile.TemporaryDirectory(prefix="cloakfox-turn-connect-") as tmp:
            cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
            cpp.write_text(source)
            subprocess.run(["c++", "-std=c++17", str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_supported_providers_and_direct_fail_closed(self):
        root = Path(__file__).resolve().parents[2]
        patch = (root / "patches/cloakfox-proxy-resolver-errors.patch").read_text()
        additions = "\n".join(line[1:] for line in patch.splitlines()
                              if line.startswith("+") and not line.startswith("+++"))
        start = additions.index("  if (aResolveFlags &")
        end = additions.index("\n  }", start) + len("\n  }")
        guard = additions[start:end]
        source = r'''
#include <cassert>
#include <string>
using nsAutoCString = std::string;
constexpr int NS_ERROR_PROXY_CONNECTION_REFUSED = -1;
#define NS_FAILED(status) ((status) < 0)
struct nsIProtocolProxyService { static constexpr unsigned RESOLVE_REQUIRE_PROXY = 64; };
struct Proxy {
  const char* type;
  bool fail = false;
  int GetType(nsAutoCString& out) { out = type; return fail ? -2 : 0; }
};
struct Channel {
  bool canceled = false;
  void Cancel(int status) { assert(status < 0); canceled = true; }
};
bool resolve(Proxy* aProxyInfo, int aStatus, unsigned aResolveFlags, Channel* aChannel) {
''' + guard + r'''
  return aStatus == 0 && aProxyInfo;
}
int main() {
  for (const char* type : {"http", "https", "masque", "socks", "socks4"}) {
    Proxy route{type}; Channel channel;
    assert(resolve(&route, 0, 64, &channel));
    assert(!channel.canceled);
  }
  for (const char* type : {"direct", "unknown", ""}) {
    Proxy head{type}; Channel channel;
    assert(!resolve(&head, 0, 64, &channel));
    assert(channel.canceled);
  }
  Proxy masque{"masque"}; Channel unavailable, absent, malformed;
  assert(!resolve(&masque, -2, 64, &unavailable) && unavailable.canceled);
  assert(!resolve(nullptr, 0, 64, &absent) && absent.canceled);
  masque.fail = true;
  assert(!resolve(&masque, 0, 64, &malformed) && malformed.canceled);
  Proxy direct{"direct"}; Channel native;
  assert(resolve(&direct, 0, 0, &native) && !native.canceled);
  assert(!resolve(nullptr, -2, 64, nullptr));
}
'''
        with tempfile.TemporaryDirectory(prefix="cloakfox-turn-routes-") as tmp:
            cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
            cpp.write_text(source)
            subprocess.run(["c++", "-std=c++17", str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
