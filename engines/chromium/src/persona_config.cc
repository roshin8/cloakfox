#include "persona_config.h"
#include "container_paths.h"
#include <set>
#include <stdexcept>

namespace cloakfox {
namespace {
void exactFields(CefRefPtr<CefDictionaryValue> value,
                 const std::set<std::string>& expected) {
  if (!value) throw std::runtime_error("Invalid config object");
  CefDictionaryValue::KeyList keys;
  value->GetKeys(keys);
  std::set<std::string> actual;
  for (const auto& key : keys) actual.insert(key.ToString());
  if (actual != expected) throw std::runtime_error("Unsupported config fields");
}
void optionFields(CefRefPtr<CefDictionaryValue> value, bool complete) {
  if (!value) throw std::runtime_error("Invalid config options");
  if (complete) exactFields(value, {"canvas", "blockWebGPUReadback"});
  CefDictionaryValue::KeyList keys;
  value->GetKeys(keys);
  for (const auto& key : keys)
    if ((key != "canvas" && key != "blockWebGPUReadback") || value->GetType(key) != VTYPE_BOOL)
      throw std::runtime_error("Unsupported config option");
}
}
PersonaConfig parsePersonaConfig(CefRefPtr<CefDictionaryValue> value,
                                int canvasVersion, int webgpuVersion) {
  exactFields(value, {"schemaVersion", "engine", "containerId", "private", "revision", "enabled", "persona"});
  if (value->GetType("schemaVersion") != VTYPE_INT || value->GetInt("schemaVersion") != 1 ||
      value->GetType("revision") != VTYPE_INT || value->GetInt("revision") < 1 ||
      value->GetType("engine") != VTYPE_STRING || value->GetString("engine") != "chromium" ||
      value->GetType("containerId") != VTYPE_STRING ||
      !isValidContainerId(value->GetString("containerId").ToString()) ||
      value->GetType("private") != VTYPE_BOOL || value->GetType("enabled") != VTYPE_BOOL ||
      value->GetType("persona") != VTYPE_DICTIONARY)
    throw std::runtime_error("Invalid config schema, engine or ownership");
  auto persona = value->GetDictionary("persona");
  exactFields(persona, {"seed", "options", "overrides"});
  if (persona->GetType("seed") != VTYPE_STRING ||
      persona->GetType("options") != VTYPE_DICTIONARY || persona->GetType("overrides") != VTYPE_DICTIONARY)
    throw std::runtime_error("Invalid persona config");
  const auto seed = persona->GetString("seed").ToString();
  if (seed.size() != 64 || seed.find_first_not_of("0123456789abcdef") != std::string::npos)
    throw std::runtime_error("Invalid persona seed");
  auto options = persona->GetDictionary("options");
  auto overrides = persona->GetDictionary("overrides");
  optionFields(options, true); optionFields(overrides, false);
  // v1 requires both current hooks, even when disabled. Never acknowledge an
  // unsupported option as implemented by an unpatched/older binary SDK.
  if (canvasVersion != 1 || webgpuVersion != 1)
    throw std::runtime_error("Backend does not support persona options");
  const auto effective = [&options, &overrides](const char* key) {
    return overrides->HasKey(key) ? overrides->GetBool(key) : options->GetBool(key);
  };
  const bool enabled = value->GetBool("enabled");
  return {value->Copy(false), value->GetString("containerId").ToString(), seed,
          value->GetInt("revision"), value->GetBool("private"),
          enabled && effective("canvas"), enabled && effective("blockWebGPUReadback")};
}
}
