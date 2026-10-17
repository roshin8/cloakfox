#pragma once
#include <string>
#include "include/cef_values.h"

namespace cloakfox {
// Portable v1 snapshot, resolved once before any renderer/worker starts.
// Unknown fields/options are rejected even if the master switch is off.
struct PersonaConfig {
  CefRefPtr<CefDictionaryValue> snapshot;
  std::string container;
  std::string seed;
  int revision = 0;
  bool isPrivate = false;
  bool canvas = true;
  bool blockWebGPUReadback = false;
  CefRefPtr<CefDictionaryValue> presentation;
};
PersonaConfig parsePersonaConfig(CefRefPtr<CefDictionaryValue> value,
                                int canvasVersion, int webgpuVersion, int identityVersion,
                                int displayVersion);
}
