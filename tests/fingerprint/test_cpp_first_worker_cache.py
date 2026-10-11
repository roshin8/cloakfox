"""Exercise the patched cpp-first reader with worker-only storage access."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CppFirstWorkerCache(unittest.TestCase):
    def test_main_thread_warms_worker_cache_and_refreshes_each_container(self):
        patch = (ROOT / 'patches/cpp-first-pref-reader.patch').read_text()
        source = '\n'.join(line[1:] for line in patch.splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
        start = source.index('RoverfoxStorageManager::TryGetCppFirstPref(')
        end = source.index('\n}', start) + 2
        helper = 'bool\n' + source[start:end]
        compiler = shutil.which('clang++') or shutil.which('g++')
        if not compiler:
            self.skipTest('C++ compiler unavailable')
        code = r'''
#include <cassert>
#include <map>
#include <string>
struct String : std::string {
  using std::string::string;
  String(const std::string& s) : std::string(s) {}
  const char* get() const { return c_str(); }
  bool IsEmpty() const { return empty(); }
};
using nsCString = String;
using nsAutoCString = String;
using nsACString = String;
using nsAString = String;
bool onMain = true, parent = false;
bool NS_IsMainThread() { return onMain; }
bool XRE_IsParentProcess() { return parent; }
bool NS_SUCCEEDED(bool result) { return result; }
struct Cache {
  std::map<std::string, String> values;
  struct Entry {
    String* value;
    explicit operator bool() const { return value != nullptr; }
    const String& Data() const { return *value; }
  };
  Entry Lookup(const String& key) {
    auto it = values.find(key);
    return {it == values.end() ? nullptr : &it->second};
  }
  void InsertOrUpdate(const String& key, const String& value) { values[key] = value; }
  void Remove(const String& key) { values.erase(key); }
};
int mutex = 0;
struct MutexAutoLock {
  explicit MutexAutoLock(int&) {}
};
namespace Preferences {
  std::map<std::string, String> values;
  int calls = 0;
  bool GetCString(const char* key, String& out) {
    assert(onMain); ++calls;
    auto it = values.find(key);
    if (it == values.end()) return false;
    out = it->second; return true;
  }
}
struct ContentChild {
  static inline std::map<std::string, String> values;
  static inline int calls = 0;
  static ContentChild* GetSingleton() {
    assert(onMain); static ContentChild child; return &child;
  }
  void SendRoverfoxStorageGet(const String& key, String* out) {
    assert(onMain); ++calls;
    auto it = values.find(key);
    if (it != values.end()) *out = it->second;
  }
};
struct RoverfoxStorageManager {
  static String MakeCppFirstPrefName(const String& key) {
    return String("cloakfox.s." + key);
  }
  static Cache& GetLocalCache() { static Cache cache; return cache; }
  static int& GetLocalCacheMutex() { return mutex; }
  static bool TryGetCppFirstPref(const String&, String&);
};
''' + helper + r'''
int main() {
  String out;
  auto read = [&](const String& key, const String& expected) {
    out.clear();
    assert(RoverfoxStorageManager::TryGetCppFirstPref(key, out));
    assert(out == expected);
  };
  // Real content-process configuration may arrive only through parent IPC.
  ContentChild::values["cloakfox.s.cloak_cfg_0"] = "{seed:0}";
  ContentChild::values["cloakfox.s.cloak_cfg_2"] = "{seed:222}";
  read("cloak_cfg_0", "{seed:0}");
  read("cloak_cfg_2", "{seed:222}");
  int prefCalls = Preferences::calls, ipcCalls = ContentChild::calls;
  onMain = false;
  read("cloak_cfg_0", "{seed:0}");
  read("cloak_cfg_2", "{seed:222}");
  assert(!RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_3", out));
  assert(Preferences::calls == prefCalls && ContentChild::calls == ipcCalls);
  // A later main-thread read refreshes the snapshot from the authoritative pref.
  onMain = true;
  Preferences::values["cloakfox.s.cloak_cfg_2"] = "{seed:999}";
  read("cloak_cfg_2", "{seed:999}");
  onMain = false;
  read("cloak_cfg_2", "{seed:999}");
  // Removal cannot leave stale data after the next main-thread refresh.
  onMain = true;
  Preferences::values.clear(); ContentChild::values.erase("cloakfox.s.cloak_cfg_2");
  assert(!RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_2", out));
  onMain = false;
  assert(!RoverfoxStorageManager::TryGetCppFirstPref("cloak_cfg_2", out));
  read("cloak_cfg_0", "{seed:0}");
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory, 'cache.cpp')
            binary = Path(directory, 'cache')
            cpp.write_text(code)
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
